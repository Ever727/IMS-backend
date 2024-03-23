import re
import json
from django.http import HttpRequest,HttpResponse
from django.contrib.auth.hashers import make_password
from django.contrib.auth.hashers import check_password
from account.models import User
from utils.utils_request import request_failed, request_success,BAD_METHOD
from utils.utils_require import require
from utils.utils_time import get_timestamp
from utils.utils_jwt import generate_jwt_token,check_jwt_token

def login(request:HttpRequest):
    return HttpResponse("Cogratulations! You have successfully logged in.")

def register(request:HttpRequest):
    pass
    

def logout(request:HttpRequest):
    pass


def delete(request:HttpRequest):
    pass