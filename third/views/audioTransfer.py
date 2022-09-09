# -*- coding: utf-8 -*-
# 非实时语音转写webapi

import base64
import datetime
import hashlib
import hmac
import json
import os
import random
import string
import time
import traceback

import requests
from django.core.paginator import Paginator, EmptyPage
from django.db import transaction
from rest_framework import viewsets
from rest_framework import filters

from invest.settings import APILOG_PATH
from third.models import AudioTranslateTaskRecord
from third.serializer import AudioTranslateTaskRecordSerializer, AudioTranslateTaskRecordUpdateSerializer
from third.thirdconfig import xunfei_appid, xunfei_secret_key
from utils.customClass import JSONResponse, InvestError
from utils.util import SuccessResponse, InvestErrorResponse, catchexcption, ExceptionResponse, \
    loginTokenIsAvailable

lfasr_host = 'http://raasr.xfyun.cn/api'

# 请求的接口名
api_prepare = '/prepare'
api_upload = '/upload'
api_merge = '/merge'
api_get_progress = '/getProgress'
api_get_result = '/getResult'
# 文件分片大小10M
file_piece_sice = 10485760

# 如果出现requests模块报错："NoneType" object has no attribute 'read', 尝试将requests模块更新到2.20.0或以上版本
# ——————————————————转写可配置参数————————————————
# 参数可在官网界面（https://doc.xfyun.cn/rest_api/%E8%AF%AD%E9%9F%B3%E8%BD%AC%E5%86%99.html）查看，根据需求可自行在gene_params方法里添加修改
# 转写类型
lfasr_type = 0
# 是否开启分词
has_participle = 'false'
has_seperate = 'true'
# 多候选词个数
max_alternatives = 0
# 子用户标识
suid = ''


class SliceIdGenerator:
    """slice id生成器"""

    def __init__(self):
        self.__ch = 'aaaaaaaaa`'

    def getNextSliceId(self):
        ch = self.__ch
        j = len(ch) - 1
        while j >= 0:
            cj = ch[j]
            if cj != 'z':
                ch = ch[:j] + chr(ord(cj) + 1) + ch[j + 1:]
                break
            else:
                ch = ch[:j] + 'a' + ch[j + 1:]
                j = j - 1
        self.__ch = ch
        return self.__ch


