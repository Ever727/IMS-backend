from django.db import models
from utils.utils_time import get_timestamp

# Create your models here.
class Friendship(models.Model):
    id = models.AutoField(primary_key=True)
    userId = models.CharField(max_length=16)
    friendId = models.CharField(max_length=16)
    tag = models.CharField(max_length=30)
    checkTime = models.FloatField(default=get_timestamp)
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'friendship'

class FriendshipRequest(models.Model):
    id = models.AutoField(primary_key=True)
    senderId = models.CharField(max_length=16)
    receiverId = models.CharField(max_length=16)
    sendTime = models.FloatField(default=get_timestamp)
    message = models.CharField(max_length=200)
    status = models.BooleanField(default=False)

    class Meta:
        db_table = 'friendship_request'
