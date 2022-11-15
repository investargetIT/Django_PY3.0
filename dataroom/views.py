#coding=utf-8
import json
import subprocess
import threading
import traceback
import sys

import pdfrw
from django.core.paginator import Paginator, EmptyPage
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import F, QuerySet, Q, Count, Max
from django.http import StreamingHttpResponse
from elasticsearch import Elasticsearch
from rest_framework import filters, viewsets

from dataroom.models import dataroom, dataroomdirectoryorfile, publicdirectorytemplate, dataroom_User_file, \
    dataroom_User_template, dataroomUserSeeFiles, dataroom_user_discuss, dataroom_user_readFileRecord
from dataroom.serializer import DataroomSerializer, DataroomCreateSerializer, DataroomdirectoryorfileCreateSerializer, \
    DataroomdirectoryorfileSerializer, DataroomdirectoryorfileUpdateSerializer, User_DataroomfileSerializer, \
    User_DataroomSerializer, User_DataroomfileCreateSerializer, User_DataroomTemplateSerializer, \
    User_DataroomTemplateCreateSerializer, DataroomdirectoryorfilePathSerializer, User_DataroomSeefilesSerializer, \
    User_DataroomSeefilesCreateSerializer, DataroomUserDiscussSerializer, DataroomUserDiscussCreateSerializer, \
    DataroomUserDiscussUpdateSerializer, DataroomUserReadFileRecordSerializer
from invest.settings import APILOG_PATH, HAYSTACK_CONNECTIONS
from proj.models import project
from third.views.qiniufile import deleteqiniufile, downloadFileToPath
from utils.customClass import InvestError, JSONResponse, RelationFilter, MySearchFilter
from utils.logicJudge import is_dataroomTrader, is_dataroomInvestor, is_projTrader
from utils.sendMessage import sendmessage_dataroomuseradd, sendmessage_dataroomuserfileupdate
from utils.somedef import file_iterator, addWaterMarkToPdfFiles, encryptPdfFilesWithPassword, getEsScrollResult
from utils.util import returnListChangeToLanguage, loginTokenIsAvailable, \
    returnDictChangeToLanguage, catchexcption, SuccessResponse, InvestErrorResponse, ExceptionResponse, \
    logexcption, checkrequesttoken, deleteExpireDir
import datetime
from django_filters import FilterSet
import os
import shutil

class DataroomFilter(FilterSet):
    supportuser = RelationFilter(filterstr='proj__supportUser',lookup_method='in')
    user = RelationFilter(filterstr='dataroom_users__user', lookup_method='in', relationName='dataroom_users__is_deleted')
    username = RelationFilter(filterstr='dataroom_users__user__usernameC', lookup_method='icontains', relationName='dataroom_users__is_deleted')
    proj = RelationFilter(filterstr='proj', lookup_method='in')
    realname = RelationFilter(filterstr='proj__realname', lookup_method='icontains')
    title = RelationFilter(filterstr='proj__projtitleC', lookup_method='icontains')
    isClose = RelationFilter(filterstr='isClose', lookup_method='in')
    isCompanyFile = RelationFilter(filterstr='isCompanyFile', lookup_method='in')
    class Meta:
        model = dataroom
        fields = ('proj', 'isClose', 'supportuser', 'user', 'isCompanyFile', 'realname', 'title', 'username',)

