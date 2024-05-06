from django.db import models
from utils.utils_time import get_timestamp
from account.models import User
from utils.utils_time import timestamp_to_datetime

# Create your models here.
class Friendship(models.Model):
    id = models.AutoField(primary_key=True)
    userId = models.CharField(max_length=16, db_index=True)
    friendId = models.CharField(max_length=16, db_index=True)
    tag = models.CharField(max_length=30,default='')
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'friendship'

    def serialize(self):
        friendInfo = User.objects.filter(userId=self.friendId).values("userId", "userName", "avatarUrl", "isDeleted").first()
        friendInfo['tag'] = self.tag
        return friendInfo

class FriendshipRequest(models.Model):
    id = models.AutoField(primary_key=True)
    senderId = models.CharField(max_length=16, db_index=True)
    receiverId = models.CharField(max_length=16, db_index=True)
    sendTime = models.FloatField(default=get_timestamp)
    message = models.CharField(max_length=200)
    status = models.IntegerField(default=0)

    class Meta:
        db_table = 'friendship_request'

    def serialize(self):
        senderInfo = User.objects.filter(userId=self.senderId).values("userName", "avatarUrl").first()
        return {
            "id": self.senderId,
            "name": senderInfo["userName"],
            "avatarUrl": senderInfo["avatarUrl"],
            "message": self.message,
            "sendTime": timestamp_to_datetime(self.sendTime),
            "status": self.status,
        }
