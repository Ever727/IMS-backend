import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    # 当客户端尝试建立 WebSocket 连接时调用
    async def connect(self) -> None:
        # 从查询字符串中提取用户名
        self.userId: str = self.scope['query_string'].decode('utf-8').split('=')[1]

        # 将当前 WebSocket 连接添加到一个全体用户组中
        # 这样可以确保发给这个组的所有消息都会被转发给目前连接的所有客户端
        await self.channel_layer.group_add(self.userId, self.channel_name)

        # 接受 WebSocket 连接
        await self.accept()

    # 当 WebSocket 连接关闭时调用
    async def disconnect(self, close_code: int) -> None:
        # 将当前 WebSocket 从其所在的组中移除
        await self.channel_layer.group_discard(self.userId, self.channel_name)

    # 向指定用户组发送 notification
    async def notify(self, event) -> None:
        await self.send(text_data=json.dumps({'type': 'notify'}))