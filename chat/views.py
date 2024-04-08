import re
import json
from datetime import datetime, timezone
from typing import Dict, Any
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from account.models import User
from friendship.models import Friendship
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Message, Conversation
from utils.utils_request import request_failed, request_success, BAD_METHOD
from utils.utils_require import require
from utils.utils_jwt import check_jwt_token


def check_username(value: str) -> bool:
    return re.match(r"^\w+$", value) and len(value) <= 20


# Create your views here.
@require_http_methods(["POST", "GET"])
def messages(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        body = json.loads(request.body.decode("utf-8"))
        conversationId = require(body, "conversationId", "int",
                            err_msg="Missing or error type of [conversationId]")
        userId = require(body, "userId", "int",
                            err_msg="Missing or error type of [userId]")
        content = require(body, "content", "string",
                            err_msg="Missing or error type of [content]")

        token = request.headers.get("Authorization")
        payload = check_jwt_token(token)

        # 验证 token
        if payload is None or payload["userId"] != userId:
            return request_failed(-3, "JWT 验证失败", 401)

        # 验证 conversationId 和 userId 的合法性
        try:
            conversation = Conversation.objects.prefetch_related("members").get(
                id=conversationId
            )
        except Conversation.DoesNotExist:
            return request_failed(-2, "会话不存在", 400)

        try:
            sender = User.objects.get(userId=userId, isDeleted=False)
        except User.DoesNotExist:
            return request_failed(-2, "用户不存在或已注销", 400)

        # 验证 sender 是否是 conversation 的成员
        if not conversation.members.filter(id=sender.id).exists():
            return request_failed(-4, "用户不在会话中", 403)

        # 创建消息 包括发送者、会话、内容
        message = Message.objects.create(
            conversation=conversation, sender=sender, content=content
        )

        message.receivers.set(conversation.members.all())

        channelLayer = get_channel_layer()
        for member in conversation.members.all():
            async_to_sync(channelLayer.group_send)(member.userId, {"type": "notify"})        
        return request_success(message.serilize())

    elif request.method == "GET":
        userId: str = request.GET.get("userId")
        conversationId: str = request.GET.get("conversationId")
        after: str = request.GET.get("after", "0")
        afterDatetime = datetime.fromtimestamp(
            (int(after) + 1) / 1000.0, tz=timezone.utc
        )
        limit: int = int(request.GET.get("limit", "100"))

        messagesQuery = Message.objects.filter(sendTime__gte=afterDatetime).order_by(
            "sendTime"
        )
        messagesQuery = messagesQuery.prefetch_related("conversation")

        token = request.headers.get("Authorization")
        payload = check_jwt_token(token)

        # 验证 token
        if payload is None or payload["userId"] != userId:
            return request_failed(-3, "JWT 验证失败", 401)

        # 验证 conversationId 和 userId 的合法性
        if userId:
            try:
                user = User.objects.get(userId=userId)
                messagesQuery = messagesQuery.filter(receivers=user)
            except User.DoesNotExist:
                return JsonResponse({"messages": [], "hasNext": False}, status=200)
        elif conversationId:
            try:
                conversation = Conversation.objects.get(id=conversationId)
                messagesQuery = messagesQuery.filter(conversation=conversation)
            except Conversation.DoesNotExist:
                return JsonResponse({"messages": [], "hasNext": False}, status=200)
        else:
            return request_failed(-2, "用户或会话不存在", 400)

        messages = list(messagesQuery[: limit + 1])
        messagesData = [message.serilize() for message in messages]

        # 检查是否还有更多消息
        hasNext = False
        if len(messagesData) > limit:
            hasNext = True
            messagesData = messagesData[:limit]
        return request_success({"messages": messagesData, "hasNext": hasNext})


@require_http_methods(["POST", "GET"])
def conversations(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        body = json.loads(request.body.decode("utf-8"))
        userId = require(body, "userId", "int",
                            err_msg="Missing or error type of [userId]")
        conversationType = require(body, "type", "string",
                            err_msg="Missing or error type of [type]")
        memberIds = body.get("members", [])

        token = request.headers.get("Authorization")
        payload = check_jwt_token(token)

        # 验证 token
        if payload is None or payload["userId"] != userId:
            return request_failed(-3, "JWT 验证失败", 401)

        # 检查用户名是否合法
        members = []
        for id in memberIds:
            try:
                user = User.objects.get(userId=id, isDeleted=False)
                members.append(user)
            except User.DoesNotExist:
                return request_failed(-2, "用户不存在", 400)

        if not members:
            return request_failed(-2, "至少需要两个用户参与聊天", 400)

        if conversationType == "private_chat":
            if len(members) != 2:
                return request_failed(-2, "私人聊天只能由两个用户参与", 400)

            try:
                Friendship.objects.get(
                    userId=members[0].userId, friendId=members[1].userId, status=True
                )
            except Friendship.DoesNotExist:
                return request_failed(-2, "用户不在好友列表中", 400)

            # 检查是否已存在私人聊天
            existingConversations = (
                Conversation.objects.filter(members__in=members, type="private_chat")
                .prefetch_related("members")
                .distinct()
            )
            for conv in existingConversations:
                if conv.members.count() == 2 and set(conv.members.all()) == set(
                    members
                ):
                    # 找到了一个已存在的私人聊天，直接返回
                    return request_success(conv.serilize())

        conversation = Conversation.objects.create(type=conversationType)
        conversation.members.set(members)
        return request_success(conversation.serilize())

    elif request.method == "GET":
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
        response_data = [conv.serilize() for conv in validConversations]
        return request_success({"conversations": response_data})
