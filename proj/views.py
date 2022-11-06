#coding=utf-8
import csv
import json
import os
import traceback
from urllib.parse import quote

import chardet
import pdfkit
from django.core.paginator import Paginator, EmptyPage
from django.db import models,transaction
from django.db.models import Q, QuerySet
from django.core.exceptions import FieldDoesNotExist
from django.shortcuts import render
from rest_framework import filters, viewsets
import datetime

from rest_framework.decorators import detail_route

from APIlog.views import viewprojlog
from dataroom.views import pulishProjectCreateDataroom
from invest.settings import PROJECTPDF_URLPATH, APILOG_PATH
from proj.models import project, finance, projectTags, projectIndustries, projectTransactionType, \
    ShareToken, attachment, projServices, projTraders, projectDiDiRecord, projcomments, GovernmentProject, \
    GovernmentProjectInfo, GovernmentProjectInfoAttachment, GovernmentProjectHistoryCase, GovernmentProjectTrader, \
    GovernmentProjectTag, GovernmentProjectIndustry
from proj.serializer import ProjSerializer, FinanceSerializer, ProjCreatSerializer, \
    FinanceChangeSerializer, FinanceCreateSerializer, ProjAttachmentSerializer, \
    ProjDetailSerializer_withoutsecretinfo, ProjAttachmentCreateSerializer, \
    ProjIndustryCreateSerializer, ProjDetailSerializer_all, ProjTradersCreateSerializer, ProjTradersSerializer, \
    DiDiRecordSerializer, TaxiRecordCreateSerializer, ProjCommentsSerializer, ProjCommentsCreateSerializer, \
    ProjListSerializer, GovernmentProjectSerializer, GovernmentProjectCreateSerializer, \
    GovernmentProjectDetailSerializer, GovernmentProjectInfoSerializer, GovernmentProjectInfoCreateSerializer, \
    GovernmentProjectInfoAttachmentCreateSerializer, GovernmentProjectInfoAttachmentSerializer, \
    GovernmentProjectHistoryCaseSerializer, GovernmentProjectHistoryCaseCreateSerializer, \
    GovernmentProjectTraderSerializer, GovernmentProjectTraderCreateSerializer
from sourcetype.models import Tag, TransactionType, DataSource, Service
from third.views.qiniufile import deleteqiniufile, qiniuuploadfile
from utils.logicJudge import is_projTrader, is_projdataroomInvestor, is_projOrgBDManager, is_companyDataroomProj
from utils.somedef import addWaterMark
from utils.sendMessage import sendmessage_projectpublish
from utils.util import catchexcption, read_from_cache, write_to_cache, loginTokenIsAvailable, \
    returnListChangeToLanguage, returnDictChangeToLanguage, SuccessResponse, InvestErrorResponse, ExceptionResponse, \
    setrequestuser, cache_delete_key, checkrequesttoken, logexcption, mySortQuery, checkrequestpagesize
from utils.customClass import JSONResponse, InvestError, RelationFilter
from django_filters import FilterSet

class ProjectFilter(FilterSet):
    supportUser = RelationFilter(filterstr='supportUser',lookup_method='in')
    ids = RelationFilter(filterstr='id', lookup_method='in')
    realname = RelationFilter(filterstr='realname', lookup_method='icontains')
    title = RelationFilter(filterstr='projtitleC', lookup_method='icontains')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')
    indGroup = RelationFilter(filterstr='indGroup', lookup_method='in')
    isoverseasproject = RelationFilter(filterstr='isoverseasproject', lookup_method='in')
    industries = RelationFilter(filterstr='industries',lookup_method='in',relationName='project_industries__is_deleted')
    tags = RelationFilter(filterstr='tags',lookup_method='in',relationName='project_tags__is_deleted')
    service = RelationFilter(filterstr='proj_services__service', lookup_method='in', relationName='proj_services__is_deleted')
    projstatus = RelationFilter(filterstr='projstatus',lookup_method='in')
    bdm = RelationFilter(filterstr='proj_orgBDs__manager', relationName='proj_orgBDs__is_deleted', lookup_method='in')
    country = RelationFilter(filterstr='country',lookup_method='in')
    netIncome_USD_F = RelationFilter(filterstr='proj_finances__netIncome_USD',lookup_method='gte')
    netIncome_USD_T = RelationFilter(filterstr='proj_finances__netIncome_USD', lookup_method='lte')
    grossProfit_F = RelationFilter(filterstr='proj_finances__grossProfit', lookup_method='gte')
    grossProfit_T = RelationFilter(filterstr='proj_finances__grossProfit', lookup_method='lte')
    class Meta:
        model = project
        fields = ('ids', 'bdm', 'indGroup', 'createuser', 'service', 'supportUser', 'isoverseasproject', 'industries',
                  'tags', 'projstatus', 'country', 'netIncome_USD_F', 'netIncome_USD_T', 'grossProfit_F',
                  'grossProfit_T', 'realname', 'title',)