class TransferRequestApi(object):
    def __init__(self, upload_file_path, speaker_number):
        self.appid = xunfei_appid
        self.secret_key = xunfei_secret_key
        self.upload_file_path = upload_file_path
        self.speaker_number = speaker_number

    # 根据不同的apiname生成不同的参数,本示例中未使用全部参数您可在官网(https://doc.xfyun.cn/rest_api/%E8%AF%AD%E9%9F%B3%E8%BD%AC%E5%86%99.html)查看后选择适合业务场景的进行更换
    def gene_params(self, apiname, taskid=None, slice_id=None):
        appid = self.appid
        secret_key = self.secret_key
        upload_file_path = self.upload_file_path
        speaker_number = self.speaker_number
        ts = str(int(time.time()))
        m2 = hashlib.md5()
        m2.update((appid + ts).encode('utf-8'))
        md5 = m2.hexdigest()
        md5 = bytes(md5, encoding='utf-8')
        # 以secret_key为key, 上面的md5为msg， 使用hashlib.sha1加密结果为signa
        signa = hmac.new(secret_key.encode('utf-8'), md5, hashlib.sha1).digest()
        signa = base64.b64encode(signa)
        signa = str(signa, 'utf-8')
        file_len = os.path.getsize(upload_file_path)
        file_name = os.path.basename(upload_file_path)
        param_dict = {}

        if apiname == api_prepare:
            # slice_num是指分片数量，如果您使用的音频都是较短音频也可以不分片，直接将slice_num指定为1即可
            slice_num = int(file_len / file_piece_sice) + (0 if (file_len % file_piece_sice == 0) else 1)
            param_dict['app_id'] = appid
            param_dict['signa'] = signa
            param_dict['ts'] = ts
            param_dict['file_len'] = str(file_len)
            param_dict['file_name'] = file_name
            param_dict['slice_num'] = str(slice_num)
            param_dict['speaker_number'] = speaker_number
            param_dict['has_seperate'] = has_seperate
            param_dict['role_type'] = 1
        elif apiname == api_upload:
            param_dict['app_id'] = appid
            param_dict['signa'] = signa
            param_dict['ts'] = ts
            param_dict['task_id'] = taskid
            param_dict['slice_id'] = slice_id
        elif apiname == api_merge:
            param_dict['app_id'] = appid
            param_dict['signa'] = signa
            param_dict['ts'] = ts
            param_dict['task_id'] = taskid
            param_dict['file_name'] = file_name
        elif apiname == api_get_progress:
            param_dict['app_id'] = appid
            param_dict['signa'] = signa
            param_dict['ts'] = ts
            param_dict['task_id'] = taskid
        return param_dict

    # 请求和结果解析，结果中各个字段的含义可参考：https://doc.xfyun.cn/rest_api/%E8%AF%AD%E9%9F%B3%E8%BD%AC%E5%86%99.html
    def gene_request(self, apiname, data, files=None, headers=None):
        response = requests.post(lfasr_host + apiname, data=data, files=files, headers=headers)
        result = json.loads(response.text)
        if result["ok"] == 0:
            return result
        else:
            raise InvestError(6100, detail="{} error:".format(apiname) + str(result))


    # 预处理
    def prepare_request(self):
        return self.gene_request(apiname=api_prepare,
                                 data=self.gene_params(api_prepare))

    # 上传
    def upload_request(self, taskid, upload_file_path):
        file_object = open(upload_file_path, 'rb')
        try:
            index = 1
            sig = SliceIdGenerator()
            while True:
                content = file_object.read(file_piece_sice)
                if not content or len(content) == 0:
                    break
                files = {
                    "filename": self.gene_params(api_upload).get("slice_id"),
                    "content": content
                }
                response = self.gene_request(api_upload,
                                             data=self.gene_params(api_upload, taskid=taskid,
                                                                   slice_id=sig.getNextSliceId()),
                                             files=files)
                if response.get('ok') != 0:
                    # 上传分片失败
                    raise InvestError(6100, detail='upload slice fail, response: ' + str(response))
                # print('upload slice ' + str(index) + ' success')
                index += 1
        finally:
            'file index:' + str(file_object.tell())
            file_object.close()
        return True

    # 合并
    def merge_request(self, taskid):
        return self.gene_request(api_merge, data=self.gene_params(api_merge, taskid=taskid))

    # 获取进度
    def get_progress_request(self, taskid):
        return self.gene_request(api_get_progress, data=self.gene_params(api_get_progress, taskid=taskid))


    def all_api_request(self):
        # 1. 预处理
        pre_result = self.prepare_request()
        taskid = pre_result["data"]
        # 2 . 分片上传
        self.upload_request(taskid=taskid, upload_file_path=self.upload_file_path)
        # 3 . 文件合并
        self.merge_request(taskid=taskid)
        return taskid



