#! /usr/bin/env python2
# encoding=utf-8
import time, random, json,  sys, os

from third.thirdconfig import my_product, apns_production_boolean
reload(sys)
sys.setdefaultencoding('utf8')
sys.path.insert(0, os.path.dirname(sys.path[0]))


import requests



'''''
    极光key配置
'''


'''''
   超出频率限制

当一个请求遇到频率限制时，JPush API 返回的 HTTP 返回码为 429，其含义是：太多的请求。
此时返回内容里，是如下的信息：
{
  "error": {
       "code": 2002,
       "message": "Rate limit exceeded"
   }
}
'''
import base64

my_secret = '%s:%s'%(my_product['app_key'],my_product['master_secret'])
#加密
encode_secret = base64.b64encode(my_secret)

def https_request(app_key, body, url, content_type=None, version=None, params=None):
    https = requests.Session()
    https.auth = (app_key['app_key'], app_key['master_secret'])
    headers = {}
    headers['user-agent'] = 'jpush-api-python-client'
    # headers['Authorization'] = 'Basic ' + str(encode_secret)

    headers['connection'] = 'keep-alive'
    headers['content-type'] = 'application/json'
    try:
        response = https.request('POST', url, data=body, params=params, headers=headers)
    # 合并返回
    except requests.exceptions.ConnectTimeout:
        raise LookupError("Connection to api.jpush.cn timed out.")
    except:
        raise LookupError("Connection to api.jpush.cn error.")
    return response


'''''
    jpush v3 params
    支持离线消息，在线通知同时发送
'''

def push_params_v3(content, receiver_value, platform, bdage, n_extras):
    sendno = int(time.time() + random.randint(10000000, 99999900))
    payload = dict()
    payload['platform'] = platform

    payload['audience'] = {
        "alias": [str(receiver_value)]
    }
    # 离线消息
    payload['message'] = {
        "msg_content": content,
        "extras": n_extras
    }
    # 在线通知
    payload['notification'] = {
        "android": {"alert": content, "extras": n_extras},
        "ios": {"alert": content, "sound": "default", "extras": n_extras,"badge":bdage},  # "badge":1,
    }
    payload['options'] = {"apns_production": apns_production_boolean, "time_to_live": 86400 * 3, 'sendno': sendno}

    return payload


'''''
    jpush v3 request
'''


def jpush_v3(app_key, payload):
    body = json.dumps(payload)
    return https_request(app_key, body, "https://api.jpush.cn/v3/push", 'application/json', version=1)


def pushnotification(content,receiver_alias,bdage,n_extras=None):
    platform = [
        "android",
        "ios",
        # "winphone"
        ]
    n_extras = n_extras if n_extras else {}
    payload = push_params_v3(content=content,receiver_value=receiver_alias,platform=platform,bdage=bdage,n_extras=n_extras)
    return jpush_v3(my_product,payload)

