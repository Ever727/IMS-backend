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
    
    body = json.loads(request.body.decode('utf-8'))
    token = request.headers.get('Authorization')
    payload = check_jwt_token(token)
    userId = require(body,"userId", "string",
                     err_msg="Missing or error type of [userId]")
    searchId = require(body,"searchId", "string",
                     err_msg="Missing or error type of [friendId]")
    message = require(body,"message", "string",
                     err_msg="Missing or error type of [message]")
    
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)
    
    if User.objects.filter(userId=searchId).exists() == False:
        return request_failed(-1, "Id不存在", 404)
    user = User.objects.get(userId=userId)
    if user.isDeleted == True:
        return request_failed(-1, "Id不存在", 404)
    if searchId == userId:
        return request_failed(-4, "不能添加自己为好友", 403)
    if Friendship.objects.filter(userId=userId, friendId=searchId).exists():
        if Friendship.objects.get(userId=searchId, friendId=userId).status == True:
            return request_failed(-4, "已经是好友", 403)
    if FriendshipRequest.objects.filter(senderId=userId, receiverId=searchId).exists():
        friendshipRequest = FriendshipRequest.objects.filter(senderId=userId, receiverId=searchId).latest("sendTime")
        if get_timestamp() - friendshipRequest.sendTime < 60 * 60:
            return request_failed(-4, "发送申请过于频繁", 403)
        
    friendshipRequest = FriendshipRequest(senderId=userId, receiverId=searchId, message=message)
    friendshipRequest.save()
    return request_success({"message": "成功发送请求"})


def delete_friend(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads(request.body.decode('utf-8'))
    token = request.headers.get('Authorization')
    payload = check_jwt_token(token)
    userId = require(body, "userId", "string",
                     err_msg="Missing or error type of [userId]")
    friendId = require(body, "friendId", "string",
                     err_msg="Missing or error type of [friendId]")
    
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)
    
    if Friendship.objects.filter(userId=userId, friendId=friendId).exists() is False:
        return request_failed(4, "好友关系不存在", 404)

    friendship = Friendship.objects.get(userId=userId, friendId=friendId)
    if friendship.status == False:
        return request_failed(4, "好友关系不存在", 404)

    friendship.status = False
    friendship.save()

    friendship = Friendship.objects.get(userId=friendId, friendId=userId)
    friendship.status = False
    friendship.save()
    
    return request_success({"message": "删除成功"})


def accept_friend(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads(request.body.decode('utf-8'))
    token = request.headers.get('Authorization')
    payload = check_jwt_token(token)
    receiverId = require(body, "receiverId", "string",
                     err_msg="Missing or error type of [userId]")
    senderId = require(body, "senderId", "string",
                     err_msg="Missing or error type of [friendId]")
    
    if payload is None or payload["userId"] != receiverId:
        return request_failed(-3, "JWT 验证失败", 401)
    
    
    friendshipRequest = FriendshipRequest.objects.get(senderId=senderId, receiverId=receiverId)
    friendshipRequest.status = 1
    friendshipRequest.save()
    
    if Friendship.objects.filter(userId=receiverId, friendId=senderId).exists() is True:
        friendship = Friendship.objects.get(userId=receiverId, friendId=senderId)
        friendship.status = True
        friendship.save()

        friendship = Friendship.objects.get(userId=senderId, friendId=receiverId)
        friendship.status = True
        friendship.save()
    else:
        friendship = Friendship(userId=receiverId, friendId=senderId)
        friendship.save()

        friendship = Friendship(userId=senderId, friendId=receiverId)
        friendship.save()
    
    return request_success({"message": "接受成功"})


# 从数据库中筛选出自己的好友列表，返回一个list
def get_friend_list(request:HttpRequest, userId:str) -> HttpResponse:
    if request.method != 'GET':
        return BAD_METHOD
    
    token = request.headers.get('Authorization')
    payload = check_jwt_token(token)
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)
    
    friendships = Friendship.objects.filter(userId=userId, status=True)
    
    friendList = []
    for friendship in friendships:
        user = User.objects.get(userId=friendship.friendId)
        friendList.append({
            "id": user.userId,
            "name": user.userName,
            "avatarUrl": user.avatarUrl
        })
    
    return request_success(friendList)


# 从数据库中筛选出发给自己的好友请求，返回一个list
def get_friendshipRequest_list(request:HttpRequest, userId:str) -> HttpResponse:
    if request.method != 'GET':
        return BAD_METHOD
    
    token = request.headers.get('Authorization')
    payload = check_jwt_token(token)
    
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)
    
    friendshipRequests = FriendshipRequest.objects.filter(receiverId=userId).order_by("-sendTime")
    
    requestList = []
    for friendshipRequest in friendshipRequests:
        user = User.objects.get(userId=friendshipRequest.senderId)
        requestList.append({
            "id": friendshipRequest.senderId,
            "name": user.userName,
            "message": friendshipRequest.message,
            "sendTime": timestamp_to_datetime(friendshipRequest.sendTime),
            "status": friendshipRequest.status,
            "avatarUrl": user.avatarUrl
        })
    
    return request_success(requestList)


def check_friendship(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
    body = json.loads(request.body.decode('utf-8'))
    userId = require(body, "userId", "string",
                     err_msg="Missing or error type of [userId]")
    friendId = require(body, "friendId", "string",
                     err_msg="Missing or error type of [friendId]")
    
    token = request.headers.get('Authorization')
    payload = check_jwt_token(token)
    
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)
    
    if User.objects.filter(userId=userId).exists() is False:
        return request_failed(-1, "用户不存在", 404)
    user = User.objects.get(userId=userId)
    deleteStatus = True if user.isDeleted == True else False
    friendshipStatus = False

    if Friendship.objects.filter(userId=userId, friendId=friendId, status=True).exists() is True:
           friendshipStatus = True
    return request_success({"deleteStatus": deleteStatus,"friendshipStatus": friendshipStatus})
