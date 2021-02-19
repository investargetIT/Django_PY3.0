#coding=utf-8
import json
import threading
import traceback
import sys
from django.core.paginator import Paginator, EmptyPage
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import F, QuerySet, Q, Count, Max
from django.http import StreamingHttpResponse
from elasticsearch import Elasticsearch
from rest_framework import filters, viewsets

from dataroom.models import dataroom, dataroomdirectoryorfile, publicdirectorytemplate, dataroom_User_file, \
    dataroom_User_template, dataroomUserSeeFiles, dataroom_user_discuss
from dataroom.serializer import DataroomSerializer, DataroomCreateSerializer, DataroomdirectoryorfileCreateSerializer, \
    DataroomdirectoryorfileSerializer, DataroomdirectoryorfileUpdateSerializer, User_DataroomfileSerializer, \
    User_DataroomSerializer, User_DataroomfileCreateSerializer, User_DataroomTemplateSerializer, \
    User_DataroomTemplateCreateSerializer, DataroomdirectoryorfilePathSerializer, User_DataroomSeefilesSerializer, \
    User_DataroomSeefilesCreateSerializer, DataroomUserDiscussSerializer, DataroomUserDiscussCreateSerializer, \
    DataroomUserDiscussUpdateSerializer
from invest.settings import APILOG_PATH, HAYSTACK_CONNECTIONS
from proj.models import project
from third.views.qiniufile import deleteqiniufile, downloadFileToPath
from utils.customClass import InvestError, JSONResponse, RelationFilter
from utils.sendMessage import sendmessage_dataroomuseradd, sendmessage_dataroomuserfileupdate
from utils.somedef import file_iterator, addWaterMarkToPdfFiles, encryptPdfFilesWithPassword
from utils.util import returnListChangeToLanguage, loginTokenIsAvailable, \
    returnDictChangeToLanguage, catchexcption, SuccessResponse, InvestErrorResponse, ExceptionResponse, \
    logexcption, checkrequesttoken, deleteExpireDir
import datetime
from django_filters import FilterSet
import os
import shutil
reload(sys)
sys.setdefaultencoding("utf-8")

class DataroomFilter(FilterSet):
    supportuser = RelationFilter(filterstr='proj__supportUser',lookup_method='in')
    user = RelationFilter(filterstr='dataroom_users__user', lookup_method='in', relationName='dataroom_users__is_deleted')
    proj = RelationFilter(filterstr='proj', lookup_method='in')
    isClose = RelationFilter(filterstr='isClose', lookup_method='in')
    class Meta:
        model = dataroom
        fields = ('proj', 'isClose', 'supportuser', 'user')

