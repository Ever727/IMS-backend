from django.http import HttpRequest, HttpResponse
from utils.utils_request import request_failed, request_success,BAD_METHOD
from utils.utils_require import require
from utils.utils_jwt import check_jwt_token, jwt_required
from utils.utils_time import  get_timestamp
from .models import Friendship, FriendshipRequest  
from account.models import User
import json
from datetime import datetime, timezone
from chat.models import Conversation
from chat.models import Message
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Q
from django.db.models import Count
from django.core.cache import cache
# Create your views here.
@jwt_required
def add_friend(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads(request.body.decode('utf-8'))
    userId = require(body,"userId", "string",
                     err_msg="Missing or error type of [userId]")
    searchId = require(body,"searchId", "string",
                     err_msg="Missing or error type of [searchId]")
    message = require(body,"message", "string",
                     err_msg="Missing or error type of [message]")
    
    
    if searchId == userId:
        return request_failed(-4, "不能添加自己为好友", 403)
    
    try:
        User.objects.get(userId=searchId, isDeleted=False)
    except User.DoesNotExist:
        return request_failed(-1, "用户不存在或已注销", 404)

   
    if Friendship.objects.filter(userId=userId, friendId=searchId, status=True).exists():
            return request_failed(-4, "已经是好友", 403)
    try:
        # 避免频繁发送请求，这里采取限制，同一用户一定时间内只能发送一次请求，方便测试采用1s
        friendshipRequest = FriendshipRequest.objects.filter(senderId=userId, receiverId=searchId).latest("sendTime")
        if get_timestamp() - friendshipRequest.sendTime < 10 :
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

@jwt_required
def delete_friend(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads(request.body.decode('utf-8'))
    userId = require(body, "userId", "string",
                    err_msg="Missing or error type of [userId]")
    friendId = require(body, "friendId", "string",
                    err_msg="Missing or error type of [friendId]")
    
    try:
        # 将双方的好友关系设置为False，清空tag，并删除会话
        Friendship.objects.filter(
            (Q(userId=userId) & Q(friendId=friendId)) | (Q(userId=friendId) & Q(friendId=userId)),
            status=True
        ).update(status=False, tag="")

        user_ids = User.objects.filter(userId__in=[userId, friendId]).values_list('id', flat=True)
        if len(user_ids) != 2:
            return request_failed(-1, "用户不存在", 404)
        conversation = Conversation.objects.filter( type='private_chat', members__in=user_ids,
            ).annotate(num_members=Count('members')).filter(num_members=2).first()
        if conversation is not None:
            conversation.status = False
            conversation.save()
        else:
            return request_failed(-1, "会话不存在", 404)
    except Friendship.DoesNotExist:
        return request_failed(-1, "好友关系不存在", 404) 

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
    
    # 更新好友请求状态为已处理
    FriendshipRequest.objects.filter(senderId=senderId, receiverId=receiverId,status=0).update(status=1)

    # 如果反向请求也存在，则更新状态为已处理
    try:
        FriendshipRequest.objects.filter(senderId=receiverId, receiverId=senderId,status=0).update(status=1)
    except FriendshipRequest.DoesNotExist:
        pass
    
    try:
        Friendship.objects.update_or_create(
            userId=receiverId, friendId=senderId,
            defaults={'status': True}
        )
        Friendship.objects.update_or_create(
            userId=senderId, friendId=receiverId,
            defaults={'status': True}
        )
    except Exception as e:
        return request_failed(-1, str(e), 500)
    
    if User.objects.filter(userId=senderId).exists() is False:
        return request_failed(-1, "用户不存在", 404)
    if User.objects.filter(userId=receiverId).exists() is False:
        return request_failed(-1, "用户不存在", 404)
    
    try:
        conversation = Conversation.objects.filter( type='private_chat', members__userId__in=[receiverId, senderId],
            ).annotate(num_members=Count('members')).filter(num_members=2).first()
        if conversation is None:
            conversation = Conversation.objects.create(type="private_chat")
            conversation.members.set(User.objects.filter(userId__in=[receiverId, senderId]))
        else:
            conversation.status = True
        conversation.save()
        for userId in [receiverId, senderId]:
            cacheKey = f'conversations_{userId}'
            if cache.get(cacheKey) is not None:
                cache.delete(cacheKey)
        
      
    except User.DoesNotExist:
        return request_failed(-1, "用户不存在", 404)
 
    receiver = User.objects.get(userId=receiverId)
    message = Message.objects.create(
            conversation=conversation, sender=receiver, content="我们已经成为好友了",
            sendTime = datetime.now(tz=timezone.utc), updateTime = datetime.now(tz=timezone.utc)
        )
    cacheKey = f"unread_count_{conversation.id}_{senderId}"
    cache.set(cacheKey, 1, 60*5)
    message.receivers.set(conversation.members.all())
    conversation.updateTime = datetime.now(tz=timezone.utc)
    conversation.save()

    channelLayer = get_channel_layer()
    for member in conversation.members.all():
        async_to_sync(channelLayer.group_send)(member.userId, {"type": "friend_request"})        
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

@jwt_required
def check_friendship(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
    body = json.loads(request.body.decode('utf-8'))
    userId = require(body, "userId", "string",
                     err_msg="Missing or error type of [userId]")
    friendId = require(body, "friendId", "string",
                     err_msg="Missing or error type of [friendId]")

    
    try:
        friend = User.objects.get(userId=friendId)
    except User.DoesNotExist:
        return request_failed(-1, "用户不存在", 404)
    
    deleteStatus = True if friend.isDeleted == True else False
    friendshipStatus = True if Friendship.objects.filter(userId=userId, friendId=friendId, status=True).exists() else False
    return request_success({"deleteStatus": deleteStatus,"friendshipStatus": friendshipStatus})

@jwt_required
def add_tag(request:HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return BAD_METHOD
    body = json.loads(request.body.decode('utf-8'))

    userId = require(body, "userId", "string",
                     err_msg="Missing or error type of [userId]")
    friendId = require(body, "friendId", "string",
                     err_msg="Missing or error type of [friendId]")
    tag = require(body, "tag", "string",
                     err_msg="Missing or error type of [tag]")
    
  
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
