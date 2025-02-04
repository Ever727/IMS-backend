from django.test import TestCase
from account.models import User
from django.contrib.auth.hashers import make_password
from friendship.models import Friendship,FriendshipRequest
from chat.models import Conversation
from django.db.models import Count

# Create your tests here.
class FriendshipTestCase(TestCase):

    def setUp(self):
        self.data1 = {"userName": "user1", "userId":"user1", "password": "123456"}
        self.data2 = {'userName': "user2", "userId":"user2", "password": '123456'}
        data1 = self.data1.copy()
        data1["password"] = make_password(data1["password"])
        data2 = self.data2.copy()
        data2["password"] = make_password(data2["password"])
        self.user1 = User.objects.create(**data1)
        self.user2 = User.objects.create(**data2)

    def login_for_test(self, data):
        response = self.client.post('/login/', data=data, content_type='application/json')
        token = response.json()['token']
        return token
    
    def add_friend_for_test(self, token,data):
        response = self.client.post('/friends/add_friend/',data=data, HTTP_AUTHORIZATION=token,content_type='application/json')
        return response
    
    def accept_friend_for_test(self, token,data):
        response = self.client.post('/friends/accept_friend/',data=data, HTTP_AUTHORIZATION=token,content_type='application/json')
        return response


    def test_send_friend_request(self): 

        token = self.login_for_test(self.data1)
        data = {
            "userId": self.data1["userId"],
            "searchId":self.data2["userId"],
            "message": "hello world"
            }
        response = self.client.post('/friends/add_friend/',data=data, HTTP_AUTHORIZATION=token,content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], '成功发送请求')
        self.assertTrue(FriendshipRequest.objects.filter(senderId=self.data1["userId"], receiverId=self.data2["userId"]).exists()) 
        friendshipRequest = FriendshipRequest.objects.get(senderId=self.data1["userId"], receiverId=self.data2["userId"])
        self.assertEqual(friendshipRequest.message, 'hello world')
        self.assertFalse(Friendship.objects.filter(userId=self.data1["userId"], friendId=self.data2["userId"]).exists())
        self.assertFalse(Friendship.objects.filter(userId=self.data2["userId"], friendId=self.data1["userId"]).exists())

    def test_add_nonexistent_user(self):

        token = self.login_for_test(self.data1)
        data = {
            "userId": self.data1["userId"],
            "searchId":"bob",
            "message": "hello world"
            }
        response = self.add_friend_for_test(token,data)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['code'], -1)
        self.assertFalse(FriendshipRequest.objects.filter(senderId=self.data1["userId"], receiverId="bob").exists())
        self.assertFalse(Friendship.objects.filter(userId=self.data1["userId"], friendId="bob").exists())
        self.assertFalse(Friendship.objects.filter(userId="bob", friendId=self.data1["userId"]).exists())

    def test_add_myself(self):

        token = self.login_for_test(self.data1)
        data = {
            "userId": self.data1["userId"],
            "searchId":self.data1["userId"],
            "message": "hello world"
            }
        response = self.add_friend_for_test(token,data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], -4)
        self.assertFalse(FriendshipRequest.objects.filter(senderId=self.data1["userId"], receiverId=self.data1["userId"]).exists())
        self.assertFalse(Friendship.objects.filter(userId=self.data1["userId"], friendId=self.data1["userId"]).exists())
        self.assertFalse(Friendship.objects.filter(userId=self.data1["userId"], friendId=self.data1["userId"]).exists())

    def test_add_friend_frenquently(self):

        token = self.login_for_test(self.data1)
        data = {
            "userId": self.data1["userId"],
            "searchId":self.data2["userId"],
            "message": "hello world"
            }
        self.add_friend_for_test(token,data)
        response = self.add_friend_for_test(token,data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], -4)
        self.assertEqual(response.json()['info'], '发送申请过于频繁')
        self.assertTrue(FriendshipRequest.objects.filter(senderId=self.data1["userId"], receiverId=self.data2["userId"]).exists())
        self.assertFalse(Friendship.objects.filter(userId=self.data1["userId"], friendId=self.data1["userId"]).exists())
        self.assertFalse(Friendship.objects.filter(userId=self.data1["userId"], friendId=self.data1["userId"]).exists())

    def test_accept_friend_request(self):

        token = self.login_for_test(self.data1)
        data = {
            "userId": self.data1["userId"],
            "searchId":self.data2["userId"],
            "message": "hello world"
            }
        self.add_friend_for_test(token,data)
        newToken = self.login_for_test(self.data2)
        accept_data = {
            "senderId": self.data1["userId"],
            "receiverId": self.data2["userId"],
        }
        response = self.accept_friend_for_test(newToken,accept_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(response.json()['message'], '接受成功')
        friendshipRequest = FriendshipRequest.objects.get(senderId=self.data1["userId"], receiverId=self.data2["userId"])
        self.assertEqual(friendshipRequest.status, True)
        self.assertTrue(Friendship.objects.filter(userId=self.data1["userId"], friendId=self.data2["userId"]).exists())
        self.assertTrue(Friendship.objects.filter(userId=self.data2["userId"], friendId=self.data1["userId"]).exists())
        members = [self.user1, self.user2]
        conversation = Conversation.objects.filter( type='private_chat', members__in=members,status=True 
            ).annotate(num_members=Count('members')).filter(num_members=2).first()
        self.assertIsNotNone(conversation)
    
    def test_delete_friend(self):
        # add friend
        token = self.login_for_test(self.data1)

        add_data = {
            "userId": self.data1["userId"],
            "searchId":self.data2["userId"],
            "message": "hello world"
            }
        self.add_friend_for_test(token,add_data)
        # accept friend
        newToken = self.login_for_test(self.data2)
        accept_data = {
            "senderId": self.data1["userId"],
            "receiverId": self.data2["userId"],
        }
        self.accept_friend_for_test(newToken,accept_data)
        # delete friend
        delete_data = {
            "userId": self.data2["userId"],
            "friendId": self.data1["userId"],
        }
        response = self.client.post('/friends/delete_friend/',data=delete_data, HTTP_AUTHORIZATION=newToken,content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(response.json()['message'], '删除成功')
        friendship = Friendship.objects.get(userId=self.data1["userId"], friendId=self.data2["userId"])
        self.assertFalse(friendship.status)
        friendship = Friendship.objects.get(userId=self.data2["userId"], friendId=self.data1["userId"])
        self.assertFalse(friendship.status)
        members = [self.user1, self.user2]
        conversation = Conversation.objects.filter( type='private_chat', members__in=members,status=False 
            ).annotate(num_members=Count('members')).filter(num_members=2).first()
        self.assertIsNotNone(conversation)
        

    def test_get_empty_friends_list(self):
        token = self.login_for_test(self.data1)

        response = self.client.get(f'/friends/myfriends/{self.data1["userId"]}/', HTTP_AUTHORIZATION=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data'], [])

    def test_get_empty_requests_list(self):
        token = self.login_for_test(self.data1)
        response = self.client.get(f'/friends/myrequests/{self.data1["userId"]}/', HTTP_AUTHORIZATION=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data'], [])

    def test_get_friends_list(self):
        newData ={
            "userName": "user3", "userId":"user3", "password": "123456"
        }
        self.client.post("/register/", data=newData, content_type='application/json')

        token1 = self.login_for_test(self.data1)
        data = {
            "userId": self.data1["userId"],
            "searchId":newData["userId"],
            "message": "hello friend"
            }
        self.add_friend_for_test(token1, data)
        
        token2 = self.login_for_test(self.data2)
        data = {
            "userId": self.data2["userId"],
            "searchId":newData["userId"],
            "message": "hello friend"
            }
        self.add_friend_for_test(token2, data)

        token = self.login_for_test(newData)
        self.accept_friend_for_test(token,{"senderId": self.data1["userId"], "receiverId": newData["userId"]})
        self.accept_friend_for_test(token,{"senderId": self.data2["userId"], "receiverId": newData["userId"]})
        response = self.client.get(f'/friends/myfriends/{newData["userId"]}/', HTTP_AUTHORIZATION=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['data']), 2)
        self.assertEqual(response.json()['data'][0]['userId'], self.data1["userId"])
        self.assertEqual(response.json()['data'][0]['userName'], self.data1["userName"])
        self.assertEqual(response.json()['data'][1]['userId'], self.data2["userId"])
        self.assertEqual(response.json()['data'][1]['userName'],self.data2["userName"])
   
    def test_get_requests_list(self):
        newData ={
            "userName": "user3", "userId":"user3", "password": "123456"
        }
        self.client.post("/register/", data=newData, content_type='application/json')
        token1 = self.login_for_test(self.data1)
        data = {
            "userId": self.data1["userId"],
            "searchId":newData["userId"],
            "message": "hello react"
            }
        self.add_friend_for_test(token1,data)
        
        token2 = self.login_for_test(self.data2)
        data = {
            "userId": self.data2["userId"],
            "searchId":newData["userId"],
            "message": "hello django"
            }
        self.add_friend_for_test(token2,data)

        token = self.login_for_test(newData)
        response = self.client.get(f'/friends/myrequests/{newData["userId"]}/', HTTP_AUTHORIZATION=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['data']), 2)
        self.assertEqual(response.json()['data'][0]['id'], self.data2["userId"])
        self.assertEqual(response.json()['data'][0]['message'], 'hello django')
        self.assertEqual(response.json()['data'][1]['id'], self.data1["userId"])
        self.assertEqual(response.json()['data'][1]['message'], 'hello react')

    def test_check_friendship(self):
        data = {
            "userId": self.data1["userId"],
            "searchId":self.data2["userId"],
            "message": "hello world"
            }
        accept_data = {
            "senderId": self.data1["userId"],
            "receiverId": self.data2["userId"],
        }
        friend_data = {
            "userId": self.data1["userId"],
            "friendId": self.data2["userId"],
        }

        token = self.login_for_test(self.data1)    
        self.add_friend_for_test(token,data)
        newToken = self.login_for_test(self.data2)
        self.accept_friend_for_test(newToken,accept_data)
        
        response = self.client.post('/friends/check_friendship/',data=friend_data, HTTP_AUTHORIZATION=token,content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertFalse(response.json()['deleteStatus'])
        self.assertTrue(response.json()['friendshipStatus'])

        self.client.post('/friends/delete_friend/',data=friend_data, HTTP_AUTHORIZATION=token,content_type='application/json')
        self.client.post('/delete/',data=self.data2, HTTP_AUTHORIZATION=newToken,content_type='application/json')

        response = self.client.post('/friends/check_friendship/',data=friend_data, HTTP_AUTHORIZATION=token,content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertTrue(response.json()['deleteStatus'])
        self.assertFalse(response.json()['friendshipStatus'])
        
    def test_add_tag(self):
        token = self.login_for_test(self.data1)
        add_data = {
            "userId": self.data1["userId"],
            "searchId":self.data2["userId"],
            "message": "hello world"
            }
        self.add_friend_for_test(token,add_data)
        newToken = self.login_for_test(self.data2)
        accept_data = {
            "senderId": self.data1["userId"],
            "receiverId": self.data2["userId"],
        }
        self.accept_friend_for_test(newToken,accept_data)
        tag_data = {
            "userId": self.data1["userId"],
            "friendId": self.data2["userId"],
            "tag": "Hola"
        }
        response = self.client.post('/friends/add_tag/',data=tag_data, HTTP_AUTHORIZATION=token,content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(response.json()['message'], 'tag添加成功')
        friendship = Friendship.objects.get(userId=self.data1["userId"], friendId=self.data2["userId"])
        self.assertEqual(friendship.tag, 'Hola')

        tag_data = {
            "userId": self.data2["userId"],
            "friendId": self.data1["userId"],
            "tag": "Adiós"
        }
        response = self.client.post('/friends/add_tag/',data=tag_data, HTTP_AUTHORIZATION=newToken,content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(response.json()['message'], 'tag添加成功')
        friendship = Friendship.objects.get(userId=self.data2["userId"], friendId=self.data1["userId"])
        self.assertEqual(friendship.tag, 'Adiós')