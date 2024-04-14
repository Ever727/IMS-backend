import json
from datetime import datetime, timezone
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from account.models import User
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Message, Conversation
from utils.utils_request import request_failed, request_success, BAD_METHOD
from utils.utils_require import require
from utils.utils_jwt import check_jwt_token
from django.db import transaction
from django.db.models import F


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


def send_message(request: HttpRequest) -> HttpResponse:
    body = json.loads(request.body.decode("utf-8"))
    conversationId = require(
        body, "conversationId", "int",
        err_msg="Missing or error type of [conversationId]",
    )
    userId = require(
        body, "userId", "string", err_msg="Missing or error type of [userId]"
    )
    content = require(
        body, "content", "string", err_msg="Missing or error type of [content]"
    )
    replyId = body.get("replyId", None)
    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)
    # 验证 conversationId 和 userId 的合法性
    try:
        conversation = Conversation.objects.prefetch_related("members").get(
            id=conversationId, status=True
        )
        sender = User.objects.get(userId=userId, isDeleted=False)
    except Conversation.DoesNotExist:
        return request_failed(-2, "会话不存在", 400)
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在或已注销", 400)
    # 验证 sender 是否是 conversation 的成员
    if not conversation.members.filter(id=sender.id).exists():
        return request_failed(-4, "用户不在会话中", 403)
    
    
    with transaction.atomic():
        if replyId is not None:
            # 更新replyCount，避免加载整个Message对象
            updated = Message.objects.filter(id=replyId, conversation=conversation).update(
                replyCount=F('replyCount') + 1,
                updateTime=datetime.now()
              )  # 更新 updateTime 字段为当前时间)
            if updated == 0:
                return request_failed(-2, "原消息不存在", 400)

        # 创建消息
        message = Message.objects.create(
            conversation=conversation, sender=sender, content=content, replyTo_id=replyId if replyId else None
        )


    message.receivers.set(conversation.members.all())

    channelLayer = get_channel_layer()
    for member in conversation.members.all():
        async_to_sync(channelLayer.group_send)(member.userId, {"type": "notify"})
    return request_success(message.serilize())


def get_message(request: HttpRequest) -> HttpResponse:
    userId: str = request.GET.get("userId")
    conversationId: str = request.GET.get("conversationId")
    after: str = request.GET.get("after", "0")
    afterDatetime = datetime.fromtimestamp((int(after) + 1) / 1000.0, tz=timezone.utc)
    limit: int = int(request.GET.get("limit", "100"))
    messagesQuery = Message.objects.filter(updateTime__gte=afterDatetime).order_by(
        "updateTime"
    )
    messagesQuery = messagesQuery.prefetch_related("conversation")

    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    # 验证 conversationId 和 userId 的合法性
    try:
        user = User.objects.get(userId=userId)
        messagesQuery = messagesQuery.filter(receivers=user).exclude(
            deleteUsers=user
        )
    except User.DoesNotExist:
        return JsonResponse({"messages": [], "hasNext": False}, status=200)
    try:
        conversation = Conversation.objects.get(id=conversationId)
        messagesQuery = messagesQuery.filter(conversation=conversation)
    except Conversation.DoesNotExist:
        return JsonResponse({"messages": [], "hasNext": False}, status=200)
   

    messages = list(messagesQuery[: limit + 1])
    messagesData = [message.serilize() for message in messages]

    # 检查是否还有更多消息
    hasNext = False
    if len(messagesData) > limit:
        hasNext = True
        messagesData = messagesData[:limit]
    return request_success({"messages": messagesData, "hasNext": hasNext})


def create_conversation(request: HttpRequest) -> HttpResponse:
    body = json.loads(request.body.decode("utf-8"))
    userId = require(
        body, "userId", "string", err_msg="Missing or error type of [userId]"
    )
    conversationType = require(
        body, "type", "string", err_msg="Missing or error type of [type]"
    )
    memberIds = body.get("members", [])

    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    # 使用 filter 替代 get，一次性获取所有指定ID的用户
    users = User.objects.filter(userId__in=memberIds, isDeleted=False)
    # 检查是否所有用户都被找到
    if users.count() != len(memberIds):
        return request_failed(-2, "用户不存在", 400)

    members = list(users)
       
        
    if not members:
        return request_failed(-2, "至少需要两个用户参与聊天", 400)

    if conversationType == "private_chat":
        return request_failed(-2, "私聊不能手动创建", 400)

    conversation = Conversation.objects.create(type=conversationType)
    conversation.members.set(members)
    # TODO: 群聊头像
    return request_success(conversation.serilize(0, None))


def get_conversation(request: HttpRequest) -> HttpResponse:
    userId: str = request.GET.get("userId")
    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    conversationIds = request.GET.getlist("id", [])
    validConversations = Conversation.objects.filter(
        id__in=conversationIds
    ).prefetch_related("members")
    response_data = []
    for conv in validConversations:
        if conv.type == "private_chat":
            avatar = conv.members.exclude(userId=userId).first().avatarUrl
        else:
            # TODO: 群聊头像
            avatar = None
        response_data.append(conv.serilize(avatar))

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

    conversationIds = list(Conversation.objects.filter(members__userId=userId).values_list('id', flat=True))

    return request_success({"conversationIds": conversationIds})


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

    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    try:
        message = Message.objects.get(id=messageId)
    except Message.DoesNotExist:
        return request_failed(-2, "消息不存在", 400)
    if message.deleteUsers.filter(userId=userId).exists():
        return request_failed(-4, "消息已删除", 403)
    message.deleteUsers.add(User.objects.get(userId=userId).id)
    message.save()

    return request_success({"info": "删除成功"})


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

    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    try:
        id = User.objects.get(userId=userId).id
    except User.DoesNotExist:
        return request_failed(-2, "用户不存在", 400)

    messages = (
        Message.objects.filter(conversation=conversationId)
        .exclude(sender=id)
        .exclude(readUsers__in=[id])
        .prefetch_related("readUsers")
    )
    
    for message in messages:
        message.readUsers.add(id)
        message.updateTime = datetime.now()
        message.save()

    
    channelLayer = get_channel_layer()
    
    memberIds = Conversation.objects.filter(id=conversationId).values_list('members__userId', flat=True)
    for memberId in memberIds:
        async_to_sync(channelLayer.group_send)(memberId, {"type": "notify"})    

    return request_success({"info": "已读成功"})


def get_unread_count(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return BAD_METHOD
    
    userId: str = request.GET.get("userId")
    conversationId: int = request.GET.get("conversationId")
    
    token = request.headers.get("Authorization")
    payload = check_jwt_token(token)

    # 验证 token
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

   
    id = User.objects.filter(userId=userId).values_list("id", flat=True).first()
    count = (
        Message.objects.filter(conversation_id=conversationId)
        .exclude(sender=id)
        .exclude(readUsers__in=[id])
        .count()
    )
    return request_success({"count": count})
