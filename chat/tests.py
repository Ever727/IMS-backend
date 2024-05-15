from django.test import TestCase
from django.contrib.auth.hashers import make_password
from account.models import User
from chat.models import Conversation, Message, Notification, Invitation
# Create your tests here.

class ChatTest(TestCase):
    def setUp(self) -> None:
        self.data1 = {
            "userId":"alice",
            "userName": "alice",
            "password": "123456",
        }
        self.data2 = {
            "userId":"bob",
            "userName": "bob",
            "password": "123456",
        }
        self.data3 = {
            "userId": "carol",
            "userName": "carol",
            "password": "123456",
        }
        self.data4 = {
            "userId": "dave",
            "userName": "dave",
            "password": "123456",
        }
        self.content_type = 'application/json'
        self.registerUrl = '/register/'
        self.loginUrl = '/login/'
        for data in [self.data1, self.data2, self.data3]:
            register_data = data.copy()
            register_data['password'] = make_password('123456')
            User.objects.create(**register_data)

    def login_for_test(self,data):
        response = self.client.post(self.loginUrl, data=data, content_type=self.content_type)
        token = response.json()['token']
        return token
    
    def create_friendship_for_test(self, data1, data2):
        token1 = self.login_for_test(data1)
        token2 = self.login_for_test(data2)
        add_data = {
            "userId": data1['userId'],
            "searchId": data2['userId'],
            "message": "Hello, I'm Alice"
        }
        accept_data = {
            "receiverId": data2['userId'],
            "senderId": data1['userId'],
        }
        self.client.post('/friends/add_friend/',data=add_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.client.post('/friends/accept_friend/', data=accept_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        return token1, token2
    
    def create_group_for_test(self):
        token1 = self.login_for_test(self.data1)
        group_data = {
            "userId": self.data1['userId'],
            "memberIds": [self.data2['userId'], self.data3['userId']],
        }
        self.client.post('/chat/conversations/', data=group_data, HTTP_AUTHORIZATION=token1, content_type='application/json')

    def set_admin_for_test(self, data, token1):
        admin_data={
            "hostId": self.data1['userId'],
            "groupId": 1,
            "adminId": data['userId']
        }
        self.client.post('/chat/set_admin/', data=admin_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
    
    def create_new_user_for_test(self):
        register_data = self.data4.copy()
        register_data['password'] = make_password('123456')
        User.objects.create(**register_data)


    def test_create_private_conversation(self):
        self.create_friendship_for_test(self.data1, self.data2)
        self.assertEqual(Conversation.objects.count(), 1)
        conversation = Conversation.objects.get(id=1)
        memberIds = list(conversation.members.all().values_list('userId', flat=True))
        self.assertEqual(conversation.members.count(), 2)
        self.assertEqual(conversation.type, "private_chat")
        self.assertEqual(memberIds, [self.data1['userId'], self.data2['userId']])

    def test_disable_private_conversation(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        delete_data = {
            "userId": self.data1['userId'],
            "friendId": self.data2['userId']
        }
        self.client.post('/friends/delete_friend/', data=delete_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        conversation = Conversation.objects.get(id=1)
        self.assertFalse(conversation.status)

    def test_get_conversation_ids(self):
        
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        token1, token3 = self.create_friendship_for_test(self.data1, self.data3)
       
        response = self.client.get(f'/chat/get_conversation_ids/?userId={self.data1["userId"]}', HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['conversationIds'], [1,2])

    def test_get_conversations(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        self.create_friendship_for_test(self.data1, self.data3)

        response = self.client.get(f'/chat/conversations/?userId={self.data1["userId"]}&id=1&id=2', HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['conversations']), 2)
 
    def test_send_message(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Conversation.objects.count(), 1)

        conversation_id = 1
        message_data = {
            "userId": self.data1['userId'],
            "conversationId": conversation_id,
            "content": "Hello, I'm Alice"
        }
        response = self.client.post('/chat/messages/', data=message_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(response.json()['content'], message_data['content'])
        self.assertEqual(response.json()['senderId'], message_data['userId'])
        self.assertEqual(response.json()['conversation'], message_data['conversationId'])

    def test_send_message_invalid_conversation(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        delete_data = {
            "userId": self.data1['userId'],
            "friendId": self.data2['userId']
        }
        self.client.post('/friends/delete_friend/', data=delete_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        conversation_id = 1
        message_data = {
            "userId": self.data1['userId'],
            "conversationId": conversation_id,
            "content": "send a message to a deleted conversation"
        }
        response = self.client.post('/chat/messages/', data=message_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['info'], '会话已失效')
        self.assertEqual(response.json()['code'], -2)

    def test_get_messages(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Conversation.objects.count(), 1)

        conversation_id = 1
        message_data = {
            "userId": self.data1['userId'],
            "conversationId": conversation_id,
            "content": "Hello, I'm Alice"
        }
        for i in range(10):
            message_data['content'] = f"Hello, I'm Alice {i}"
            self.client.post('/chat/messages/', data=message_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        response = self.client.get(f'/chat/messages/?userId={self.data1["userId"]}&conversationId={conversation_id}', HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['messages']), 11)
        self.assertFalse(response.json()['hasNext'])
        for index, message in enumerate(response.json()['messages']):
            if index == 0:
                self.assertEqual(message['senderId'], self.data2['userId'])
            else:    
                self.assertEqual(message['senderId'], self.data1['userId'])
            self.assertEqual(message['conversation'], conversation_id)
            self.assertEqual(message['replyId'], None)
            self.assertEqual(message['readList'], [])
            self.assertEqual(message['replyCount'],0)

    def test_reply_message(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        conversation_id = 1
        reply_id = 1
        message_data = {
            "userId": self.data1['userId'],
            "conversationId": conversation_id,
            "content": "reply message",
            "replyId": reply_id
        }
        response = self.client.post('/chat/messages/', data=message_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(response.json()['content'], message_data['content'])
        self.assertEqual(response.json()['senderId'], message_data['userId'])
        self.assertEqual(response.json()['conversation'], message_data['conversationId'])
        self.assertEqual(response.json()['replyId'], message_data['replyId'])
        self.assertEqual( Message.objects.filter(replyTo__id=reply_id).count(), 1)
        new_message = Message.objects.get(id=2)
        self.assertEqual(new_message.replyTo.id, reply_id)
        self.assertNotEqual(new_message.sendTime, new_message.updateTime)

    def test_reply_message_not_exist(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        conversation_id = 1
        reply_id = 100
        message_data = {
            "userId": self.data1['userId'],
            "conversationId": conversation_id,
            "content": "reply message",
            "replyId": reply_id
        }
        response = self.client.post('/chat/messages/', data=message_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['info'], '原消息不存在')
        self.assertEqual(response.json()['code'], -2)
      
    def test_reply_message_multi_times(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        conversation_id = 1
        reply_id = 1
        message_data = {
            "userId": self.data1['userId'],
            "conversationId": conversation_id,
            "content": "reply message 1",
            "replyId": reply_id
        }
        for _ in range(10):
            message_data['content'] = "reply message"
            self.client.post('/chat/messages/', data=message_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual( Message.objects.filter(replyTo__id=reply_id).count(), 10)

    def test_read_message(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Conversation.objects.count(), 1)

        conversation_id = 1
        message_data = {
            "userId": self.data2['userId'],
            "conversationId": conversation_id,
            "content": "Hello, I'm Alice"
        }
        for i in range(10):
            message_data['content'] = f"Hello, I'm Alice {i}"
            response = self.client.post('/chat/messages/', data=message_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['readList'], [])

        read_data = {
            "userId": self.data1['userId'],
            "conversationId": conversation_id,
        }

        response = self.client.post('/chat/read_message/', data=read_data, HTTP_AUTHORIZATION=token1, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        
        for i in range(1,11):
            message = Message.objects.get(id=i)
            read_list = message.readUsers.all().values_list('userId', flat=True)
            self.assertEqual(len(read_list), 1)
            self.assertEqual(read_list[0], self.data1['userId'])
            self.assertNotEqual(message.sendTime, message.updateTime)
                 
    def test_delete_message(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        delete_data = {
            "userId": self.data1['userId'],
            "messageId": 1, 
        }
        response = self.client.post('/chat/delete_message/', data=delete_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        response = self.client.get(f'/chat/messages/?userId={self.data1["userId"]}&conversationId=1', HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['messages']), 0)
        message = Message.objects.get(id=1)
        self.assertTrue(message.deleteUsers.filter(userId=self.data1['userId']).exists())
        self.assertFalse(message.deleteUsers.filter(userId=self.data2['userId']).exists())
        response = self.client.get(f'/chat/messages/?userId={self.data2["userId"]}&conversationId=1', HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['messages']), 1)
        
    def test_get_unread_count(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Conversation.objects.count(), 1)

        conversation_id = 1
        message_data = {
            "userId": self.data2['userId'],
            "conversationId": conversation_id,
            "content": "Hello, I'm Alice"
        }
        for i in range(10):
            message_data['content'] = f"Hello, I'm Alice {i}"
            self.client.post('/chat/messages/', data=message_data, HTTP_AUTHORIZATION=token2, content_type='application/json')

        response = self.client.get(f'/chat/get_unread_count/?userId={self.data1["userId"]}&conversationId={conversation_id}', HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 11)

    
    def test_create_group_conversation(self):
        token1 = self.login_for_test(self.data1)
        group_data = {
            "userId": self.data1['userId'],
            "memberIds": [self.data2['userId'], self.data3['userId']],
        }
        response = self.client.post('/chat/conversations/', data=group_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Conversation.objects.count(), 1)
        conversation = Conversation.objects.get(id=1)
        self.assertEqual(conversation.members.count(), 3)
        self.assertEqual(conversation.type, "group_chat")
        self.assertEqual(list(conversation.members.all().values_list('userId', flat=True)), [self.data1['userId'], self.data2['userId'], self.data3['userId']])
        self.assertEqual(conversation.host.userId, self.data1['userId'])
        self.assertEqual(conversation.groupNotificationList.count(), 0)
  
    def test_create_group_conversation_invalid_member(self):
        token1 = self.login_for_test(self.data1)
        group_data = {
            "userId": self.data1['userId'],
            "memberIds": [self.data1['userId'], self.data2['userId'], 1000],
        }
        response = self.client.post('/chat/conversations/', data=group_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['info'], '用户不存在')
        self.assertEqual(response.json()['code'], -2)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_create_group_conversation_no_member(self):
        token1 = self.login_for_test(self.data1)
        group_data = {
            "userId": self.data1['userId'],
            "memberIds": [],
        }
        response = self.client.post('/chat/conversations/', data=group_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['info'], '群聊人数过少')
        self.assertEqual(response.json()['code'], -2)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_upload_notification_by_host(self):
        token1 = self.login_for_test(self.data1)
        self.create_group_for_test()
        notification_data = {
            "userId": self.data1['userId'],
            "groupId": 1,
            "content": "This is a test notification"
        }
        response = self.client.post('/chat/upload_notification/', data=notification_data, HTTP_AUTHORIZATION=token1, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Conversation.objects.get(id=1).groupNotificationList.count(), 1)
        self.assertEqual(Notification.objects.get(id=1).content, "This is a test notification")
        self.assertEqual(Notification.objects.get(id=1).userId, self.data1['userId'])
        self.assertEqual(Notification.objects.get(id=1).conversation.id, 1)

    def test_upload_notification_invalid_user(self):
        token2 = self.login_for_test(self.data2)
        self.create_group_for_test()

        notification_data = {
            "userId": self.data2['userId'],
            "groupId": 1,
            "content": "This is a test notification"
        }
        response = self.client.post('/chat/upload_notification/', data=notification_data, HTTP_AUTHORIZATION=token2, content_type='application/json')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '权限不足')
        self.assertEqual(response.json()['code'], -4)
        self.assertEqual(Conversation.objects.get(id=1).groupNotificationList.count(), 0)

    def test_set_host_valid(self):
        token1 = self.login_for_test(self.data1)
        self.create_group_for_test()

        set_host_data = {
            "oldHostId": self.data1['userId'],
            "groupId": 1,
            "newHostId": self.data2['userId']

        }
        response = self.client.post('/chat/set_host/', data=set_host_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Conversation.objects.get(id=1).host.userId, self.data2['userId'])

    def test_set_host_invalid_JWT(self):
        token2 = self.login_for_test(self.data2)
        self.create_group_for_test()

        set_host_data = {
            "oldHostId": self.data1['userId'],
            "groupId": 1,
            "newHostId": self.data2['userId']

        } 
        response = self.client.post('/chat/set_host/', data=set_host_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['info'], 'JWT 验证失败')
        self.assertEqual(response.json()['code'], -3)
        self.assertEqual(Conversation.objects.get(id=1).host.userId, self.data1['userId'])

    def test_set_host_invalid_host(self):
        token2 = self.login_for_test(self.data2)
        self.create_group_for_test()

        set_host_data = {
            "oldHostId": self.data2['userId'],
            "groupId": 1,
            "newHostId": self.data1['userId']

        } 
        response = self.client.post('/chat/set_host/', data=set_host_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '权限不足')
        self.assertEqual(response.json()['code'], -4)
        self.assertEqual(Conversation.objects.get(id=1).host.userId, self.data1['userId'])    

    def test_set_admin(self):
        token1 = self.login_for_test(self.data1)
        self.create_group_for_test()

        admin_data={
            "hostId": self.data1['userId'],
            "groupId": 1,
            "adminId": self.data2['userId']
        }
        response = self.client.post('/chat/set_admin/', data=admin_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        admins = Conversation.objects.get(id=1).admins
        self.assertEqual(admins.count(), 1)

    def test_set_admin_by_others(self):
        token2 = self.login_for_test(self.data2)
        self.create_group_for_test()

        admin_data={
            "hostId": self.data2['userId'],
            "groupId": 1,
            "adminId": self.data2['userId']
        }
        response = self.client.post('/chat/set_admin/', data=admin_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '权限不足')
        self.assertEqual(response.json()['code'], -4)

    def test_set_admin_twice(self):
        token1 = self.login_for_test(self.data1)
        self.create_group_for_test()

        admin_data={
            "hostId": self.data1['userId'],
            "groupId": 1,
            "adminId": self.data2['userId']
        }
        self.client.post('/chat/set_admin/', data=admin_data, HTTP_AUTHORIZATION=token1, content_type='application/json')     
        response = self.client.post('/chat/set_admin/', data=admin_data, HTTP_AUTHORIZATION=token1, content_type='application/json')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '权限已存在')
        self.assertEqual(response.json()['code'], -4)

    def test_remove_amin(self):
        token1 = self.login_for_test(self.data1)
        self.create_group_for_test()

        admin_data={
            "hostId": self.data1['userId'],
            "groupId": 1,
            "adminId": self.data2['userId']
        }
        self.client.post('/chat/set_admin/', data=admin_data, HTTP_AUTHORIZATION=token1, content_type='application/json') 

        admin_data={
            'hostId':self.data1['userId'],
            'groupId':1,
            'adminId':self.data2['userId']
        }
        response = self.client.post('/chat/remove_admin/', data=admin_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        admins = Conversation.objects.get(id=1).admins
        self.assertEqual(admins.count(), 0)

    def test_remove_admin_unexistant(self):
        token1 = self.login_for_test(self.data1)
        self.create_group_for_test()
        
        admin_data={
            'hostId':self.data1['userId'],
            'groupId':1,
            'adminId':self.data2['userId']
        }
        response = self.client.post('/chat/remove_admin/', data=admin_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '权限不存在')
        self.assertEqual(response.json()['code'], -4)

    def test_kick_member(self):
        #群主踢人
        token1 = self.login_for_test(self.data1)
        self.create_group_for_test()

        kick_data={
            'opId':self.data1['userId'],
            'groupId':1,
            'memberId':self.data2['userId']
        }
        response = self.client.post('/chat/kick_member/', data=kick_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        members = Conversation.objects.get(id=1).members
        self.assertEqual(members.count(), 2)
        self.assertFalse(members.filter(userId=self.data2['userId']).exists())

    def test_kick_member_by_others(self):
        # 非管理员踢人
        token1 = self.login_for_test(self.data1)
        token2 = self.login_for_test(self.data2)
        self.create_group_for_test()

        kick_data={
            'opId':self.data2['userId'],
            'groupId':1,
            'memberId':self.data3['userId']
        }
        response = self.client.post('/chat/kick_member/', data=kick_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '权限不足')
        self.assertEqual(response.json()['code'], -4)

        # 管理员踢群主
        self.set_admin_for_test(self.data2, token1)
        kick_data['memberId']=self.data1['userId']
        response = self.client.post('/chat/kick_member/', data=kick_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '权限不足')
        self.assertEqual(response.json()['code'], -4)

        # 管理员踢自己或其他管理员
        kick_data['memberId']=self.data2['userId']
        response = self.client.post('/chat/kick_member/', data=kick_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '权限不足')
        self.assertEqual(response.json()['code'], -4)

    def test_exit_from_group(self):
        # 管理员成功退出
        token1 = self.login_for_test(self.data1)
        token2 = self.login_for_test(self.data2)
        self.create_group_for_test()
        self.set_admin_for_test(self.data2, token1)
        exit_data={
            'userId':self.data2['userId'],
            'groupId':1
        }
        response = self.client.post('/chat/exit_group/', data=exit_data, HTTP_AUTHORIZATION=token2, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        members = Conversation.objects.get(id=1).members
        admins = Conversation.objects.get(id=1).admins
        self.assertEqual(admins.count(), 0)
        self.assertEqual(members.count(), 2)
        self.assertFalse(members.filter(userId=self.data2['userId']).exists())

    def test_exit_from_group_invalid(self):
        token1 = self.login_for_test(self.data1)
        token2 = self.login_for_test(self.data2)
        self.create_group_for_test()

        # 群不存在
        exit_data={
            'userId':self.data2['userId'],
            'groupId':2
        }
        response = self.client.post('/chat/exit_group/', data=exit_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['info'], '群聊不存在')
        self.assertEqual(response.json()['code'], -2)

        # 群主试图退出
        exit_data={
            'userId':self.data1['userId'],
            'groupId':1
        }
        response = self.client.post('/chat/exit_group/', data=exit_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '群主不能退群')
        self.assertEqual(response.json()['code'], -4)

        # 非群成员试图退出
        exit_data={
            'userId':self.data2['userId'],
            'groupId':1
        }
        self.client.post('/chat/exit_group/', data=exit_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        response = self.client.post('/chat/exit_group/', data=exit_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '权限不足')
        self.assertEqual(response.json()['code'], -4)

    def test_invite_user_by_host(self):
        # 群主或管理员拉人
        token1 = self.login_for_test(self.data1)
        self.create_new_user_for_test()
        self.create_group_for_test()

        invite_data={
            'opId':self.data1['userId'],
            'groupId':1,
            'memberIds':[self.data4['userId']]
        }
        response = self.client.post('/chat/invite_member/', data=invite_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        members = Conversation.objects.get(id=1).members
        self.assertEqual(members.count(), 4)
        self.assertTrue(members.filter(userId=self.data4['userId']).exists())

    def test_invite_user_by_others(self):
        # 普通成员拉人
        token3 = self.login_for_test(self.data3)
        self.create_group_for_test()
        self.create_new_user_for_test()

        invite_data={
            'opId':self.data3['userId'],
            'groupId':1,
            'memberIds':[self.data4['userId']]
        }
        response = self.client.post('/chat/invite_member/', data=invite_data, HTTP_AUTHORIZATION=token3, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Invitation.objects.filter(conversation__id=1).count(), 1)
        invitation = Invitation.objects.get(conversation__id=1)
        self.assertEqual(invitation.sender.userId, self.data3['userId'])
        self.assertEqual(invitation.receiver.userId, self.data4['userId'])

    def test_invite_members(self):
        token1 = self.login_for_test(self.data1)
        self.create_new_user_for_test()
        self.create_group_for_test()

        # 再次邀请在群里的群成员    
        invite_data={
            'opId':self.data1['userId'],
            'groupId':1,
            'memberIds':[self.data2['userId'], self.data4['userId']]
        }
        response = self.client.post('/chat/invite_member/', data=invite_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '成员已在群里')

        # 邀请不存在的成员
        invite_data={
            'opId':self.data1['userId'],
            'groupId':1,
            'memberIds':['12345678901234']
        }
        response = self.client.post('/chat/invite_member/', data=invite_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['info'], '邀请对象账户不存在')
        self.assertEqual(response.json()['code'], -2)

        #邀请加入不存在的群
        invite_data={
            'opId':self.data1['userId'],
            'groupId':2,
            'memberIds':[self.data2['userId']]
        }   
        response = self.client.post('/chat/invite_member/', data=invite_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['info'], '群聊不存在')
        self.assertEqual(response.json()['code'], -2)

    def test_empty_group_requests(self):
        token1 = self.login_for_test(self.data1)
        self.create_new_user_for_test()
        self.create_group_for_test()

        # 得到空列表
        response = self.client.get(f'/chat/group_requests/{self.data1["userId"]}/',HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data'], [])

    def test_group_requests(self):
        token1 = self.login_for_test(self.data1)
        token2 = self.login_for_test(self.data2)
        self.create_new_user_for_test()
        self.create_group_for_test()
       
        invite_data={
            'opId':self.data2['userId'],    
            'groupId':1,
            'memberIds':[self.data4['userId']]
        }
        self.client.post('/chat/invite_member/', data=invite_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.set_admin_for_test(self.data2, token1)
        self.set_admin_for_test(self.data3, token1)    
        # 得到邀请列表
        for data in [self.data1, self.data2, self.data3]:
            token = self.login_for_test(data)
            userId = data['userId']    
            response = self.client.get(f'/chat/group_requests/{userId}/',HTTP_AUTHORIZATION=token, content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()['data']), 1)
            self.assertEqual(response.json()['data'][0]['senderId'], self.data2['userId'])
            self.assertEqual(response.json()['data'][0]['receiverId'], self.data4['userId'])

        token4 = self.login_for_test(self.data4)
        response = self.client.get(f'/chat/group_requests/{self.data4["userId"]}/',HTTP_AUTHORIZATION=token4, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['data']), 0)

    def test_update_group(self):
        
        # 群主更新
        token1 = self.login_for_test(self.data1)
        self.create_group_for_test()
        update_data={
            'userId':self.data1['userId'],
            'groupId':1,
            'newName':'new_group_name1',
        }

        response = self.client.post('/chat/update_group/', data=update_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        group = Conversation.objects.get(id=1)
        self.assertEqual(group.groupName, 'new_group_name1')

        # 无权限更新
        token2 = self.login_for_test(self.data2)
        update_data['userId'] = self.data2['userId']
        response = self.client.post('/chat/update_group/', data=update_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '权限不足')
        self.assertEqual(response.json()['code'], -4)

        # 管理员更新
        self.set_admin_for_test(self.data2, token1)
        update_data['newName'] = 'new_group_name2'
        response = self.client.post('/chat/update_group/', data=update_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        group = Conversation.objects.get(id=1)
        self.assertEqual(group.groupName, 'new_group_name2')

        # 更新字段为空
        update_data['newName'] = ''
        response = self.client.post('/chat/update_group/', data=update_data, HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['info'], '群聊名称不能为空')
        self.assertEqual(response.json()['code'], -4)