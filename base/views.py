from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout
from .models import Room, Topic, Message, User, UserFollow, RoomInvitation, RoomVote, MessageVote
from .forms import RoomForm, UserForm, MyUserCreationForm
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def loginPage(request):
    page = 'login'
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email').lower()
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'User does not exist')
            user = None

        if user is not None:
            user = authenticate(request, email=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'Username OR password does not exist')
        else:
            messages.error(request, 'Username OR password does not exist')

    context = {'page': page}
    return render(request, 'base/login_register.html', context)


def logoutUser(request):
    logout(request)
    return redirect('home')


def registerPage(request):
    form = MyUserCreationForm()

    if request.method == 'POST':
        form = MyUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.save()
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'An error occurred during registration')

    return render(request, 'base/login_register.html', {'form': form})


def home(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''

    # Filter rooms by visibility (public or user has access to private)
    if request.user.is_authenticated:
        authorized_rooms = Room.objects.filter(
            Q(is_private=False) |
            Q(host=request.user) |
            Q(participants=request.user) |
            Q(roominvitation__recipient=request.user)
        ).distinct()
    else:
        authorized_rooms = Room.objects.filter(is_private=False)

    rooms = authorized_rooms.filter(
        Q(topic__name__icontains=q) |
        Q(name__icontains=q) |
        Q(description__icontains=q)
    )

    topics = Topic.objects.all()[0:5]
    room_count = rooms.count()

    # Filter activity messages to only those from authorized rooms
    room_messages = Message.objects.filter(
        room__in=authorized_rooms,
        room__topic__name__icontains=q
    ).order_by('-created')[0:5]

    # Map vote details for rooms
    user_votes = {}
    if request.user.is_authenticated:
        user_votes = {v.room_id: v.value for v in RoomVote.objects.filter(user=request.user)}

    context = {
        'rooms': rooms,
        'topics': topics,
        'room_count': room_count,
        'room_messages': room_messages,
        'user_votes': user_votes
    }
    return render(request, 'base/home.html', context)


def room(request, pk):
    room = Room.objects.get(id=pk)

    # Permission check for private rooms
    if room.is_private:
        if not request.user.is_authenticated:
            return redirect('login')

        is_host = room.host == request.user
        is_participant = room.participants.filter(id=request.user.id).exists()
        invitation = RoomInvitation.objects.filter(room=room, recipient=request.user).first()

        if not (is_host or is_participant or invitation):
            return HttpResponse('Bạn không có quyền truy cập phòng riêng tư này!')

        # Auto accept pending invitation on visit
        if invitation and invitation.status == 'pending':
            invitation.status = 'accepted'
            invitation.save()
            room.participants.add(request.user)

    room_messages = room.message_set.filter(parent=None).order_by('created')
    participants = room.participants.all()

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')

        parent_id = request.POST.get('parent_id')
        parent_msg = None
        if parent_id:
            parent_msg = Message.objects.get(id=parent_id)

        message = Message.objects.create(
            user=request.user,
            room=room,
            body=request.POST.get('body'),
            parent=parent_msg,
            image=request.FILES.get('image'),
            video=request.FILES.get('video')
        )
        room.participants.add(request.user)

        # Notify via WebSocket channel layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{room.id}",
            {
                "type": "chat_message",
                "message_id": message.id,
                "user": request.user.username,
                "avatar": request.user.avatar.url,
                "body": message.body or '',
                "image_url": message.image.url if message.image else None,
                "video_url": message.video.url if message.video else None,
                "parent_id": parent_id or None,
                "created": message.created.strftime('%B %d, %Y, %I:%M %p')
            }
        )

        return redirect('room', pk=room.id)

    # Followings to invite (if host and private room)
    followings = []
    pending_invite_ids = []
    if request.user.is_authenticated and room.host == request.user and room.is_private:
        followings = User.objects.filter(followers__follower=request.user).exclude(id__in=room.participants.all())
        pending_invite_ids = list(RoomInvitation.objects.filter(room=room, status='pending').values_list('recipient_id', flat=True))

    user_votes = {}
    if request.user.is_authenticated:
        user_votes = {v.message_id: v.value for v in MessageVote.objects.filter(user=request.user, message__room=room)}

    context = {
        'room': room,
        'room_messages': room_messages,
        'participants': participants,
        'followings': followings,
        'pending_invite_ids': pending_invite_ids,
        'user_votes': user_votes
    }
    return render(request, 'base/room.html', context)


def userProfile(request, pk):
    user = User.objects.get(id=pk)

    # Filter rooms by visibility (public or viewer has access)
    if request.user.is_authenticated:
        rooms = user.room_set.filter(
            Q(is_private=False) |
            Q(host=request.user) |
            Q(participants=request.user) |
            Q(roominvitation__recipient=request.user)
        ).distinct()
    else:
        rooms = user.room_set.filter(is_private=False)

    # Filter messages from visible rooms
    if request.user.is_authenticated:
        room_messages = user.message_set.filter(
            Q(room__is_private=False) |
            Q(room__host=request.user) |
            Q(room__participants=request.user) |
            Q(room__roominvitation__recipient=request.user)
        ).distinct()
    else:
        room_messages = user.message_set.filter(room__is_private=False)

    topics = Topic.objects.all()

    # Follow check
    is_following = False
    if request.user.is_authenticated and request.user != user:
        is_following = UserFollow.objects.filter(follower=request.user, followed=user).exists()

    context = {
        'user': user,
        'rooms': rooms,
        'room_messages': room_messages,
        'topics': topics,
        'is_following': is_following
    }
    return render(request, 'base/profile.html', context)