class GetResultRequestApi(object):
    def __init__(self, task_id):
        self.appid = xunfei_appid
        self.secret_key = xunfei_secret_key
        self.task_id = task_id

    def gene_params(self):
        ts = str(int(time.time()))
        m2 = hashlib.md5()
        m2.update((self.appid + ts).encode('utf-8'))
        md5 = m2.hexdigest()
        md5 = bytes(md5, encoding='utf-8')
        signa = hmac.new(self.secret_key.encode('utf-8'), md5, hashlib.sha1).digest()
        signa = base64.b64encode(signa)
        signa = str(signa, 'utf-8')
        param_dict = {}
        param_dict['app_id'] = self.appid
        param_dict['signa'] = signa
        param_dict['ts'] = ts
        param_dict['task_id'] = self.task_id
        return param_dict

    def gene_request(self, apiname, data, files=None, headers=None):
        response = requests.post(lfasr_host + apiname, data=data, files=files, headers=headers)
        result = json.loads(response.text)
        if result["ok"] == 0:
            return result
        else:
            raise InvestError(6100, detail="{} error:".format(apiname) + str(result))


    def all_api_request(self):
        # 4 . 获取任务进度
        progress = self.gene_request(api_get_progress, data=self.gene_params())
        progress_dic = progress
        if progress_dic['err_no'] != 0 and progress_dic['err_no'] != 26605:
            # print('task error: ' + progress_dic['failed'])
            raise InvestError(6100, detail='task error: ' + progress_dic['failed'])
        else:
            data = progress_dic['data']
            task_status = json.loads(data)
            if task_status['status'] == 9:
                # 5 . task 完成， 获取结果
                return {'task_status': task_status, 'result': self.gene_request(api_get_result, data=self.gene_params())}
            else:
                # task 未完成，返回task状态
                return {'task_status': task_status}



class AudioTranslateTaskRecordView(viewsets.ModelViewSet):
    """
        list:        获取所有转换记录
        audioFileTranslateToWord: 创建转换任务
        getAudioFileTranslateToWordTaskResult: 获取转换结果
        update: 编辑 转换结果内容、发言人数量
    """
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    filter_fields = ('cretateUserId', 'taskStatus', 'file_key')
    search_fields = ('file_name',)
    queryset = AudioTranslateTaskRecord.objects.all().filter(is_deleted=False)
    serializer_class = AudioTranslateTaskRecordSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)  # 从第一页开始
            queryset = self.filter_queryset(self.get_queryset())
            count = queryset.count()
            try:
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count': count, 'data': serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['third.addaudiotranslatetask'])
    def audioFileTranslateToWord(self, request, *args, **kwargs):
        try:
            speaker_number = request.data.get('speaker_number', 0)
            uploaddata = request.FILES.get('file')
            dirpath = APILOG_PATH['audioTranslateFile']
            file_key = request.data.get('key')
            if not file_key:
                filetype = str(uploaddata.name).split('.')[-1]
                randomPrefix = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + ''.join(
                    random.sample(string.ascii_lowercase, 6))
                file_key = randomPrefix + '.' + filetype
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)
            file_Path = os.path.join(dirpath, file_key)
            with open(file_Path, 'wb+') as destination:
                for chunk in uploaddata.chunks():
                    destination.write(chunk)
            api = TransferRequestApi(upload_file_path=file_Path, speaker_number=speaker_number)
            task_id = api.all_api_request()
            instance = AudioTranslateTaskRecord(task_id=task_id, file_key=file_key, file_name=uploaddata.name,
                                     speaker_number=speaker_number, cretateUserId=request.user.id)
            instance.save()
            return JSONResponse(SuccessResponse(self.serializer_class(instance).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def getAudioFileTranslateToWordTaskResult(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.taskStatus != '9':
                task_id = instance.task_id
                api = GetResultRequestApi(task_id=task_id)
                res = api.all_api_request()
                instance.taskStatus = res['task_status']['status']
                if res.get('result'):
                    instance.onebest = res['result']['data']
                instance.save()
            return JSONResponse(SuccessResponse(self.serializer_class(instance).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.cretateUserId == request.user.id or request.user.is_superuser:
                pass
            else:
                raise InvestError(2009, msg='没有权限编辑', detail='非创建人无法编辑文字内容')
            with transaction.atomic():
                data = request.data
                serializer = AudioTranslateTaskRecordUpdateSerializer(instance, data=data)
                if serializer.is_valid():
                    instance = serializer.save()
                else:
                    raise InvestError(20071, msg='%s' % serializer.error_messages)
                return JSONResponse(SuccessResponse(self.serializer_class(instance).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


def getAudioFileTranslateTaskResult(trans_id):
    try:
        trans_ins = AudioTranslateTaskRecord.objects.get(is_deleted=False, id=trans_id)
        return trans_ins.onebest
    except Exception:
        return '未找到语音转换任务'

