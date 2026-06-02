from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Room, Topic, Message, UserFollow, RoomInvitation, RoomVote, MessageVote

User = get_user_model()


class StudyBudTestCase(TestCase):
    def setUp(self):
        # Khởi tạo dữ liệu kiểm thử
        self.user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="password123"
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="password123"
        )
        self.topic = Topic.objects.create(name="Python")

    def test_user_follow(self):
        # Kiểm thử chức năng follow
        follow = UserFollow.objects.create(follower=self.user1, followed=self.user2)
        self.assertEqual(self.user1.following_count, 1)
        self.assertEqual(self.user2.followers_count, 1)

        # Kiểm thử chức năng unfollow
        follow.delete()
        self.assertEqual(self.user1.following_count, 0)
        self.assertEqual(self.user2.followers_count, 0)

    def test_private_room_access(self):
        # Tạo phòng riêng tư do user1 làm host
        room = Room.objects.create(
            host=self.user1,
            topic=self.topic,
            name="Private Python Room",
            is_private=True
        )
        room.participants.add(self.user1)

        # Kiểm tra xem user2 có được mời chưa (mặc định chưa)
        is_invited = RoomInvitation.objects.filter(room=room, recipient=self.user2).exists()
        self.assertFalse(is_invited)

        # Gửi lời mời tới user2
        invite = RoomInvitation.objects.create(
            room=room,
            sender=self.user1,
            recipient=self.user2,
            status='pending'
        )
        
        # Kiểm tra xem lời mời đã tồn tại chưa
        is_invited_now = RoomInvitation.objects.filter(room=room, recipient=self.user2).exists()
        self.assertTrue(is_invited_now)

    def test_room_vote(self):
        room = Room.objects.create(
            host=self.user1,
            topic=self.topic,
            name="Vote Room",
        )
        
        # User 1 Upvote
        RoomVote.objects.create(user=self.user1, room=room, value=1)
        self.assertEqual(room.vote_score, 1)
        
        # User 2 Downvote -> Điểm vote trở về 0
        RoomVote.objects.create(user=self.user2, room=room, value=-1)
        self.assertEqual(room.vote_score, 0)