class ProjectView(viewsets.ModelViewSet):
    """
    list:获取项目列表
    countProject: 查看项目数量
    create:创建项目
    retrieve:获取项目详情
    update:修改项目
    destroy:删除项目
    getshareprojtoken:获取分享项目token
    getshareproj:获取分享的项目详情
    sendWXGroupPdf:发送群pdf
    """
    filter_backends = (filters.SearchFilter,filters.DjangoFilterBackend,)
    queryset = project.objects.all().filter(is_deleted=False)
    filter_class = ProjectFilter
    search_fields = ('projtitleC', 'projtitleE', 'realname')
    serializer_class = ProjSerializer
    redis_key = 'project'
    Model = project

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            if self.request.user.is_authenticated:
                queryset = queryset.filter(datasource=self.request.user.datasource)
            else:
                queryset = queryset.all()
        else:
            raise InvestError(code=8890)
        return queryset

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        assert lookup_url_kwarg in self.kwargs, (
            'Expected view %s to be called with a URL keyword argument '
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            'attribute on the view correctly.' %
            (self.__class__.__name__, lookup_url_kwarg)
        )
        obj = read_from_cache(self.redis_key + '_%s' % self.kwargs[lookup_url_kwarg])
        if not obj:
            try:
                obj = self.Model.objects.get(id=self.kwargs[lookup_url_kwarg], is_deleted=False)
            except self.Model.DoesNotExist:
                raise InvestError(code=4002, msg='项目不存在', detail='项目不存在')
            else:
                write_to_cache(self.redis_key + '_%s' % self.kwargs[lookup_url_kwarg], obj)
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='查询项目失败')
        return obj

    def list(self, request, *args, **kwargs):
        try:
            max_size = request.GET.get('max_size')
            skip_count = request.GET.get('skip_count')  # 从第一页开始
            lang = request.GET.get('lang')
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            source = request.META.get('HTTP_SOURCE')
            if source:
                datasource = DataSource.objects.filter(id=source, is_deleted=False)
                if datasource.exists():
                    userdatasource = datasource.first()
                    queryset = self.get_queryset().filter(datasource=userdatasource)
                else:
                    raise InvestError(code=8888, msg='获取项目失败')
            else:
                raise InvestError(code=8888, msg='获取项目失败')
            if not max_size:
                max_size = 10
            if not skip_count or int(skip_count) < 1:
                skip_count = 0
            setrequestuser(request)
            checkrequestpagesize(request)
            queryset = self.filter_queryset(queryset)
            if request.GET.get('iscomproj') in [1, '1', 'True', True]:
                queryset = queryset.filter(proj_datarooms__isCompanyFile=True)
            elif request.GET.get('iscomproj') in [0, '0', 'False', False]:
                queryset = queryset.exclude(proj_datarooms__isCompanyFile=True)
            if request.GET.get('user'):
                userlist = request.GET.get('user').split(',')
                queryset = queryset.filter(Q(proj_traders__user__in=userlist, proj_traders__is_deleted=False) | Q(PM__in=userlist))
            if request.user.is_anonymous:
                queryset = queryset.filter(isHidden=False,projstatus_id__in=[4,6,7,8])
            else:
                if request.user.has_perm('proj.admin_manageproj'):
                    queryset = queryset
                elif request.user.has_perm('usersys.as_trader') and request.user.userstatus_id == 2:
                    queryset = queryset.filter(Q(createuser=request.user) | Q(PM=request.user) | Q(isHidden=False) | Q(proj_traders__user=request.user, proj_traders__is_deleted=False) | Q(supportUser=request.user) | Q(isHidden=True, proj_orgBDs__manager=request.user, proj_orgBDs__is_deleted=False))
                else:
                    queryset = queryset.filter(Q(isHidden=False,projstatus_id__in=[4,6,7,8]) | Q(isHidden=True, proj_datarooms__is_deleted=False, proj_datarooms__dataroom_users__user=request.user, proj_datarooms__dataroom_users__is_deleted=False))
            queryset = queryset.distinct()
            queryset = mySortQuery(queryset, sortfield, desc)
            count = queryset.count()
            queryset = queryset[int(skip_count):int(max_size)+int(skip_count)]
            instancedata = ProjListSerializer(queryset, many=True).data
            return JSONResponse(SuccessResponse({'count': count, 'data': returnListChangeToLanguage(instancedata, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['proj.admin_manageproj', 'usersys.as_trader'])
    def countProject(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            if request.GET.get('user'):
                userlist = request.GET.get('user').split(',')
                queryset = queryset.filter( Q(proj_traders__user__in=userlist, proj_traders__is_deleted=False) | Q(PM__in=userlist))
            return JSONResponse(SuccessResponse({'count': queryset.count()}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            if request.user.has_perm('proj.admin_manageproj'):
                pass
            elif request.user.has_perm('usersys.as_trader') and request.user.indGroup:
                pass
            else:
                raise InvestError(2009, msg='新增项目B失败')
            projdata = request.data
            lang = request.GET.get('lang')
            projdata['createuser'] = request.user.id
            projdata['createdtime'] = datetime.datetime.now()
            projdata['datasource'] = request.user.datasource_id
            projdata['projstatus'] = 2
            tagsdata = projdata.pop('tags',None)
            industrydata = projdata.pop('industries',None)
            transactiontypedata = projdata.pop('transactionType',None)
            projAttachmentdata = projdata.pop('projAttachment',None)
            financedata = projdata.pop('finance',None)
            servicedata = projdata.pop('service',None)
            takeUserData = projdata.pop('takeUser', None)
            makeUserData = projdata.pop('makeUser', None)
            with transaction.atomic():
                proj = ProjCreatSerializer(data=projdata)
                if proj.is_valid():
                    pro = proj.save()
                    if takeUserData:
                        takeUserList = []
                        if not isinstance(takeUserData,list):
                            raise InvestError(20071, msg='新增项目失败', detail='takeUser must be a list')
                        for takeUser_id in takeUserData:
                            takeUserList.append(projTraders(proj=pro, user_id=takeUser_id, createuser=request.user, type=0, createdtime=datetime.datetime.now()))
                        pro.project_tags.bulk_create(takeUserList)
                    if makeUserData:
                        makeUserList = []
                        if not isinstance(makeUserData,list):
                            raise InvestError(20071, msg='新增项目失败', detail='makeUser must be a list')
                        for makeUser_id in makeUserData:
                            makeUserList.append(projTraders(proj=pro, user_id=makeUser_id, createuser=request.user, type=1, createdtime=datetime.datetime.now()))
                        pro.project_tags.bulk_create(makeUserList)
                    if tagsdata:
                        tagslist = []
                        if not isinstance(tagsdata,list):
                            raise InvestError(20071, msg='新增项目失败', detail='tags must be a list')
                        for tagid in tagsdata:
                            tagslist.append(projectTags(proj=pro, tag_id=tagid,createuser=request.user))
                        pro.project_tags.bulk_create(tagslist)
                    if servicedata:
                        servicelist = []
                        if not isinstance(servicedata,list):
                            raise InvestError(20071, msg='新增项目失败', detail='service must be a list')
                        for serviceid in servicedata:
                            servicelist.append(projServices(proj=pro, service_id=serviceid,createuser=request.user))
                        pro.proj_services.bulk_create(servicelist)
                    if industrydata:
                        industrylist = []
                        if not isinstance(industrydata,list):
                            raise InvestError(20071, msg='新增项目失败', detail='industries must be a list')
                        for oneindustrydata in industrydata:
                            industrylist.append(projectIndustries(proj=pro, industry_id=oneindustrydata.get('industry',None),createuser=request.user,bucket=oneindustrydata.get('bucket',None),key=oneindustrydata.get('key',None)))
                        pro.project_industries.bulk_create(industrylist)
                    if transactiontypedata:
                        transactiontypelist = []
                        if not isinstance(transactiontypedata,list):
                            raise InvestError(20071, msg='新增项目失败', detail='transactionType must be a list')
                        for transactionPhaseid in transactiontypedata:
                            transactiontypelist.append(projectTransactionType(proj=pro, transactionType_id=transactionPhaseid,createuser=request.user))
                        pro.project_TransactionTypes.bulk_create(transactiontypelist)
                    if projAttachmentdata:
                        if not isinstance(projAttachmentdata, list):
                            raise InvestError(20071, msg='新增项目失败', detail='transactionType must be a list')
                        for oneprojAttachmentdata in projAttachmentdata:
                            oneprojAttachmentdata['proj'] = pro.id
                            oneprojAttachmentdata['createuser'] = request.user.id
                            projAttachmentSerializer = ProjAttachmentCreateSerializer(data=oneprojAttachmentdata)
                            if projAttachmentSerializer.is_valid():
                                projAttachmentSerializer.save()
                    if financedata:
                        if not isinstance(financedata, list):
                            raise InvestError(20071, msg='新增项目失败', detail='transactionType must be a list')
                        for onefinancedata in financedata:
                            onefinancedata['proj'] = pro.id
                            onefinancedata['datasource'] = request.user.datasource_id
                            onefinancedata['createuser'] = request.user.id
                            financeSerializer = FinanceCreateSerializer(data=onefinancedata)
                            if financeSerializer.is_valid():
                                financeSerializer.save()
                else:
                    raise InvestError(code=4001, msg='新增项目失败', detail='上传项目参数有误%s' % proj.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(ProjSerializer(pro).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            clienttype = request.META.get('HTTP_CLIENTTYPE')
            instance = self.get_object()
            if request.user == instance.supportUser or request.user.has_perm('proj.admin_manageproj') or is_projTrader(request.user, instance.id):
                serializerclass = ProjDetailSerializer_all
            else:
                if request.user.has_perm('proj.get_secretinfo'):
                    serializerclass = ProjDetailSerializer_all
                else:
                    serializerclass = ProjDetailSerializer_withoutsecretinfo
                if instance.isHidden:
                    if is_projdataroomInvestor(request.user, instance.id):
                        pass
                    elif is_projOrgBDManager(request.user, instance.id):
                        pass
                    elif is_companyDataroomProj(instance) and request.user.has_perm('dataroom.get_companydataroom'):
                        pass
                    else:
                        raise InvestError(code=4004, msg='查看项目失败', detail='该项目为隐藏项目，没有权限查看')
            serializer = serializerclass(instance)
            viewprojlog(userid=request.user.id,projid=instance.id,sourceid=clienttype)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def getshareprojdetail(self, request, *args, **kwargs):
        try:
            setrequestuser(request)
            if request.user.is_anonymous:
                raise InvestError(2009, msg='查看分享项目失败')
            elif request.user.has_perm('usersys.as_investor') and not request.user.is_superuser and request.user.datasource_id == 1:
                raise InvestError(2009, msg='查看分享项目失败')
            lang = request.GET.get('lang')
            clienttype = request.META.get('HTTP_CLIENTTYPE')
            tokenkey = request.GET.get('token')
            if tokenkey:
                token = ShareToken.objects.filter(key=tokenkey)
                if token.exists():
                    instance = token.first().proj
                else:
                    raise InvestError(4004, msg='查看分享项目失败', detail='分享项目token无效')
            else:
                raise InvestError(code=4004, msg='查看分享项目失败', detail='没有权限查看项目')
            serializer = ProjDetailSerializer_withoutsecretinfo(instance)
            viewprojlog(userid=None,projid=instance.id,sourceid=clienttype)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            pro = self.get_object()
            lang = request.GET.get('lang')
            projdata = request.data
            if request.user.has_perm('proj.admin_manageproj') or is_projTrader(request.user, pro.id):
                pass
            elif request.user in [pro.supportUser, pro.createuser] :
                pass
            else:
                raise InvestError(code=2009, msg='修改项目信息失败', detail='非上传方或管理员无法修改项目')
            projdata['lastmodifyuser'] = request.user.id
            projdata['lastmodifytime'] = datetime.datetime.now()
            projdata['datasource'] = request.user.datasource_id
            tagsdata = projdata.pop('tags', None)
            industrydata = projdata.pop('industries', None)
            transactiontypedata = projdata.pop('transactionType', None)
            projAttachmentdata = projdata.pop('projAttachment', None)
            financedata = projdata.pop('finance', None)
            servicedata = projdata.pop('service', None)
            sendmsg = False
            if projdata.get('projstatus') and projdata.get('projstatus') != pro.projstatus_id:
                if projdata['projstatus'] == 4:
                    sendmsg = True
                    projdata['publishDate'] = datetime.datetime.now()
            takeUserData = projdata.pop('takeUser', None)
            makeUserData = projdata.pop('makeUser', None)
            with transaction.atomic():
                proj = ProjCreatSerializer(pro,data=projdata)
                if proj.is_valid():
                    pro = proj.save()
                    if takeUserData is not None:
                        if not isinstance(takeUserData,list):
                            raise InvestError(20071, msg='修改项目信息失败', detail='takeUser must be a list')
                        if len(takeUserData) == 0:
                            pro.proj_traders.filter(type=0, is_deleted=False).update(is_deleted=True, deletedtime=datetime.datetime.now(), deleteduser=request.user)
                        else:
                            userExists_list = pro.proj_traders.filter(type=0, is_deleted=False).values_list('user_id', flat=True)
                            addlist = [item for item in takeUserData if item not in userExists_list]
                            removelist = [item for item in userExists_list if item not in takeUserData]
                            pro.proj_traders.filter(user__in=removelist, type=0, is_deleted=False).update(is_deleted=True,
                                                                                                 deletedtime=datetime.datetime.now(),
                                                                                                 deleteduser=request.user)
                            takeUserList = []
                            for user_id in addlist:
                                takeUserList.append(projTraders(proj=pro, user_id=user_id, createuser=request.user, type=0, createdtime=datetime.datetime.now()))
                            pro.proj_traders.bulk_create(takeUserList)
                    if makeUserData is not None:
                        if not isinstance(makeUserData,list):
                            raise InvestError(20071, msg='修改项目信息失败', detail='makeUser must be a list')
                        if len(makeUserData) == 0:
                            pro.proj_traders.filter(type=1, is_deleted=False).update(is_deleted=True, deletedtime=datetime.datetime.now(), deleteduser=request.user)
                        else:
                            userExists_list = pro.proj_traders.filter(type=1, is_deleted=False).values_list('user_id', flat=True)
                            addlist = [item for item in makeUserData if item not in userExists_list]
                            removelist = [item for item in userExists_list if item not in makeUserData]
                            pro.proj_traders.filter(user__in=removelist, type=1, is_deleted=False).update(is_deleted=True,
                                                                                                 deletedtime=datetime.datetime.now(),
                                                                                                 deleteduser=request.user)
                            makeUserList = []
                            for user_id in addlist:
                                makeUserList.append(projTraders(proj=pro, user_id=user_id, createuser=request.user, type=1, createdtime=datetime.datetime.now()))
                            pro.proj_traders.bulk_create(makeUserList)
                    if tagsdata is not None:
                        taglist = Tag.objects.in_bulk(tagsdata)
                        addlist = [item for item in taglist if item not in pro.tags.all()]
                        removelist = [item for item in pro.tags.all() if item not in taglist]
                        pro.project_tags.filter(tag__in=removelist, is_deleted=False).update(is_deleted=True,
                                                                                           deletedtime=datetime.datetime.now(),
                                                                                           deleteduser=request.user)
                        usertaglist = []
                        for tag in addlist:
                            usertaglist.append(projectTags(proj=pro, tag_id=tag, createuser=request.user))
                        pro.project_tags.bulk_create(usertaglist)
                    if servicedata is not None:
                        if not isinstance(servicedata, list) or len(servicedata) == 0:
                            raise InvestError(20071, msg='修改项目信息失败', detail='service must be a list')
                        servicelist = Service.objects.in_bulk(servicedata)
                        addlist = [item for item in servicelist if item not in pro.service.all()]
                        removelist = [item for item in pro.service.all() if item not in servicelist]
                        pro.proj_services.filter(service__in=removelist, is_deleted=False).update(is_deleted=True,
                                                                                             deletedtime=datetime.datetime.now(),
                                                                                             deleteduser=request.user)
                        projservicelist = []
                        for serviceid in addlist:
                            projservicelist.append(projServices(proj=pro, service_id=serviceid,createuser=request.user))
                        pro.proj_services.bulk_create(projservicelist)

                    if industrydata is not None:
                        if not isinstance(industrydata, list) or len(industrydata) == 0:
                            raise InvestError(20071, msg='修改项目信息失败', detail='industrydata must be a list')
                        pro.project_industries.filter(is_deleted=False).update(is_deleted=True, deletedtime=datetime.datetime.now(), deleteduser=request.user)
                        for oneindustrydata in industrydata:
                            oneindustrydata['proj'] = pro.id
                            industrydataSerializer = ProjIndustryCreateSerializer(data=oneindustrydata)
                            if industrydataSerializer.is_valid():
                                industrydataSerializer.save()

                    if transactiontypedata is not None:
                        transactionTypelist = TransactionType.objects.in_bulk(transactiontypedata)
                        addlist = [item for item in transactionTypelist if item not in pro.transactionType.all()]
                        removelist = [item for item in pro.transactionType.all() if item not in transactionTypelist]
                        pro.project_TransactionTypes.filter(transactionType__in=removelist, is_deleted=False).update(is_deleted=True,
                                                                                           deletedtime=datetime.datetime.now(),
                                                                                           deleteduser=request.user)
                        projtransactiontypelist = []
                        for transactionPhase in addlist:
                            projtransactiontypelist.append(projectTransactionType(proj=pro, transactionType_id=transactionPhase, createuser=request.user))
                        pro.project_TransactionTypes.bulk_create(projtransactiontypelist)

                    if projAttachmentdata is not None:
                        if not isinstance(projAttachmentdata, list) or len(projAttachmentdata) == 0:
                            raise InvestError(20071, msg='修改项目信息失败', detail='transactionType must be a list')
                        pro.proj_attachment.filter(is_deleted=False).update(is_deleted=True, deletedtime=datetime.datetime.now(), deleteduser=request.user)
                        for oneprojAttachmentdata in projAttachmentdata:
                            oneprojAttachmentdata['proj'] = pro.id
                            projAttachmentSerializer = ProjAttachmentCreateSerializer(data=oneprojAttachmentdata)
                            if projAttachmentSerializer.is_valid():
                                projAttachmentSerializer.save()

                    if financedata is not None:
                        if not isinstance(financedata, list):
                            raise InvestError(20071, msg='修改项目信息失败', detail='transactionType must be a list')
                        pro.proj_finances.filter(is_deleted=False).update(is_deleted=True, deletedtime=datetime.datetime.now(), deleteduser=request.user)
                        for onefinancedata in financedata:
                            onefinancedata['proj'] = pro.id
                            financeSerializer = FinanceCreateSerializer(data=onefinancedata)
                            if financeSerializer.is_valid():
                                financeSerializer.save()
                    cache_delete_key(self.redis_key + '_%s' % pro.id)
                else:
                    raise InvestError(code=4001, msg='修改项目信息失败', detail='项目参数有误-%s' % proj.errors)
                if sendmsg:
                    sendmessage_projectpublish(pro, pro.supportUser,['email', 'webmsg'],sender=request.user)
                    for proj_trader in pro.proj_traders.filter(type=0, is_deleted=False):
                        sendmessage_projectpublish(pro, proj_trader.user, ['email', 'webmsg'], sender=request.user)
            if projdata.get('projstatus') in [4, 6, 7]:  # 已发布，交易中，已完成
                publicdataroom = pro.proj_datarooms.filter(is_deleted=False)
                if publicdataroom.exists():
                    pass
                else:
                    pulishProjectCreateDataroom(pro, request.user)  # 创建dataroom，（已创建自动跳过）
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(ProjSerializer(pro).data, lang)))
        except InvestError as err:
                return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def sendWXGroupPdf(self, request, *args, **kwargs):
        try:
            pro = self.get_object()
            if request.user.has_perm('proj.admin_manageproj') or request.user == pro.supportUser or is_projTrader(request.user, pro.id):
                pass
            else:
                raise InvestError(code=2009, msg='微信群发项目pdf失败', detail='非承揽承做或上传方无法发送项目pdf邮件')
            if pro.projstatus_id == 4 and not pro.is_deleted:
                propath = APILOG_PATH['wxgroupsendpdf'] + pro.projtitleC + '.pdf'
                if not os.path.exists(propath):
                    self.makePdf(pro)
            else:
                raise InvestError(20071, msg='微信群发项目pdf失败', detail='项目状态不满足发送条件')
            return JSONResponse(SuccessResponse({"status":'发送中，请稍后'}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            lang = request.GET.get('lang')
            if request.user.has_perm('proj.admin_manageproj'):
                pass
            elif request.user == instance.supportUser or is_projTrader(request.user, instance.id):
                pass
            else:
                raise InvestError(code=2009, msg='删除项目失败', detail='没有权限，请联系管理员删除')
            if instance.proj_datarooms.filter(is_deleted=False, proj=instance).exists():
                raise InvestError(code=2010, msg='删除项目失败', detail='{} 上有关联数据'.format('proj_datarooms'))
            with transaction.atomic():
                for link in ['proj_finances', 'proj_attachment', 'project_tags', 'project_industries', 'project_TransactionTypes', 'proj_traders', 'historycase_govprojs',
                             'proj_sharetoken', 'proj_datarooms', 'proj_services', 'proj_schedule', 'proj_orgBDs','proj_OrgBdBlacks', 'relate_projects']:
                    if link in ['proj_datarooms', 'relate_projects']:
                        manager = getattr(instance, link, None)
                        if not manager:
                            continue
                        # one to one
                        if isinstance(manager, models.Model):
                            if hasattr(manager, 'is_deleted') and not manager.is_deleted:
                                raise InvestError(code=2010, msg='删除项目失败', detail='{} 上有关联数据'.format(link))
                        else:
                            try:
                                manager.model._meta.get_field('is_deleted')
                                if manager.all().filter(is_deleted=False).count():
                                    raise InvestError(code=2010, msg='删除项目失败', detail='{} 上有关联数据'.format(link))
                            except FieldDoesNotExist:
                                if manager.all().count():
                                    raise InvestError(code=2010, msg='删除项目失败', detail='{} 上有关联数据'.format(link))
                    else:
                        manager = getattr(instance, link, None)
                        if not manager:
                            continue
                        # one to one
                        if isinstance(manager, models.Model):
                            if hasattr(manager, 'is_deleted') and not manager.is_deleted:
                                manager.is_deleted = True
                                manager.save()
                        else:
                            try:
                                manager.model._meta.get_field('is_deleted')
                                if manager.all().filter(is_deleted=False).count():
                                    manager.all().update(is_deleted=True)
                            except FieldDoesNotExist:
                                pass
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletetime = datetime.datetime.now()
                instance.save()
                cache_delete_key(self.redis_key + '_%s' % instance.id)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(ProjSerializer(instance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @detail_route(methods=['get'])
    @loginTokenIsAvailable()
    def getshareprojtoken(self, request, *args, **kwargs):
        try:
            proj = self.get_object()
            with transaction.atomic():
                sharetokenset = ShareToken.objects.filter(user=request.user,proj=proj,created__gt=(datetime.datetime.now()-datetime.timedelta(hours=1 * 1)))
                if sharetokenset.exists():
                    sharetoken = sharetokenset.last()
                else:
                    sharetoken = ShareToken(user=request.user,proj=proj)
                    sharetoken.save()
                return JSONResponse(SuccessResponse(sharetoken.key))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @detail_route(methods=['get'])
    def sendPDF(self, request, *args, **kwargs):
        try:
            request.user = checkrequesttoken(request.GET.get('acw_tk'))
            lang = request.GET.get('lang', 'cn')
            proj = self.get_object()
            if proj.isHidden:
                if request.user.has_perm('proj.admin_manageproj') or request.user == proj.supportUser or is_projTrader(request.user, proj.id):
                    pass
                else:
                    raise InvestError(2009, msg='获取项目pdf失败', detail='隐藏项目，只有项目承揽承做及上传方可以获取相关项目信息')
            options = {
                'dpi': 1400,
                'page-size': 'A4',
                'margin-top': '0in',
                'margin-right': '0in',
                'margin-bottom': '0in',
                'margin-left': '0in',
                'encoding': "UTF-8",
                'no-outline': None,
            }
            pdfpath = APILOG_PATH['pdfpath_base'] + 'P' + datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '.pdf'
            config = pdfkit.configuration(wkhtmltopdf=APILOG_PATH['wkhtmltopdf'])
            aaa = pdfkit.from_url(PROJECTPDF_URLPATH + '{}&lang={}'.format(proj.id, lang), pdfpath, configuration=config, options=options)
            if not aaa:
                raise InvestError(4008, msg='获取项目pdf失败', detail='项目pdf生成失败')
            if not is_projTrader(request.user, proj.id):
                username = request.user.usernameC
                orgname = request.user.org.orgnameC if request.user.org else ''
                if lang == 'en':
                    username = request.user.usernameE if request.user.usernameE else request.user.usernameC
                    if request.user.org:
                        orgname = request.user.org.orgnameE if request.user.org.orgnameE else request.user.org.orgnameC
                out_path = addWaterMark(pdfpath, watermarkcontent=[username, orgname, request.user.email])
            else:
                out_path = pdfpath
            bucket_key = "{}.pdf".format(proj.projtitleC if lang == 'cn' else proj.projtitleE)
            res, url, key = qiniuuploadfile(out_path, 'file', bucket_key)
            if os.path.exists(out_path):
                os.remove(out_path)
            if res:
                return JSONResponse(SuccessResponse(url))
            else:
                raise InvestError(4008, msg='获取项目pdf失败', detail='pdf上传七牛失败')
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def makePdf(self, proj):
        try:
            options = {
                'dpi': 1400,
                'page-size': 'A4',
                'margin-top': '0in',
                'margin-right': '0in',
                'margin-bottom': '0in',
                'margin-left': '0in',
                'encoding': "UTF-8",
                'no-outline': None,
            }
            pdfpath = APILOG_PATH['wxgroupsendpdf'] + proj.projtitleC.replace('/','-') + '.pdf'
            config = pdfkit.configuration(wkhtmltopdf=APILOG_PATH['wkhtmltopdf'])
            aaa = pdfkit.from_url(PROJECTPDF_URLPATH + str(proj.id) + '&lang=cn', pdfpath, configuration=config,
                                  options=options)
            if not aaa:
                raise InvestError(4008, msg='微信群发项目pdf失败', detail='生成项目pdf失败')
            if proj.country_id == 42 and proj.currency_id == 1:
                amount_field, currency, currencytype = 'financeAmount', '￥', 'CNY'
            else:
                amount_field, currency, currencytype = 'financeAmount_USD', '$', 'USD'

            f = open(APILOG_PATH['wxgroupsendpdf'] + '/projdesc.txt', 'a')
            content = {proj.projtitleC.split('：')[0]: '本周项目自动推送：%s%s' % (proj.projtitleC.split('：')[-1],
                                       ('，拟交易规模：%s%s %s' % (currency, '{:,}'.format(getattr(proj,amount_field)) if getattr(proj,amount_field) else 'N/A', currencytype)))}
            f.writelines(json.dumps(content, ensure_ascii=False))
            f.writelines('\n')
            f.close()
        except Exception:
            logexcption()


class ProjTradersView(viewsets.ModelViewSet):
    """
    list: 获取项目承揽承做
    create: 增加项目承揽承做
    update: 修改项目承揽承做
    destroy: 删除项目承揽承做
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = projTraders.objects.filter(is_deleted=False)
    filter_fields = ('user', 'proj', 'type')
    serializer_class = ProjTradersSerializer

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

    def get_proj(self, pk):
        try:
            obj = project.objects.get(id=pk, is_deleted=False)
        except project.DoesNotExist:
            raise InvestError(code=4002, msg='获取项目承揽承做失败', detail='项目不存在')
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取项目承揽承做失败')
        if obj.is_deleted:
            raise InvestError(code=4002, msg='获取项目承揽承做失败', detail='项目已删除')
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('proj.admin_manageproj'):
                queryset = queryset
            else:
                queryset = queryset.filter(Q(proj__PM=request.user) | Q(proj__supportUser=request.user) | Q(proj__proj_traders__user=request.user, proj__proj_traders__is_deleted=False)).distinct()
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializers = self.serializer_class(queryset, many=True)
            return JSONResponse(
                SuccessResponse({'count': count, 'data': returnListChangeToLanguage(serializers.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            instance = self.get_proj(data['proj'])
            if request.user.has_perm('proj.admin_manageproj') or is_projTrader(request.user, instance.id):
                pass
            elif request.user in [instance.supportUser, instance.createuser]:
                pass
            else:
                raise InvestError(code=2009, msg='添加项目承揽承做失败', detail='没有权限增加承揽承做')
            with transaction.atomic():
                instanceSerializer = ProjTradersCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instance = instanceSerializer.save()
                else:
                    raise InvestError(40011, msg='添加项目承揽承做失败', detail='%s' % instanceSerializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data, lang)))
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
            instance = self.get_object()
            if request.user.has_perm('proj.admin_manageproj') or is_projTrader(request.user, instance.proj.id):
                pass
            elif request.user in [instance.proj.supportUser, instance.createuser]:
                pass
            else:
                raise InvestError(code=2009, msg='修改项目承揽承做失败', detail='没有权限修改承揽承做')
            with transaction.atomic():
                newinstanceSeria = ProjTradersCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstance = newinstanceSeria.save()
                else:
                    raise InvestError(40011, msg='修改项目承揽承做失败', detail='修改失败—%s' % newinstanceSeria.errors)
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(self.serializer_class(newinstance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('proj.admin_manageproj') or is_projTrader(request.user, instance.proj.id):
                pass
            elif request.user in [instance.proj.supportUser, instance.createuser]:
                pass
            else:
                raise InvestError(code=2009, msg='删除项目承揽承做失败', detail='没有权限删除承揽承做')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
            return JSONResponse(SuccessResponse({'isDeleted': True, }))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class ProjAttachmentView(viewsets.ModelViewSet):
    """
    list:获取项目附件
    create:创建项目附件 （projid+data）
    update:修改项目附件（批量idlist+data）
    destroy:删除项目附件 （批量idlist）
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = attachment.objects.all().filter(is_deleted=False)
    filter_fields = ('proj',)
    serializer_class = ProjAttachmentSerializer



    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            if self.request.user.is_authenticated:
                queryset = queryset.filter(proj__datasource=self.request.user.datasource)
            else:
                queryset = queryset.all()
        else:
            raise InvestError(code=8890)
        return queryset

    def get_object(self, pk=None):
        if pk:

            try:
                obj = self.queryset.get(id=pk)
            except attachment.DoesNotExist:
                raise InvestError(code=40031, msg='获取项目附件失败', detail='项目附件不存在')
        else:
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            assert lookup_url_kwarg in self.kwargs, (
                'Expected view %s to be called with a URL keyword argument '
                'named "%s". Fix your URL conf, or set the `.lookup_field` '
                'attribute on the view correctly.' %
                (self.__class__.__name__, lookup_url_kwarg)
            )
            try:
                obj = self.queryset.get(id=self.kwargs[lookup_url_kwarg])
            except attachment.DoesNotExist:
                raise InvestError(code=40031, msg='获取项目附件失败', detail='项目附件不存在')
        if obj.proj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取项目附件失败')
        return obj
    def get_proj(self, pk):
        obj = read_from_cache('project_%s' % pk)
        if not obj:
            try:
                obj = project.objects.get(id=pk, is_deleted=False)
            except project.DoesNotExist:
                raise InvestError(code=4002, msg='获取项目失败', detail='项目不存在')
            else:
                write_to_cache('project_%s' % pk, obj)
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取项目失败')
        if obj.is_deleted:
            raise InvestError(code=4002, msg='获取项目失败', detail='项目已删除')
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            projid = request.GET.get('proj')
            if projid:
                self.get_proj(projid)
            else:
                raise InvestError(20072, msg='获取项目附件失败', detail='项目（proj）不能为空')
            queryset = self.filter_queryset(self.get_queryset())
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = ProjAttachmentSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            projid = data.get('proj')
            lang = request.GET.get('lang')
            proj = self.get_proj(projid)
            if request.user.has_perm('proj.admin_manageproj') or request.user == proj.supportUser or is_projTrader(request.user, proj.id):
                pass
            else:
                raise InvestError(code=2009, msg='新增项目附件失败', detail='没有增加该项目附件的权限')
            with transaction.atomic():
                data['createuser'] = request.user.id
                attachments = ProjAttachmentCreateSerializer(data=data)
                if attachments.is_valid():
                    attachments.save()
                else:
                    raise InvestError(code=40012, msg='新增项目附件失败', detail='%s' % attachments.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(attachments.data,lang)))
        except InvestError as err:
                return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        attachmentdata = data.get('attachment')
        try:
            with transaction.atomic():
                if attachmentdata:
                    newfinances = []
                    for f in attachmentdata:
                        fid = f['id']
                        if not isinstance(fid,(int,str)) or not fid:
                            raise InvestError(20071, msg='修改项目附件信息失败', detail='attachment[\'id\'] must be a int/str type')
                        projAttachment = self.get_object(fid)
                        if request.user.has_perm('proj.admin_manageproj') or is_projTrader(request.user, projAttachment.proj.id):
                            pass
                        elif request.user in [projAttachment.proj.supportUser, projAttachment.createuser]:
                            pass
                        else:
                            raise InvestError(code=2009, msg='修改项目附件信息失败')
                        f['lastmodifyuser'] = request.user.id
                        f['lastmodifytime'] = datetime.datetime.now()
                        attachmentSer = ProjAttachmentCreateSerializer(projAttachment,data=attachmentdata)
                        if attachmentSer.is_valid():
                            attachmentSer.save()
                        else:
                            raise InvestError(code=40012, msg='修改项目附件信息失败', detail='%s' % attachmentSer.error_messages)
                        newfinances.append(attachmentSer.data)
                else:
                    raise InvestError(code=20072, msg='修改项目附件信息失败', detail='attachment field cannot be null')
                return JSONResponse(SuccessResponse(returnListChangeToLanguage(newfinances, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                attachmentidlist = request.data.get('attachment',None)
                if not isinstance(attachmentidlist,list) or not attachmentidlist:
                    raise InvestError(code=20072, msg='删除项目附件失败', detail='\'attachment\' expect a non-empty array')
                lang = request.GET.get('lang')
                returnlist = []
                for projattachmentid in attachmentidlist:
                    projAttachment = self.get_object(projattachmentid)
                    if request.user.has_perm('proj.admin_manageproj') or is_projTrader(request.user, projAttachment.proj.id):
                        pass
                    elif request.user in [projAttachment.proj.supportUser, projAttachment.createuser]:
                        pass
                    else:
                        raise InvestError(code=2009, msg='删除项目附件失败', detail='没有权限')
                    projAttachment.is_deleted = True
                    projAttachment.deleteduser = request.user
                    projAttachment.deletedtime = datetime.datetime.now()
                    projAttachment.save()
                    deleteqiniufile(projAttachment.bucket, projAttachment.key)
                    deleteqiniufile(projAttachment.bucket, projAttachment.realfilekey)
                    returnlist.append(ProjAttachmentSerializer(projAttachment).data)
                return JSONResponse(SuccessResponse(returnListChangeToLanguage(returnlist,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



class ProjFinanceView(viewsets.ModelViewSet):
    """
    list:获取财务信息
    create:创建财务信息 （projid+data）
    update:修改财务信息（批量idlist+data）
    destroy:删除财务信息 （批量idlist）
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = finance.objects.all().filter(is_deleted=False)
    filter_fields = ('proj',)
    serializer_class = FinanceSerializer



    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            if self.request.user.is_authenticated:
                queryset = queryset.filter(datasource=self.request.user.datasource)
            else:
                queryset = queryset.all()
        else:
            raise InvestError(code=8890)
        return queryset

    def get_object(self, pk=None):
        if pk:

            try:
                obj = self.queryset.get(id=pk)
            except finance.DoesNotExist:
                raise InvestError(code=40031, msg='获取项目财务信息失败', detail='财务信息不存在')
        else:
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            assert lookup_url_kwarg in self.kwargs, (
                'Expected view %s to be called with a URL keyword argument '
                'named "%s". Fix your URL conf, or set the `.lookup_field` '
                'attribute on the view correctly.' %
                (self.__class__.__name__, lookup_url_kwarg)
            )
            try:
                obj = self.queryset.get(id=self.kwargs[lookup_url_kwarg])
            except finance.DoesNotExist:
                raise InvestError(code=40031, msg='获取项目财务信息失败', detail='财务信息不存在')
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取项目财务信息失败')
        return obj
    def get_proj(self,pk):
        obj = read_from_cache('project_%s' % pk)
        if not obj:
            try:
                obj = project.objects.get(id=pk, is_deleted=False)
            except project.DoesNotExist:
                raise InvestError(code=4002, msg='获取项目失败', detail='项目不存在')
            else:
                write_to_cache('project_%s' % pk, obj)
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取项目失败')
        if obj.is_deleted:
            raise InvestError(code=4002, msg='获取项目失败', detail='项目已删除')
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            projid = request.GET.get('proj')
            if projid:
                proj = self.get_proj(projid)
            else:
                raise InvestError(20072, msg='获取项目财务信息失败', detail='项目不能为空')
            queryset = self.filter_queryset(self.get_queryset())
            if not proj.financeIsPublic:
                if request.user in [proj.supportUser, proj.createuser]:
                    pass
                elif request.user.has_perm('proj.admin_manageproj'):
                    pass
                elif is_projTrader(request.user, projid):
                    pass
                else:
                    return JSONResponse(SuccessResponse({'count':0,'data':[]}, msg='没有符合的结果'))
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count':0,'data':[]}, msg='没有符合的结果'))
            serializer = FinanceSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            projid = data.get('proj')
            proj = self.get_proj(projid)
            if request.user.has_perm('proj.admin_manageproj'):
                pass
            elif request.user in [proj.createuser, proj.supportUser]:
                pass
            elif is_projTrader(request.user, proj.id):
                pass
            else:
                raise InvestError(code=2009, msg='新增项目财务信息失败', detail='没有增加该项目财务信息的权限')
            lang = request.GET.get('lang')
            with transaction.atomic():

                data['createuser'] = request.user.id
                data['datasource'] = request.user.datasource.id
                finances = FinanceCreateSerializer(data=data)
                if finances.is_valid():
                    finances.save()
                else:
                    raise InvestError(code=40013, msg='新增项目财务信息失败', detail='财务信息有误_%s\n%s' % (finances.error_messages, finances.errors))
                return JSONResponse(SuccessResponse(returnListChangeToLanguage(finances.data,lang)))
        except InvestError as err:
                return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        financedata = data.get('finances')
        try:
            with transaction.atomic():
                if financedata:
                    newfinances = []
                    for f in financedata:
                        fid = f['id']
                        f.pop('proj', None)
                        if not isinstance(fid,(int,str)) or not fid:
                            raise InvestError(20072, msg='修改项目财务信息失败', detail='finances[\'id\'] must be a int/str type')
                        projfinance = self.get_object(fid)
                        if request.user.has_perm('proj.admin_manageproj') or is_projTrader(request.user, projfinance.proj.id):
                            pass
                        elif request.user in [projfinance.proj.createuser, projfinance.proj.supportUser]:
                            pass
                        else:
                            raise InvestError(code=2009, msg='修改项目财务信息失败', detail='没有权限修改项目（%s）的相关信息'%projfinance.proj)
                        f['lastmodifyuser'] = request.user.id
                        f['lastmodifytime'] = datetime.datetime.now()
                        finance = FinanceChangeSerializer(projfinance,data=f)
                        if finance.is_valid():
                            finance.save()
                        else:
                            raise InvestError(code=40013, msg='修改项目财务信息失败', detail='%s' % finance.error_messages)
                        newfinances.append(finance.data)
                else:
                    raise InvestError(code=20072, msg='修改项目财务信息失败', detail='finances field cannot be null')
                return JSONResponse(SuccessResponse(returnListChangeToLanguage(newfinances, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                financeidlist = request.data.get('finances',None)
                if not isinstance(financeidlist,list) or not financeidlist:
                    raise InvestError(code=20072, msg='删除项目财务信息失败', detail='\'finances\' expect an not null list')
                lang = request.GET.get('lang')
                returnlist = []
                for projfinanceid in financeidlist:
                    projfinance = self.get_object(projfinanceid)
                    if request.user.has_perm('proj.admin_manageproj') or is_projTrader(request.user, projfinance.proj.id):
                        pass
                    elif request.user in [projfinance.proj.createuser, projfinance.proj.supportUser]:
                        pass
                    else:
                        raise InvestError(code=2009, msg='删除项目财务信息失败', detail='没有权限删除财务信息')
                    projfinance.is_deleted = True
                    projfinance.deleteduser = request.user
                    projfinance.deletedtime = datetime.datetime.now()
                    projfinance.save()
                    returnlist.append(FinanceSerializer(projfinance).data)
                return JSONResponse(SuccessResponse(returnListChangeToLanguage(returnlist,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



class ProjDiDiRecordView(viewsets.ModelViewSet):
    """
    list:获取打车订单信息
    """
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    queryset = projectDiDiRecord.objects.all().filter(is_deleted=False)
    filter_fields = ('proj', 'projName', 'orderNumber', 'orderDate', 'orderPerm', 'city', 'startPlace', 'endPlace')
    search_fields = ('projName', 'orderPerm', 'city', 'orderNumber')
    serializer_class = DiDiRecordSerializer

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            if self.request.user.is_authenticated:
                queryset = queryset.filter(datasource=self.request.user.datasource)
            else:
                queryset = queryset.all()
        else:
            raise InvestError(code=8890)
        return queryset

    @loginTokenIsAvailable(['usersys.as_trader'])
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            sortfield = request.GET.get('sort', 'lastmodifytime')
            desc = request.GET.get('desc', 0)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            with transaction.atomic():
                data['createuser'] = request.user.id
                newInstance = TaxiRecordCreateSerializer(data=data)
                if newInstance.is_valid():
                    newInstance.save()
                else:
                    raise InvestError(code=4011, msg='滴滴打车信息存储失败', detail='_%s' % newInstance.error_messages)
            return JSONResponse(SuccessResponse(newInstance.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


def testPdf(request):
    projid = request.GET.get('id')
    lang = request.GET.get('lang', 'cn')
    proj = project.objects.get(id=projid)
    aaa = {
        'project': ProjDetailSerializer_withoutsecretinfo(proj).data,
        'finance': FinanceSerializer(proj.proj_finances.filter(is_deleted=False), many=True).data
    }
    if lang == 'cn':
        res = render(request, 'proj_template_cn.html', aaa)
    else:
        res = render(request, 'proj_template_en.html', aaa)
    return res


def readDidiRecord(csvFilePath):
    modelKeyField = {'成本中心名称': 'projName', '成本中心id': 'proj', '专快订单号': 'orderNumber', '支付时间': 'orderDate',
                     '用车权限': 'orderPerm', '用车城市': 'city', '实际出发地': 'startPlace', '实际目的地': 'endPlace', '企业实付金额': 'money'}
    values = ['成本中心名称', '成本中心id', '专快订单号', '支付时间', '用车权限', '用车城市', '实际出发地', '实际目的地', '企业实付金额']
    valuesdic, data_list = {}, []
    with open(csvFilePath, 'rb') as file:
        encod = chardet.detect(file.readline())['encoding']
        encod = "GBK" if encod =='GB2312' else encod
    with open(csvFilePath, 'r', encoding=encod)as f:
        f_csv = csv.reader(f)
        line_count = 0
        for row in f_csv:
            line_count += 1
            if line_count == 1:
                for i in range(0, len(values)):
                    for j in range(0, len(row)):
                        if row[j] == values[i]:
                            valuesdic[values[i]] = j
                            break
            else:
                data = {'createuser': 1, 'datasource': 1}
                for key, value in modelKeyField.items():
                    data.update({value: row[valuesdic[key]].replace('\t', '')})
                data_list.append(data)
    return data_list

def importDidiRecord(data_list):
    for data in data_list:
        try:
            newInstance = TaxiRecordCreateSerializer(data=data)
            if newInstance.is_valid():
                newInstance.save()
            else:
                logexcption(msg='存储滴滴记录失败--%s' % newInstance.errors)
        except Exception as e:
            logexcption(msg='didi save error')

def importDidiRecordCsvFile():
    csvFilePath = APILOG_PATH['didiRecordCsvFilePath']
    if os.path.exists(csvFilePath):
        try:
            recordData = readDidiRecord(csvFilePath)
            importDidiRecord(recordData)
            os.remove(csvFilePath)
        except Exception as e:
            logexcption(str(e))



class ProjCommentsFilter(FilterSet):
    proj = RelationFilter(filterstr='proj', lookup_method='in')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')
    class Meta:
        model = projcomments
        fields = ('proj', 'createuser')

class ProjCommentsView(viewsets.ModelViewSet):
    """
        list:获取项目进展list
        create:新增项目进展
        retrieve:查看项目进展
        update:修改项目进展
        destroy:删除项目进展
    """
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = ProjCommentsFilter
    queryset = projcomments.objects.all().filter(is_deleted=False)
    serializer_class = ProjCommentsSerializer

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        try:
            obj = projcomments.objects.get(id=self.kwargs[lookup_url_kwarg], is_deleted=False)
        except projcomments.DoesNotExist:
            raise InvestError(code=8892, msg='项目进展不存在', detail='项目进展不存在')
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='查询项目进展失败')
        return obj

    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
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
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable(['usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                data = request.data
                data['datasource'] = request.user.datasource_id
                serializer = ProjCommentsCreateSerializer(data=data)
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

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            serializer = self.serializer_class(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.as_trader'])
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            with transaction.atomic():
                data = request.data
                data["lastmodifyuser"] = request.user.id
                if not data.get('commenttime'):
                    data['commenttime'] = datetime.datetime.now()
                serializer = ProjCommentsCreateSerializer(instance, data=data)
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

    @loginTokenIsAvailable(['usersys.as_trader'])
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.is_deleted = True
            instance.deletedtime = datetime.datetime.now()
            instance.deleteduser = request.user
            instance.save(update_fields=['is_deleted', 'deletedtime', 'deleteduser'])
            return JSONResponse(SuccessResponse({'is_deleted': instance.is_deleted}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


def feishu_update_proj_response(proj_id, response_id, requsetuser_id):
    try:
        proj = project.objects.get(id=proj_id)
        proj.response_id = response_id
        proj.lastmodifyuser_id = requsetuser_id
        proj.save(update_fields=['response', 'lastmodifyuser'])
    except project.DoesNotExist:
        logexcption('飞书项目id：%s,未找到对应项目' % proj_id)
    except Exception as err:
        logexcption('飞书项目状态更新失败: %s' % str(err))


def feishu_update_proj_traders(proj_id, traders, type, requsetuser_id):
    try:
        proj = project.objects.get(id=proj_id)
        for trader in traders:
            if not projTraders.objects.filter(is_deleted=False, user=trader, type=type, proj=proj).exists():
                ins = projTraders(proj=proj, user=trader, type=type,
                            createuser_id=requsetuser_id, createdtime=datetime.datetime.now())
                ins.save()
    except project.DoesNotExist:
        logexcption('飞书项目id：%s,未找到对应项目' % proj_id)
    except Exception as err:
        logexcption('飞书项目交易师导入失败: %s，type：%s' % (str(err), type))


def feishu_update_proj_comments(proj_id, comments, requsetuser_id):
    try:
        proj = project.objects.get(id=proj_id)
        for comment in comments:
            if not projcomments.objects.filter(is_deleted=False, comment=comment, proj=proj).exists():
                ins = projcomments(proj=proj, comment=comment, createuser_id=requsetuser_id,
                             commenttime=datetime.datetime.now(),  createdtime=datetime.datetime.now())
                ins.save()
    except project.DoesNotExist:
        logexcption('飞书项目id：%s,未找到对应项目' % proj_id)
    except Exception as err:
        logexcption('飞书项目最新进展备注导入失败: %s' % str(err))


class GovernmentProjectFilter(FilterSet):
    id = RelationFilter(filterstr='id', lookup_method='in')
    name = RelationFilter(filterstr='name', lookup_method='icontains')
    location = RelationFilter(filterstr='location', lookup_method='in', relationName='location__is_deleted')
    leader = RelationFilter(filterstr='leader', lookup_method='icontains')
    business = RelationFilter(filterstr='business', lookup_method='icontains')
    preference = RelationFilter(filterstr='preference', lookup_method='icontains')
    trader = RelationFilter(filterstr='govproj_traders__trader', lookup_method='in', relationName='govproj_traders__is_deleted')
    tag = RelationFilter(filterstr='govproj_tags__tag', lookup_method='in', relationName='govproj_tags__tag__is_deleted')
    industry = RelationFilter(filterstr='govproj_industrys__industry', lookup_method='in', relationName='govproj_industrys__industry__is_deleted')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')

    class Meta:
        model = GovernmentProject
        fields = ('id', 'name', 'location', 'leader', 'business', 'preference', 'trader', 'tag', 'industry', 'createuser')

class GovernmentProjectView(viewsets.ModelViewSet):
    """
        list:获取政府项目list
        create:新增政府项目
        retrieve:查看政府项目
        update:修改政府项目
        destroy:删除政府项目
    """
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = GovernmentProjectFilter
    queryset = GovernmentProject.objects.all().filter(is_deleted=False)
    serializer_class = GovernmentProjectSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            queryset = self.queryset.filter(datasource=self.request.user.datasource)
        else:
            queryset = self.queryset.all()
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
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
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable(['usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                data = request.data
                tagsdata = data.get('tags')
                infosdata = data.get('infos')
                industrysdata = data.get('industrys')
                historycasesdata = data.get('historycases')
                tradersdata = data.get('traders')
                data['datasource'] =  request.user.datasource_id
                serializer = GovernmentProjectCreateSerializer(data=data)
                if serializer.is_valid():
                    instance = serializer.save()
                    if tagsdata and isinstance(tagsdata,list):
                        newdatalist = []
                        for tagid in tagsdata:
                            newdatalist.append(GovernmentProjectTag(govproj=instance, tag_id=tagid))
                        instance.govproj_tags.bulk_create(newdatalist)
                    if industrysdata and isinstance(industrysdata,list):
                        newdatalist = []
                        for industrydata in industrysdata:
                            newdatalist.append(GovernmentProjectIndustry(govproj=instance, industry_id=industrydata['industry'], bucket=industrydata['bucket'], key=industrydata['key']))
                        instance.govproj_industrys.bulk_create(newdatalist)
                    if infosdata and isinstance(infosdata,list):
                        newdatalist = []
                        for info in infosdata:
                            newdatalist.append(GovernmentProjectInfo(govproj=instance, info=info['info'], type=info['type'], createuser=request.user, createdtime=datetime.datetime.now(), datasource=request.user.datasource))
                        instance.govproj_infos.bulk_create(newdatalist)
                    if historycasesdata and isinstance(historycasesdata,list):
                        newdatalist = []
                        for case in historycasesdata:
                            newdatalist.append(GovernmentProjectHistoryCase(govproj=instance, proj_id=case, createuser=request.user, createdtime=datetime.datetime.now(), datasource=request.user.datasource))
                        instance.govproj_historycases.bulk_create(newdatalist)
                    if tradersdata and isinstance(tradersdata,list):
                        newdatalist = []
                        for trader in tradersdata:
                            newdatalist.append(GovernmentProjectTrader(govproj=instance, trader_id=trader['trader'], type=trader['type'], createuser=request.user, createdtime=datetime.datetime.now(), datasource=request.user.datasource))
                        instance.govproj_traders.bulk_create(newdatalist)
                else:
                    raise InvestError(20071, msg='%s' % serializer.error_messages)
                return JSONResponse(SuccessResponse(GovernmentProjectDetailSerializer(instance).data))
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
            serializer = GovernmentProjectDetailSerializer(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.as_trader'])
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            with transaction.atomic():
                data = request.data
                data["lastmodifyuser"] = request.user.id
                tagsdata = data.get('tags')
                industrysdata = data.get('industrys')
                historycasesdata = data.get('historycases')
                serializer = GovernmentProjectCreateSerializer(instance, data=data)
                if serializer.is_valid():
                    instance = serializer.save()
                    if tagsdata is not None and isinstance(tagsdata,list):
                        exist_tags = instance.govproj_tags.filter(tag__is_deleted=False).values_list('tag', flat=True)
                        addlist = [item for item in tagsdata if item not in exist_tags]
                        removelist = [item for item in exist_tags if item not in tagsdata]
                        instance.govproj_tags.filter(tag__in=removelist).delete()
                        govprojtaglist = []
                        for tag in addlist:
                            govprojtaglist.append(GovernmentProjectTag(govproj=instance, tag_id=tag))
                        instance.govproj_tags.bulk_create(govprojtaglist)
                    if industrysdata is not None and isinstance(industrysdata,list):
                        instance.govproj_industrys.all().delete()
                        newdatalist = []
                        for industrydata in industrysdata:
                            newdatalist.append(GovernmentProjectIndustry(govproj=instance, industry_id=industrydata['industry'], bucket=industrydata['bucket'], key=industrydata['key']))
                        instance.govproj_industrys.bulk_create(newdatalist)
                    if historycasesdata and isinstance(historycasesdata, list):
                        exist_projs = instance.govproj_historycases.filter(proj__is_deleted=False).values_list('proj', flat=True)
                        addlist = [item for item in historycasesdata if item not in exist_projs]
                        removelist = [item for item in exist_projs if item not in historycasesdata]
                        instance.govproj_historycases.filter(proj__in=removelist).update(is_deleted=True, deletedtime=datetime.datetime.now(), deleteduser=request.user)
                        newdatalist = []
                        for case in addlist:
                            newdatalist.append(GovernmentProjectHistoryCase(govproj=instance, proj_id=case, createuser=request.user, createdtime=datetime.datetime.now(), datasource=request.user.datasource))
                        instance.govproj_historycases.bulk_create(newdatalist)
                else:
                    raise InvestError(20071, msg='%s' % serializer.error_messages)
                return JSONResponse(SuccessResponse(GovernmentProjectDetailSerializer(instance).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.as_trader'])
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            for link in ['govproj_infos', 'govprojinfo_attachments', 'govproj_historycases', 'govproj_tags', 'govproj_traders', 'govproj_industrys']:
                manager = getattr(instance, link, None)
                if not manager:
                    continue
                if isinstance(manager, models.Model):
                    if hasattr(manager, 'is_deleted'):
                        if not manager.is_deleted:
                            manager.is_deleted = True
                            manager.save()
                    else:
                        manager.delete()
                else:
                    try:
                        manager.model._meta.get_field('is_deleted')
                        if manager.all().filter(is_deleted=False).count():
                            manager.all().update(is_deleted=True)
                    except FieldDoesNotExist:
                        manager.all().delete()
            instance.is_deleted = True
            instance.deletedtime = datetime.datetime.now()
            instance.deleteduser = request.user
            instance.save(update_fields=['is_deleted', 'deletedtime', 'deleteduser'])
            return JSONResponse(SuccessResponse({'is_deleted': instance.is_deleted}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class GovernmentProjectInfoFilter(FilterSet):
    id = RelationFilter(filterstr='id', lookup_method='in')
    govproj = RelationFilter(filterstr='govproj', lookup_method='in')
    info = RelationFilter(filterstr='info', lookup_method='icontains')
    type = RelationFilter(filterstr='type', lookup_method='in')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')

    class Meta:
        model = GovernmentProjectInfo
        fields = ('id', 'govproj', 'info', 'type', 'createuser')

class GovernmentProjectInfoView(viewsets.ModelViewSet):
    """
        list:获取政府项目信息list
        create:新增政府项目信息
        update:修改政府项目信息
    """
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = GovernmentProjectInfoFilter
    queryset = GovernmentProjectInfo.objects.all().filter(is_deleted=False)
    serializer_class = GovernmentProjectInfoSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            queryset = self.queryset.filter(datasource=self.request.user.datasource)
        else:
            queryset = self.queryset.all()
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
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
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable(['usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                data = request.data
                data['datasource'] = request.user.datasource_id
                serializer = GovernmentProjectInfoCreateSerializer(data=data)
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


    @loginTokenIsAvailable(['usersys.as_trader'])
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            with transaction.atomic():
                data = request.data
                data["lastmodifyuser"] = request.user.id
                serializer = GovernmentProjectInfoCreateSerializer(instance, data=data)
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

class GovernmentProjectInfoAttachmentFilter(FilterSet):
    id = RelationFilter(filterstr='id', lookup_method='in')
    govproj = RelationFilter(filterstr='govprojinfo__govproj', lookup_method='in')
    govprojinfo = RelationFilter(filterstr='govprojinfo', lookup_method='in')
    bucket = RelationFilter(filterstr='bucket', lookup_method='in')
    filename = RelationFilter(filterstr='type', lookup_method='icontains')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')

    class Meta:
        model = GovernmentProjectInfoAttachment
        fields = ('id', 'govproj', 'govprojinfo', 'bucket', 'filename', 'createuser')

class GovernmentProjectInfoAttachmentView(viewsets.ModelViewSet):
    """
        list:获取政府项目附件
        create:新增政府项目附件
        destroy:删除政府项目附件
    """
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = GovernmentProjectInfoAttachmentFilter
    queryset = GovernmentProjectInfoAttachment.objects.all().filter(is_deleted=False)
    serializer_class = GovernmentProjectInfoAttachmentSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            queryset = self.queryset.filter(datasource=self.request.user.datasource)
        else:
            queryset = self.queryset.all()
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
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
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable(['usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                data = request.data
                data['datasource'] = request.user.datasource_id
                serializer = GovernmentProjectInfoAttachmentCreateSerializer(data=data)
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


    @loginTokenIsAvailable(['usersys.as_trader'])
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save(update_fields=['is_deleted', 'deletedtime', 'deleteduser'])
            return JSONResponse(SuccessResponse({'is_deleted': instance.is_deleted}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class GovernmentProjectHistoryCaseFilter(FilterSet):
    id = RelationFilter(filterstr='id', lookup_method='in')
    govproj = RelationFilter(filterstr='govproj', lookup_method='in')
    proj = RelationFilter(filterstr='proj', lookup_method='in')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')

    class Meta:
        model = GovernmentProjectHistoryCase
        fields = ('id', 'govproj', 'proj', 'createuser')


class GovernmentProjectHistoryCaseView(viewsets.ModelViewSet):
    """
        list:获取政府项目附件历史案例
        create:新增政府项目附件历史案例
        destroy:删除政府项目附件历史案例
    """
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = GovernmentProjectHistoryCaseFilter
    queryset = GovernmentProjectHistoryCase.objects.all().filter(is_deleted=False)
    serializer_class = GovernmentProjectHistoryCaseSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            queryset = self.queryset.filter(datasource=self.request.user.datasource)
        else:
            queryset = self.queryset.all()
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
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
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                data = request.data
                data['datasource'] = request.user.datasource_id
                serializer = GovernmentProjectHistoryCaseCreateSerializer(data=data)
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

    @loginTokenIsAvailable(['usersys.as_trader'])
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save(update_fields=['is_deleted', 'deletedtime', 'deleteduser'])
            return JSONResponse(SuccessResponse({'is_deleted': instance.is_deleted}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class GovernmentProjectTraderFilter(FilterSet):
    id = RelationFilter(filterstr='id', lookup_method='in')
    govproj = RelationFilter(filterstr='govproj', lookup_method='in')
    trader = RelationFilter(filterstr='trader', lookup_method='in')
    type = RelationFilter(filterstr='type', lookup_method='in')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')

    class Meta:
        model = GovernmentProjectTrader
        fields = ('id', 'govproj', 'trader', 'type', 'createuser')


class GovernmentProjectTraderView(viewsets.ModelViewSet):
    """
        list:获取政府项目交易师
        create:新增政府项目附件交易师
        destroy:删除政府项目附件交易师
    """
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = GovernmentProjectTraderFilter
    queryset = GovernmentProjectTrader.objects.all().filter(is_deleted=False)
    serializer_class = GovernmentProjectTraderSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            queryset = self.queryset.filter(datasource=self.request.user.datasource)
        else:
            queryset = self.queryset.all()
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
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
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                data = request.data
                data['datasource'] = request.user.datasource_id
                serializer = GovernmentProjectTraderCreateSerializer(data=data)
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


    @loginTokenIsAvailable(['usersys.as_trader'])
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save(update_fields=['is_deleted', 'deletedtime', 'deleteduser'])
            return JSONResponse(SuccessResponse({'is_deleted': instance.is_deleted}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))