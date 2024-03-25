from django.test import TestCase

# Create your tests here.
class AccountTests(TestCase):
    
    # ! Test section
    # * Tests for register view
    def test_register_bad_method(self):
        data = {}
        response =self.client.get('/register/', data=data, content_type='application/json')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()['code'], -3)
        self.assertEqual(response.json()['info'], 'Bad method')

    def test_register_new_user(self):
        data = {
            "userId":"123456",
            "userName": "AsRight",
            "password": "123456",
        }
        response = self.client.post('/register/', data=data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)

    def  test_register_existing_user(self):
        data = {
            "userId":"123456",
            "userName": "AsRight",
            "password": "123456",
        }
        self.client.post('/register/', data=data, content_type='application/json')
        response = self.client.post('/register/', data=data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], -2)
        self.assertEqual(response.json()['info'], '用户已存在')

    # * Tests for login view
    def test_login_existing_user_correct_password(self):
        data = {
            "userId":"123456",
            "userName": "AsRight",
            "password": "123456",
        }
        self.client.post('/register/', data=data, content_type='application/json')
        res = self.client.post('/login/', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue(res.json()['token'].count('.') == 2)

    def test_login_existing_user_wrong_password(self):
        data = {
            "userId":"123456",
            "userName": "AsRight",
            "password": "123456",
        }
        self.client.post('/register/', data=data, content_type='application/json')
        data['password'] = '12345'
        res = self.client.post('/login/', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], -3)
        self.assertEqual(res.json()['info'], '密码错误')

    def test_login_non_existing_user(self):
       data = {
            "userId":"123456",
            "userName": "AsRight",
            "password": "123456",
        }
       response = self.client.post('/login/', data=data, content_type='application/json')     
       self.assertEqual(response.status_code, 404)
       self.assertEqual(response.json()['code'], -1)

     # * Tests for logout view
    def test_logout_existing_user(self):
        data = {
            "userId":"123456",
            "userName": "AsRight",
            "password": "123456",
        }
        self.client.post('/register/', data=data, content_type='application/json')
        res = self.client.post('/login/', data=data, content_type='application/json')
        token = res.json()['token']
        res = self.client.post('/logout/', HTTP_AUTHORIZATION=token,data=data, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)


    # * Tests for delete view
    # TODO: Implement delete view tests
    def test_delete_existing_user(self):
        data = {
            "userId":"123456",
            "userName": "AsRight",
            "password": "123456",
        }    
        self.client.post('/register/', data=data, content_type='application/json')
        res = self.client.post('/login/', data=data, content_type='application/json')
        token = res.json()['token']
        res = self.client.post('/delete/', HTTP_AUTHORIZATION=token,data=data, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
