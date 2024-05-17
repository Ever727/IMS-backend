from django.db import models
from account.models import User
from datetime import datetime
from django.utils import timezone

# Create your models here.


class Notification(models.Model):
    id = models.AutoField(primary_key=True)
    userId = models.CharField(max_length=16, db_index=True)
    userName = models.CharField(max_length=16, db_index=True)
    avatarUrl = models.TextField()
    content = models.TextField()
    timestamp = models.DateTimeField()

    conversation = models.ForeignKey(
        "Conversation",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        db_index=True,
    )

    def serialize(self):
        return {
            "userId": self.userId,
            "userName": self.userName,
            "avatarUrl": self.avatarUrl,
            "content": self.content,
            "timestamp": int(self.timestamp.timestamp() * 1_000),
        }


class Conversation(models.Model):
    TYPE_CHOICES = [
        ("private_chat", "Private Chat"),
        ("group_chat", "Group Chat"),
    ]
    type = models.CharField(max_length=12, choices=TYPE_CHOICES, db_index=True)
    members = models.ManyToManyField(User, related_name="conversations")
    status = models.BooleanField(default=True, db_index=True)
    avatarUrl = models.CharField(max_length=200, default="", blank=True, null=True)
    updateTime = models.DateTimeField(default=timezone.now)


    # 以下为群聊所需的字段
    host = models.ForeignKey(
        User,
        related_name="host_conversations",
        on_delete=models.CASCADE,
        default=None,
        null=True,
    )
    admins = models.ManyToManyField(
        User, related_name="admin_conversations", default=None
    )
    groupName = models.CharField(max_length=20, default="", blank=True, null=True)
    groupNotificationList = models.ManyToManyField(
        Notification, related_name="notificationList", blank=True
    )

    def serialize(self, excludeUserId=None, otherUserId = None):
        members = self.members.all().exclude(userId=excludeUserId)
        # 不包含userID对应的用户
        data = {
            "id": self.id,
            "type": self.type,
            "members": [user.serialize() for user in members.all()],
            "status": self.status,
            "updateTime": int(self.updateTime.timestamp() * 1_000),
        }
        if self.type == "private_chat":
            data['otherUserId'] = otherUserId       
        elif self.type == "group_chat":
            data['groupName'] = self.groupName
            data['avatarUrl'] =self.avatarUrl
            data['hostId'] = self.host.userId if self.host else None
            data['adminIdList'] = list(self.admins.values_list('userId', flat=True))
            data['groupNotificationList'] = [
                notification.serialize()
                for notification in self.groupNotificationList.all()
            ]
        return data


class Message(models.Model):
    id = models.AutoField(primary_key=True)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,
        db_index=True,
    )
    sender = models.ForeignKey(
        User, related_name="sent_messages", on_delete=models.CASCADE, db_index=True
    )
    receivers = models.ManyToManyField(User, related_name="received_messages")
    sendTime = models.DateTimeField()
    updateTime = models.DateTimeField(db_index=True)
    content = models.CharField(max_length=200, default="", blank=True, null=True)
    replyTo = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="reply_message",
        blank=True,
        default=None,
        null=True,
    )
    readUsers = models.ManyToManyField(User, related_name="read_message", blank=True, db_index=True)
    deleteUsers = models.ManyToManyField(
        User, related_name="delete_message", symmetrical=False, blank=True
    )
    replyCount = models.IntegerField(default=0)

    def serialize(self):
    
        readUsers = list(self.readUsers.values_list('userName', flat=True))
        deleteUsers = list(self.deleteUsers.values_list('userId', flat=True))

        return {
            "id": self.id,
            "conversation": self.conversation_id,
            "sender": self.sender.userName,
            "senderId": self.sender.userId,
            "content": self.content,
            "timestamp": int(self.updateTime.timestamp() * 1_000),
            "sendTime": int(self.sendTime.timestamp() * 1_000),
            "replyId": self.replyTo_id if self.replyTo_id else None,
            "replyCount": self.replyCount,
            "readList": readUsers,
            "deleteList": deleteUsers,
        }

    class Meta:
        db_table = "message"


class Invitation(models.Model):
    id = models.AutoField(primary_key=True)
    sender = models.ForeignKey(
        User, related_name="sent_invitations", on_delete=models.CASCADE
    )
    receiver = models.ForeignKey(
        User, related_name="received_invitations", on_delete=models.CASCADE
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="invitations",
        null=True,
        db_index=True,
    )
    timestamp = models.DateTimeField(default=datetime.now)

    def serialize(self):
        sender_info = self.sender.serialize()
        receiver_info = self.receiver.serialize()
        return {
            "id": self.id,
            "senderId": sender_info['userId'],
            "senderName": sender_info['userName'],
            "senderAvatar": sender_info['avatarUrl'],
            "receiverId":receiver_info['userId'],
            "receiverName": receiver_info['userName'],
            "receiverAvatar": receiver_info['avatarUrl'],
            "conversationId": self.conversation_id,
            "conversationName": self.conversation.groupName,
            "conversationAvatar": self.conversation.avatarUrl,
            "timestamp": int(self.timestamp.timestamp() * 1_000),
        }