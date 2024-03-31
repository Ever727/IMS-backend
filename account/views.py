import re
import json
from django.http import HttpRequest
from django.http import HttpRequest
from django.contrib.auth.hashers import make_password
from django.contrib.auth.hashers import check_password
from account.models import User
from utils.utils_request import request_failed, request_success, BAD_METHOD
from utils.utils_require import require
from utils.utils_jwt import generate_jwt_token,check_jwt_token
from utils.utils_time import get_timestamp

def login(request:HttpRequest):
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads(request.body.decode('utf-8'))
    userId = require(body, "userId", "string",
                     err_msg="Missing or error type of [userId]")
    password = require(body, "password", "string",
                    err_msg="Missing or error type of [password]")
    
    if User.objects.filter(userId=userId).exists() is False:
        return request_failed(-1,"ID错误",404)
    user = User.objects.get(userId=userId)
    if user.isDeleted:
        return request_failed(-1,"ID错误",404)
    if check_password(password,user.password) == False:
        return request_failed(-3,"密码错误",401)
    user.status = True
    user.save()
    data = {
        "url": f"/chat/{user.userId}",
        "userId": user.userId,
        "userName": user.userName,
        "avatarUrl": user.avatarUrl,
        "token": generate_jwt_token(user.userId)
    }
    return request_success(data=data)
   
def register(request:HttpRequest):
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads(request.body.decode('utf-8'))
    userId = require(body, "userId", "string",
                    err_msg="Missing or error type of [userId]")
    password = require(body, "password", "string",
                    err_msg="Missing or error type of [password]")
    userName = require(body, "userName", "string",
                    err_msg="Missing or error type of [userName]")
    
    pattern1,pattern2 = r'^\w+$',r'^[\w\u4e00-\u9fa5]+$' 
    if len(userId) < 3 or len(userId) > 16 or not re.match(pattern1, userId):
        return request_failed(-2,"用户 ID 格式错误",400)
    if len(password) < 6 or len(password) > 16 or  not re.match(pattern1, password):
        return request_failed(-2,"密码格式错误",400)
    if len(userName) < 3 or len(userName) > 16 or  not re.match(pattern2, userName):
        return request_failed(-2,"用户名格式错误",400)
   
    if User.objects.filter(userId=userId).exists():
        return request_failed(-2,"用户已存在",400)
    
    user = User(userId=userId, password=make_password(password), userName=userName)
    user.save()
    return request_success(data={"url":"/login"})
    
def logout(request:HttpRequest):
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads(request.body.decode('utf-8'))
    userId = require(body, "userId", "string",
                     err_msg="Missing or error type of [userId]")
    token = request.headers.get("Authorization")
    body = json.loads(request.body.decode("utf-8"))
    payload = check_jwt_token(token)
    
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)
    
    user = User.objects.get(userId=userId)
    user.loginTime = get_timestamp()
    user.status = False
    user.save()
    return request_success(data={"url":"/login"})

def delete(request:HttpRequest):
    if request.method != 'POST':
        return BAD_METHOD
    
    token = request.headers.get("Authorization")
    body = json.loads(request.body.decode('utf-8'))
    payload = check_jwt_token(token)
    userId = require(body, "userId", "string",
                     err_msg="Missing or error type of [userId]")
    password = require(body, "password", "string",
                       err_msg="Missing or error type of [password]")
    
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    if User.objects.filter(userId=userId).exists() is False:
        return request_failed(-1,"用户不存在",404)
    user = User.objects.get(userId=userId)
    if user.isDeleted:
        return request_failed(-1,"用户已注销",404)
    if check_password(password,user.password) == False:
        return request_failed(-3,"密码错误",401)
    
    user.isDeleted = True
    user.save()
    return request_success(data={"url":"/login"})

def search_user(request:HttpRequest, userId:str):
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads ( request.body.decode('utf-8'))
    token = request.headers.get('Authorization')
    payload = check_jwt_token(token)
    searchId = require(body,"searchId", "string",
                     err_msg="Missing or error type of [searchId]")

    
    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)
    
    if User.objects.filter(userId=searchId).exists() is False:
        return request_failed(-1,"用户不存在",404)
    users = User.objects.get(userId=searchId)
    data = {
        "id": users.userId,
        "name": users.userName,
        "avatarUrl": users.avatarUrl
    }

    return request_success(data=data)

def profile(request: HttpRequest, userId: str):
    if request.method != "GET":
        return BAD_METHOD

    if User.objects.filter(userId=userId).exists() is False:
        return request_failed(-1, "用户不存在", 404)
    user = User.objects.get(userId=userId)
    if user.isDeleted:
        return request_failed(-1, "用户已注销", 404)

    return request_success(
        data={
            "userId": user.userId,
            "userName": user.userName,
            "avatarUrl": user.avatarUrl,
            "email": user.email,
            "phoneNumber": user.phoneNumber,
        }
    )


def update_profile(request: HttpRequest, userId: str):
    if request.method != "POST":
        return BAD_METHOD

    token = request.headers.get("Authorization")
    body = json.loads(request.body.decode("utf-8"))
    password = require(
        body, "password", "string", err_msg="Missing or error type of [password]"
    )
    payload = check_jwt_token(token)

    if payload is None or payload["userId"] != userId:
        return request_failed(-3, "JWT 验证失败", 401)

    if User.objects.filter(userId=userId).exists() is False:
        return request_failed(-1, "用户不存在", 404)
    user = User.objects.get(userId=userId)

    if user.isDeleted:
        return request_failed(-1, "用户已注销", 404)
    if check_password(password, user.password) == False:
        return request_failed(-3, "密码错误", 401)

    if "newName" in body:
        user.userName = body["newName"]
    if "newPassword" in body:
        user.password = make_password(body["newPassword"])
    if "newEmail" in body:
        user.email = body["newEmail"]
    if "newPhoneNumber" in body:
        user.phoneNumber = body["newPhoneNumber"]
    if "newAvatarUrl" in body:
        user.avatarUrl = body["newAvatarUrl"]
    user.save()

    return request_success(data={"url": f"/profile/{userId}"})
