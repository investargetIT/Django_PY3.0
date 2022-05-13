#coding=utf-8
# Create your views here.
import datetime
import hashlib
import json
import os
import random
import shutil
import string
import threading
import traceback
from subprocess import TimeoutExpired
from urllib.parse import unquote

import qiniu
import requests
from django.core.cache import caches

from qiniu import BucketManager
from qiniu.services.storage.uploader import _Resume, put_file, put_stream
from rest_framework.decorators import api_view
from invest.settings import APILOG_PATH
from third.thirdconfig import qiniu_url, ACCESS_KEY, SECRET_KEY, max_chunk_size
from utils.customClass import JSONResponse, InvestError, MyUploadProgressRecorder
from utils.util import InvestErrorResponse, ExceptionResponse, SuccessResponse, logexcption, checkRequestToken, \
    catchexcption


#覆盖上传
@api_view(['POST'])
def qiniu_coverupload(request):
    try:
        isChangeToPdf = request.GET.get('topdf', True)
        bucket_name = request.GET.get('bucket')
        key = request.GET.get('key')
        if not bucket_name or not key or bucket_name not in qiniu_url.keys():
            raise InvestError(2020,msg='bucket/key error')
        deleteqiniufile(bucket_name, key)
        uploaddata = request.FILES['file']
        q = qiniu.Auth(ACCESS_KEY, SECRET_KEY)
        filetype = str(uploaddata.name).split('.')[-1]
        randomPrefix = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + ''.join(random.sample(string.ascii_lowercase, 6))
        inputFileKey = randomPrefix + '.' + filetype
        outputFileKey = randomPrefix + '.' + 'pdf'
        token = q.upload_token(bucket_name, inputFileKey, 3600)
        ret, info = put_stream(token, inputFileKey, uploaddata, uploaddata.name, uploaddata.size)
        if info is not None:
            if info.status_code == 200:
                return_url = getUrlWithBucketAndKey(bucket_name, ret['key'])
            else:
                raise InvestError(2020, msg=str(info))
        else:
            raise InvestError(2020, msg=str(ret))
        if filetype in ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'] and isChangeToPdf in ['true', True, '1', 1, u'true']:
            key = outputFileKey
            dirpath = APILOG_PATH['uploadFilePath']
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)
            inputFilePath = os.path.join(dirpath, inputFileKey)
            outputFilePath = os.path.join(dirpath, outputFileKey)
            with open(inputFilePath, 'wb+') as destination:
                for chunk in uploaddata.chunks():
                    destination.write(chunk)
            convertAndUploadOfficeInThread(inputFilePath, outputFilePath, bucket_name, outputFileKey)
        else:
            key = inputFileKey
        return JSONResponse(SuccessResponse({'key': key, 'url': return_url, 'realfilekey': inputFileKey}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


@api_view(['POST'])
def bigfileupload(request):
    """
    文件上传
    """
    try:
        isChangeToPdf = request.GET.get('topdf', True)
        bucket_name = request.GET.get('bucket')
        if bucket_name not in qiniu_url.keys():
            raise InvestError(2020,msg='bucket error')
        uploaddata = request.FILES['file']
        q = qiniu.Auth(ACCESS_KEY, SECRET_KEY)
        filetype = str(uploaddata.name).split('.')[-1]
        randomPrefix = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + ''.join(
            random.sample(string.ascii_lowercase, 6))
        inputFileKey = randomPrefix + '.' + filetype
        outputFileKey = randomPrefix + '.' + 'pdf'
        token = q.upload_token(bucket_name, inputFileKey, 3600)
        ret, info = put_stream(token, inputFileKey, uploaddata, uploaddata.name, uploaddata.size)
        if info is not None:
            if info.status_code == 200:
                return_url = getUrlWithBucketAndKey(bucket_name, ret['key'])
            else:
                raise InvestError(2020, msg=str(info))
        else:
            raise InvestError(2020, msg=str(ret))
        if filetype in ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'] and isChangeToPdf in ['true', True, '1', 1, u'true']:
            key = outputFileKey
            dirpath = APILOG_PATH['uploadFilePath']
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)
            inputFilePath = os.path.join(dirpath, inputFileKey)
            outputFilePath = os.path.join(dirpath, outputFileKey)
            with open(inputFilePath, 'wb+') as destination:
                for chunk in uploaddata.chunks():
                    destination.write(chunk)
            convertAndUploadOfficeInThread(inputFilePath, outputFilePath, bucket_name, outputFileKey)
        else:
            key = inputFileKey
        return JSONResponse(SuccessResponse({'key':key,'url':return_url,'realfilekey':inputFileKey}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



@api_view(['POST'])
@checkRequestToken()
def fileChunkUpload(request):
    """
    文件分片上传
    """
    try:
        data = request.data
        file = {
            'name': unquote(data['filename']),
            'currentSize': data['currentSize'],
            'totalSize': data['totalSize'],
            'currentChunk': data['currentChunk'],
            'totalChunk': data['totalChunk'],
            'md5': data['md5'],
            'bucket': data['bucket'],
            'file': request.FILES['file']
        }
        if data.get('temp_key'):
            temp_key = data['temp_key']
        else:
            if file['currentChunk'] != '1':
                raise InvestError(8300, msg='文件上传失败', detail='非首个文件块，temp_key不能为空')
            temp_key = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + ''.join(random.sample(string.ascii_lowercase, 6))
        bucket_name = data.get('bucket')
        if bucket_name not in qiniu_url.keys():
            raise InvestError(8300, msg='文件上传失败', detail='无效的bucket')
        filetype = file['name'].split('.')[-1]
        file_path = os.path.join(APILOG_PATH['uploadFilePath'], '%s.%s' % (temp_key, filetype))
        print(file_path)
        file_path_temp = file_path + '.temp'
        if file['currentChunk'] == '1' and caches['default'].get(file_path):  # 同名文件上传冲突，不进行其它操作
            raise InvestError(8300, msg='文件上传失败', detail='同名文件正在上传')
        else:  # 标记文件正在上传
            caches['default'].set(file_path, 'uploading', 2)

        checkresponse = check_file(file, file_path, file_path_temp)
        # 文件上传失败或者上传完毕后，清理暂存文件和缓存
        if checkresponse['code'] != '0' or checkresponse['is_end']:
            remove_file(file_path_temp)
            caches['default'].delete_pattern(file_path + '*')
        if checkresponse['code'] == '0':
            if checkresponse['is_end']:
                if os.path.exists(file_path):
                    inputFileKey = temp_key + '.' + filetype
                    outputFileKey = temp_key + '.' + 'pdf'
                    if filetype in ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'] and data.get('topdf', True) in ['true', True, '1', 1, u'true']:
                        changeToPdf = True
                        outputFilePath = os.path.join(APILOG_PATH['uploadFilePath'], outputFileKey)
                        key = outputFileKey
                    else:
                        changeToPdf = False
                        outputFilePath = None
                        key = inputFileKey
                    qiniuuploadfileInThread(file_path, bucket_name, inputFileKey, changeToPdf, outputFilePath)
                    return JSONResponse(SuccessResponse({'key': key, 'url': getUrlWithBucketAndKey(bucket_name, key), 'realfilekey': inputFileKey, 'bucket':bucket_name}))
                else:
                    raise InvestError(8300, msg='文件上传失败', detail='上传文件丢失')
            else:
                return JSONResponse(SuccessResponse({'temp_key': temp_key, 'nextChunk': min(int(file['currentChunk']) + 1, int(file['totalChunk']))}))
        else:
            raise InvestError(8300, msg='文件上传失败', detail=checkresponse['msg'])
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


@api_view(['POST'])
def qiniu_uploadtoken(request):
    try:
        data = request.data
        bucket_name = data['bucket']
        key = data['key']
        if not bucket_name or not key:
            raise InvestError(2020,msg='bucket/key error')
        policy = data.get('policy',None)
        q = qiniu.Auth(ACCESS_KEY, SECRET_KEY)
        token = q.upload_token(bucket_name, key, 3600, policy=policy)
        return JSONResponse(SuccessResponse(token))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

@api_view(['POST'])
def qiniu_downloadurl(request):
    try:
        data = request.data
        bucket_name = data['bucket']
        key = data['key']
        return_url = getUrlWithBucketAndKey(bucket_name,key)
        return JSONResponse(SuccessResponse(return_url))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


@api_view(['POST'])
def qiniu_deletefile(request):
    """
    param：{'bucket':str,'key':str}
    """
    try:
        data = request.data
        bucket = data.get('bucket',None)
        key = data.get('key',None)
        if bucket not in qiniu_url.keys():
            return None
        ret, info = deleteqiniufile(bucket,key)
        if info.req_id is None or info.status_code != 200:
            raise InvestError(7010,msg=json.dumps(info.text_body))
        return JSONResponse(SuccessResponse('删除成功'))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

def deleteqiniufile(bucket,key):
    if bucket and key:
        q = qiniu.Auth(ACCESS_KEY, SECRET_KEY)
        bucketManager = BucketManager(q)
        ret, info = bucketManager.delete(bucket, key)
        return ret, info

def getUrlWithBucketAndKey(bucket,key):
    if bucket not in qiniu_url.keys():
        return None
    if key is None:
        return None
    q = qiniu.Auth(ACCESS_KEY, SECRET_KEY)
    return_url = "https://%s/%s" % (qiniu_url[bucket], key)
    if bucket == 'file':
        return_url = q.private_download_url(return_url)
    return return_url

#上传本地文件
def qiniuuploadfile(filepath, bucket_name, bucket_key=None):
    q = qiniu.Auth(ACCESS_KEY, SECRET_KEY)
    if not bucket_key:
        filetype = filepath.split('.')[-1]
        bucket_key = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + ''.join(random.sample(string.ascii_lowercase, 6)) + filetype
    token = q.upload_token(bucket_name, bucket_key, 3600, policy={}, strict_policy=True)
    ret, info = put_file(token, bucket_key, filepath, version='v2')
    if info is not None:
        if info.status_code == 200:
            return True, getUrlWithBucketAndKey(bucket_name, ret["key"]),bucket_key
        else:
            return False, str(info),None
    else:
        return False,None,None


#子线程上传本地文件
def qiniuuploadfileInThread(filepath, bucket_name, bucket_key, changeToPdf, outputFilePath):
    class qiniuuploadfileThread(threading.Thread):
        def run(self):
            try:
                q = qiniu.Auth(ACCESS_KEY, SECRET_KEY)
                uploading = True
                retry_times = 1
                while uploading and retry_times <= 3:
                    retry_times += 1
                    token = q.upload_token(bucket_name, bucket_key, 3600, policy={}, strict_policy=True)
                    ret, info = put_file(token, bucket_key, filepath, version='v2')
                    if info is not None:
                        if info.status_code == 200:
                            uploading = False
            except Exception:
                logexcption(msg='文件上传七牛服务器失败')
            if changeToPdf:
                convertAndUploadOffice(filepath, outputFilePath, bucket_name, bucket_key)
            if os.path.exists(filepath):
                os.remove(filepath)

    qiniuuploadfileThread().start()




#下载文件到本地
def downloadFileToPath(key,bucket,path):
    try:
        download_url = getUrlWithBucketAndKey(bucket, key)
        if download_url is None:
            raise InvestError(8002, msg='bucket/key error')
        r = requests.get(download_url)
        if r.status_code != 200:
            raise InvestError(8002, msg=repr(r.content))
        with open(path, "wb") as code:
            code.write(r.content)
    except Exception as err:
        logexcption(msg=str(err))
        return None
    else:
        return path



def convertAndUploadOfficeInThread(inputpath, outputpath, bucket_name, bucket_key):
    """
    :param inputpath: 源文件路径
    :param outputpath: 转化后文件路径
    :return:
    """
    class convertAndUploadOfficeThread(threading.Thread):
        def run(self):
            convertAndUploadOffice(inputpath, outputpath, bucket_name, bucket_key)


    convertAndUploadOfficeThread().start()


def convertAndUploadOffice(inputpath, outputpath, bucket_name, bucket_key):
    try:
        import subprocess
        subprocess.check_output(['python3', '/var/www/DocumentConverter.py', inputpath, outputpath], timeout=300)  # 执行完毕程序才会往下进行
    except ImportError:
        logexcption(msg='引入模块失败')
    except TimeoutExpired:
        logexcption(msg='文件转换超时')
    except Exception:
        logexcption(msg='文件转换失败')
    if os.path.exists(outputpath):
        success, url, key = qiniuuploadfile(outputpath, bucket_name, bucket_key)
        print(success, url, key)
        os.remove(outputpath)
    if os.path.exists(inputpath):
        os.remove(inputpath)


def get_md5(path):
    m = hashlib.md5()
    with open(path, 'rb') as f:
        for line in f:
            m.update(line)
    return m.hexdigest()


def remove_file(file_path):
    if not os.path.isfile(file_path):
        return
    os.remove(file_path)


def write_file(file_path_temp, file):
    if not os.path.isdir(os.path.dirname(file_path_temp)):
        os.makedirs(os.path.dirname(file_path_temp))
    try:
        with open(file_path_temp,  "ab") as destination:
            for chunk in file['file'].chunks():
                destination.write(chunk)
    except OSError as exc:
        return exc.errno


def check_file(file, file_path, file_path_temp):
    # is_end表示传输完毕了

    if file['currentChunk'] == '1' and os.path.exists(file_path_temp):
        remove_file(file_path_temp)  # 开始上传时删除已有的暂存文件
    elif file['currentChunk'] != '1' and not os.path.exists(file_path_temp):
        # 上传过程中暂存文件丢失
        return {'code': '1', 'msg': '暂存文件丢失，上传失败', 'is_end': True}

    # 校验文件内容及大小
    if not file['file']:
        return {'code': '1', 'msg': '不能上传空文件'}
    if not 0 < int(file['currentSize']) <= max_chunk_size:
        return {'code': '1', 'msg': '文件大小不符合要求'}
    # 校验文件大小
    file_size = len(file['file'])
    if not 0 < file_size <= max_chunk_size:
        return {'code': '1', 'msg': '文件大小不符合要求'}
    # 获得已传输的文件大小
    if os.path.exists(file_path_temp):
        file_size += os.path.getsize(file_path_temp)
    if (file['currentChunk'] == file['totalChunk'] and file_size != int(file['totalSize'])) or file_size > int(file['totalSize']):
        return {'code': '1', 'msg': '文件大小校验失败'}


    if file['currentChunk'] == file['totalChunk'] or file_size == int(file['totalSize']):  # 传输完毕的状态
        if write_file(file_path_temp, file) == 36:
            return {'code': '1', 'msg': '文件名过长'}
        shutil.move(file_path_temp, file_path)
        # 校验md5值，保证内容一致性
        if file['md5'] != get_md5(file_path):
            return {'code': '1', 'msg': '文件校验失败'}
        return {'code': '0', 'msg': '上传并提交成功', 'is_end': True}
    else:
        if write_file(file_path_temp, file) == 36:
            return {'code': '1', 'msg': '文件名过长'}
        return {'code': '0', 'msg': '上传并提交文件块成功', 'is_end': False}