import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']

        # Check room access
        is_allowed = await self.check_room_access()
        if not is_allowed:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        body = data.get('body')
        parent_id = data.get('parent_id')

        if body:
            # Save message to database
            message = await self.save_message(body, parent_id)
            # Broadcast to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_id': message['id'],
                    'user': message['user'],
                    'avatar': message['avatar'],
                    'body': message['body'],
                    'image_url': None,
                    'video_url': None,
                    'parent_id': parent_id,
                    'created': message['created']
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def check_room_access(self):
        from base.models import Room, RoomInvitation
        try:
            room = Room.objects.get(id=self.room_id)
        except Room.DoesNotExist:
            return False

        if not room.is_private:
            return True

        user = self.user
        if not user.is_authenticated:
            return False

        is_host = room.host == user
        is_participant = room.participants.filter(id=user.id).exists()
        is_invited = RoomInvitation.objects.filter(room=room, recipient=user).exists()
        return is_host or is_participant or is_invited

    @database_sync_to_async
    def save_message(self, body, parent_id):
        from base.models import Room, Message
        room = Room.objects.get(id=self.room_id)
        parent_msg = None
        if parent_id:
            try:
                parent_msg = Message.objects.get(id=parent_id)
            except Message.DoesNotExist:
                pass

        message = Message.objects.create(
            user=self.user,
            room=room,
            body=body,
            parent=parent_msg
        )
        room.participants.add(self.user)
        return {
            'id': message.id,
            'user': message.user.username,
            'avatar': message.user.avatar.url,
            'body': message.body,
            'created': message.created.strftime('%B %d, %Y, %I:%M %p')
        }


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_authenticated:
            self.group_name = f"notifications_{self.user.id}"
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def send_notification(self, event):
        await self.send(text_data=json.dumps(event))