@login_required(login_url='login')
def createRoom(request):
    form = RoomForm()
    topics = Topic.objects.all()
    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        topic, created = Topic.objects.get_or_create(name=topic_name)

        is_private = request.POST.get('is_private') == 'on'

        Room.objects.create(
            host=request.user,
            topic=topic,
            name=request.POST.get('name'),
            description=request.POST.get('description'),
            is_private=is_private
        )
        return redirect('home')

    context = {'form': form, 'topics': topics}
    return render(request, 'base/room_form.html', context)


@login_required(login_url='login')
def updateRoom(request, pk):
    room = Room.objects.get(id=pk)
    form = RoomForm(instance=room)
    topics = Topic.objects.all()
    if request.user != room.host:
        return HttpResponse('Your are not allowed here!!')

    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        topic, created = Topic.objects.get_or_create(name=topic_name)
        room.name = request.POST.get('name')
        room.topic = topic
        room.description = request.POST.get('description')
        room.is_private = request.POST.get('is_private') == 'on'
        room.save()
        return redirect('home')

    context = {'form': form, 'topics': topics, 'room': room}
    return render(request, 'base/room_form.html', context)


@login_required(login_url='login')
def deleteRoom(request, pk):
    room = Room.objects.get(id=pk)

    if request.user != room.host:
        return HttpResponse('Your are not allowed here!!')

    if request.method == 'POST':
        room.delete()
        return redirect('home')
    return render(request, 'base/delete.html', {'obj': room})


@login_required(login_url='login')
def deleteMessage(request, pk):
    message = Message.objects.get(id=pk)

    if request.user != message.user:
        return HttpResponse('Your are not allowed here!!')

    if request.method == 'POST':
        message.delete()
        return redirect('home')
    return render(request, 'base/delete.html', {'obj': message})


@login_required(login_url='login')
def updateUser(request):
    user = request.user
    form = UserForm(instance=user)

    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect('user-profile', pk=user.id)

    return render(request, 'base/update-user.html', {'form': form})


def topicsPage(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    topics = Topic.objects.filter(name__icontains=q)
    return render(request, 'base/topics.html', {'topics': topics})


def activityPage(request):
    # Filter messages from visible rooms
    if request.user.is_authenticated:
        room_messages = Message.objects.filter(
            Q(room__is_private=False) |
            Q(room__host=request.user) |
            Q(room__participants=request.user) |
            Q(room__roominvitation__recipient=request.user)
        ).distinct().order_by('-created')
    else:
        room_messages = Message.objects.filter(room__is_private=False).order_by('-created')
    return render(request, 'base/activity.html', {'room_messages': room_messages})


@login_required(login_url='login')
def followUser(request, pk):
    user_to_follow = User.objects.get(id=pk)
    if user_to_follow != request.user:
        follow, created = UserFollow.objects.get_or_create(
            follower=request.user,
            followed=user_to_follow
        )
        if not created:
            follow.delete()
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required(login_url='login')
def voteRoom(request, pk, vote_type):
    room = Room.objects.get(id=pk)
    value = 1 if vote_type == 'up' else -1

    vote, created = RoomVote.objects.get_or_create(
        user=request.user,
        room=room,
        defaults={'value': value}
    )
    if not created:
        if vote.value == value:
            vote.delete()
        else:
            vote.value = value
            vote.save()

    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required(login_url='login')
def voteMessage(request, pk, vote_type):
    message = Message.objects.get(id=pk)
    value = 1 if vote_type == 'up' else -1

    vote, created = MessageVote.objects.get_or_create(
        user=request.user,
        message=message,
        defaults={'value': value}
    )
    if not created:
        if vote.value == value:
            vote.delete()
        else:
            vote.value = value
            vote.save()

    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required(login_url='login')
def sendInvitation(request, room_pk, user_pk):
    room = Room.objects.get(id=room_pk)
    recipient = User.objects.get(id=user_pk)

    if room.host != request.user:
        return HttpResponse('You are not allowed to invite users to this room.')

    if room.participants.filter(id=recipient.id).exists():
        messages.error(request, f"{recipient.username} đã tham gia phòng.")
        return redirect(request.META.get('HTTP_REFERER', 'home'))

    invite, created = RoomInvitation.objects.get_or_create(
        room=room,
        sender=request.user,
        recipient=recipient,
        defaults={'status': 'pending'}
    )

    if created:
        messages.success(request, f"Đã gửi lời mời tới {recipient.username}.")
        # Send Real-time notification via Channels
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"notifications_{recipient.id}",
            {
                "type": "send_notification",
                "message": f"{request.user.username} đã mời bạn tham gia phòng '{room.name}'.",
                "room_id": room.id,
                "invite_id": invite.id
            }
        )
    else:
        messages.info(request, f"Đã có lời mời đang chờ phản hồi từ {recipient.username}.")

    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required(login_url='login')
def respondInvitation(request, pk, action):
    invitation = RoomInvitation.objects.get(id=pk, recipient=request.user)

    if action == 'accept':
        invitation.status = 'accepted'
        invitation.save()
        invitation.room.participants.add(request.user)
        messages.success(request, f"Bạn đã tham gia phòng {invitation.room.name}.")
        return redirect('room', pk=invitation.room.id)
    elif action == 'decline':
        invitation.status = 'declined'
        invitation.save()
        messages.info(request, f"Đã từ chối lời mời tham gia {invitation.room.name}.")

    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required(login_url='login')
def invitationsPage(request):
    invitations = RoomInvitation.objects.filter(recipient=request.user, status='pending')
    context = {'invitations': invitations}
    return render(request, 'base/invitations.html', context)

