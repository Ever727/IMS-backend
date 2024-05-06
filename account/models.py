from django.db import models
from utils.constants import user_default_avatarUrl



# Create your models here.
class User(models.Model):
    # userId: str，唯一主键
    # userName: str，长度不超过16，不唯一
    # password: str，   长度不超过16，加密
    # email: str，长度不超过50
    # phoneNumber: str，长度不超过11
    # avatarUrl：str，长度不超过100
    # status: bool，是否激活
    # isDeleted: bool 是否注销
    id = models.BigAutoField(primary_key=True)
    userId = models.CharField(max_length=16, unique=True, db_index=True)
    userName = models.CharField(max_length=16)
    password = models.CharField(max_length=100)
    email = models.EmailField(max_length=50, null=True)
    phoneNumber = models.CharField(max_length=11, null=True)
    avatarUrl = models.TextField(default=user_default_avatarUrl)
    status = models.BooleanField(default=False)
    isDeleted = models.BooleanField(default=False)

    def serialize(self):
        return {
            'userId': self.userId,
            'userName': self.userName,
            'avatarUrl': self.avatarUrl,
            'isDeleted': self.isDeleted,
        }
    class Meta:
        db_table = 'user'
        
    

