from django.db import models
from account.models import User
from datetime import datetime

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
    type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    members = models.ManyToManyField(User, related_name="conversations")

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
    status = models.BooleanField(default=True)
    avatarUrl = models.CharField(max_length=200, default="", blank=True, null=True)
    groupName = models.CharField(max_length=20, default="", blank=True, null=True)
    groupNotificationList = models.ManyToManyField(
        Notification, related_name="notificationList", blank=True
    )

    def serialize(self, avatarUrl):
        return {
            "id": self.id,
            "type": self.type,
            "members": [user.serialize() for user in self.members.all()],
            "status": self.status,
            "avatarUrl": avatarUrl,
            "groupName": self.groupName,
            "host": self.host.serialize() if self.host else None,
            "adminList": [user.serialize() for user in self.admins.all()],
            "groupNotificationList": [
                notification.serialize()
                for notification in self.groupNotificationList.all()
            ],
        }


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
        User, related_name="sent_messages", on_delete=models.CASCADE
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
    readUsers = models.ManyToManyField(User, related_name="read_message", blank=True)
    deleteUsers = models.ManyToManyField(
        User, related_name="delete_message", symmetrical=False, blank=True
    )
    replyCount = models.IntegerField(default=0)

    def serialize(self):
        return {
            "id": self.id,
            "conversation": self.conversation.id,
            "sender": self.sender.userName,
            "senderId": self.sender.userId,
            "content": self.content,
            "timestamp": int(self.updateTime.timestamp() * 1_000),
            "sendTime": int(self.sendTime.timestamp() * 1_000),
            "avatar": self.sender.avatarUrl,
            "replyId": self.replyTo.id if self.replyTo else None,
            "replyCount": self.replyCount,
            "readList": [user.userName for user in self.readUsers.all()],
            "deleteList": [user.userId for user in self.deleteUsers.all()],
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
        return {
            "id": self.id,
            "senderId": self.sender.userId,
            "senderName": self.sender.userName,
            "senderAvatar": self.sender.avatarUrl,
            "receiverId": self.receiver.userId,
            "receiverName": self.receiver.userName,
            "receiverAvatar": self.receiver.avatarUrl,
            "conversationId": self.conversation.id,
            "conversationName": self.conversation.groupName,
            "conversationAvatar": self.conversation.avatarUrl,
            "timestamp": int(self.timestamp.timestamp() * 1_000),
        }