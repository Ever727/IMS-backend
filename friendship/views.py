from django.http import HttpRequest, HttpResponse
from utils.utils_request import request_failed, request_success,BAD_METHOD
from utils.utils_require import require
from utils.utils_jwt import check_jwt_token
from utils.utils_time import timestamp_to_datetime, get_timestamp
from .models import Friendship, FriendshipRequest  
from account.models import User
import json

# Create your views here.
def add_friend(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
    
    return request_success({"message": "成功发送请求"})


def delete_friend(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
    
    return request_success({"message": "删除成功"})


def accept_friend(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
   
    return request_success({"message": "成功接受好友请求"})

# 从数据库中筛选出自己的好友列表，返回一个list
def get_friend_list(request:HttpRequest) -> HttpResponse:
    if request.method != 'GET':
        return BAD_METHOD
    
    
    return request_success({})


# 从数据库中筛选出发给自己的好友请求，返回一个list
def get_friendshipRequest_list(request:HttpRequest) -> HttpResponse:
    if request.method != 'GET':
        return BAD_METHOD
    
    return request_success({})
