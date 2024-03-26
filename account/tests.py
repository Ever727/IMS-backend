from django.test import TestCase
from .models import User
from django.contrib.auth.hashers import make_password

# Create your tests here.
class AccountTests(TestCase):
    
    def setUp(self):
        self.data = {
            "userId":"123456",
            "userName": "TAsRight",
            "password": "123456",
        }
        self.newData = {
            "userId":"alice",
            "userName": "Alice",
            "password": "123456",
        }
        self.content_type = 'application/json'
        self.registerUrl = '/register/'
        self.loginUrl = '/login/'
        data = self.data.copy()
        data['password'] = make_password('123456')
        self.user = User.objects.create(**data)

    # ! Test section
    # * Tests for register view
    def test_register_bad_method(self):
        response =self.client.get('/register/', content_type=self.content_type)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()['code'], -3)
        self.assertEqual(response.json()['info'], 'Bad method')

    def test_register_new_user(self):
        
        response = self.client.post('/register/', data=self.newData, content_type=self.content_type)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)

    def  test_register_existing_user(self):
        
        response = self.client.post('/register/', data=self.data, content_type=self.content_type)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], -2)
        self.assertEqual(response.json()['info'], '用户已存在')

    # * Tests for login view
    def test_login_existing_user_correct_password(self):
        res = self.client.post('/login/', data=self.data, content_type=self.content_type)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue(res.json()['token'].count('.') == 2)

    def test_login_existing_user_wrong_password(self):
        data = self.data.copy()
        data['password'] = '12345'
        res = self.client.post('/login/', data=data, content_type=self.content_type)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], -3)
        self.assertEqual(res.json()['info'], '密码错误')

    def test_login_non_existing_user(self):
       response = self.client.post('/login/', data=self.newData, content_type=self.content_type)     
       self.assertEqual(response.status_code, 404)
       self.assertEqual(response.json()['code'], -1)

     # * Tests for logout view
    def test_logout_logined_user(self):
        res = self.client.post('/login/', data=self.data, content_type=self.content_type)
        token = res.json()['token']
        res = self.client.post('/logout/', HTTP_AUTHORIZATION=token, data=self.data, content_type=self.content_type)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)


    # * Tests for delete view
    # TODO: Implement delete view tests
    def test_delete_existing_user(self):
        res = self.client.post('/login/', data=self.data, content_type='application/json')
        token = res.json()['token']
        res = self.client.post('/delete/', HTTP_AUTHORIZATION=token, data=self.data, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
