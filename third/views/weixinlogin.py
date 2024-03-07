#coding=utf-8
import json
import traceback
import requests
from rest_framework.decorators import api_view

from third.thirdconfig import WX_APPID, WX_APPSECRET, PeiDiWX_APPID, PeiDiWX_APPSECRET
from utils.customClass import InvestError, JSONResponse
from utils.util import logexcption, catchexcption, SuccessResponse, ExceptionResponse


def get_openid(code):
    try:
        if code:
            url = 'https://api.weixin.qq.com/sns/jscode2session?appid=%s&secret=%s&js_code=%s&grant_type=authorization_code' % (WX_APPID, WX_APPSECRET, code)
            response = requests.get(url).content
            res = json.loads(response.decode())
            openid = res.get('openid')
            if openid:
                return openid
            errcode = res.get('errcode')
            if errcode == 40163:
                raise InvestError(2050)
            logexcption(msg=str(res))
    except InvestError:
        raise InvestError(2050, msg='code失效')
    except Exception:
        raise InvestError(2049, msg='获取openid失败')
    else:
        return None

def getAccessTokenWithCode(code):
    url = 'https://api.weixin.qq.com/sns/oauth2/access_token?appid=%s&secret=%s&code=%s&grant_type=authorization_code' \
          % (PeiDiWX_APPID, PeiDiWX_APPSECRET, code)
    response = requests.get(url).content
    res = json.loads(response.decode())
    access_token, open_id = res['access_token'], res['open_id']
    expires_in = res['expires_in'] < 360
    if expires_in:
        access_token, open_id = refreshAccessToken(res['refresh_token'])
    return access_token, open_id


def refreshAccessToken(refresh_token):
    url = 'https://api.weixin.qq.com/sns/oauth2/refresh_token?appid=%s&grant_type=refresh_token&refresh_token=%s' % \
          (PeiDiWX_APPID, refresh_token)
    response = requests.get(url).content
    res = json.loads(response.decode())
    access_token, open_id = res['access_token'], res['open_id']
    return access_token, open_id

def getUserInfo(access_token , open_id):
    url = 'https://api.weixin.qq.com/sns/userinfo?access_token=%s&openid=%s&lang=zh_CN' % (access_token, open_id)
    response = requests.get(url).content
    res = json.loads(response.decode())
    return res


@api_view(['POST'])
def getWeiXinUserInfo(request):
    try:
        code = request.data.get('code')
        access_token, open_id = getAccessTokenWithCode(code)
        userinfo = getUserInfo(access_token, open_id)
        return JSONResponse(SuccessResponse(userinfo))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))