class DataroomView(viewsets.ModelViewSet):
    """
       list:dataroom列表
       create:新建dataroom
       retrieve:查看dataroom目录结构
       update:关闭dataroom
       destroy:删除dataroom
       checkZipStatus: 开始打包压缩任务
       downloadDataroomZip: 下载压缩包
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = dataroom.objects.all().filter(is_deleted=False)
    filter_class = DataroomFilter
    serializer_class = DataroomSerializer

    def get_object(self):
        lookup_url_kwarg = 'pk'
        try:
            obj = dataroom.objects.get(id=self.kwargs[lookup_url_kwarg], is_deleted=False)
        except dataroom.DoesNotExist:
            raise InvestError(code=6002, msg='获取dataroom失败', detail='dataroom with this "%s" is not exist' % self.kwargs[lookup_url_kwarg])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取dataroom失败')
        return obj


    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')
            lang = request.GET.get('lang')
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.get_queryset().filter(datasource=self.request.user.datasource)
            if not request.user.has_perm('dataroom.get_companydataroom'):
                queryset = queryset.filter(isCompanyFile=False)
            if request.user.has_perm('dataroom.admin_managedataroom'):
                queryset = queryset
            elif request.user.has_perm('usersys.as_trader'):
                queryset = queryset.filter(Q(proj__PM=request.user) | Q(proj__proj_traders__user=request.user, proj__proj_traders__is_deleted=False)
                                           | Q(isCompanyFile=True, proj__indGroup=request.user.indGroup)
                                           | Q(isCompanyFile=True, proj__indGroup__in=request.user.user_indgroups.all().values_list('indGroup', flat=True))
                                           | Q(isCompanyFile=True, proj__indGroup__isnull=True))
            else:
                queryset = queryset.filter(dataroom_users__in=request.user.user_datarooms.filter(), dataroom_users__is_deleted=False)
            queryset = self.filter_queryset(queryset).distinct()
            sort = request.GET.get('sort')
            if sort not in ['True', 'true', True, 1, 'Yes', 'yes', 'YES', 'TRUE']:
                queryset = queryset.order_by('-lastmodifytime', '-createdtime')
            else:
                queryset = queryset.order_by('lastmodifytime', 'createdtime')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = DataroomSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            projid = data.get('proj',None)
            if not projid:
                raise InvestError(20072, msg='创建dataroom失败', detail='项目不能为空' )
            try:
                proj = project.objects.get(id=projid,datasource=request.user.datasource,is_deleted=False)
            except project.DoesNotExist:
                raise InvestError(4002, msg='创建dataroom失败', detail='项目不存在')
            if proj.projstatus_id < 4:
                raise InvestError(5003, msg='创建dataroom失败', detail='项目尚未终审发布')
            with transaction.atomic():
                if request.user.has_perm('dataroom.admin_managedataroom') or is_projTrader(request.user, projid):
                    pass
                else:
                    raise InvestError(2009, msg='创建dataroom失败')
                publicdataroom = self.get_queryset().filter(proj=proj)
                if publicdataroom.exists():
                    responsedataroom = DataroomCreateSerializer(publicdataroom.first()).data
                else:
                    dataroomdata = {'proj': projid, 'datasource': request.user.datasource.id, 'createuser': request.user.id}
                    publicdataroomserializer = DataroomCreateSerializer(data=dataroomdata)
                    if publicdataroomserializer.is_valid():
                        publicdataroom = publicdataroomserializer.save()
                        creatpublicdataroomdirectorywithtemplate(request.user, publicdataroomid=publicdataroom.id)
                        responsedataroom = publicdataroomserializer.data
                    else:
                        raise InvestError(20071, msg='创建dataroom失败', detail=publicdataroomserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(responsedataroom, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            serializer = DataroomdirectoryorfileSerializer(dataroomdirectoryorfile.objects.filter(is_deleted=False, dataroom=instance, isFile=False), many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    #关闭/打开dataroom
    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, instance):
                pass
            else:
                raise InvestError(2009, msg='关闭dataroom失败')
            instance.isClose = not instance.isClose
            instance.closeDate=datetime.datetime.now()
            instance.save()
            return JSONResponse(
                SuccessResponse(returnListChangeToLanguage(DataroomSerializer(instance).data)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, instance):
                pass
            else:
                raise InvestError(2009, msg='删除dataroom失败')
            with transaction.atomic():
                instance.dataroom_directories.all().update(is_deleted=True, deletedtime=datetime.datetime.now())
                for fileOrDirectory in instance.dataroom_directories.all():
                    fileOrDirectory.file_userSeeFile.all().update(is_deleted=True)
                    deleteInstance(fileOrDirectory, request.user)
                instance.dataroom_users.all().update(is_deleted=True)
                instance.dataroom_userTemp.all().update(is_deleted=True)
                instance.dataroom_userdiscuss.all().update(is_deleted=True)
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(returnListChangeToLanguage(DataroomSerializer(instance).data)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def checkZipStatus(self, request, *args, **kwargs):
        try:
            deleteExpireDir(APILOG_PATH['dataroomFilePath'])
            dataroominstance = self.get_object()
            files = request.GET.get('files')
            userid = int(request.GET.get('user', request.user.id))
            password = request.GET.get('password')
            nowater = True if request.GET.get('nowater') in ['1', 1, u'1'] else False
            is_adminPerm = True if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, dataroominstance) else False
            if nowater:
                zipfile_prefix = 'novirtual_dataroom'
                if (not is_adminPerm) and (not request.user.has_perm('dataroom.downloadNoWatermarkFile')):
                    raise InvestError(2009, msg='下载dataroom文件失败', detail='没有下载无水印文件权限')
            else:
                zipfile_prefix = 'virtual_dataroom'
            if userid != request.user.id:
                if is_adminPerm:
                    seefiles = dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile__dataroom=dataroominstance, dataroomUserfile__user_id=userid)
                    file_qs = dataroomdirectoryorfile.objects.filter(id__in=seefiles.values_list('file_id'))
                else:
                    raise InvestError(2009, msg='下载dataroom文件失败', detail='没有相关下载权限')
            else:
                if is_adminPerm:
                    file_qs = dataroominstance.dataroom_directories.all().filter(is_deleted=False, isFile=True)
                else:
                    if is_dataroomInvestor(request.user, dataroominstance.id):
                        seefiles = dataroomUserSeeFiles.objects.filter(is_deleted=False,
                                                                       dataroomUserfile__dataroom=dataroominstance,
                                                                       dataroomUserfile__user_id=userid)
                        file_qs = dataroomdirectoryorfile.objects.filter(id__in=seefiles.values_list('file_id'))
                    else:
                        raise InvestError(2009, msg='下载dataroom文件失败，没有相关下载权限', detail='没有相关下载权限')
            if files:
                files = files.split(',')
                file_qs = file_qs.filter(id__in=files)
                path = '%s_%s%s_part' % (zipfile_prefix, dataroominstance.id, ('_%s' % userid) if userid else '') + '.zip'  # 压缩文件名称
            else:
                path = '%s_%s%s' % (zipfile_prefix, dataroominstance.id, ('_%s' % userid) if userid else '') + '.zip'  # 压缩文件名称
            if not file_qs.exists():
                raise InvestError(20071, msg='下载dataroom文件失败，没有用户可见文件', detail='没有可见文件')
            zipfilepath = APILOG_PATH['dataroomFilePath'] + '/' + path  # 压缩文件路径
            direcpath = zipfilepath.replace('.zip', '')  # 文件夹路径
            if os.path.exists(zipfilepath):
                response = JSONResponse(SuccessResponse({'code': 8005, 'msg': '压缩文件已备好', 'seconds': 0}))
            else:
                if os.path.exists(direcpath):
                    seconds, all = getRemainingTime(direcpath)
                    response = JSONResponse(SuccessResponse({'code': 8004, 'msg': '压缩中', 'seconds': seconds, 'all': all}))
                else:
                    watermarkcontent = None if nowater else str(request.GET.get('water', '').replace('@', '[at]')).split(',')
                    directory_qs = dataroominstance.dataroom_directories.all().filter(is_deleted=False, isFile=False)
                    startMakeDataroomZipThread(directory_qs, file_qs, direcpath, watermarkcontent, password)
                    response = JSONResponse(SuccessResponse({'code': 8002, 'msg': '文件不存在', 'seconds': 999}))
            return response
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    def downloadDataroomZip(self, request, *args, **kwargs):
        try:
            userid = request.GET.get('user')
            request.user = checkrequesttoken(request.GET.get('token',None))
            dataroominstance = self.get_object()
            ispart = request.GET.get('part')
            nowater = True if request.GET.get('nowater') in ['1', 1, u'1'] else False
            is_adminPerm = True if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, dataroominstance) else False
            if nowater:
                zipfile_prefix = 'novirtual_dataroom'
                if (not is_adminPerm) and (not request.user.has_perm('dataroom.downloadNoWatermarkFile')):
                    raise InvestError(2009, msg='下载dataroom文件失败', detail='没有下载无水印文件权限')
            else:
                zipfile_prefix = 'virtual_dataroom'
            if int(userid) != request.user.id:
                if not is_adminPerm:
                    raise InvestError(2009, msg='下载dataroom文件失败', detail='没有相关下载权限')
            if ispart in ['1', 1, u'1']:
                path = '%s_%s%s_part' % (zipfile_prefix, dataroominstance.id, ('_%s' % userid) if userid else '') + '.zip'
            else:
                path = '%s_%s%s' % (zipfile_prefix, dataroominstance.id, ('_%s' % userid) if userid else '') + '.zip'
            zipFilepath = APILOG_PATH['dataroomFilePath'] + '/' + path
            direcpath = zipFilepath.replace('.zip','')
            if os.path.exists(zipFilepath):
                fn = open(zipFilepath, 'rb')
                response = StreamingHttpResponse(file_iterator(fn))
                zipFileSize = os.path.getsize(zipFilepath)
                response['Content-Length'] = zipFileSize
                if dataroom_User_file.objects.filter(dataroom=dataroominstance, user=request.user, is_deleted=False).exists():
                    dataroom_User_file.objects.filter(dataroom=dataroominstance, user=request.user, is_deleted=False).update(lastdowntime=datetime.datetime.now(), lastdownsize=zipFileSize / (1024 * 1024))
                response['Content-Type'] = 'application/octet-stream'
                response["content-disposition"] = 'attachment;filename=%s' % path
                if (zipFileSize < 10 * 1024 * 1024) or ispart in ['1', 1, u'1']:
                    os.remove(zipFilepath)  # 删除压缩包
                    if os.path.exists(direcpath):  # 删除源文件
                        shutil.rmtree(direcpath)
            else:
                if os.path.exists(direcpath):
                    response = JSONResponse(SuccessResponse({'code':8004, 'msg': '压缩中'}))
                else:
                    response = JSONResponse(SuccessResponse({'code':8002, 'msg': '文件不存在'}))
            return response
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

def getRemainingTime(rootpath):
    # 若文件大小丢失，则默认为 10 MB （10*1024*1024 bytes）
    downloadSpeed, encryptSpeed = 2 * 1024 * 1024, 2 * 1024 * 1024  # bytes/s
    progress_path = os.path.join(rootpath, 'zipProgress')
    time = 999
    all = 999
    if os.path.exists(progress_path):
        with open(progress_path, encoding='utf-8', mode='r') as load_f:
            load_data = json.load(load_f)
        time = load_data['unDownloadSize'] / downloadSpeed + load_data['unEncryptSize'] / encryptSpeed + 2
        all = load_data['allDownloadSize'] / downloadSpeed + load_data['allEncryptSize'] / encryptSpeed + 2
    return round(time, 2), round(all, 2)


def checkDirectoryLatestdate(direcory_path, file_qs):
    if os.path.exists(direcory_path):
        date = os.path.getctime(direcory_path)
        for file_obj in file_qs:
            path = getPathWithFile(file_obj, direcory_path)
            if os.path.exists(path):
                date_new = os.path.getctime(path)
                date = date_new if date_new > date else date
        date = datetime.datetime.fromtimestamp(date)
        if date < (datetime.datetime.now() - datetime.timedelta(hours=1)):
            shutil.rmtree(direcory_path)


def startMakeDataroomZipThread(directory_qs, file_qs, path, watermarkcontent=None, password=None):
    class downloadAllDataroomFile(threading.Thread):
        def __init__(self, directory_qs, file_qs, path):
            self.directory_qs = directory_qs
            self.file_qs = file_qs
            self.path = path
            self.progress_path = os.path.join(self.path, 'zipProgress')
            threading.Thread.__init__(self)

        def run(self):
            if os.path.exists(self.path):
                shutil.rmtree(self.path)
            os.makedirs(self.path)
            self.saveAllFileSize()
            self.downloadFiles()
            self.zipDirectory()

        def saveAllFileSize(self):
            fileSizes, encrySizes = 0, 0
            if password:
                for file_obj in self.file_qs:
                    fileSize = file_obj.size if file_obj.size else 10 * 1024 * 1024
                    if os.path.splitext(file_obj.filename)[-1] == '.pdf':
                        encrySizes = encrySizes + fileSize
                    fileSizes = fileSizes + fileSize
            else:
                for file_obj in self.file_qs:
                    fileSize = file_obj.size if file_obj.size else 10 * 1024 * 1024
                    fileSizes = fileSizes + fileSize
            data = {'unDownloadSize': fileSizes, 'allDownloadSize': fileSizes,
                    'unEncryptSize': encrySizes, 'allEncryptSize': encrySizes}
            with open(self.progress_path, encoding='utf-8', mode="w") as f:
                json.dump(data, f)

        def saveFileSize(self, size):
            with open(self.progress_path, encoding='utf-8', mode='r') as load_f:
                load_data = json.load(load_f)
            load_data['unDownloadSize'] = 0 if load_data['unDownloadSize'] < size else load_data['unDownloadSize'] - size
            with open(self.progress_path, encoding='utf-8', mode="w") as dump_f:
                json.dump(load_data, dump_f)


        def downloadFiles(self):
            makeDirWithdirectoryobjs(self.directory_qs, self.path)
            filepaths = []
            for file_obj in self.file_qs:
                path = getPathWithFile(file_obj, self.path)
                savepath = downloadFileToPath(key=file_obj.realfilekey, bucket=file_obj.bucket, path=path)
                filesize = file_obj.size if file_obj.size else 10 * 1024 * 1024
                self.saveFileSize(filesize)
                if savepath:
                    filetype = path.split('.')[-1]
                    if filetype in ['pdf', u'pdf']:
                        filepaths.append(path)
                else:
                    logexcption(msg='下载文件失败，保存路径：%s' % path)
            if len(filepaths) > 0:
                if watermarkcontent is not None:
                    addWaterMarkToPdfFiles(filepaths, watermarkcontent)
                if password:
                    print('开始加密')
                    subprocess.check_output([APILOG_PATH['encryptShellPythonVersion'], APILOG_PATH['encryptShellPath'], self.path, password, APILOG_PATH['excptionlogpath'],
                         APILOG_PATH['encryptPdfLogPath']])  # 执行完毕程序才会往下进行
                    print('加密完成')


        def zipDirectory(self):
            print('加密压缩')
            if not os.path.exists(self.path + '.zip'):
                import zipfile
                zipf = zipfile.ZipFile(self.path + '.zip', 'w')
                pre_len = len(os.path.dirname(self.path))
                for parent, dirnames, filenames in os.walk(self.path):
                    for filename in filenames:
                        pathfile = os.path.join(parent, filename)
                        if pathfile != self.progress_path:
                            arcname = pathfile[pre_len:].strip(os.path.sep)  # 相对路径
                            zipf.write(pathfile, arcname)
                zipf.close()

            if os.path.exists(self.path):
                shutil.rmtree(self.path)

    d = downloadAllDataroomFile(directory_qs, file_qs, path)
    d.start()

def makeDirWithdirectoryobjs(directory_objs ,rootpath):
    for file_obj in directory_objs:
        try:
            path = getPathWithFile(file_obj,rootpath)
            os.makedirs(path)
        except OSError:
            pass

def getPathWithFile(file_obj,rootpath,currentpath=None):
    if currentpath is None:
        currentpath = file_obj.filename
    if file_obj.parent is None:
        return rootpath + '/' + currentpath
    else:
        currentpath = file_obj.parent.filename + '/' + currentpath
        return getPathWithFile(file_obj.parent, rootpath, currentpath)


def downloadDataroomFiles(hours):
    createstart = datetime.datetime.now() - datetime.timedelta(hours=hours)
    file_qs = dataroomdirectoryorfile.objects.filter(is_deleted=False, isFile=True, dataroom__is_deleted=False, createdtime__gt=createstart)
    for fileInstance in file_qs:
        try:
            dataroomPath = os.path.join(APILOG_PATH['es_dataroomPDFPath'], 'dataroom_{}'.format(fileInstance.dataroom_id))
            if not os.path.exists(dataroomPath):
                os.makedirs(dataroomPath)
            file_path = os.path.join(dataroomPath,  fileInstance.key)
            filename, type = os.path.splitext(file_path)
            if type in ['.pdf', '.docx', '.doc', '.png', '.jpg', '.jpeg', '.txt'] and not os.path.exists(file_path):
                downloadFileToPath(key=fileInstance.key, bucket=fileInstance.bucket, path=file_path)
                fileInstance.save()
        except Exception:
            logexcption()

class DataroomdirectoryorfileFilter(FilterSet):
    dataroom = RelationFilter(filterstr='dataroom', lookup_method='in')
    parent = RelationFilter(filterstr='parent', lookup_method='in')
    isFile = RelationFilter(filterstr='isFile', lookup_method='in')
    id = RelationFilter(filterstr='id', lookup_method='in')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')
    stime = RelationFilter(filterstr='createdtime', lookup_method='gte')
    etime = RelationFilter(filterstr='createdtime', lookup_method='lt')
    stimeM = RelationFilter(filterstr='lastmodifytime', lookup_method='gte')
    etimeM = RelationFilter(filterstr='lastmodifytime', lookup_method='lt')
    class Meta:
        model = dataroomdirectoryorfile
        fields = ('dataroom', 'parent', 'isFile', 'id', 'createuser', 'stime', 'etime', 'stimeM', 'etimeM')

class DataroomdirectoryorfileView(viewsets.ModelViewSet):
    """
