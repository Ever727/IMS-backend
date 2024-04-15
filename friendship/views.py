from django.http import HttpRequest, HttpResponse
from utils.utils_request import request_failed, request_success,BAD_METHOD
from utils.utils_require import require
from utils.utils_jwt import check_jwt_token
from utils.utils_time import  get_timestamp
from .models import Friendship, FriendshipRequest  
from account.models import User
import json
from chat.models import Conversation
from django.db.models import Count
from chat.models import Message
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
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
                     err_msg="Missing or error type of [searchId]")
    message = require(body,"message", "string",
                     err_msg="Missing or error type of [message]")
    
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)
    
    if searchId == userId:
        return request_failed(-4, "不能添加自己为好友", 403)
    
    try:
        User.objects.get(userId=searchId, isDeleted=False)
    except User.DoesNotExist:
        return request_failed(-1, "Id不存在", 404)

   
    if Friendship.objects.filter(userId=userId, friendId=searchId, status=True).exists():
            return request_failed(-4, "已经是好友", 403)
    try:
        friendshipRequest = FriendshipRequest.objects.filter(senderId=userId, receiverId=searchId).latest("sendTime")
        if get_timestamp() - friendshipRequest.sendTime <  1 :
            return request_failed(-4, "发送申请过于频繁", 403)
        else:
            friendshipRequest.status = 2
            friendshipRequest.save()
    except FriendshipRequest.DoesNotExist:
        pass
        
    friendshipRequest = FriendshipRequest(senderId=userId, receiverId=searchId, message=message)
    friendshipRequest.save()
    
    channelLayer = get_channel_layer()
    async_to_sync(channelLayer.group_send)(
        searchId, {"type": "friend_request", "message":  friendshipRequest.serialize()})
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
    
    try:
        friendship = Friendship.objects.get(userId=userId, friendId=friendId,status=True)
        friendship.status = False
        friendship.tag = ""
        friendship.save()

        friendship = Friendship.objects.get(userId=friendId, friendId=userId,status=True)
        friendship.status = False
        friendship.tag = ""
        friendship.save()

        members = [User.objects.get(userId=userId).id, User.objects.get(userId=friendId).id]
        conversation = Conversation.objects.filter( type='private_chat', members__in=members,
            ).annotate(num_members=Count('members')).filter(num_members=2).first()
        conversation.status = False
        conversation.save()
    except Friendship.DoesNotExist:
        return request_failed(-1, "好友关系不存在", 404)
    except Conversation.DoesNotExist:
        return request_failed(-1, "会话不存在", 404)
    
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
    
    if Friendship.objects.filter(userId=receiverId, friendId=senderId, status=True).exists():
        return request_failed(-4, "已经是好友", 403)
    
    friendshipRequest = FriendshipRequest.objects.filter(senderId=senderId, receiverId=receiverId,status=0).latest("sendTime")
    friendshipRequest.status = 1
    friendshipRequest.save()

    try:
        friendshipRequest = FriendshipRequest.objects.filter(senderId=receiverId, receiverId=senderId,status=0).latest("sendTime")
        friendshipRequest.status = 1
        friendshipRequest.save()
    except FriendshipRequest.DoesNotExist:
        pass
    
    try:
       friendship = Friendship.objects.get(userId=receiverId, friendId=senderId)
       friendship.status = True
       friendship.save()

       friendship = Friendship.objects.get(userId=senderId, friendId=receiverId)
       friendship.status = True
       friendship.save()

       members = [User.objects.get(userId=receiverId), User.objects.get(userId=senderId)]
       conversation = Conversation.objects.filter( type='private_chat', members__in=members,
            ).annotate(num_members=Count('members')).filter(num_members=2).first()
       
       
       conversation.status = True
       conversation.save()

    except Friendship.DoesNotExist:   
        friendship = Friendship(userId=receiverId, friendId=senderId)
        friendship.save()

        friendship = Friendship(userId=senderId, friendId=receiverId)
        friendship.save()

        members = [User.objects.get(userId=receiverId), User.objects.get(userId=senderId)]
        conversation = Conversation.objects.create(type="private_chat")
        conversation.save()
        conversation.members.set(members)
        conversation.save()

    sender = User.objects.get(userId=senderId)
    message = Message.objects.create(
            conversation=conversation, sender=sender, content="我们已经成为好友了"
        )

    message.receivers.set(conversation.members.all())

    channelLayer = get_channel_layer()
    for member in conversation.members.all():
        async_to_sync(channelLayer.group_send)(member.userId, {"type": "notify"})        
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
    friendList = [friendship.serialize() for friendship in friendships]

    return request_success(friendList)



# 从数据库中筛选出发给自己的好友请求，返回一个list
def get_friendshipRequest_list(request:HttpRequest, userId:str) -> HttpResponse:
    if request.method != 'GET':
        return BAD_METHOD
    
    token = request.headers.get('Authorization')
    payload = check_jwt_token(token)
    
    if payload is None or payload["userId"] != userId:  
        return request_failed(-3, "JWT 验证失败", 401)
    
    friendshipRequests = FriendshipRequest.objects.filter(receiverId=userId).order_by("-sendTime")[:30]
    requestList = [friendshipRequest.serialize() for friendshipRequest in friendshipRequests]

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
    
    try:
        friend = User.objects.get(userId=friendId)
    except User.DoesNotExist:
        return request_failed(-1, "用户不存在", 404)
    
    deleteStatus = True if friend.isDeleted == True else False
    friendshipStatus = True if Friendship.objects.filter(userId=userId, friendId=friendId, status=True).exists() else False
    return request_success({"deleteStatus": deleteStatus,"friendshipStatus": friendshipStatus})


def add_tag(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
    body = json.loads(request.body.decode('utf-8'))
    token = request.headers.get('Authorization')
    payload = check_jwt_token(token)
    userId = require(body, "userId", "string",
                     err_msg="Missing or error type of [userId]")
    friendId = require(body, "friendId", "string",
                     err_msg="Missing or error type of [friendId]")
    tag = require(body, "tag", "string",
                     err_msg="Missing or error type of [tag]")
    
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)
    if User.objects.filter(userId=friendId, isDeleted=False).exists() is False:
        return request_failed(-1, "好友已注销", 404)
    if len(tag) > 30:
        return request_failed(-2, "tag长度不能超过30", 400)
    
    try:
        friendship = Friendship.objects.get(userId=userId, friendId=friendId,status=True)
        friendship.tag = tag
        friendship.save()
    except Friendship.DoesNotExist:
        return request_failed(-1, "好友关系不存在", 404)
    
    return request_success({"message": "tag添加成功"})
