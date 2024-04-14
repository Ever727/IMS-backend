from django.test import TestCase
from django.contrib.auth.hashers import make_password
from account.models import User
from chat.models import Conversation, Message
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
    

    def test_create_private_conversation(self):
        token1, token2 = self.create_friendship_for_test(self.data1, self.data2)
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
        response = self.client.get(f'/chat/get_conversation_ids/?userId={self.data1["userId"]}', HTTP_AUTHORIZATION=token1, content_type='application/json')

        conversation_ids = response.json()['conversationIds']
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
        for message in response.json()['messages']:
            self.assertEqual(message['senderId'], self.data1['userId'])
            self.assertEqual(message['conversation'], conversation_id)
            self.assertEqual(message['replyId'], None)
            self.assertEqual(message['readList'], [])
            self.assertEqual(message['deleteList'], [])
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

    def test_read_message(self):
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
            response = self.client.post('/chat/messages/', data=message_data, HTTP_AUTHORIZATION=token1, content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['readList'], [])

        read_data = {
            "userId": self.data2['userId'],
            "conversationId": conversation_id,
        }

        response = self.client.post('/chat/read_message/', data=read_data, HTTP_AUTHORIZATION=token2, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        
        for i in range(1,11):
            message = Message.objects.get(id=i)
            read_list = message.readUsers.all().values_list('userId', flat=True)
            self.assertEqual(len(read_list), 1)
            self.assertEqual(read_list[0], self.data2['userId'])
                 
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
            "userId": self.data1['userId'],
            "conversationId": conversation_id,
            "content": "Hello, I'm Alice"
        }
        for i in range(10):
            message_data['content'] = f"Hello, I'm Alice {i}"
            response = self.client.post('/chat/messages/', data=message_data, HTTP_AUTHORIZATION=token1, content_type='application/json')

        response = self.client.get(f'/chat/get_unread_count/?userId={self.data2["userId"]}&conversationId={conversation_id}', HTTP_AUTHORIZATION=token2, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 11)
