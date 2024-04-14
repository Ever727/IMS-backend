from django.db import models
from utils.utils_time import get_timestamp
from account.models import User
# Create your models here.

class Conversation(models.Model):
    TYPE_CHOICES = [
        ('private_chat', 'Private Chat'),
        ('group_chat', 'Group Chat'),
    ]
    type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    members = models.ManyToManyField(User, related_name='conversations')
    status = models.BooleanField(default=True)

    def serilize(self, avatarUrl):
        return {
            "id": self.id,
            "type": self.type,
            "members": [user.serialize() for user in self.members.all()],
            "status": self.status,
            "avatarUrl": avatarUrl

        }

class Message(models.Model):
    id = models.AutoField(primary_key=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    receivers = models.ManyToManyField(User, related_name='received_messages')
    sendTime = models.DateTimeField(auto_now_add=True, db_index=True)
    content = models.CharField(max_length=200,default='',blank=True,null=True)
    replyTo = models.ForeignKey('self', on_delete=models.CASCADE,related_name='reply_message', blank=True, default=None, null=True)
    readUsers = models.ManyToManyField(User, related_name='read_message',  blank=True)
    deleteUsers = models.ManyToManyField(User, related_name='delete_message', symmetrical=False, blank=True)

    def serilize(self):
         replyCount = Message.objects.filter(replyTo=self).count()
         return {
            "id": self.id,
            "conversation": self.conversation.id,
            "sender": self.sender.userName,
            "senderId":self.sender.userId,
            "content": self.content,
            "timestamp":  int(self.sendTime.timestamp() * 1_000),
            "avatar": self.sender.avatarUrl,
            "replyId": self.replyTo.id if self.replyTo else None,
            "replyCount": replyCount,
            "readList": [user.userName for user in self.readUsers.all()],
            "deleteList": [user.userId for user in self.deleteUsers.all()],
    }

    class Meta:
        db_table = 'message'