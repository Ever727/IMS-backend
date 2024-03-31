from django.db import models
from utils.utils_time import get_timestamp
from account.models import User
# Create your models here.
class Message(models.Model):
    id = models.AutoField(primary_key=True)
    type = models.BooleanField(default=False)
    sender = models.CharField(max_length=20)
    receiver = models.CharField(max_length=20)
    session = models.IntegerField(null = True, blank = True)
    sendTime = models.FloatField(default=get_timestamp)
    content = models.CharField(max_length=200,default='',blank=True,null=True)
    replyId = models.ManyToManyField('self', related_name='reply_message', symmetrical=False, blank=True)
    readId = models.ManyToManyField(User, related_name='read_message', symmetrical=False, blank=True)
    deleteId = models.ManyToManyField(User, related_name='delete_message', symmetrical=False, blank=True)


    class Meta:
        db_table = 'message'