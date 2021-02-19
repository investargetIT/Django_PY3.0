# -*- coding: utf-8 -*-
import gzip
import hashlib
import json
from time import time

import datetime
import requests
from requests.auth import AuthBase
from rest_framework.decorators import api_view

from mongoDoc.views import saveChatMessageDataToMongo
from third.thirdconfig import org, app, client_id, client_secret, password
from utils.customClass import JSONResponse, InvestError
from utils.util import logexcption

JSON_HEADER = {'content-type': 'application/json'}
# EASEMOB_HOST = "http://localhost:8080"#
EASEMOB_HOST = "https://a1.easemob.com"
DEBUG = True


def http_result(r):
    if DEBUG:
        error_log = {
            "method": r.request.method,
            "url": r.request.url,
            "request_header": dict(r.request.headers),
            "response_header": dict(r.headers),
            "response": r.text
        }
        if r.request.body:
            error_log["payload"] = r.request.body

    if r.status_code == requests.codes.ok:
        return True, r.json()
    else:
        return False, r.text

def delete(url, auth=None):
    r = requests.delete(url, headers=JSON_HEADER, auth=auth)
    return http_result(r)

def post(url, payload, auth=None):
    r = requests.post(url, data=json.dumps(payload), headers=JSON_HEADER, auth=auth)
    return http_result(r)

def get(url, auth=None):
    r = requests.get(url, headers=JSON_HEADER, auth=auth)
    return http_result(r)


class Token:
    """表示一个登陆获取到的token对象"""

    def __init__(self, token, exipres_in):
        self.token = token
        self.exipres_in = exipres_in + int(time())

    def is_not_valid(self):
        """这个token是否还合法, 或者说, 是否已经失效了, 这里我们只需要
        检查当前的时间, 是否已经比或者这个token的时间过去了exipreis_in秒

        即  current_time_in_seconds < (expires_in + token_acquired_time)
        """
        return time() > self.exipres_in



class EasemobAuth(AuthBase):
    """环信认证类"""

    def __init__(self):
        self.token = ""

    def __call__(self, r):
        r.headers['Authorization'] = 'Bearer ' + self.get_token()
        return r

    def get_token(self):
        """在这里我们先检查是否已经获取过token, 并且这个token有没有过期"""
        if (self.token is None) or (self.token.is_not_valid()):
            # refresh the token
            self.token = self.acquire_token()
        return self.token.token

    def acquire_token(self):
        """真正的获取token的方法, 返回值是一个我们定义的Token对象
            这个留给子类去实现
        """
        pass


class AppClientAuth(EasemobAuth):
    """使用app的client_id和client_secret来获取app管理员token"""

    def __init__(self, org, app, client_id, client_secret):
        super(AppClientAuth, self).__init__()
        self.client_id = client_id
        self.client_secret = client_secret
        self.url = EASEMOB_HOST + ("/%s/%s/token" % (org, app))
        self.token = None

    def acquire_token(self):
        """
        使用client_id / client_secret来获取token, 具体的REST API为

        POST /{org}/{app}/token {'grant_type':'client_credentials', 'client_id':'xxxx', 'client_secret':'xxxxx'}
        """
        payload = {'grant_type': 'client_credentials', 'client_id': self.client_id, 'client_secret': self.client_secret}
        success, result = post(self.url, payload)
        if success:
            return Token(result['access_token'], result['expires_in'])
        else:
            # throws exception
            pass


def register_new_user(username, password, nickname=None):
    """注册新的app用户
    POST /{org}/{app}/users {"username":"xxxxx", "password":"yyyyy"}
    """
    auth = AppClientAuth(org, app, client_id, client_secret)
    payload = {"username": username, "password": password, 'nickname':nickname}
    url = EASEMOB_HOST + ("/%s/%s/users" % (org, app))
    return post(url, payload, auth)    #bool:success,result:result


def delete_user(username):
    """删除app用户
    DELETE /{org}/{app}/users/{username}
    """
    auth = AppClientAuth(org, app, client_id, client_secret)

    url = EASEMOB_HOST + ("/%s/%s/users/%s" % (org, app, username))
    return delete(url, auth)  # bool:success,result:result



def delete_users(limit):
    """批量删除IM用户
        DELETE /{org}/{app}/users?limit=5
        """
    auth = AppClientAuth(org, app, client_id, client_secret)

    url = EASEMOB_HOST + ("/%s/%s/users?limit=%s" % (org, app, limit))
    return delete(url, auth)  # bool:success,result:result


def makePaswd(password):
    m = hashlib.md5()
    m.update(password)
    return m.hexdigest()


def deleteHuanXinIMWithUser(user):
    username = user.id
    success, result = delete_user(username)
    # if not success:
    #     raise InvestError(2023,msg=result)
    if success:
        user.hasIM = False
        user.save()
    return result


def registHuanXinIMWithUser(user):
    username = user.id
    raw_password = makePaswd(str(user.id))
    nickname = user.usernameC
    success, result = register_new_user(username, raw_password, nickname)
    # if not success:
    #     raise InvestError(2023,msg=result)
    if success:
        user.hasIM = True
        user.save()
    return result

def downloadChatMessages():
    auth = AppClientAuth(org, app, client_id, client_secret)
    times = datetime.datetime.now() - datetime.timedelta(hours=2 * 1)
    strtime = times.strftime('%Y%m%d%H')
    url = 'http://a1.easemob.com/%s/%s/chatmessages/%s' % (org, app, strtime)
    success, res = get(url, auth)
    if success:
        fileurllist = res.get('data')
        for fileurldic in fileurllist:
            fileurl = fileurldic.get('url')
            getmsg(fileurl)
    else:
        logexcption(msg=str({'downloadchatmsg':res}))
    return success,res

def getmsg(url):
    r = requests.get(url)
    file_name = "chatmsg.gz"
    with open(file_name, "wb") as code:
        code.write(r.content)
    un_gz(file_name)


def un_gz(file_name):
    """ungz zip file"""
    f_name = file_name.replace(".gz", "")
    g_file = gzip.GzipFile(file_name)
    msgfile = open(f_name, "wb")
    msgfile.write(g_file.read())
    g_file.close()
    msgfile.close()
    readMsgFromFile(f_name)

def readMsgFromFile(file_name):
    file = open(file_name,'r+')
    msgdatalist = file.readlines()
    if len(msgdatalist) > 0:
        for onemsgdata in msgdatalist:
            saveMsgToMongo(json.loads(onemsgdata))
        file.truncate()
    file.close()

def saveMsgToMongo(msgdata):
    if isinstance(msgdata,dict) and msgdata.get('msg_id',None) is not None:
        chatfrom = msgdata.pop('from')
        msgdata['chatfrom'] = chatfrom
        saveChatMessageDataToMongo(msgdata)