class DataroomView(viewsets.ModelViewSet):
    """
       list:dataroom列表
       create:新建dataroom
       retrieve:查看dataroom目录结构
       update:关闭dataroom
       destroy:删除dataroom
    """
    filter_backends = (filters.SearchFilter,filters.DjangoFilterBackend,)
    queryset = dataroom.objects.all().filter(is_deleted=False)
    search_fields = ('proj__projtitleC', 'proj__projtitleE', 'proj__supportUser__usernameC', 'dataroom_users__user__usernameC')
    filter_class = DataroomFilter
    serializer_class = DataroomSerializer

    def get_object(self):
        lookup_url_kwarg = 'pk'
        try:
            obj = dataroom.objects.get(id=self.kwargs[lookup_url_kwarg], is_deleted=False)
        except dataroom.DoesNotExist:
            raise InvestError(code=6002,msg='dataroom with this "%s" is not exist' % self.kwargs[lookup_url_kwarg])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888)
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
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=self.request.user.datasource, isCompanyFile=False)
            sort = request.GET.get('sort')
            if sort not in ['True', 'true', True, 1, 'Yes', 'yes', 'YES', 'TRUE']:
                queryset = queryset.order_by('-lastmodifytime', '-createdtime')
            else:
                queryset = queryset.order_by('lastmodifytime', 'createdtime')
            if request.user.has_perm('dataroom.admin_getdataroom'):
                queryset = queryset
            else:
                queryset = queryset.filter(Q(dataroom_users__in=request.user.user_datarooms.filter(), dataroom_users__is_deleted=False) | Q(proj__proj_traders__user=request.user, proj__proj_traders__is_deleted=False)).distinct()
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
    def companylist(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=self.request.user.datasource, isCompanyFile=True)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = DataroomSerializer(queryset, many=True)
            return JSONResponse(
                SuccessResponse({'count': count, 'data': returnListChangeToLanguage(serializer.data, lang)}))
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
                raise InvestError(20072,msg='proj 不能为空 int类型')
            try:
                proj = project.objects.get(id=projid,datasource=request.user.datasource,is_deleted=False)
            except project.DoesNotExist:
                raise InvestError(code=4002)
            if proj.projstatus_id < 4:
                raise InvestError(5003, msg='项目尚未终审发布')
            with transaction.atomic():
                if proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                    pass
                elif request.user.has_perm('dataroom.admin_adddataroom'):
                    pass
                else:
                    raise InvestError(2009)
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
                        raise InvestError(code=20071, msg=publicdataroomserializer.errors)
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
            serializer = DataroomdirectoryorfileSerializer(dataroomdirectoryorfile.objects.filter(is_deleted=False,dataroom=instance,isFile=False),many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    #关闭/打开dataroom
    @loginTokenIsAvailable(['dataroom.admin_closedataroom'])
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.isClose = not instance.isClose
            instance.closeDate=datetime.datetime.now()
            instance.save()
            return JSONResponse(
                SuccessResponse(returnListChangeToLanguage(DataroomSerializer(instance).data)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['dataroom.admin_deletedataroom'])
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
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
            if nowater:
                zipfile_prefix = 'novirtual_dataroom'
                if not request.user.has_perm('dataroom.downloadNoWatermarkFile'):
                    raise InvestError(2009, msg='没有下载无水印文件权限')
            else:
                zipfile_prefix = 'virtual_dataroom'
            if userid != request.user.id:
                if request.user.has_perm('dataroom.admin_getdataroom') or dataroominstance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                    seefiles = dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile__dataroom=dataroominstance, dataroomUserfile__user_id=userid)
                    file_qs = dataroomdirectoryorfile.objects.filter(id__in=seefiles.values_list('file_id'))
                else:
                    raise InvestError(2009, msg='非管理员权限')
            else:
                if request.user.has_perm('dataroom.admin_getdataroom') or dataroominstance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                    file_qs = dataroominstance.dataroom_directories.all().filter(is_deleted=False, isFile=True)
                else:
                    if dataroom_User_file.objects.filter(dataroom=dataroominstance, user_id=userid, is_deleted=False).exists():
                        seefiles = dataroomUserSeeFiles.objects.filter(is_deleted=False,
                                                                       dataroomUserfile__dataroom=dataroominstance,
                                                                       dataroomUserfile__user_id=userid)
                        file_qs = dataroomdirectoryorfile.objects.filter(id__in=seefiles.values_list('file_id'))
                    else:
                        raise InvestError(2009, msg='没有权限查看该dataroom')
            if files:
                files = files.split(',')
                file_qs = file_qs.filter(id__in=files)
                path = '%s_%s%s_part' % (zipfile_prefix, dataroominstance.id, ('_%s' % userid) if userid else '') + '.zip'  # 压缩文件名称
            else:
                path = '%s_%s%s' % (zipfile_prefix, dataroominstance.id, ('_%s' % userid) if userid else '') + '.zip'  # 压缩文件名称
            if not file_qs.exists():
                raise InvestError(20071, msg='没有可见文件')
            zipfilepath = APILOG_PATH['dataroomFilePath'] + '/' + path  # 压缩文件路径
            direcpath = zipfilepath.replace('.zip', '')  # 文件夹路径
            if os.path.exists(zipfilepath):
                response = JSONResponse(SuccessResponse({'code': 8005, 'msg': '压缩文件已备好', 'seconds': 0}))
            else:
                checkDirectoryLatestdate(direcpath, file_qs)
                seconds = getRemainingTime(direcpath, file_qs)
                if os.path.exists(direcpath):
                    response = JSONResponse(SuccessResponse({'code': 8004, 'msg': '压缩中', 'seconds': seconds}))
                else:
                    watermarkcontent = None if nowater else str(request.GET.get('water', '').replace('@', '[at]')).split(',')
                    directory_qs = dataroominstance.dataroom_directories.all().filter(is_deleted=False, isFile=False)
                    startMakeDataroomZip(directory_qs, file_qs, direcpath, watermarkcontent, password)
                    response = JSONResponse(SuccessResponse({'code': 8002, 'msg': '文件不存在', 'seconds': seconds}))
            return response
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def downloadDataroomZip(self, request, *args, **kwargs):
        try:
            userid = request.GET.get('user')
            user = checkrequesttoken(request.GET.get('token',None))
            request.user = user
            ispart = request.GET.get('part')
            nowater = True if request.GET.get('nowater') in ['1', 1, u'1'] else False
            if nowater:
                zipfile_prefix = 'novirtual_dataroom'
                if not request.user.has_perm('dataroom.downloadNoWatermarkFile'):
                    raise InvestError(2009, msg='没有下载无水印文件权限')
            else:
                zipfile_prefix = 'virtual_dataroom'
            dataroominstance = self.get_object()
            if not user.has_perm('dataroom.downloadDataroom'):
                raise InvestError(2009)
            if int(userid) != user.id:
                if user.has_perm('dataroom.admin_changedataroom') or user.has_perm('dataroom.admin_adddataroom'):
                    pass
                elif dataroominstance.proj.proj_traders.all().filter(user=user, is_deleted=False).exists():
                    pass
                else:
                    raise InvestError(2009, msg='非管理员权限')
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
                response['Content-Type'] = 'application/octet-stream'
                response["content-disposition"] = 'attachment;filename=%s' % path
                if (zipFileSize < 10 * 1024 * 1024) or ispart in ['1', 1, u'1']:
                    os.remove(zipFilepath)            # 删除压缩包
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

def getRemainingTime(rootpath, file_qs):
    downloadSpeed = 2 * 1024 * 1024   # bytes/s
    filesizes = 0
    for file_obj in file_qs:
        path = getPathWithFile(file_obj, rootpath)
        filesize = file_obj.size if file_obj.size else 10 * 1024 * 1024   # 若文件大小丢失，则默认为 10 MB （10*1024*1024 bytes）
        if os.path.exists(path):
            if filesize > os.path.getsize(path):
                filesizes = filesizes + (filesize - os.path.getsize(path))
        else:
            filesizes = filesizes + filesize
    times = filesizes / downloadSpeed + 2
    return times


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


def startMakeDataroomZip(directory_qs, file_qs, path, watermarkcontent=None, password=None):
    class downloadAllDataroomFile(threading.Thread):
        def __init__(self, directory_qs, file_qs, path):
            self.directory_qs = directory_qs
            self.file_qs = file_qs
            self.path = path
            threading.Thread.__init__(self)

        def run(self):
            self.downloadFiles(self.file_qs)
            self.zipDirectory()

        def downloadFiles(self, files):
            if os.path.exists(self.path):
                shutil.rmtree(self.path)
            makeDirWithdirectoryobjs(self.directory_qs, self.path)
            filepaths = []
            for file_obj in files:
                path = getPathWithFile(file_obj, self.path)
                savepath = downloadFileToPath(key=file_obj.realfilekey, bucket=file_obj.bucket, path=path)
                if savepath:
                    filetype = path.split('.')[-1]
                    if filetype in ['pdf', u'pdf']:
                        filepaths.append(path)
                else:
                    logexcption(msg='下载文件失败，保存路径：%s' % path)
            if len(filepaths) > 0:
                if watermarkcontent is not None:
                    addWaterMarkToPdfFiles(filepaths, watermarkcontent)
                if password is not None:
                    encryptPdfFilesWithPassword(filepaths, password)

        def zipDirectory(self):
            import zipfile
            zipf = zipfile.ZipFile(self.path + '.zip', 'w')
            pre_len = len(os.path.dirname(self.path))
            for parent, dirnames, filenames in os.walk(self.path):
                for filename in filenames:
                    pathfile = os.path.join(parent, filename)
                    arcname = pathfile[pre_len:].strip(os.path.sep)  # 相对路径
                    zipf.write(pathfile, arcname)
            zipf.close()
            if os.path.exists(self.path):
                shutil.rmtree(self.path)

    d = downloadAllDataroomFile(directory_qs, file_qs, path)
    d.start()

def makeDirWithdirectoryobjs(directory_objs ,rootpath):
    if os.path.exists(rootpath):
        shutil.rmtree(rootpath)
    os.makedirs(rootpath)
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


def downloadDataroomPDFs():
    file_qs = dataroomdirectoryorfile.objects.filter(is_deleted=False, isFile=True, dataroom__is_deleted=False)
    for fileInstance in file_qs:
        try:
            dataroomPath = os.path.join(APILOG_PATH['es_dataroomPDFPath'], 'dataroom_{}'.format(fileInstance.dataroom_id))
            if not os.path.exists(dataroomPath):
                os.makedirs(dataroomPath)
            file_path = os.path.join(dataroomPath,  fileInstance.realfilekey)
            filename, type = os.path.splitext(file_path)
            if type == '.pdf' and not os.path.exists(file_path):
                downloadFileToPath(key=fileInstance.realfilekey, bucket=fileInstance.bucket, path=file_path)
                fileInstance.save()
        except Exception:
            logexcption()


class DataroomdirectoryorfileView(viewsets.ModelViewSet):
    """
           list:dataroom文件或目录列表
           create:新建dataroom文件或目录
           update:移动目录或文件到目标位置
           destroy:删除dataroom文件或目录
           getFilePath: 获取文件路径
        """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = dataroomdirectoryorfile.objects.all().filter(is_deleted=False)
    filter_fields = ('dataroom', 'parent','isFile')
    serializer_class = DataroomdirectoryorfileCreateSerializer
    Model = dataroomdirectoryorfile

    def get_object(self,pk=None):
        if pk:
            try:
                obj = self.Model.objects.get(id=pk, is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='dataroom with this "%s" is not exist' % pk)
        else:
            try:
                obj = self.Model.objects.get(id=self.kwargs['pk'], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002,msg='dataroom with this （"%s"） is not exist' % self.kwargs['pk'])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888)
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang',None)
            dataroomid = request.GET.get('dataroom',None)
            if dataroomid is None:
                raise InvestError(code=20072,msg='dataroom 不能空')
            dataroominstance = dataroom.objects.get(id=dataroomid, is_deleted=False)
            if request.user.has_perm('dataroom.admin_getdataroom'):
                pass
            elif dataroominstance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            elif dataroominstance.isCompanyFile and request.user.has_perm('dataroom.get_companydataroom'):
                pass
            else:
                raise InvestError(2009)
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=self.request.user.datasource)
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
                raise InvestError(code=20072, msg='dataroom 不能空')
            dataroominstance = dataroom.objects.get(id=dataroomid, is_deleted=False)
            if request.user.has_perm('dataroom.admin_getdataroom') or dataroominstance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists() or (dataroominstance.isCompanyFile and request.user.has_perm('dataroom.get_companydataroom')):
                queryset = self.get_queryset()
            elif dataroom_User_file.objects.filter(user=request.user, dataroom=dataroomid).exists():
                user_dataroomInstance = dataroom_User_file.objects.filter(user=request.user, dataroom__id=dataroomid).first()
                queryset = user_dataroomInstance.file_userSeeFile.all().filter(is_deleted=False)
            else:
                raise InvestError(2009)
            queryset = self.filter_queryset(queryset).filter(isFile=True)
            fileid_list = list(queryset.values_list('id', flat=True))
            search = request.GET.get('search', '')
            es = Elasticsearch({HAYSTACK_CONNECTIONS['default']['URL']})
            ret = es.search(index=HAYSTACK_CONNECTIONS['default']['INDEX_NAME'],
                            body={
                                    "_source": ["id", "dataroom", "filename"],
                                    "query": {
                                        "bool": {
                                            "must":[
                                                {"terms": {"id": fileid_list}},
                                                {"bool": {"should": [
                                                            {"match_phrase": {"fileContent": search}}
                                                ]}}
                                            ]
                                        }
                                    }
                            })
            searchIds = set()
            for source in ret["hits"]["hits"]:
                searchIds.add(source['_source']['id'])
            file_qs = queryset.filter(Q(id__in=searchIds) | Q(filename__icontains=search))
            count = file_qs.count()
            serializer = DataroomdirectoryorfilePathSerializer(file_qs, many=True)
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
            data = request.data
            lang = request.GET.get('lang')
            dataroomid = data.get('dataroom', None)
            dataroominstance = dataroom.objects.get(id=dataroomid, is_deleted=False)
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            if request.user.has_perm('dataroom.admin_adddataroom'):
                pass
            elif request.user.has_perm('dataroom.user_adddataroomfile'):
                if dataroominstance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                    pass
                else:
                    raise InvestError(2009, msg='非承揽承做无法上传文件')
            else:
                raise InvestError(2009, msg='没有上传文件的权限')
            if data.get('parent', None):
                parentfile = self.get_object(data['parent'])
                if parentfile.isFile:
                    raise InvestError(7007, msg='非文件夹类型')
                if parentfile.dataroom_id != dataroomid:
                    raise InvestError(7011, msg='dataroom下没有该目录')
            with transaction.atomic():
                directoryorfileserializer = DataroomdirectoryorfileCreateSerializer(data=data)
                if directoryorfileserializer.is_valid():
                    directoryorfile = directoryorfileserializer.save()
                else:
                    raise InvestError(code=20071, msg='data有误_%s' % directoryorfileserializer.errors)
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
                raise InvestError(2007,msg='fileid cannot be null')
            file = self.get_object(fileid)
            if file.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            elif request.user.has_perm('dataroom.admin_changedataroom'):
                pass
            else:
                raise InvestError(2009)
            data['lastmodifyuser'] = request.user.id
            data['lastmodifytime'] = datetime.datetime.now()
            if data.get('dataroom', None):
                if file.dataroom_id != data.get('dataroom', None):
                    raise InvestError(7011, msg='不能移动到其他dataroom下')
            if data.get('parent', None):
                parentfile = self.get_object(data['parent'])
                if parentfile.dataroom != file.dataroom:
                    raise InvestError(7011, msg='不能移动到其他dataroom下')
                if parentfile.isFile:
                    raise InvestError(7007, msg='非文件夹类型')
            with transaction.atomic():
                directoryorfileserializer = DataroomdirectoryorfileUpdateSerializer(file,data=data)
                if directoryorfileserializer.is_valid():
                    directoryorfile = directoryorfileserializer.save()
                else:
                    raise InvestError(code=20071, msg='data有误_%s'% directoryorfileserializer.errors)
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
                raise InvestError(code=20071,msg='need an id list')
            with transaction.atomic():
                for fileid in filelist:
                    instance = self.get_object(fileid)
                    if request.user.has_perm('dataroom.admin_deletedataroom'):
                        pass
                    elif request.user.has_perm('dataroom.user_deletedataroomfile'):
                        if instance.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                            pass
                        else:
                            raise InvestError(2009, msg='非承揽承做无法删除文件')
                    else:
                        raise InvestError(2009, msg='没有删除文件的权限')
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
    class Meta:
        model = dataroom_User_file
        fields = ('dataroom', 'user')

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
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    queryset = dataroom_User_file.objects.all().filter(is_deleted=False,dataroom__isClose=False,dataroom__is_deleted=False)
    filter_class = User_DataroomfileFilter
    search_fields = ('dataroom__proj__projtitleC','dataroom__proj__projtitleE')
    serializer_class = User_DataroomfileCreateSerializer
    Model = dataroom_User_file

    def get_object(self,pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk, is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='dataroom-user with this "%s" is not exist' % pk)
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002,msg='dataroom-user with this （"%s"） is not exist' % self.kwargs['pk'])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888)
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang', 'cn')
            user = request.GET.get('user',None)
            if request.user.has_perm('dataroom.admin_getdataroom'):
                filters = {'datasource':request.user.datasource}
                queryset = self.filter_queryset(self.get_queryset()).filter(**filters)
            else:
                if user:
                    if user != request.user.id:
                        raise InvestError(2009)
                queryset = self.filter_queryset(self.get_queryset()).filter(Q(datasource=request.user.datasource,user=request.user) | Q(dataroom__proj__proj_traders__user=request.user, dataroom__proj__proj_traders__is_deleted=False))
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
            if request.user.has_perm('dataroom.admin_getdataroom'):
                serializerclass = User_DataroomfileSerializer
            elif request.user == instance.user:
                serializerclass = User_DataroomfileSerializer
            elif instance.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                serializerclass = User_DataroomfileSerializer
            else:
                raise InvestError(code=2009)
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
                raise InvestError(code=2007, msg='dataroom不能为空')
            user_id = request.GET.get('user', request.user.id)
            qs = self.get_queryset().filter(dataroom_id=dataroom_id,user_id=user_id)
            if qs.exists():
                instance = qs.first()
            else:
                raise InvestError(code=2007, msg='dataroom用户不存在')
            if instance.lastgettime:
                files_queryset = dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile=instance, createdtime__gte=instance.lastgettime)
            else:
                files_queryset = dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile=instance)
            if request.user == instance.user:
                instance.lastgettime = datetime.datetime.now()
                instance.save()
            elif request.user.has_perm('dataroom.admin_getdataroom') or instance.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(code=2009)
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
            if dataroominstance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            elif request.user.has_perm('dataroom.admin_adddataroom'):
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                data['datasource'] = request.user.datasource_id
                data['createuser'] = request.user.id
                user_dataroomserializer = User_DataroomfileCreateSerializer(data=data)
                if user_dataroomserializer.is_valid():
                    user_dataroomserializer.save()
                else:
                    raise InvestError(code=20071, msg='data有误_%s' % user_dataroomserializer.errors)
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
            if request.user.has_perm('dataroom.admin_adddataroom'):
                pass
            elif user_dataroom.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
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
            if request.user.has_perm('dataroom.admin_adddataroom'):
                pass
            elif user_dataroom.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
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
            if request.user.has_perm('dataroom.admin_changedataroom'):
                pass
            elif user_dataroom.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                user_dataroomserializer = User_DataroomfileCreateSerializer(user_dataroom, data=data)
                if user_dataroomserializer.is_valid():
                    user_dataroomserializer.save()
                else:
                    raise InvestError(code=20071, msg='data有误_%s' % user_dataroomserializer.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(user_dataroomserializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['dataroom.admin_deletedataroom'])
    def destroy(self, request, *args, **kwargs):
        try:
            user_dataroom = self.get_object()
            if request.user.has_perm('dataroom.admin_deletedataroom'):
                pass
            elif user_dataroom.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
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
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    queryset = dataroomUserSeeFiles.objects.all().filter(is_deleted=False, dataroomUserfile__is_deleted=False)
    filter_class = DataroomUserSeeFilesFilter
    serializer_class = User_DataroomSeefilesSerializer
    Model = dataroom_User_file

    def get_object(self,pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk, is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='用户没有该可见文件（%s）' % pk)
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='用户没有该可见文件（%s）' % self.kwargs['pk'])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888)
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang', 'cn')
            dataroomid = request.GET.get('dataroom')
            if not dataroomid:
                raise InvestError(2007, msg='dataroom 参数不能为空')
            dataroominstance = dataroom.objects.get(is_deleted=False, id=dataroomid, datasource=request.user.datasource)
            if request.user.has_perm('dataroom.admin_getdataroom') or dataroominstance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
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
            if dataroominstance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            elif request.user.has_perm('dataroom.admin_adddataroom'):
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                data['createuser'] = request.user.id
                user_dataroomserializer = User_DataroomSeefilesCreateSerializer(data=data)
                if user_dataroomserializer.is_valid():
                    user_dataroomserializer.save()
                else:
                    raise InvestError(code=20071, msg='data有误_%s' % user_dataroomserializer.errors)
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
            if user_seefile.dataroomUserfile.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            elif request.user.has_perm('dataroom.admin_adddataroom'):
                pass
            else:
                raise InvestError(2009)
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
    templatequery = publicdirectorytemplate.objects.all()
    topdirectories = templatequery.filter(parent=None)
    if topdirectories.exists():
        for directory in topdirectories:
            create_diractory(user, directoryname=directory.name, dataroom=publicdataroomid,
                             templatedirectoryID=directory.id, orderNO=directory.orderNO, parent=None)


