import json
import re
from datetime import datetime, timezone
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from account.models import User
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Invitation, Message, Conversation, Notification
from utils.utils_request import request_failed, request_success, BAD_METHOD
from utils.utils_require import require
from utils.utils_jwt import check_jwt_token, jwt_required
from utils.constants import group_default_avatarUrl
from django.db import transaction
from django.db.models import F, Q
from django.core.cache import cache


# Create your views here.
@require_http_methods(["POST", "GET"])
def messages(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return send_message(request)
    elif request.method == "GET":
        return get_message(request)
    else:
        return BAD_METHOD


@require_http_methods(["POST", "GET"])
def conversations(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return create_conversation(request)
    elif request.method == "GET":
        return get_conversation(request)
    else:
        return BAD_METHOD

@jwt_required
def send_message(request: HttpRequest) -> HttpResponse:
    body = json.loads(request.body.decode("utf-8"))
    conversationId = require(
        body,
        "conversationId",
        "int",
        err_msg="Missing or error type of [conversationId]",
    )
    userId = require(
        body, "userId", "string", err_msg="Missing or error type of [userId]"
    )
    content = require(
        body, "content", "string", err_msg="Missing or error type of [content]"
    )
    replyId = body.get("replyId", None)

    senderId = User.objects.filter(userId=userId, isDeleted=False).values_list('id', flat=True).first()
    if senderId is None:
        return request_failed(-2, "用户不存在或已注销", 400)
    try:
        conversation = Conversation.objects.prefetch_related("members").get(
            id=conversationId, status=True, members__id=senderId
        )
    except Conversation.DoesNotExist:
        return request_failed(-2, "会话已失效", 400)
    except Exception:
        return request_failed(-4, "用户不在会话中", 403)
    

    if conversation.type == "private_chat":
        receiverStatus = conversation.members.exclude(id=senderId).values_list('isDeleted', flat=True).first()
        if receiverStatus == True:
            return request_failed(-2, "好友已注销", 400)

    with transaction.atomic():
        if replyId is not None:
            # 更新replyCount，避免加载整个Message对象
            updated = Message.objects.filter(
                id=replyId, conversation_id=conversationId
            ).update(
                replyCount=F("replyCount") + 1, updateTime=datetime.now(tz=timezone.utc)
            )  # 更新 updateTime 字段为当前时间)
            if updated == 0:
                return request_failed(-2, "原消息不存在", 400)

        # 创建消息
        message = Message.objects.create(
            conversation_id=conversationId,
            sender_id=senderId,
            content=content,
            replyTo_id=replyId if replyId else None,
            sendTime=datetime.now(tz=timezone.utc),
            updateTime=datetime.now(tz=timezone.utc),
        )

    message.receivers.set(conversation.members.all())

    channelLayer = get_channel_layer()
    for member in conversation.members.all():
        async_to_sync(channelLayer.group_send)(member.userId, {"type": "notify"})
        cacheKey = f"unread_count_{conversation.id}_{member.userId}"
        if member.userId != userId and cache.get(cacheKey, -1) != -1:
            cache.set(cacheKey, cache.get(cacheKey, -1) + 1, 60*5)
    return request_success({})


def get_message(request: HttpRequest) -> HttpResponse:
    userId: str = request.GET.get("userId")
    conversationId: str = request.GET.get("conversationId")
    after: str = request.GET.get("after", "0")
    afterDatetime = datetime.fromtimestamp((int(after) + 1) / 1000.0, tz=timezone.utc)
    limit: int = int(request.GET.get("limit", "100"))
   
    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)
    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    messagesQuery = Message.objects.filter(updateTime__gte=afterDatetime).order_by(
        "updateTime"
    ).prefetch_related("conversation")

    if messagesQuery.count() == 0:
        return JsonResponse({"messages": [], "hasNext": False}, status=200)

    if userId:
        messagesQuery = messagesQuery.filter(receivers__userId=userId).exclude(
                deleteUsers__userId=userId
            )
        if not messagesQuery.exists():            
            return JsonResponse({"messages": [], "hasNext": False}, status=200)
    elif conversationId:
        messagesQuery = messagesQuery.filter(conversation_id=conversationId)
        if not messagesQuery.exists():
            return JsonResponse({"messages": [], "hasNext": False}, status=200)
    else:
        return request_failed(-2, "用户或会话不存在", 400)

    messages = list(messagesQuery[: limit + 1])
    messagesData = [message.serialize() for message in messages]

    # 检查是否还有更多消息
    hasNext = False
    if len(messagesData) > limit:
        hasNext = True
        messagesData = messagesData[:limit]
    return request_success({"messages": messagesData, "hasNext": hasNext})

@jwt_required
def create_conversation(request: HttpRequest) -> HttpResponse:
    body = json.loads(request.body.decode("utf-8"))
    userId = require(
        body, "userId", "string", err_msg="Missing or error type of [userId]"
    )
    memberIds = body.get("memberIds", [])
    memberIds.append(userId)
    memberIds = list(set(memberIds))
    # 使用 filter 替代 get，一次性获取所有指定ID的用户
    users = User.objects.filter(userId__in=memberIds, isDeleted=False)
    # 检查是否所有用户都被找到
    if users.count() != len(memberIds):
        return request_failed(-2, "用户不存在", 400)
    members = list(users)
    if len(memberIds) < 2:
        return request_failed(-2, "群聊人数过少", 400)

    host = User.objects.get(userId=userId)
    conversation = Conversation.objects.create(type="group_chat", host=host, avatarUrl=group_default_avatarUrl)
    conversation.members.set(members)
    conversation.groupName = ", ".join([member.userName for member in members])
    if len(conversation.groupName) > 20:
        conversation.groupName = (
            ", ".join([member.userName for member in members])[:17] + "..."
        )
    conversation.save()

    channelLayer = get_channel_layer()
    async_to_sync(channelLayer.group_send)(userId, {"type": "notify"})
    for memberId in memberIds:
        cacheKey = f'conversations_{memberId}'
        if cache.get(cacheKey) != None:
            cache.delete(cacheKey)
        async_to_sync(channelLayer.group_send)(memberId, {"type": "notify"})

    return request_success(conversation.serialize(group_default_avatarUrl))


def get_conversation(request: HttpRequest) -> HttpResponse:
    userId: str = request.GET.get("userId")
    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    conversationIds = request.GET.getlist("id", [])
    conversations = Conversation.objects.filter(
        id__in=conversationIds
    ).prefetch_related("members")
    response_data = []
    cacheKey = f'conversations_{userId}'
    response_data = cache.get(cacheKey, [])
    if len(response_data) == 0:
        for conv in conversations:
            if conv.type == "private_chat":
                avatar = conv.members.exclude(userId=userId).first().avatarUrl
            else:
                avatar = conv.avatarUrl
            response_data.append(conv.serialize(avatar))
        cache.set(cacheKey, response_data, 60*5)    

    return request_success({"conversations": response_data})


def get_conversation_ids(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return BAD_METHOD

    userId: str = request.GET.get("userId")
    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    conversationIds = list(
        Conversation.objects.filter(members__userId=userId).values_list("id", flat=True)
    )

    return request_success({"conversationIds": conversationIds})

@jwt_required
def delete_message(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD

    body = json.loads(request.body.decode("utf-8"))
    userId = require(
        body, "userId", "string", err_msg="Missing or error type of [userId]"
    )
    messageId = require(
        body, "messageId", "int", err_msg="Missing or error type of [messageId]"
    )

    try:
        message = Message.objects.get(id=messageId)
    except Message.DoesNotExist:
        return request_failed(-2, "消息不存在", 400)
    user, _ = User.objects.get_or_create(userId=userId)
    if not message.deleteUsers.filter(userId=userId).exists():
        message.deleteUsers.add(user.id)
        message.save()
    else:
        return request_failed(-4, "消息已删除", 403)
    return request_success({"info": "删除成功"})

@jwt_required
def read_message(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD

    body = json.loads(request.body.decode("utf-8"))
    userId = require(
        body, "userId", "string", err_msg="Missing or error type of [userId]"
    )
    conversationId = require(
        body,
        "conversationId",
        "int",
        err_msg="Missing or error type of [conversationId]",
    )

    id = User.objects.filter(userId=userId).values_list('id', flat=True).first()
    if id is None:    
        return request_failed(-2, "用户不存在", 400)

    messages = (
        Message.objects.filter(conversation_id=conversationId)
        .exclude(Q(sender=id) | Q(readUsers__in=[id]))
        .prefetch_related("readUsers")
    )

    # 更新所有选中消息的updateTime
    Message.objects.filter(id__in=messages.values_list('id', flat=True)).update(updateTime=datetime.now(tz=timezone.utc))

    # 批量处理多对多关系的添加
    ReadUser_Message = Message.readUsers.through
    readuser_message_objects = [
        ReadUser_Message(user_id=id, message_id=message.id) for message in messages
    ]

    # 使用数据库事务确保所有操作都能一次性成功，否则全部回滚
    with transaction.atomic():
        # 批量创建多对多关系
        ReadUser_Message.objects.bulk_create(readuser_message_objects, ignore_conflicts=True)

    cacheKey = f"unread_count_{conversationId}_{userId}"
    cache.set(cacheKey, 0, 60*5)

    channelLayer = get_channel_layer()
    memberIds = Conversation.objects.filter(id=conversationId).values_list(
        "members__userId", flat=True
    )
    for memberId in memberIds:
        async_to_sync(channelLayer.group_send)(memberId, {"type": "notify"})

    return request_success({"info": "已读成功"})


def get_unread_count(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return BAD_METHOD

    userId: str = request.GET.get("userId")
    conversationId: int = request.GET.get("conversationId")

    cacheKey = f"unread_count_{conversationId}_{userId}"
    count = cache.get(cacheKey, -1)
    if count == -1:
        id = User.objects.filter(userId=userId).values_list("id", flat=True).first()
        count = (
            Message.objects.filter(conversation_id=conversationId)
            .exclude(Q(sender__id=id) | Q(readUsers__in=[id]))
            .count()
        )
        cache.set(cacheKey, count, 60*5)

    return request_success({"count": count})

@jwt_required
def upload_notification(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD

    body = json.loads(request.body.decode("utf-8"))
    userId = require(
        body, "userId", "string", err_msg="Missing or error type of [userId]"
    )
    groupId = require(
        body, "groupId", "int", err_msg="Missing or error type of [groupId]"
    )
    
    content = body.get("content", "")
    if len(content) == 0:
        return request_failed(-2, "通知内容不能为空", 400)


    try:
        user = User.objects.get(userId=userId)
        conversation = Conversation.objects.get(id=groupId, type="group_chat")
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)
    except Conversation.DoesNotExist:
        return request_failed(-2, "会话不存在", 400)


    if user not in conversation.admins.all() and user != conversation.host:
        return request_failed(-4, "权限不足", 403)

    newNotification = Notification.objects.create(
        conversation_id=groupId,
        content=content,
        userId=userId,
        userName=user.userName,
        avatarUrl=user.avatarUrl,
        timestamp=datetime.now(timezone.utc),
    )

    conversation.groupNotificationList.add(newNotification)
    conversation.save()

    channelLayer = get_channel_layer()
    memberIds = conversation.members.values_list("userId", flat=True)
    for memberId in memberIds:
        cacheKey = f"conversations_{memberId}"
        if cache.get(cacheKey) != None:
           cache.delete(cacheKey)
        async_to_sync(channelLayer.group_send)(memberId, {"type": "notify"})

    return request_success({})


def set_host(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD

    body = json.loads(request.body.decode("utf-8"))
    oldHostId = require(
        body, "oldHostId", "string", err_msg="Missing or error type of [userId]"
    )
    newHostId = require(
        body, "newHostId", "string", err_msg="Missing or error type of [newHostId]"
    )
    groupId = require(
        body, "groupId", "int", err_msg="Missing or error type of [groupId]"
    )

    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)
    if payload is None or payload["userId"] != oldHostId:
        return request_failed(-3, "JWT 验证失败", 401)

    try:
        user = User.objects.get(userId=oldHostId)
        newHost = User.objects.get(userId=newHostId)
        conversation = Conversation.objects.get(id=groupId, type="group_chat")
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)
    except Conversation.DoesNotExist:
        return request_failed(-2, "会话不存在", 400)


    if user != conversation.host:
        return request_failed(-4, "权限不足", 403)
    if user == newHost:
        return request_failed(-4, "新群主不能与旧群主相同", 403)
    if newHost in conversation.admins.all():
        conversation.admins.remove(newHost)

    conversation.host = newHost
    conversation.save()

    channelLayer = get_channel_layer()
    memberIds = conversation.members.values_list("userId", flat=True)
    for memberId in memberIds:
        cacheKey = f"conversations_{memberId}"
        if cache.get(cacheKey) is not None:
           cache.delete(cacheKey)
        async_to_sync(channelLayer.group_send)(memberId, {"type": "notify"})

    return request_success(conversation.serialize(conversation.avatarUrl))


def set_admin(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD

    body = json.loads(request.body.decode("utf-8"))
    hostId = require(
        body, "hostId", "string", err_msg="Missing or error type of [hostId]"
    )
    groupId = require(
        body, "groupId", "int", err_msg="Missing or error type of [groupId]"
    )
    adminId = require(
        body, "adminId", "string", err_msg="Missing or error type of [adminId]"
    )

    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != hostId:
        return request_failed(-3, "JWT 验证失败", 401)

    try:
        user = User.objects.get(userId=hostId)
        conversation = Conversation.objects.get(id=groupId, type="group_chat")
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)
    except Conversation.DoesNotExist:
        return request_failed(-2, "会话不存在", 400)


    if user != conversation.host:
        return request_failed(-4, "权限不足", 403)

    try:
        admin = conversation.members.get(userId=adminId)
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)

    if admin in conversation.admins.all() or admin == conversation.host:
        return request_failed(-4, "权限已存在", 403)

    conversation.admins.add(admin)
    conversation.save()

    channelLayer = get_channel_layer()
    memberIds = conversation.members.values_list("userId", flat=True)
    for memberId in memberIds:
        cacheKey = f"conversations_{memberId}"
        convs = cache.get(cacheKey)
        if convs is not None:
            cache.delete(cacheKey)
        async_to_sync(channelLayer.group_send)(memberId, {"type": "notify"})

    return request_success({})


def remove_admin(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD

    body = json.loads(request.body.decode("utf-8"))
    hostId = require(
        body, "hostId", "string", err_msg="Missing or error type of [userId]"
    )
    groupId = require(
        body, "groupId", "int", err_msg="Missing or error type of [groupId]"
    )
    adminId = require(
        body, "adminId", "string", err_msg="Missing or error type of [adminId]"
    )

    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != hostId:
        return request_failed(-3, "JWT 验证失败", 401)

    try:
        user = User.objects.get(userId=hostId)
        conversation = Conversation.objects.get(id=groupId, type="group_chat")
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)
    except Conversation.DoesNotExist:
        return request_failed(-2, "会话不存在", 400)


    if user != conversation.host:
        return request_failed(-4, "权限不足", 403)

    try:
        admin = conversation.members.get(userId=adminId)
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)

    if admin not in conversation.admins.all():
        return request_failed(-4, "权限不存在", 403)

    conversation.admins.remove(admin)
    conversation.save()

    channelLayer = get_channel_layer()
    memberIds = conversation.members.values_list("userId", flat=True)
    for memberId in memberIds:
        cacheKey = f"conversations_{memberId}"
        convs = cache.get(cacheKey)
        if convs is not None:
              cache.delete(cacheKey)
        async_to_sync(channelLayer.group_send)(memberId, {"type": "notify"})

    return request_success({})


def kick_member(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD

    body = json.loads(request.body.decode("utf-8"))
    opId = require(body, "opId", "string", err_msg="Missing or error type of [opId]")
    groupId = require(
        body, "groupId", "int", err_msg="Missing or error type of [groupId]"
    )
    memberId = require(
        body, "memberId", "string", err_msg="Missing or error type of [memberId]"
    )

    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != opId:
        return request_failed(-3, "JWT 验证失败", 401)

    try:
        user = User.objects.get(userId=opId)
        conversation = Conversation.objects.get(id=groupId, type="group_chat")
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)
    except Conversation.DoesNotExist:
        return request_failed(-2, "群聊不存在", 400)


    # 是否是群主或管理员
    if (user != conversation.host) and (user not in conversation.admins.all()):
        return request_failed(-4, "权限不足", 403)
    try:
        member = conversation.members.get(userId=memberId)
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)
    if member == conversation.host or (
        user != conversation.host and member in conversation.admins.all()
    ):
        return request_failed(-4, "权限不足", 403)
    conversation.members.remove(member)
    if member in conversation.admins.all():
        conversation.admins.remove(member)
    conversation.save()

    channelLayer = get_channel_layer()
    cacheKey = f"conversations_{memberId}"
    if cache.get(cacheKey) is not None:
        cache.delete(cacheKey)
    async_to_sync(channelLayer.group_send)(memberId, {"type": "kick_member"})

    memberIds = conversation.members.values_list("userId", flat=True)
    for memberId in memberIds:
        cacheKey = f"conversations_{memberId}"
        if cache.get(cacheKey) is not None:
            cache.delete(cacheKey)
        async_to_sync(channelLayer.group_send)(memberId, {"type": "kick_member"})

    return request_success({})

@jwt_required
def exit_group(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD

    body = json.loads(request.body.decode("utf-8"))
    userId = require(
        body, "userId", "string", err_msg="Missing or error type of [userId]"
    )
    groupId = require(
        body, "groupId", "int", err_msg="Missing or error type of [groupId]"
    )


    try:
        user = User.objects.get(userId=userId)
        conversation = Conversation.objects.get(id=groupId, type="group_chat")
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)
    except Conversation.DoesNotExist:
        return request_failed(-2, "群聊不存在", 400)
    if user not in conversation.members.all():
        return request_failed(-4, "权限不足", 403)
    
    memberCount = conversation.members.count()
    channelLayer = get_channel_layer()
    if memberCount == 1:
        conversation.delete()
    else:    
        if user == conversation.host:
            return request_failed(-4, "群主不能退群", 403)
        conversation.members.remove(user)
        if user in conversation.admins.all():
            conversation.admins.remove(user)
        conversation.save()
        memberIds = conversation.members.values_list("userId", flat=True)
        for memberId in memberIds:
            cacheKey = f"conversations_{memberId}"
            if cache.get(cacheKey) is not None:
                cache.delete(cacheKey)
            async_to_sync(channelLayer.group_send)(memberId, {"type": "notify"})

    cacheKey = f"conversations_{userId}"
    if cache.get(cacheKey) is not None:
        cache.delete(cacheKey)
    async_to_sync(channelLayer.group_send)(userId, {"type": "notify"})
    
    return request_success({})


def invite_member(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD


    body = json.loads(request.body.decode("utf-8"))
    opId = require(body, "opId", "string", err_msg="Missing or error type of [opId]")
    groupId = require(
        body, "groupId", "int", err_msg="Missing or error type of [groupId]"
    )
    memberIds = require(
        body, "memberIds", "list", err_msg="Missing or error type of [memberIds]"
    )

    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)
    # 验证 token
    if payload is None or payload["userId"] != opId:
        return request_failed(-3, "JWT 验证失败", 401)


    try:
        user = User.objects.get(userId=opId)
        conversation = Conversation.objects.get(id=groupId, type="group_chat")
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)
    except Conversation.DoesNotExist:
        return request_failed(-2, "群聊不存在", 400)
    
    if memberIds is None or len(memberIds) == 0:
        return request_failed(-4, "邀请对象不能为空", 403)
    members = User.objects.filter(userId__in=memberIds)
    if len(members) != len(set(memberIds)):
        return request_failed(-2, "邀请对象账户不存在", 400)
    
    if set(members).intersection(conversation.members.all()):
        return request_failed(-4, "成员已在群里", 403)


    if (user != conversation.host) and (user not in conversation.admins.all()):
        for member in members:
            invitation = Invitation.objects.create(
                conversation=conversation,
                sender=user,
                receiver=member,
                timestamp=datetime.now(timezone.utc),
            )

        channelLayer = get_channel_layer()
        for member in conversation.admins.all():
            async_to_sync(channelLayer.group_send)(
                member.userId, {"type": "group_request"}
            )
        async_to_sync(channelLayer.group_send)(
            conversation.host.userId, {"type": "group_request"}
        )

        return request_success({})

    elif user in conversation.admins.all() or user == conversation.host:
        for member in members:
            conversation.members.add(member)
        conversation.save()

        channelLayer = get_channel_layer()
        memberIds = conversation.members.values_list("userId", flat=True)
        for memberId in memberIds:
            cacheKey = f"conversations_{memberId}"
            convs = cache.get(cacheKey)
            if convs is not None:
                cache.delete(cacheKey)
            async_to_sync(channelLayer.group_send)(memberId, {"type": "notify"})

        return request_success({})


