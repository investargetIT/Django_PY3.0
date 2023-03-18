#coding=utf-8
import base64
import json
import os
import random
import string
import traceback

import datetime
import requests
from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view

from invest.settings import APILOG_PATH
from mongoDoc.views import saveOpenAiChatDataToMongo, updateOpenAiChatTopicChat, getOpenAiChatConversationDataChat
from third.thirdconfig import baiduaip_appid, baiduaip_secretkey, baiduaip_appkey, OPENAI_API_KEY, OPENAI_URL, \
    OPENAI_MODEL, hokong_URL
from third.views.qiniufile import deleteqiniufile
from utils.customClass import JSONResponse, InvestError
from utils.somedef import file_iterator
from utils.util import SuccessResponse, catchexcption, ExceptionResponse, InvestErrorResponse, checkrequesttoken, \
    write_to_cache, read_from_cache, checkRequestToken, cache_delete_key


#获取汇率
@api_view(['GET'])
@checkRequestToken()
def getcurrencyreat(request):
    try:
        tokenkey = request.META.get('HTTP_TOKEN')
        checkrequesttoken(tokenkey)
        scur = request.GET.get('scur', None)  # 原币种
        tcur = request.GET.get('tcur', None)  # 目标币种
        if not tcur or not scur:
            raise InvestError(20072)
        if scur == tcur:
            result = [
                {
                    "currencyF": scur,
                    "currencyT": tcur,
                    "currencyFD": "1",
                    "exchange": "1",
                    "result": "1",
                },
                {
                    "currencyF": tcur,
                    "currencyT": scur,
                    "currencyFD": "1",
                    "exchange": "1",
                    "result": "1",
                },
            ]
        else:
            response = requests.get('http://op.juhe.cn/onebox/exchange/currency?from={}&to={}&key=92ad022726cff74d15d1d3b761701fa4'.format(scur, tcur)).content
            response = json.loads(response.decode())
            if isinstance(response, dict):
                error_code = response.get('error_code')
                if error_code == 0:
                    result = response.get('result',{})
                else:
                    raise InvestError(20071,msg=response.get('reason',None))
            else:
                raise InvestError(20071,msg=response)
        return JSONResponse(SuccessResponse(result))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

#获取手机号码归属地
@api_view(['GET'])
@checkRequestToken()
def getMobilePhoneAddress(request):
    try:
        tokenkey = request.META.get('HTTP_TOKEN')
        checkrequesttoken(tokenkey)
        mobile = request.GET.get('mobile', None)
        if not mobile:
            raise InvestError(20072, msg='手机号码不能为空')
        response = requests.get('http://apis.juhe.cn/mobile/get?phone={}&dtype=&key=f439062c59bb86db8156446aa9737c72'.format(mobile)).content
        response = json.loads(response.decode())
        if isinstance(response,dict):
            error_code = response.get('error_code')
            if error_code == 0:
                result = response.get('result', {})
            else:
                raise InvestError(20071, msg=response.get('reason', None))
        else:
            raise InvestError(20071,msg=response)
        return JSONResponse(SuccessResponse(result))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



#百度名片识别
import json
from urllib.request import urlopen
from urllib.request import Request
from urllib.error import URLError
from urllib.parse import urlencode
import ssl
ssl._create_default_https_context = ssl._create_unverified_context


"""
    获取百度ocrtoken
"""
def fetch_token():
    params = {'grant_type': 'client_credentials',
              'client_id': baiduaip_appkey,
              'client_secret': baiduaip_secretkey}
    post_data = urlencode(params).encode('utf-8')
    req = Request('https://aip.baidubce.com/oauth/2.0/token', post_data)
    try:
        f = urlopen(req, timeout=10)
        result_str = f.read()
    except URLError as err:
        raise InvestError(9999, msg='网络错误', detail=str(err))
    result_str = result_str.decode()
    result = json.loads(result_str)
    if ('access_token' in result.keys() and 'scope' in result.keys()):
        if not 'brain_all_scope' in result['scope'].split(' '):
            raise InvestError(20071, msg='获取百度ocr token失败', detail='please ensure has check the ability')
        return result['access_token']
    else:
        raise InvestError(20071, msg='获取百度ocr token失败', detail='client_id/client_secret参数错误')


@checkRequestToken()
def ccupload_baidu(request):
    try:
        data_dict = request.FILES
        uploaddata = None
        for keya in data_dict.keys():
            uploaddata = data_dict[keya]
        token = fetch_token()
        urlstr = "https://aip.baidubce.com/rest/2.0/ocr/v1/business_card" + "?access_token=" + token
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        params = {"image": base64.b64encode(uploaddata.read())}
        response = requests.post(urlstr, data=params, headers=headers)
        return JSONResponse(SuccessResponse(response.content))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


