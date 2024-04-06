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
from django.shortcuts import render
from utils.utils_request import request_failed, request_success, BAD_METHOD
from utils.utils_require import require
from utils.utils_jwt import generate_jwt_token, check_jwt_token
from utils.utils_time import get_timestamp


def to_timestamp(dt: datetime) -> int:
    # 转换为毫秒级 UNIX 时间戳
    return int(dt.timestamp() * 1_000)


def format_message(message: Message) -> dict:
    return {
        "id": message.id,
        "conversation": message.conversation.id,
        "sender": message.sender.userName,
        "content": message.content,
        "timestamp": to_timestamp(message.timestamp),
    }


def format_conversation(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "type": conversation.type,
        "members": [user.userId for user in conversation.members.all()],
    }


def check_username(value: str) -> bool:
    return re.match(r"^\w+$", value) and len(value) <= 20


# Create your views here.
@require_http_methods(["POST", "GET"])
def messages(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = json.loads(request.body)
        conversationId = data.get("conversationId")  # 会话 ID
        userId = data.get("userId")  # 发送者 ID
        content = data.get("content", "")  # 消息内容

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
            sender = User.objects.get(userId=userId)
        except User.DoesNotExist:
            return request_failed(-2, "用户不存在", 400)

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

        return JsonResponse(format_message(message), status=200)

    elif request.method == "GET":
        userId: str = request.GET.get("userId")
        conversationId: str = request.GET.get("conversationId")
        after: str = request.GET.get("after", "0")
        afterDatetime = datetime.fromtimestamp(
            (int(after) + 1) / 1000.0, tz=timezone.utc
        )
        limit: int = int(request.GET.get("limit", "100"))

        messagesQuery = Message.objects.filter(timestamp__gte=afterDatetime).order_by(
            "timestamp"
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
        messagesData = [format_message(message) for message in messages]

        # 检查是否还有更多消息
        hasNext = False
        if len(messagesData) > limit:
            hasNext = True
            messagesData = messagesData[:limit]

        return JsonResponse({"messages": messagesData, "hasNext": hasNext}, status=200)


@require_http_methods(["POST", "GET"])
def conversations(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = json.loads(request.body)
        userId = data.get("userId")
        conversation_type = data.get("type")
        memberIds = data.get("members", [])

        token = request.headers.get("Authorization")
        payload = check_jwt_token(token)

        # 验证 token
        if payload is None or payload["userId"] != userId:
            return request_failed(-3, "JWT 验证失败", 401)

        # 检查用户名是否合法
        members = []
        for id in memberIds:
            try:
                user = User.objects.get(userId=id)
                members.append(user)
            except User.DoesNotExist:
                return request_failed(-2, "用户不存在", 400)

        if not members:
            return request_failed(-2, "至少需要两个用户参与聊天", 400)

        if conversation_type == "private_chat":
            if len(members) != 2:
                return request_failed(-2, "私人聊天只能由两个用户参与", 400)

            try:
                Friendship.objects.get(
                    userId=members[0].userId, friendId=members[1].userId
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
                    return JsonResponse(format_conversation(conv), status=200)

        conversation = Conversation.objects.create(type=conversation_type)
        conversation.members.set(members)
        return JsonResponse(format_conversation(conversation), status=200)

    elif request.method == "GET":
        userId = request.GET.get("userId")
        token = request.headers.get("Authorization")
        payload = check_jwt_token(token)

        # 验证 token
        if payload is None or payload["userId"] != userId:
            return request_failed(-3, "JWT 验证失败", 401)

        conversationIds = request.GET.getlist("id", [])
        validConversations = Conversation.objects.filter(
            id__in=conversationIds
        ).prefetch_related("members")
        response_data = [format_conversation(conv) for conv in validConversations]
        return JsonResponse({"conversations": response_data}, status=200)
