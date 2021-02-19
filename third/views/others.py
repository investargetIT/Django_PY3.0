#coding=utf-8
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
from third.views.qiniufile import deleteqiniufile
from utils.customClass import JSONResponse, InvestError
from utils.somedef import file_iterator
from utils.util import SuccessResponse, catchexcption, ExceptionResponse, InvestErrorResponse, checkrequesttoken, \
    write_to_cache, read_from_cache, checkRequestToken, cache_delete_key


#获取汇率
@api_view(['GET'])
def getcurrencyreat(request):
    try:
        tokenkey = request.META.get('HTTP_TOKEN')
        checkrequesttoken(tokenkey)
        tcur = request.GET.get('tcur', None)
        scur = request.GET.get('scur', None)
        if not tcur or not scur:
            raise InvestError(20072)
        response = requests.get('https://sapi.k780.com/?app=finance.rate&scur=%s&tcur=%s&appkey=18220&sign=9b97118c7cf61df11c736c79ce94dcf9'% (scur, tcur)).content
        response = json.loads(response)
        if isinstance(response,dict):
            success = response.get('success',False)
            if success in ['1',True]:
                result = response.get('result',{})
            else:
                raise InvestError(code=2007,msg=response.get('msg',None))
        else:
            raise InvestError(code=2007,msg=response)
        return JSONResponse(SuccessResponse(result))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

#获取手机号码归属地
@api_view(['GET'])
def getMobilePhoneAddress(request):
    try:
        tokenkey = request.META.get('HTTP_TOKEN')
        checkrequesttoken(tokenkey)
        mobile = request.GET.get('mobile', None)
        if not mobile:
            raise InvestError(20072, msg='mobile 不能为空')
        response = requests.get('http://api.k780.com/?app=phone.get&phone=%s&appkey=18220&sign=9b97118c7cf61df11c736c79ce94dcf9&format=json' % mobile).content
        response = json.loads(response)
        if isinstance(response,dict):
            success = response.get('success',False)
            if success in ['1',True]:
                result = response.get('result',{})
            else:
                raise InvestError(code=2007,msg=response.get('msg',None))
        else:
            raise InvestError(code=2007,msg=response)
        return JSONResponse(SuccessResponse(result))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


#名片识别
@api_view(['POST'])
def ccupload(request):
    try:
        data_dict = request.FILES
        uploaddata = None
        for keya in data_dict.keys():
            uploaddata = data_dict[keya]
        urlstr = 'http://bcr2.intsig.net/BCRService/BCR_VCF2?user=summer.xia@investarget.com&pass=P8YSCG7AQLM66S7M&json=1&lang=15'
        response = requests.post(urlstr, uploaddata)
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