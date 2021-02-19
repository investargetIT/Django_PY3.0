import datetime
import traceback

from django.core.paginator import EmptyPage
from django.core.paginator import Paginator


# Create your views here.
from rest_framework import filters
from rest_framework import viewsets

from APIlog.models import loginlog, userviewprojlog, APILog, userinfoupdatelog
from APIlog.serializer import APILogSerializer, ViewProjLogSerializer, LoginLogSerializer, UserInfoUpdateLogSerializer
from utils.customClass import JSONResponse, InvestError
from utils.util import SuccessResponse, InvestErrorResponse, ExceptionResponse, catchexcption, loginTokenIsAvailable


def logininlog(loginaccount,logintypeid,datasourceid,userid=None,ipaddress=None):
    if isinstance(logintypeid,str):
        logintypeid = int(logintypeid)
    loginlog(loginaccount=loginaccount,ipaddress=ipaddress,logintype=logintypeid,datasource=datasourceid,user=userid).save()

def viewprojlog(userid,projid,sourceid):
    userviewprojlog(user=userid,proj=projid,source=sourceid).save()

def apilog(request,modeltype,request_before,request_after,modelID=None,datasource=None,model_name=None):
    if request.META.has_key('HTTP_X_FORWARDED_FOR'):
        ip = request.META['HTTP_X_FORWARDED_FOR']
    else:
        ip = request.META['REMOTE_ADDR']
    url = request.get_full_path()
    method = request.method
    requestbody = request.data
    if request.user.is_anonymous:
        requestuser = None
        datasource = datasource
        requestuser_name = None
    else:
        requestuser = request.user.id
        requestuser_name = request.user.usernameC
        datasource = request.user.datasource_id
    APILog(IPaddress=ip,URL=url,method=method,requestbody=requestbody,requestuser_id=requestuser,requestuser_name=requestuser_name,
           modeltype=modeltype,model_id=modelID,model_name=model_name,request_before=request_before,request_after=request_after,datasource=datasource).save()



# def LogUserInfoUpdate(userid,username,fieldtype,before,after,requestuserid,requestusername,datasource):
#     userinfoupdatelog(user_id=userid,user_name=username,type=fieldtype,before=before,after=after,requestuser_id=requestuserid,requestuser_name=requestusername,datasource=datasource).save()





class APILogView(viewsets.ModelViewSet):
    queryset = APILog.objects.filter(is_deleted=False)
    serializer_class = APILogSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=request.user.datasource_id)
            count = queryset.count()
            try:
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count': count, 'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class LoginLogView(viewsets.ModelViewSet):

    queryset = loginlog.objects.filter(is_deleted=False)
    serializer_class = LoginLogSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=request.user.datasource_id)
            count = queryset.count()
            try:
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count': count, 'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class ViewprojLogView(viewsets.ModelViewSet):

    queryset = userviewprojlog.objects.filter(is_deleted=False)
    serializer_class = ViewProjLogSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=request.user.datasource_id)
            count = queryset.count()
            try:
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count': count, 'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class UserInfoUpdateLogView(viewsets.ModelViewSet):

    filter_backends = (filters.SearchFilter,)
    search_fields = ('user_name','requestuser_name')
    queryset = userinfoupdatelog.objects.filter(is_deleted=False)
    serializer_class = UserInfoUpdateLogSerializer

    @loginTokenIsAvailable(['APILog.manage_userinfolog'])
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=request.user.datasource_id).order_by('-updatetime')
            count = queryset.count()
            try:
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count': count, 'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))