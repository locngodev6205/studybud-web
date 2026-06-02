from django.contrib import admin

# Register your models here.

from .models import Room, Topic, Message, User, UserFollow, RoomInvitation, RoomVote, MessageVote

admin.site.register(User)
admin.site.register(Room)
admin.site.register(Topic)
admin.site.register(Message)
admin.site.register(UserFollow)
admin.site.register(RoomInvitation)
admin.site.register(RoomVote)
admin.site.register(MessageVote)
