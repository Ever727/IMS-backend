from django.test import TestCase
from .models import User
from django.contrib.auth.hashers import make_password

# Create your tests here.
class AccountTests(TestCase):
    
    def setUp(self):
        self.data = {
            "userId":"Bob",
            "userName": "Bob",
            "password": "123456",
        }
        self.newData = {
            "userId":"Alice",
            "userName": "Alice",
            "password": "123456",
        }
        self.content_type = 'application/json'
        self.registerUrl = '/register/'
        self.loginUrl = '/login/'
        data = self.data.copy()
        data['password'] = make_password('123456')
        self.user = User.objects.create(**data)


    def login_for_test(self,data):
        response = self.client.post(self.loginUrl, data=data, content_type=self.content_type)
        token = response.json()['token']
        return token

    # ! Test section
    # * Tests for register view
    def test_register_bad_method(self):
        response =self.client.get(self.registerUrl , content_type=self.content_type)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()['code'], -3)
        self.assertEqual(response.json()['info'], 'Bad method')

    def test_register_new_user(self):
        
        response = self.client.post(self.registerUrl , data=self.newData, content_type=self.content_type)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)

    def  test_register_existing_user(self):
        
        response = self.client.post(self.registerUrl , data=self.data, content_type=self.content_type)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], -2)
        self.assertEqual(response.json()['info'], '用户已存在')

    # * Tests for login view
    def test_login_existing_user_correct_password(self):
        res = self.client.post(self.loginUrl, data=self.data, content_type=self.content_type)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue(res.json()['token'].count('.') == 2)

    def test_login_existing_user_wrong_password(self):
        data = self.data.copy()
        data['password'] = '12345'
        res = self.client.post(self.loginUrl, data=data, content_type=self.content_type)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], -3)
        self.assertEqual(res.json()['info'], '密码错误')

    def test_login_non_existing_user(self):
       response = self.client.post(self.loginUrl, data=self.newData, content_type=self.content_type)     
       self.assertEqual(response.status_code, 404)
       self.assertEqual(response.json()['code'], -1)

     # * Tests for logout view
    def test_logout_logined_user(self):
        token = self.login_for_test(self.data)
        res = self.client.post('/logout/', HTTP_AUTHORIZATION=token, data=self.data, content_type=self.content_type)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

    # * Tests for delete view
    def test_delete_existing_user(self):
        token = self.login_for_test(self.data)
        response = self.client.post('/delete/', HTTP_AUTHORIZATION=token, data=self.data, content_type=self.content_type)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)

    def test_login_delete_user(self):    
        token = self.login_for_test(self.data)
        self.client.post('/delete/', HTTP_AUTHORIZATION=token, data=self.data, content_type=self.content_type)
        response = self.client.post(self.loginUrl, data=self.data, content_type=self.content_type)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['code'], -1)
        self.assertEqual(response.json()['info'], 'ID错误')

    def test_register_delete_user(self):
       token = self.login_for_test(self.data)
       self.client.post('/delete/', HTTP_AUTHORIZATION=token, data=self.data, content_type=self.content_type)
       response = self.client.post(self.registerUrl, data=self.data, content_type=self.content_type)
       self.assertEqual(response.status_code, 400)
       self.assertEqual(response.json()['code'], -2)
       self.assertEqual(response.json()['info'], '用户已存在')

    # * Tests for search_user view
    def test_search_user_existing_user(self):
        self.client.post(self.registerUrl, data=self.newData, content_type=self.content_type)
        searchData = {
            "searchId":self.newData["userId"]
        }
        token = self.login_for_test(self.data)
        response = self.client.post(f'/search/{self.data["userId"]}/', HTTP_AUTHORIZATION=token, data=searchData, content_type=self.content_type)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(response.json()['id'], 'Alice')
        self.assertEqual(response.json()['name'], 'Alice')

    def test_search_user_non_existing_user(self):
        token = self.login_for_test(self.data)
        searchData = {
            "searchId":self.newData["userId"]
        }
        response = self.client.post(f'/search/{self.data["userId"]}/', HTTP_AUTHORIZATION=token, data=searchData, content_type=self.content_type)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['code'], -1)
        self.assertEqual(response.json()['info'], '用户不存在')

    def test_get_profile_existing_user(self):
        token = self.login_for_test(self.data)
        response = self.client.get(f'/profile/{self.data["userId"]}/', HTTP_AUTHORIZATION=token, content_type=self.content_type)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(response.json()['userId'], 'Bob')
        self.assertEqual(response.json()['userName'], 'Bob')

    def test_get_profile_nonexisting_user(self):    
        token = self.login_for_test(self.data)
        response = self.client.get(f'/profile/{self.newData["userId"]}/', HTTP_AUTHORIZATION=token, content_type=self.content_type)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['code'], -1)
        self.assertEqual(response.json()['info'], '用户不存在')

    def test_get_profile_deleted_user(self):
        token = self.login_for_test(self.data)
        self.client.post('/delete/', HTTP_AUTHORIZATION=token, data=self.data, content_type=self.content_type)
        response = self.client.get(f'/profile/{self.data["userId"]}/', HTTP_AUTHORIZATION=token, content_type=self.content_type)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['code'], -1)
        self.assertEqual(response.json()['info'], '用户已注销')


    def test_update_profile_existing_user(self):
        token = self.login_for_test(self.data)
        data = {
            "password":self.data["password"],
            "newName": "Bob123",
            "newPassword": "123456",
            "newEmail": "123456@123.com",
            "newPhoneNumber": "12345678901"
        }
        self.client.post(f'/update_profile/{self.data["userId"]}/', HTTP_AUTHORIZATION=token, data=data, content_type=self.content_type)
        response = self.client.get(f'/profile/{self.data["userId"]}/', HTTP_AUTHORIZATION=token, content_type=self.content_type)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(response.json()['userName'], 'Bob123')
        self.assertEqual(response.json()['email'], '123456@123.com')
        self.assertEqual(response.json()['phoneNumber'], '12345678901')
    