import qrcode

def makeQRCode(content,path):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image()
    img.save(path)

@api_view(['GET'])
@checkRequestToken()
def getQRCode(request):
    """
    获取二维码
    """
    try:
        request.user = checkrequesttoken(request.GET.get('acw_tk'))
        url = request.GET.get('url',None)
        if url:
            qrcode_path = APILOG_PATH['excptionlogpath'] + 'qrcode.png'
            makeQRCode(url,qrcode_path)
            fn = open(qrcode_path, 'rb')
            response = StreamingHttpResponse(file_iterator(fn))
            response['Content-Type'] = 'application/octet-stream'
            response["content-disposition"] = 'attachment;filename=qrcode.png'
            os.remove(qrcode_path)
        else:
            raise InvestError(50010, msg='二维码生成失败')
        return response
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

#生成上传记录（开始上传）
@api_view(['GET'])
@checkRequestToken()
def recordUpload(request):
    try:
        record = datetime.datetime.now().strftime('%y%m%d%H%M%S')+''.join(random.sample(string.ascii_lowercase,6))
        write_to_cache(record, {'files': [], 'is_active': True})
        return JSONResponse(SuccessResponse({record: read_from_cache(record)}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

#上传完成，更新上传记录
@api_view(['POST'])
def updateUpload(request):
    try:
        data = request.data
        record = data.get('record')
        files = data.get('files', [])
        if read_from_cache(record) is None:
            raise InvestError(8003, msg='没有这条记录')
        write_to_cache(record, {'files': files, 'is_active':True}, 3600)
        return JSONResponse(SuccessResponse({record: read_from_cache(record)}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

#查询上传记录
@api_view(['GET'])
def selectUpload(request):
    try:
        record = request.GET.get('record')
        recordDic = read_from_cache(record)
        if recordDic is None:
            raise InvestError(8003, msg='没有这条记录')
        return JSONResponse(SuccessResponse({record: read_from_cache(record)}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

#取消上传，状态置为非活跃
@api_view(['POST'])
def cancelUpload(request):
    try:
        data = request.data
        record = data.get('record')
        recordDic = read_from_cache(record)
        if recordDic is None:
            raise InvestError(8003, msg='没有这条记录')
        recordDic['is_active'] = False
        write_to_cache(record, recordDic, 3600)
        return JSONResponse(SuccessResponse({record: read_from_cache(record)}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

#取消上传，删除上传记录
@api_view(['POST'])
def deleteUpload(request):
    try:
        data = request.data
        record = data.get('record')
        recordDic = read_from_cache(record)
        if recordDic is None:
            raise InvestError(8003, msg='没有这条记录')
        files = recordDic.get('files', [])
        for file in files:
            deleteqiniufile(key=file['key'], bucket=file['bucket'])
            deleteqiniufile(key=file['realfilekey'], bucket=file['bucket'])
        cache_delete_key(record)
        return JSONResponse(SuccessResponse({record: read_from_cache(record)}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



@api_view(['POST'])
@checkRequestToken()
def getopenaitextcompletions(request):
    try:
        data = request.data
        data['model'] = OPENAI_MODEL
        topic_id = data.pop('topic_id', None)
        newmessages = data['messages']
        if not topic_id:
            raise InvestError(20072, msg='会话id不能为空')
        if not newmessages:
            raise InvestError(20072, msg='会话消息不能为空')
        isMultiple = data.pop('isMultiple', True)
        if isMultiple:
            historydata = getOpenAiChatConversationDataChat(topic_id)
            chatmessages = historydata.extend(newmessages)
            data['messages'] = chatmessages
        hokongdata = {
            "aidata" : {'url': OPENAI_URL,'key': OPENAI_API_KEY},
            "chatdata": data
        }
        # 构造代理地址
        res = requests.post(hokong_URL, data=json.dumps(hokongdata), headers={'Content-Type': "application/json"}).content.decode()
        res = json.loads(res)
        if res['success']:
            result = json.loads(res['result'])
            saveOpenAiChatDataToMongo({
                'topic_id': topic_id,
                'user_id': request.user.id,
                'content': str(newmessages),
                'isAI': False
            })
            saveOpenAiChatDataToMongo({
                'topic_id': topic_id,
                'user_id': request.user.id,
                'content': res,
                'reset': True if result['usage']['total_tokens'] >= 4000 else False,
                'isAI': True
            })
        else:
            raise InvestError(8312, msg=res['errmsg'], detail=res['errmsg'])
        updateOpenAiChatTopicChat(topic_id, {'lastchat_time': datetime.datetime.now()})
        return JSONResponse(SuccessResponse(res))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))