def create_diractory(user, directoryname, dataroom, templatedirectoryID, orderNO, parent=None):
    directoryobj = dataroomdirectoryorfile(filename=directoryname, dataroom_id=dataroom, orderNO=orderNO,
                                           parent_id=parent, createdtime=datetime.datetime.now(), createuser_id=user.id,
                                           datasource_id=user.datasource_id)
    directoryobj.save()
    sondirectoryquery = publicdirectorytemplate.objects.filter(parent=templatedirectoryID)
    if sondirectoryquery.exists():
        for sondirectory in sondirectoryquery:
            create_diractory(user, directoryname=sondirectory.name, dataroom=dataroom,
                             templatedirectoryID=sondirectory.id, orderNO=sondirectory.orderNO, parent=directoryobj.id)


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
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    queryset = dataroom_User_template.objects.all().filter(is_deleted=False, dataroom__isClose=False, dataroom__is_deleted=False)
    filter_fields = ('dataroom', 'user')
    serializer_class = User_DataroomTemplateSerializer
    Model = dataroom_User_template

    def get_object(self, pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk, is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=8892, msg='dataroom_User_template with this "%s" is not exist' % pk)
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=8892,msg='dataroom_User_template with this （"%s"） is not exist' % self.kwargs['pk'])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888)
        return obj


    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang', 'cn')
            if request.user.has_perm('dataroom.admin_getdataroom'):
                filters = {'datasource':request.user.datasource}
                queryset = self.filter_queryset(self.get_queryset()).filter(**filters)
            else:
                queryset = self.filter_queryset(self.get_queryset()).filter(Q(datasource=request.user.datasource, user=request.user) | Q(dataroom__proj__proj_traders__user=request.user, dataroom__proj__proj_traders__is_deleted=False))
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
            if request.user.has_perm('dataroom.admin_getdataroom'):
                pass
            elif instance.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists() or request.user == instance.user:
                pass
            else:
                raise InvestError(code=2009)
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
            if dataroominstance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            elif request.user.has_perm('dataroom.admin_adddataroom'):
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                data['datasource'] = request.user.datasource_id
                data['createuser'] = request.user.id
                user_dataroomserializer = User_DataroomTemplateCreateSerializer(data=data)
                if user_dataroomserializer.is_valid():
                    instance = user_dataroomserializer.save()
                    if data.has_key('password'):
                        dataroom_User_template.objects.filter(is_deleted=False, dataroom=instance.dataroom).update(password=instance.password)
                else:
                    raise InvestError(code=20071, msg='data有误_%s' % user_dataroomserializer.errors)
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
            if request.user.has_perm('dataroom.admin_changedataroom'):
                pass
            elif user_dataroom_temp.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(code=2009)
            try:           # 文件模板应用到用户文件
                user_dataroom = dataroom_User_file.objects.get(is_deleted=False, user_id=user_id, dataroom=user_dataroom_temp.dataroom)
            except dataroom_User_file.DoesNotExist:
                raise InvestError(20071, msg='用户不在模板dataroom中，请先将用户添加至dataroom中。')
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
            if request.user.has_perm('dataroom.admin_changedataroom'):
                pass
            elif user_dataroom_temp.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                user_dataroomtempserializer = User_DataroomTemplateCreateSerializer(user_dataroom_temp, data=data)
                if user_dataroomtempserializer.is_valid():
                    instance = user_dataroomtempserializer.save()
                    if data.has_key('password'):
                        dataroom_User_template.objects.filter(is_deleted=False, dataroom=instance.dataroom).update(password=instance.password)
                else:
                    raise InvestError(code=20071, msg='data有误_%s' % user_dataroomtempserializer.errors)
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
            if request.user.has_perm('dataroom.admin_deletedataroom'):
                pass
            elif user_dataroom_temp.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(code=2009)
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
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    queryset = dataroom_user_discuss.objects.all().filter(is_deleted=False, file__is_deleted=False, dataroom__is_deleted=False)
    filter_class = DataroomUserDiscussFilter
    serializer_class = DataroomUserDiscussSerializer
    Model = dataroom_user_discuss

    def get_object(self,pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk, is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='用户没有该可见文件（%s）' % pk)
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=7002, msg='用户没有该可见文件（%s）' % self.kwargs['pk'])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888)
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('dataroom.admin_getdataroom'):
                queryset = queryset
            else:
                queryset = queryset.filter(Q(file__in=dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile__user=request.user).values_list('file')) |
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
            if request.user.has_perm('dataroom.admin_getdataroom'):
                queryset = queryset
            else:
                queryset = queryset.filter(Q(file__in=dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile__user=request.user).values_list('file')) |
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
                raise InvestError(2007, msg='file不能为空')
            if not dataroomUserSeeFiles.objects.filter(is_deleted=False, file_id=data['file'], dataroomUserfile__user=request.user).exists():
                raise InvestError(2009, msg='只有文件可见投资人可以添加标注')
            with transaction.atomic():
                data['user'] = request.user.id
                data['createuser'] = request.user.id
                data['asktime'] = datetime.datetime.now()
                user_dataroomserializer = DataroomUserDiscussCreateSerializer(data=data)
                if user_dataroomserializer.is_valid():
                    user_dataroomserializer.save()
                else:
                    raise InvestError(code=20071, msg='data有误_%s' % user_dataroomserializer.errors)
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
            if discussInstance.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            elif request.user.has_perm('dataroom.admin_adddataroom'):
                pass
            else:
                raise InvestError(2009, msg='只有承揽承做可以回复标注')
            with transaction.atomic():
                data['trader'] = request.user.id
                data['lastmodifyuser'] = request.user.id
                data['answertime'] = datetime.datetime.now()
                user_dataroomserializer = DataroomUserDiscussUpdateSerializer(discussInstance, data=data)
                if user_dataroomserializer.is_valid():
                    user_dataroomserializer.save()
                else:
                    raise InvestError(code=20071, msg='data有误_%s' % user_dataroomserializer.errors)
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
            if request.user == instance.user:
                pass
            elif request.user.has_perm('dataroom.admin_adddataroom'):
                pass
            elif instance.dataroom.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
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