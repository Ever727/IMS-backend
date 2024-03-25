from django.db import models
from utils.utils_time import get_timestamp


# Create your models here.
class User(models.Model):
    # userId: str，唯一主键
    # userName: str，长度不超过16，不唯一
    # password: str，   长度不超过16，加密
    # registerTime: 时间戳
    # loginTime: 时间戳
    # email: str，长度不超过50
    # phoneNumber: str，长度不超过11
    # avatarUrl：str，长度不超过100
    # status: bool，是否激活
    # isDeleted: bool 是否注销
    id = models.BigAutoField(primary_key=True)
    userId = models.CharField(max_length=16, unique=True)
    userName = models.CharField(max_length=16)
    password = models.CharField(max_length=100)
    registerTime = models.FloatField(default=get_timestamp)
    loginTime = models.FloatField(default=get_timestamp)
    email = models.EmailField(max_length=50, null=True)
    phoneNumber = models.CharField(max_length=11, null=True)
    avatarUrl = models.CharField(max_length=100, null=True)
    status = models.BooleanField(default=False)
    isDeleted = models.BooleanField(default=False)

    class Meta:
        db_table = "user"

    def serialize(self):
        return {
            "userId": self.userId,
            "userName": self.userName,
            "email": self.email,
            "phoneNumber": self.phoneNumber,
            "avatarUrl": self.avatarUrl,
            "registerTime": self.registerTime,
            "loginTime": self.loginTime,
            "status": self.status,
            "isDeleted": self.isDeleted,
        }

    def __str__(self):
        return self.userName
