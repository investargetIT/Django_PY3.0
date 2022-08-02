import datetime
import json
import os
import threading
import traceback

import requests
from rest_framework.decorators import api_view
from usersys.models import MyUser
from BD.views import feishu_update_projbd_status, feishu_update_projbd_manager, feishu_update_projbd_comments
from proj.views import feishu_update_proj_response, feishu_update_proj_traders, feishu_update_proj_comments
from sourcetype.views import get_response_id_by_text, getmenulist
from usersys.views import get_traders_by_names, maketoken
from utils.customClass import InvestError, JSONResponse
from utils.somedef import excel_table_byindex
from utils.util import catchexcption, ExceptionResponse, InvestErrorResponse, SuccessResponse, checkRequestToken, \
    logexcption, logfeishuexcptiontofile, returnDictChangeToLanguage


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
        r = requests.post(url, data=json.dumps(post_data))
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
        r = requests.post(url, data=json.dumps(post_data), headers=headers)
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
        r = requests.post(url, data=json.dumps(post_data), headers=headers)
        mobile = r.json()['data']['mobile'].replace('+86','')
        user =  MyUser.objects.get(is_deleted=False, mobile=mobile)
        clienttype = request.META.get('HTTP_CLIENTTYPE')
        perimissions = user.get_all_permissions()
        menulist = getmenulist(user)
        response = maketoken(user, clienttype)
        response['permissions'] = perimissions
        response['menulist'] = menulist
        response['is_superuser'] = user.is_superuser
        return JSONResponse(SuccessResponse({'feishu': r.json(), 'investarget': returnDictChangeToLanguage(response, 'cn')}))
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

@api_view(['POST'])
@checkRequestToken()
def update_feishu_excel(request):
    """
        更新飞书表格数据
    """
    try:
        # uploaddata = request.FILES.get('file')
        # dirpath = APILOG_PATH['audioTranslateFile']
        # filetype = str(uploaddata.name).split('.')[-1]
        # randomPrefix = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        # file_name = randomPrefix + '.' + filetype
        # if not os.path.exists(dirpath):
        #     os.makedirs(dirpath)
        # file_Path = os.path.join(dirpath, file_name)
        # with open(file_Path, 'wb+') as destination:
        #     for chunk in uploaddata.chunks():
        #         destination.write(chunk)
        uploaddata = request.FILES.get('file')
        uploaddata.open()
        r = uploaddata.read()
        uploaddata.close()
        xls_datas = excel_table_byindex(file_contents=r)
        t = threading.Thread(target=update_feishu_excel_task, args=(xls_datas, request.user))
        t.start()  # 启动线程，即让线程开始执行
        return JSONResponse(SuccessResponse({'isStart': True}))

    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



def update_feishu_excel_task(xls_datas, user):
    try:
        for data in xls_datas:
            try:
                if data['项目类型'] == 'On going':
                    proj_id = int(data['系统ID'])
                    proj_respone_text = data['项目进度']
                    proj_respone_id = get_response_id_by_text(proj_respone_text, 1)
                    traders_2_text = data['承做-PM']
                    traders_2 = get_traders_by_names(traders_2_text)
                    traders_3_text = data['承做-参与人员']
                    traders_3 = get_traders_by_names(traders_3_text)
                    traders_4_text = data['承销-主要人员']
                    traders_4 = get_traders_by_names(traders_4_text)
                    traders_5_text = data['承销-参与人员']
                    traders_5 = get_traders_by_names(traders_5_text)
                    comments = data['项目最新进展']
                    if len(comments) > 0:
                        comment_list = comments.split('；')
                    else:
                        comment_list = []
                    feishu_update_proj_response(proj_id, proj_respone_id, user)
                    feishu_update_proj_traders(proj_id, traders_2, 2, user)
                    feishu_update_proj_traders(proj_id, traders_3, 3, user)
                    feishu_update_proj_traders(proj_id, traders_4, 4, user)
                    feishu_update_proj_traders(proj_id, traders_5, 5, user)
                    feishu_update_proj_comments(proj_id, comment_list, user)

                elif data['项目类型'] == 'BD中':
                    projbd_id = int(data['系统ID'])
                    projbd_status_text = data['项目进度']
                    projbd_status_id = get_response_id_by_text(projbd_status_text, 0)
                    managers_2_text = data['BD-线索提供']
                    managers_2 = get_traders_by_names(managers_2_text)
                    managers_3_text = data['BD-主要人员']
                    managers_3 = get_traders_by_names(managers_3_text)
                    managers_4_text = data['BD-参与或材料提供人员']
                    managers_4 = get_traders_by_names(managers_4_text)
                    comments = data['项目最新进展']
                    if len(comments) > 0:
                        comment_list = comments.split('；')
                    else:
                        comment_list = []
                    feishu_update_projbd_status(projbd_id, projbd_status_id, user)
                    feishu_update_projbd_manager(projbd_id, managers_2, 2, user)
                    feishu_update_projbd_manager(projbd_id, managers_3, 3, user)
                    feishu_update_projbd_manager(projbd_id, managers_4, 4, user)
                    feishu_update_projbd_comments(projbd_id, comment_list, user)
            except Exception:
                logfeishuexcptiontofile(msg=str(data))


    except Exception:
        logexcption()
