import json
import traceback

import requests
from rest_framework.decorators import api_view

from utils.customClass import InvestError, JSONResponse
from utils.util import catchexcption, ExceptionResponse, InvestErrorResponse, SuccessResponse


@api_view(['POST'])
def get_access_token(request):
    """
       获取 飞书access_token
    """
    try:
        data = request.data
        app_id = data.get('app_id')
        app_secret = data.get('app_secret')
        token_type = data.get('token_type', 'app_access_token')
        if token_type == 'app_access_token':
            url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
        elif token_type == 'tenant_access_token':
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        else:
            raise InvestError(20072, msg='token_type 无效', detail='token_type 无效')
        if not app_id or not app_secret:
            raise InvestError(20072, msg='app_id/app_secret  是必传参数', detail='app_id/app_secret 不能为空')
        post_data = {"app_id": app_id, "app_secret": app_secret}
        r = requests.post(url, data=post_data)
        return JSONResponse(SuccessResponse(r.json()))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

@api_view(['POST'])
def refresh_access_token(request):
    """
       刷新 飞书access_token
    """
    try:
        data = request.data
        Authorization = data.get('Authorization')
        refresh_token = data.get('refresh_token')
        if not Authorization or not refresh_token:
            raise InvestError(20072, msg='Authorization/refresh_token  是必传参数', detail='Authorization/refresh_token 不能为空')
        url = "https://open.feishu.cn/open-apis/authen/v1/refresh_access_token"
        post_data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        headers = {"Authorization": "Bearer {}".format(Authorization),
                   "Content-Type": "application/json; charset=utf-8"}
        r = requests.post(url, data=post_data, headers=headers)
        return JSONResponse(SuccessResponse(r.json()))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



@api_view(['POST'])
def get_login_user_identity(request):
    """
        获取 飞书 登录用户身份
    """
    try:
        data = request.data
        Authorization = data.get('Authorization')
        code = data.get('code')
        if not Authorization  or not code:
            raise InvestError(20072, msg='Authorization/code  是必传参数', detail='Authorization/code 不能为空')
        url = "https://open.feishu.cn/open-apis/authen/v1/access_token"
        post_data = {"grant_type": "authorization_code", "code": code}
        headers = {"Authorization": "Bearer {}".format(Authorization),
                   "Content-Type":"application/json; charset=utf-8"}
        r = requests.post(url, data=post_data, headers=headers)
        return JSONResponse(SuccessResponse(r.json()))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


@api_view(['POST'])
def get_jsapi_ticket(request):
    """
        获取 飞书 jsapi—ticket
    """
    try:
        data = request.data
        Authorization = data.get('Authorization')
        if not Authorization:
            raise InvestError(20072, msg='Authorization 是必传参数', detail='Authorization 不能为空')
        url = "https://open.feishu.cn/open-apis/jssdk/ticket/get"
        headers = {"Authorization": "Bearer {}".format(Authorization), "Content-Type":"application/json; charset=utf-8"}
        r = requests.post(url, headers=headers)
        return JSONResponse(SuccessResponse(r.json()))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))
