import re
import json
from django.http import HttpRequest
from django.contrib.auth.hashers import make_password,check_password
from account.models import User
from utils.utils_request import request_failed, request_success, BAD_METHOD
from utils.utils_require import require
from utils.utils_jwt import generate_jwt_token, jwt_required

def login(request:HttpRequest):
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads(request.body.decode('utf-8'))
    userId = require(body, "userId", "string",
                     err_msg="Missing or error type of [userId]")
    password = require(body, "password", "string",
                    err_msg="Missing or error type of [password]")
    
    try:
        user = User.objects.get(userId=userId, isDeleted=False)
        if check_password(password,user.password) == False:
            return request_failed(-3,"密码错误",401)
    except User.DoesNotExist:
        return request_failed(-1,"ID错误",404)
   
    data = user.serialize()
    data["token"] = generate_jwt_token(user.userId)
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


@jwt_required
def delete(request:HttpRequest):
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads(request.body.decode('utf-8'))
    userId = require(body, "userId", "string",
                     err_msg="Missing or error type of [userId]")
    password = require(body, "password", "string",
                       err_msg="Missing or error type of [password]")


    try:
        user = User.objects.get(userId=userId, isDeleted=False)
        if check_password(password,user.password) == False:
            return request_failed(-3,"密码错误",401)
    except User.DoesNotExist:
        return request_failed(-1,"用户不存在或已注销",404)
    
    user.isDeleted = True
    user.save()
    return request_success(data={"url":"/login"})

@jwt_required
def search_user(request:HttpRequest, userId:str):
    if request.method != 'POST':
        return BAD_METHOD
    
    body = json.loads ( request.body.decode('utf-8'))
    searchId = require(body,"searchId", "string",
                     err_msg="Missing or error type of [searchId]")

    
    user_info = User.objects.filter(userId=searchId).values("userId", "userName", "avatarUrl","isDeleted").first()
    if user_info is None:
        return request_failed(-1,"用户不存在",404)

    return request_success(data={
        "id": user_info["userId"],
        "name": user_info["userName"],
        "avatarUrl": user_info["avatarUrl"],
        "isDeleted": user_info["isDeleted"]
    })


def profile(request: HttpRequest, userId: str):
    if request.method != "GET":
        return BAD_METHOD

    user_info = User.objects.filter(userId=userId).values(
            "userId", "userName", "avatarUrl", "email", "phoneNumber"
        ).first()
    if user_info is None:
        return request_failed(-1, "用户不存在", 404)

    return request_success(data=user_info)

@jwt_required
def update_profile(request: HttpRequest, userId: str):
    if request.method != "POST":
        return BAD_METHOD
    
    body = json.loads(request.body.decode("utf-8"))
    password = require(
        body, "password", "string", err_msg="Missing or error type of [password]"
    )
   

    try:
        user = User.objects.get(userId=userId, isDeleted=False)
        if check_password(password, user.password) == False:
            return request_failed(-3, "密码错误", 401)
    except User.DoesNotExist:
        return request_failed(-1, "用户不存在或已注销", 404)
    
    for (key, attr) in [("newName", "userName"), ("newEmail", "email"), ("newPhoneNumber", "phoneNumber"), ("newAvatarUrl", "avatarUrl")]:
        if key in body:
            setattr(user, attr, body[key])
        
    if "newPassword" in body:
        user.password = make_password(body["newPassword"])
    user.save()

    return request_success(data={"url": f"/profile/{userId}"})
