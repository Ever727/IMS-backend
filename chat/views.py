import re
import json
from datetime import datetime, timezone
from typing import Dict, Any
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from account.models import User
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Message, Conversation
from django.shortcuts import render

# Create your views here.
@require_http_methods(["POST", "GET"])
def messages(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = json.loads(request.body)
        conversationId = data.get('conversationId')
        senderUserName = data.get('username')
        content = data.get('content', '')

        # 验证 conversationId 和 senderUserName 的合法性
        try:
            conversation = Conversation.objects.prefetch_related('members').get(id=conversationId) 
        except Conversation.DoesNotExist:
            return JsonResponse({'error': 'Invalid conversation ID'}, status=400)

        try:
            sender = User.objects.get(userName=senderUserName)
        except User.DoesNotExist:
            return JsonResponse({'error': 'Invalid username'}, status=400)

        # 验证 sender 是否是 conversation 的成员
        if not conversation.members.filter(id=sender.id).exists():
            return JsonResponse({'error': 'Sender is not a member of the conversation'}, status=403)

        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content
        )

        message.receivers.set(conversation.members.all())

        channelLayer = get_channel_layer()
        for member in conversation.members.all():
            async_to_sync(channelLayer.group_send)(member.userName, {'type': 'notify'})

        return JsonResponse(format_message(message), status=200)

    elif request.method == "GET":
        userName: str = request.GET.get('userName')
        conversationId: str = request.GET.get('conversationId')
        after: str = request.GET.get('after', '0')
        afterDatetime = datetime.fromtimestamp((int(after) + 1) / 1000.0, tz=timezone.utc)
        limit: int = int(request.GET.get('limit', '100'))

        messagesQuery = Message.objects.filter(timestamp__gte=afterDatetime).order_by('timestamp')
        messagesQuery = messagesQuery.prefetch_related('conversation')

        if userName:
            try:
                user = User.objects.get(userName=userName)
                messagesQuery = messagesQuery.filter(receivers=user)
            except User.DoesNotExist:
                return JsonResponse({'messages': [], 'hasNext': False}, status=200)
        elif conversationId:
            try:
                conversation = Conversation.objects.get(id=conversationId)
                messagesQuery = messagesQuery.filter(conversation=conversation)
            except Conversation.DoesNotExist:
                return JsonResponse({'messages': [], 'hasNext': False}, status=200)
        else:
            return JsonResponse({'error': 'Either username or conversation ID must be specified'}, status=400)
        
        messages = list(messagesQuery[:limit+1])
        messagesData = [format_message(message) for message in messages]

        # 检查是否还有更多消息
        hasNext = False
        if len(messagesData) > limit:
            hasNext = True
            messagesData = messagesData[:limit]

        return JsonResponse({'messages': messagesData, 'hasNext': hasNext}, status=200)


def to_timestamp(dt: datetime) -> int:
    # 转换为毫秒级 UNIX 时间戳
    return int(dt.timestamp() * 1_000)

def format_message(message: Message) -> dict:
    return {
        'id': message.id,
        'conversation': message.conversation.id,
        'sender': message.sender.username,
        'content': message.content,
        'timestamp': to_timestamp(message.timestamp)
    }

def format_conversation(conversation: Conversation) -> dict:
    return {
        'id': conversation.id,
        'type': conversation.type,
        'members': [user.username for user in conversation.members.all()],
    }

def check_username(value: str) -> bool:
    return re.match(r'^\w+$', value) and len(value) <= 20