def group_requests(request: HttpRequest, userId: str) -> HttpResponse:
    if request.method != "GET":
        return BAD_METHOD

    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    conversations = Conversation.objects.filter(members__userId=userId)
    conversations = conversations.filter(
        Q(host__userId=userId) | Q(admins__userId=userId)
    )

    invitations = Invitation.objects.filter(conversation__in=conversations)

    return request_success([invitation.serialize() for invitation in invitations])

@jwt_required
def accept_invitation(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD

    body = json.loads(request.body.decode("utf-8"))
    userId = require(
        body, "userId", "string", err_msg="Missing or error type of [userId]"
    )
    invitationId = require(
        body, "invitationId", "int", err_msg="Missing or error type of [invitationId]"
    )


    try:
        invitation = Invitation.objects.get(id=invitationId)
    except Invitation.DoesNotExist:
        return request_failed(-2, "邀请不存在", 400)

    conversation = invitation.conversation
    if conversation.type != "group_chat":
        return request_failed(-2, "群聊不存在", 400)

    user = User.objects.get(userId=userId)

    if user not in conversation.admins.all() and user != conversation.host:
        return request_failed(-4, "权限不足", 403)

    if invitation.receiver not in conversation.members.all():
        conversation.members.add(invitation.receiver)

    conversation.save()

    invitationList = Invitation.objects.filter(
        conversation=conversation, receiver=invitation.receiver
    )
    invitationList.delete()

    channelLayer = get_channel_layer()
    memberIds = conversation.members.values_list("userId", flat=True)
    for memberId in memberIds:
        cacheKey = f"conversations_{memberId}"
        convs = cache.get(cacheKey)
        if convs is not None:
            cache.delete(cacheKey)
        async_to_sync(channelLayer.group_send)(memberId, {"type": "group_request"})

    return request_success({})

@jwt_required
def update_group(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return BAD_METHOD
    
    body = json.loads(request.body.decode("utf-8"))
    userId = require(
        body, "userId", "string", err_msg="Missing or error type of [userId]"
    )
    groupId = require(
        body, "groupId", "int", err_msg="Missing or error type of [groupId]"
    )

    try:
        user = User.objects.get(userId=userId, isDeleted=False)
        conversation = Conversation.objects.get(id=groupId, type="group_chat")
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)
    except Conversation.DoesNotExist:
        return request_failed(-2, "群聊不存在", 400)

    if user != conversation.host and user not in conversation.admins.all():
        return request_failed(-4, "权限不足", 403)
    if "newName" not in body and "newAvatarUrl" not in body:
        return request_failed(-4, "更新内容不能为空", 403)
    if "newName" in body:
        newName = body["newName"]
        if len(newName) == 0:
            return request_failed(-4,"群聊名称不能为空",403)
        if len(newName) < 3 or len(newName) > 20 or not re.match(r'^\w+$', newName):
            return request_failed(-4,"群聊名称格式错误",403)
        conversation.groupName = newName
    if "newAvatarUrl" in body:
        conversation.avatarUrl = body["newAvatarUrl"]
    conversation.save()    
    
    channelLayer = get_channel_layer()
    memberIds = conversation.members.values_list("userId", flat=True)
    for memberId in memberIds:
        cacheKey = f'conversations_{memberId}'
        convs = cache.get(cacheKey)
        if convs is not None:
            for conv in convs:
                if conv["id"] == conversation.id:
                    conv["groupName"] = conversation.groupName
                    conv["avatarUrl"] = conversation.avatarUrl
                    break
            cache.set(cacheKey, convs, 60*5)
        async_to_sync(channelLayer.group_send)(memberId, {"type": "group_modify"})

    return request_success(conversation.serialize(conversation.avatarUrl))