@ -479,7 +487,7 @@ class DataroomdirectoryorfileView(viewsets.ModelViewSet):
        """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = dataroomdirectoryorfile.objects.all().filter(is_deleted=False)
    filter_class = DataroomdirectoryorfileFilter
    serializer_class = DataroomdirectoryorfileCreateSerializer
    Model = dataroomdirectoryorfile

    def get_object(self,pk=None):
        if pk:
            try:
                obj = self.Model.objects.get(id=pk, is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='获取dataroom文件失败', detail='directory or file with this id is not exist')
        else:
            try:
                obj = self.Model.objects.get(id=self.kwargs['pk'], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='获取dataroom文件失败', detail='directory or file with this id is not exist')
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取dataroom文件失败')
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang',None)
            sortfield = request.GET.get('sort', 'createdtime')
            if request.GET.get('desc', 1) in ('1', u'1', 1):
                sortfield = '-' + sortfield
            dataroomid = request.GET.get('dataroom',None)
            if dataroomid is None or not dataroom.objects.filter(id=dataroomid).exists():
                raise InvestError(code=20072, msg='获取dataroom文件失败', detail='dataroom不能为空或者不存在')
            dataroominstance = dataroom.objects.get(id=dataroomid, is_deleted=False)
            queryset = self.get_queryset().filter(datasource=self.request.user.datasource)
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, dataroominstance):
                pass
            elif is_dataroomInvestor(request.user, dataroominstance.id):
                user_dataroomInstance = dataroom_User_file.objects.filter(user=request.user, dataroom__id=dataroomid, is_deleted=False).first()
                queryset = queryset.filter(file_userSeeFile__dataroomUserfile=user_dataroomInstance, file_userSeeFile__is_deleted=False)
            else:
                raise InvestError(2009, msg='获取该dataroom文件失败')
            queryset = self.filter_queryset(queryset).order_by(sortfield)
            count = queryset.count()
            serializer = DataroomdirectoryorfileSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def getFilePath(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang', None)
            dataroomid = request.GET.get('dataroom', None)
            if dataroomid is None:
                raise InvestError(code=20072, msg='获取dataroom文件路径失败', detail='dataroom 不能空')
            dataroominstance = dataroom.objects.get(id=dataroomid, is_deleted=False)
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, dataroominstance):
                queryset = self.get_queryset()
            elif is_dataroomInvestor(request.user, dataroominstance.id):
                user_dataroomInstance = dataroom_User_file.objects.filter(user=request.user, dataroom__id=dataroomid, is_deleted=False).first()
                queryset = self.get_queryset().filter(file_userSeeFile__dataroomUserfile=user_dataroomInstance, file_userSeeFile__is_deleted=False)
            else:
                raise InvestError(2009, msg='获取dataroom文件路径失败', detail='没有权限查看该dataroom')
            queryset = self.filter_queryset(queryset)
            search = request.GET.get('search', '')
            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "bool": {
                                    "must": [{"term": {"django_ct": "dataroom.dataroomdirectoryorfile"}},
                                             {"term": {"dataroom": int(dataroomid)}}]
                                },
                            },
                            {
                                "bool": {
                                    "should": [
                                        {"match_phrase": {"filename": search}},
                                        {"match_phrase": {"fileContent": search}}
                                    ]
                                }
                            }
                        ]
                    }
                },
                "_source": ["id", "dataroom", "filename", "django_ct"]
            }
            results = getEsScrollResult(search_body)
            searchIds = set()
            for source in results:
                searchIds.add(source['_source']['id'])
            file_qs = queryset.filter(Q(id__in=searchIds) | Q(filename__icontains=search))
            count = file_qs.count()
            serializer = DataroomdirectoryorfilePathSerializer(file_qs, many=True)
            return JSONResponse(SuccessResponse({'count': count, 'data': returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            dataroomid = data.get('dataroom', None)
            dataroominstance = dataroom.objects.get(id=dataroomid, is_deleted=False)
            if not data.get('createuser'):
                data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, dataroominstance):
                pass
            else:
                raise InvestError(2009, msg='上传dataroom文件失败', detail='没有上传文件的权限')
            if data.get('parent', None):
                parentfile = self.get_object(data['parent'])
                if parentfile.isFile:
                    raise InvestError(7007, msg='上传dataroom文件失败', detail='parent非文件夹类型')
                if parentfile.dataroom_id != dataroomid:
                    raise InvestError(7011, msg='上传dataroom文件失败', detail='dataroom下没有该目录')
            with transaction.atomic():
                directoryorfileserializer = DataroomdirectoryorfileCreateSerializer(data=data)
                if directoryorfileserializer.is_valid():
                    directoryorfile = directoryorfileserializer.save()
                else:
                    raise InvestError(20071, msg='上传dataroom文件失败', detail='%s' % directoryorfileserializer.error_messages)
                if directoryorfile.parent is not None:
                    destquery = directoryorfile.parent.asparent_directories.exclude(pk=directoryorfile.pk).filter(is_deleted=False,orderNO__gte=directoryorfile.orderNO)
                    if destquery.exists():
                        destquery.update(orderNO = F('orderNO') + 1)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(DataroomdirectoryorfileSerializer(directoryorfile).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            fileid = data.pop('id',None)
            if fileid is None:
                raise InvestError(20072, msg='修改dataroom文件信息失败', detail='fileid cannot be null')
            file = self.get_object(fileid)
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, file.dataroom):
                pass
            else:
                raise InvestError(2009, msg='修改dataroom文件信息失败')
            data['lastmodifyuser'] = request.user.id
            data['lastmodifytime'] = datetime.datetime.now()
            if data.get('dataroom', None):
                if file.dataroom_id != data.get('dataroom', None):
                    raise InvestError(7011, msg='修改dataroom文件信息失败', detail='不能移动到其他dataroom下')
            if data.get('parent', None):
                parentfile = self.get_object(data['parent'])
                if parentfile.dataroom != file.dataroom:
                    raise InvestError(7011, msg='修改dataroom文件信息失败', detail='不能移动到其他dataroom文件夹下')
                if parentfile.isFile:
                    raise InvestError(7007, msg='修改dataroom文件信息失败', detail='parent非文件夹类型')
            with transaction.atomic():
                directoryorfileserializer = DataroomdirectoryorfileUpdateSerializer(file,data=data)
                if directoryorfileserializer.is_valid():
                    directoryorfile = directoryorfileserializer.save()
                else:
                    raise InvestError(20071, msg='修改dataroom文件信息失败', detail='%s'% directoryorfileserializer.errors)
                if directoryorfile.parent is not None and data.get('orderNo', None):
                    destquery = directoryorfile.parent.asparent_directories.exclude(pk=directoryorfile.pk).filter(is_deleted=False,orderNO__gte=directoryorfile.orderNO)
                    if destquery.exist():
                        destquery.update(orderNO = F('orderNO')+ 1)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(directoryorfileserializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            filelist = request.data.get('filelist',None)
            if not isinstance(filelist,list) or not filelist:
                raise InvestError(20071, msg='删除dataroom文件失败', detail='except a non-empty array')
            with transaction.atomic():
                for fileid in filelist:
                    try:
                        instance = dataroomdirectoryorfile.objects.get(id=fileid, is_deleted=False)
                    except dataroomdirectoryorfile.DoesNotExist:
                        continue
                    if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, instance.dataroom):
                        pass
                    else:
                        raise InvestError(2009, msg='删除dataroom文件信息失败', detail='没有删除文件的权限')
                    instance.file_userSeeFile.all().update(is_deleted=True)
                    deleteInstance(instance, request.user)
                return JSONResponse(SuccessResponse(filelist))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class User_DataroomfileFilter(FilterSet):
    dataroom = RelationFilter(filterstr='dataroom',lookup_method='in')
    user = RelationFilter(filterstr='user', lookup_method='in')
    realname = RelationFilter(filterstr='dataroom__proj__realname', lookup_method='icontains')
    title = RelationFilter(filterstr='dataroom__proj__projtitleC', lookup_method='icontains')
    class Meta:
        model = dataroom_User_file
        fields = ('dataroom', 'user', 'realname', 'title',)

class User_DataroomfileView(viewsets.ModelViewSet):
    """
           list:用户dataroom列表
           getUserUpdateFiles: 获取用户新增文件列表
           create:新建用户-dataroom关系
           retrieve:查看该dataroom用户可见文件列表
           update:编辑该dataroom用户可见文件列表
           sendEmailNotifaction:发送邮件通知
           sendFileUpdateEmailNotifaction:发送文件更新邮件通知
           destroy:减少用户可见dataroom
        """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = dataroom_User_file.objects.all().filter(is_deleted=False,dataroom__isClose=False,dataroom__is_deleted=False)
    filter_class = User_DataroomfileFilter
    serializer_class = User_DataroomfileCreateSerializer
    Model = dataroom_User_file

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            if self.request.user.is_authenticated:
                queryset = queryset.filter(datasource_id=self.request.user.datasource_id)
            else:
                queryset = queryset
        else:
            raise InvestError(code=8890)
        return queryset

    def get_object(self,pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk, is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='获取dataroom用户失败', detail='dataroom-user with this "%s" is not exist' % pk)
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='获取dataroom用户失败', detail='dataroom-user with this （"%s"） is not exist' % self.kwargs['pk'])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取dataroom用户失败')
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang', 'cn')
            user = request.GET.get('user',None)
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('dataroom.admin_managedataroom'):
                pass
            else:
                queryset = queryset.filter(Q(user=request.user) | Q(dataroom__proj__PM=request.user) | Q(dataroom__proj__proj_traders__user=request.user, dataroom__proj__proj_traders__is_deleted=False)).distinct()
            count = queryset.count()
            serializer = User_DataroomSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom'):
                serializerclass = User_DataroomfileSerializer
            elif request.user == instance.user:
                serializerclass = User_DataroomfileSerializer
            elif is_dataroomTrader(request.user, instance.dataroom):
                serializerclass = User_DataroomfileSerializer
            else:
                raise InvestError(code=2009, msg='查看dataroom用户信息失败')
            serializer = serializerclass(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def getUserUpdateFiles(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            dataroom_id = request.GET.get('dataroom')
            if not dataroom_id:
                raise InvestError(20072, msg='获取dataroom用户近期更新文件失败', detail='dataroom不能为空')
            user_id = request.GET.get('user', request.user.id)
            qs = self.get_queryset().filter(dataroom_id=dataroom_id,user_id=user_id)
            if qs.exists():
                instance = qs.first()
            else:
                raise InvestError(20071, msg='获取dataroom用户近期更新文件失败', detail='dataroom用户不存在')
            if instance.lastgettime:
                files_queryset = dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile=instance, createdtime__gte=instance.lastgettime)
            else:
                files_queryset = dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile=instance)
            if request.user == instance.user:
                instance.lastgettime = datetime.datetime.now()
                instance.save()
            elif request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, instance.dataroom):
                pass
            else:
                raise InvestError(code=2009, msg='获取dataroom用户近期更新文件失败')
            files = dataroomdirectoryorfile.objects.filter(id__in=files_queryset.values_list('file_id'))
            serializer = DataroomdirectoryorfilePathSerializer(files, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            dataroomid = data['dataroom']
            dataroominstance = dataroom.objects.get(is_deleted=False, id=dataroomid, datasource=request.user.datasource)
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, dataroominstance):
                pass
            else:
                raise InvestError(2009, msg='新增dataroom用户失败')
            with transaction.atomic():
                data['datasource'] = request.user.datasource_id
                data['createuser'] = request.user.id
                user_dataroomserializer = User_DataroomfileCreateSerializer(data=data)
                if user_dataroomserializer.is_valid():
                    user_dataroomserializer.save()
                else:
                    raise InvestError(20071, msg='新增dataroom用户失败', detail='%s' % user_dataroomserializer.error_messages)
                return JSONResponse(SuccessResponse(user_dataroomserializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def sendEmailNotifaction(self,  request, *args, **kwargs):
        try:
            user_dataroom = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, user_dataroom.dataroom):
                pass
            else:
                raise InvestError(2009, msg='发送dataroom邮件通知失败')
            sendmessage_dataroomuseradd(user_dataroom, user_dataroom.user, ['email', 'webmsg'], sender=request.user)
            return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def sendFileUpdateEmailNotifaction(self, request, *args, **kwargs):
        try:
            user_dataroom = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, user_dataroom.dataroom):
                pass
            else:
                raise InvestError(2009, msg='获取dataroom用户文件更新邮件通知失败')
            sendmessage_dataroomuserfileupdate(user_dataroom, user_dataroom.user, ['email', 'webmsg'], sender=request.user)
            return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            user_dataroom = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, user_dataroom.dataroom):
                pass
            else:
                raise InvestError(2009, msg='修改dataroom用户信息失败')
            with transaction.atomic():
                user_dataroomserializer = User_DataroomfileCreateSerializer(user_dataroom, data=data)
                if user_dataroomserializer.is_valid():
                    user_dataroomserializer.save()
                else:
                    raise InvestError(20071, msg='修改dataroom用户信息失败', detail='%s' % user_dataroomserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(user_dataroomserializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            user_dataroom = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, user_dataroom.dataroom):
                pass
            else:
                raise InvestError(2009, msg='删除dataroom用户失败')
            with transaction.atomic():
                user_dataroom.deletedtime = datetime.datetime.now()
                user_dataroom.deleteduser = request.user
                user_dataroom.is_deleted = True
                user_dataroom.save()
                user_dataroom.dataroomuser_seeFiles.all().filter(is_deleted=False).update(is_deleted=True, deleteduser=request.user, deletedtime=datetime.datetime.now())
                user_dataroom.user_dataroomTempFiles.all().filter(is_deleted=False).update(is_deleted=True, deleteduser=request.user, deletedtime=datetime.datetime.now())
                return JSONResponse(SuccessResponse({'isDeleted':True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class DataroomUserSeeFilesFilter(FilterSet):
    dataroom = RelationFilter(filterstr='dataroomUserfile__dataroom')
    user = RelationFilter(filterstr='dataroomUserfile__user')
    file = RelationFilter(filterstr='file', lookup_method='in')
    class Meta:
        model = dataroomUserSeeFiles
        fields = ('dataroom', 'user', 'file')

class User_DataroomSeefilesView(viewsets.ModelViewSet):
    """
           list:用户dataroom可见文件列表
           create:新建用户可见文件
           destroy:删除用户某可见文件
        """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = dataroomUserSeeFiles.objects.all().filter(is_deleted=False, dataroomUserfile__is_deleted=False)
    filter_class = DataroomUserSeeFilesFilter
    serializer_class = User_DataroomSeefilesSerializer
    Model = dataroom_User_file

    def get_object(self,pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk, is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='获取dataroom用户文件失败', detail='用户没有该可见文件（%s）' % pk)
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='获取dataroom用户文件失败', detail='用户没有该可见文件（%s）' % self.kwargs['pk'])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取dataroom用户文件失败')
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang', 'cn')
            dataroomid = request.GET.get('dataroom')
            if not dataroomid:
                raise InvestError(20072, msg='获取dataroom用户文件失败', detail='dataroom不能为空')
            dataroominstance = dataroom.objects.get(is_deleted=False, id=dataroomid, datasource=request.user.datasource)
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, dataroominstance):
                queryset = self.filter_queryset(self.get_queryset())
            else:
                queryset = self.filter_queryset(self.get_queryset()).filter(dataroomUserfile__user=request.user, dataroomUserfile__dataroom=dataroominstance)
            count = queryset.count()
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            dataroomid = data['dataroom']
            dataroominstance = dataroom.objects.get(is_deleted=False, id=dataroomid, datasource=request.user.datasource)
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, dataroominstance):
                pass
            else:
                raise InvestError(2009, msg='新增dataroom用户文件失败')
            with transaction.atomic():
                data['createuser'] = request.user.id
                user_dataroomserializer = User_DataroomSeefilesCreateSerializer(data=data)
                if user_dataroomserializer.is_valid():
                    user_dataroomserializer.save()
                else:
                    raise InvestError(20071, msg='新增dataroom用户文件失败', detail='%s' % user_dataroomserializer.error_messages)
                return JSONResponse(SuccessResponse(user_dataroomserializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            user_seefile = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, user_seefile.dataroomUserfile.dataroom):
                pass
            else:
                raise InvestError(2009, msg='删除dataroom用户文件失败')
            with transaction.atomic():
                user_seefile.is_deleted = True
                user_seefile.deleteduser = request.user
                user_seefile.save()
                return JSONResponse(SuccessResponse({'isDeleted':True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



# dataroom 公共函数
# 创建public模板
def creatpublicdataroomdirectorywithtemplate(user, publicdataroomid):
    class creatpublicdataroomdirectory_Thread(threading.Thread):
        def __init__(self, user, publicdataroomid):
            self.user = user
            self.publicdataroomid = publicdataroomid
            threading.Thread.__init__(self)

        def create_diractory(self, user, directoryname, dataroom, templatedirectoryID, orderNO, parent=None):
            directoryobj = dataroomdirectoryorfile(filename=directoryname, dataroom_id=dataroom, orderNO=orderNO,
                                                   parent_id=parent, createdtime=datetime.datetime.now(),
                                                   createuser_id=user.id, datasource_id=user.datasource_id)
            directoryobj.save()
            sondirectoryquery = publicdirectorytemplate.objects.filter(parent=templatedirectoryID, is_deleted=False)
            if sondirectoryquery.exists():
                for sondirectory in sondirectoryquery:
                    self.create_diractory(user, directoryname=sondirectory.name, dataroom=dataroom,
                                     templatedirectoryID=sondirectory.id, orderNO=sondirectory.orderNO,
                                     parent=directoryobj.id)

        def run(self):
            templatequery = publicdirectorytemplate.objects.filter(is_deleted=False)
            topdirectories = templatequery.filter(parent=None)
            if topdirectories.exists():
                for directory in topdirectories:
                    self.create_diractory(self.user, directoryname=directory.name, dataroom=self.publicdataroomid,
                                     templatedirectoryID=directory.id, orderNO=directory.orderNO, parent=None)

    creatpublicdataroomdirectory_Thread(user, publicdataroomid).start()


def pulishProjectCreateDataroom(proj, user):
    try:
        queryset = dataroom.objects.filter(is_deleted=False, datasource=user.datasource)
        publicdataroom = queryset.filter(proj=proj)
        if publicdataroom.exists():
            pass
        else:
            dataroomdata = {}
            dataroomdata['proj'] = proj.id
            dataroomdata['datasource'] = user.datasource_id
            dataroomdata['createuser'] = user.id
            publicdataroomserializer = DataroomCreateSerializer(data=dataroomdata)
            if publicdataroomserializer.is_valid():
                publicdataroom = publicdataroomserializer.save()
                creatpublicdataroomdirectorywithtemplate(user, publicdataroomid=publicdataroom.id)
    except Exception:
        logexcption(msg='public创建失败')
        pass


def deleteInstance(instance, deleteuser):
    if instance.isFile:
        bucket = instance.bucket
        key = instance.key
        realkey = instance.realfilekey
        instance.delete()
        deleteqiniufile(bucket, key)
        deleteqiniufile(bucket, realkey)
    else:
        filequery = instance.asparent_directories.filter(is_deleted=False)
        if filequery.count():
            for fileordirectoriey in filequery:
                deleteInstance(fileordirectoriey, deleteuser)
        instance.is_deleted = True
        instance.deleteduser = deleteuser
        instance.deletedtime = datetime.datetime.now()
        instance.save()


class User_Dataroom_TemplateView(viewsets.ModelViewSet):
    """
           list: 用户dataroom文件模板列表
           create: 新建用户dataroom文件模板
           retrieve: 查看用户dataroom文件模板
           update: 编辑用户dataroom文件模板
           userTempToUser: 将模板应用到用户
           destroy: 删除用户dataroom文件模板
        """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = dataroom_User_template.objects.all().filter(is_deleted=False, dataroom__isClose=False, dataroom__is_deleted=False)
    filter_fields = ('dataroom', 'user')
    serializer_class = User_DataroomTemplateSerializer
    Model = dataroom_User_template

    def get_object(self, pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk, is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=8892, msg='获取dataroom用户文件模板失败', detail='dataroom_User_template with this "%s" is not exist' % pk)
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=8892, msg='获取dataroom用户文件模板失败', detail='dataroom_User_template with this （"%s"） is not exist' % self.kwargs['pk'])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取dataroom用户文件模板失败')
        return obj


    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=request.user.datasource)
            if request.user.has_perm('dataroom.admin_managedataroom'):
                pass
            else:
                queryset = queryset.filter(Q(user=request.user) | Q(dataroom__proj__PM=request.user) | Q(dataroom__proj__proj_traders__user=request.user, dataroom__proj__proj_traders__is_deleted=False)).distinct()
            count = queryset.count()
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, instance.dataroom):
                pass
            elif request.user == instance.user:
                pass
            else:
                raise InvestError(code=2009, msg='查看该dataroom用户文件模板失败')
            serializer = self.serializer_class(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            dataroomid = data['dataroom']
            dataroominstance = dataroom.objects.get(is_deleted=False, id=dataroomid, datasource=request.user.datasource)
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, dataroominstance):
                pass
            else:
                raise InvestError(2009, msg='新增dataroom用户文件模板失败')
            with transaction.atomic():
                data['datasource'] = request.user.datasource_id
                data['createuser'] = request.user.id
                user_dataroomserializer = User_DataroomTemplateCreateSerializer(data=data)
                if user_dataroomserializer.is_valid():
                    instance = user_dataroomserializer.save()
                    if 'password' in data:
                        dataroom_User_template.objects.filter(is_deleted=False, dataroom=instance.dataroom).update(password=instance.password)
                else:
                    raise InvestError(20071, msg='新增dataroom用户文件模板失败', detail='%s' % user_dataroomserializer.error_messages)
                return JSONResponse(SuccessResponse(user_dataroomserializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def userTempToUser(self, request, *args, **kwargs):
        try:
            data = request.data
            user_id = data['user']
            user_dataroom_temp = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, user_dataroom_temp.dataroom):
                pass
            else:
                raise InvestError(code=2009, msg='应用dataroom用户文件模板失败')
            try:           # 文件模板应用到用户文件
                user_dataroom = dataroom_User_file.objects.get(is_deleted=False, user_id=user_id, dataroom=user_dataroom_temp.dataroom)
            except dataroom_User_file.DoesNotExist:
                raise InvestError(20071, msg='获取dataroom用户文件模板失败', detail='用户不在模板dataroom中，请先将用户添加至dataroom中。')
            else:
                oldFiles = dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile=user_dataroom, file__isnull=False)
                allFiles = dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile=user_dataroom_temp.dataroomUserfile, file__isnull=False)
                addFiles = allFiles.exclude(file__in=oldFiles.values_list('file'))
                removeFiles = oldFiles.exclude(file__in=allFiles.values_list('file'))
                deleteTime = datetime.datetime.now()
                for seefile in addFiles:
                    dataroomUserSeeFiles(dataroomUserfile=user_dataroom, file=seefile.file, createuser=request.user).save()
                for seefile in removeFiles:
                    seefile.is_deleted = True
                    seefile.deleteduser = request.user
                    seefile.deletedtime = deleteTime
                    seefile.save()
            return JSONResponse(SuccessResponse(User_DataroomfileSerializer(user_dataroom).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            user_dataroom_temp = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, user_dataroom_temp.dataroom):
                pass
            else:
                raise InvestError(2009, msg='修改dataroom用户文件模板失败')
            with transaction.atomic():
                user_dataroomtempserializer = User_DataroomTemplateCreateSerializer(user_dataroom_temp, data=data)
                if user_dataroomtempserializer.is_valid():
                    instance = user_dataroomtempserializer.save()
                    if 'password' in data:
                        dataroom_User_template.objects.filter(is_deleted=False, dataroom=instance.dataroom).update(password=instance.password)
                else:
                    raise InvestError(20071, msg='修改dataroom用户文件模板失败', detail='%s' % user_dataroomtempserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(user_dataroomtempserializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            user_dataroom_temp = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, user_dataroom_temp.dataroom):
                pass
            else:
                raise InvestError(code=2009, msg='删除dataroom用户文件模板失败')
            with transaction.atomic():
                user_dataroom_temp.delete()
                return JSONResponse(SuccessResponse({'isDeleted':True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))




class DataroomUserDiscussFilter(FilterSet):
    dataroom = RelationFilter(filterstr='dataroom', lookup_method='in')
    user = RelationFilter(filterstr='user', lookup_method='in')
    file = RelationFilter(filterstr='file', lookup_method='in')
    class Meta:
        model = dataroom_user_discuss
        fields = ('dataroom', 'user', 'file')

class DataroomUserDiscussView(viewsets.ModelViewSet):
    """
        list: 获取文件的标注信息列表（普通过滤）
        listGroupBy: 获取有标注的dataroom/file列表（groupby（dataroom）/(file)）
        create: 用户发起提问/标注
        update: 交易师回复提问/标注
        destroy: 删除标注
        """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = dataroom_user_discuss.objects.all().filter(is_deleted=False, file__is_deleted=False, dataroom__is_deleted=False)
    filter_class = DataroomUserDiscussFilter
    serializer_class = DataroomUserDiscussSerializer
    Model = dataroom_user_discuss

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            if self.request.user.is_authenticated:
                queryset = queryset.filter(datasource_id=self.request.user.datasource_id)
            else:
                queryset = queryset
        else:
            raise InvestError(code=8890)
        return queryset

    def get_object(self, pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk, is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='获取dataroom用户文件标注信息失败', detail='用户没有标注文件（%s）' % pk)
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='获取dataroom用户文件标注信息失败', detail='用户没有标注文件（%s）' % self.kwargs['pk'])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取dataroom用户文件标注信息失败')
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('dataroom.admin_managedataroom'):
                queryset = queryset
            else:
                queryset = queryset.filter(Q(file__in=dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile__user=request.user).values_list('file')) | Q(dataroom__proj__PM=request.user) |
                                           Q(dataroom__proj__proj_traders__user=request.user, dataroom__proj__proj_traders__is_deleted=False)).distinct()
            sortfield = request.GET.get('sort', 'lastmodifytime')
            desc = request.GET.get('desc', 1)
            if desc in ('1', u'1', 1):
                sortfield = '-' + sortfield
            queryset = queryset.order_by(sortfield)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count, 'data': returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def listGroupBy(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            group_by =  request.GET.get('by', 'dataroom')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('dataroom.admin_managedataroom'):
                queryset = queryset
            else:
                queryset = queryset.filter(Q(file__in=dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile__user=request.user).values_list('file')) | Q(dataroom__proj__PM=request.user) |
                                           Q(dataroom__proj__proj_traders__user=request.user, dataroom__proj__proj_traders__is_deleted=False)).distinct()
            queryset = queryset.values(group_by).annotate(count=Count('id', distinct=True))
            try:
                count = len(queryset)
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = json.dumps(list(queryset), cls=DjangoJSONEncoder)
            return JSONResponse(SuccessResponse({'count': count, 'data': json.loads(serializer)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            if not data.get('file'):
                raise InvestError(20072, msg='新增dataroom用户文件标注信息失败', detail='文件不能为空')
            if not dataroomUserSeeFiles.objects.filter(is_deleted=False, file_id=data['file'], dataroomUserfile__user=request.user).exists():
                raise InvestError(2009, msg='新增dataroom用户文件标注信息失败', detail='只有可见文件可以添加标注')
            with transaction.atomic():
                data['user'] = request.user.id
                data['createuser'] = request.user.id
                data['asktime'] = datetime.datetime.now()
                user_dataroomserializer = DataroomUserDiscussCreateSerializer(data=data)
                if user_dataroomserializer.is_valid():
                    user_dataroomserializer.save()
                else:
                    raise InvestError(20071, msg='新增dataroom用户文件标注信息失败', detail='%s' % user_dataroomserializer.errors)
                return JSONResponse(SuccessResponse(user_dataroomserializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            data = request.data
            discussInstance = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, discussInstance.dataroom):
                pass
            else:
                raise InvestError(2009, msg='回复dataroom用户文件标注信息失败', detail='只有承揽承做可以回复标注')
            with transaction.atomic():
                data['trader'] = request.user.id
                data['lastmodifyuser'] = request.user.id
                data['answertime'] = datetime.datetime.now()
                user_dataroomserializer = DataroomUserDiscussUpdateSerializer(discussInstance, data=data)
                if user_dataroomserializer.is_valid():
                    user_dataroomserializer.save()
                else:
                    raise InvestError(20071, msg='回复dataroom用户文件标注信息失败', detail='%s' % user_dataroomserializer.error_messages)
                return JSONResponse(SuccessResponse(user_dataroomserializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('dataroom.admin_managedataroom') or is_dataroomTrader(request.user, instance.dataroom):
                pass
            elif request.user == instance.user:
                pass
            else:
                raise InvestError(2009, msg='删除dataroom用户文件标注信息失败')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.save()
                return JSONResponse(SuccessResponse({'isDeleted':True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



class DataroomUserReadFileRecordFilter(FilterSet):
    dataroom = RelationFilter(filterstr='file__dataroom', lookup_method='in')
    user = RelationFilter(filterstr='user', lookup_method='in')
    file = RelationFilter(filterstr='file', lookup_method='in')
    class Meta:
        model = dataroom_user_readFileRecord
        fields = ('dataroom', 'user', 'file')

class DataroomUserReadFileRecordView(viewsets.ModelViewSet):
    """
        list: 获取用户读取文件时间列表
        create: 记录用户读取时间开始/结束
        """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = dataroom_user_readFileRecord.objects.all().filter(is_deleted=False, file__is_deleted=False)
    filter_class = DataroomUserReadFileRecordFilter
    serializer_class = DataroomUserReadFileRecordSerializer
    Model = dataroom_user_readFileRecord

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            if self.request.user.is_authenticated:
                queryset = queryset.filter(user__datasource_id=self.request.user.datasource_id)
            else:
                queryset = queryset
        else:
            raise InvestError(code=8890)
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('dataroom.admin_managedataroom'):
                queryset = queryset
            else:
                queryset = queryset.filter(Q(file__in=dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile__user=request.user).values_list('file')) | Q(file__dataroom__proj__PM=request.user) |
                                           Q(file__dataroom__proj__proj_traders__user=request.user, file__dataroom__proj__proj_traders__is_deleted=False)).distinct()
            sortfield = request.GET.get('sort', 'lastmodifytime')
            desc = request.GET.get('desc', 1)
            if desc in ('1', u'1', 1):
                sortfield = '-' + sortfield
            queryset = queryset.order_by(sortfield)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(
                SuccessResponse({'count': count, 'data': returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            type = request.data.get('type', 0)
            if type in ('0', u'0', 0):
                timeField = 'startTime'
            else:
                timeField = 'endTime'
            with transaction.atomic():
                requestTime = datetime.datetime.now()
                file = request.data.get('file')
                if self.queryset.filter(file=file, user=request.user).exists():
                    instance = self.queryset.filter(file=file, user=request.user).first()
                    instance.__dict__.update(**{timeField: requestTime})
                    instance.save()
                else:
                    data = {'user': request.user.id, 'file': file, timeField: requestTime}
                    serializer = self.serializer_class(data=data)
                    if serializer.is_valid():
                        serializer.save()
                    else:
                        raise InvestError(20071, msg='记录dataroom用户读取文件日期失败', detail='%s' % serializer.errors)
                return JSONResponse(SuccessResponse({timeField: requestTime}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))
