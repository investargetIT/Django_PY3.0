#coding=utf-8
import os
import threading
import traceback
import datetime
import xlwt
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q, FieldDoesNotExist, Count
from django.http import StreamingHttpResponse
from rest_framework import filters , viewsets
from rest_framework.decorators import api_view

from invest.settings import APILOG_PATH
from mongoDoc.models import ProjectData, MergeFinanceData
from org.models import organization, orgTransactionPhase, orgRemarks, orgContact, orgBuyout, orgManageFund, \
    orgInvestEvent, orgCooperativeRelationship, \
    orgTags, orgExportExcelTask, orgAttachments, orgalias
from org.serializer import OrgCommonSerializer, OrgDetailSerializer, OrgRemarkDetailSerializer, OrgCreateSerializer, \
    OrgUpdateSerializer, OrgBuyoutCreateSerializer, OrgContactCreateSerializer, OrgInvestEventCreateSerializer, \
    OrgManageFundCreateSerializer, OrgCooperativeRelationshipCreateSerializer, OrgBuyoutSerializer, \
    OrgContactSerializer, \
    OrgInvestEventSerializer, OrgManageFundSerializer, OrgCooperativeRelationshipSerializer, OrgListSerializer, \
    OrgExportExcelTaskSerializer, \
    OrgExportExcelTaskDetailSerializer, OrgAttachmentSerializer, OrgRemarkCreateSerializer, orgaliasCreateSerializer, \
    orgaliasSerializer
from sourcetype.models import TransactionPhases, TagContrastTable
from third.views.qiniufile import deleteqiniufile, downloadFileToPath
from usersys.models import UserRelation, MyUser
from utils.customClass import InvestError, JSONResponse, RelationFilter, MySearchFilter
from utils.logicJudge import is_orgUserTrader
from utils.somedef import file_iterator, getEsScrollResult
from utils.util import loginTokenIsAvailable, catchexcption, read_from_cache, write_to_cache, \
    returnListChangeToLanguage, \
    returnDictChangeToLanguage, SuccessResponse, InvestErrorResponse, ExceptionResponse, setrequestuser, \
    cache_delete_key, mySortQuery, checkrequesttoken, logexcption, china_mobile, hongkong_mobile, hongkong_telephone, \
    checkRequestToken, checkrequestpagesize
from django.db import transaction,models
from django_filters import FilterSet


class OrganizationFilter(FilterSet):
    proj = RelationFilter(filterstr='org_orgBDs__proj', relationName='org_orgBDs__is_deleted', lookup_method='in')
    orgfullname = RelationFilter(filterstr='orgfullname')
    ids = RelationFilter(filterstr='id', lookup_method='in')
    country = RelationFilter(filterstr='country', lookup_method='in', relationName='country__is_deleted')
    stockcode = RelationFilter(filterstr='stockcode',lookup_method='in')
    stockshortname = RelationFilter(filterstr='stockshortname',lookup_method='in')
    issub = RelationFilter(filterstr='issub', lookup_method='exact')
    investoverseasproject = RelationFilter(filterstr='investoverseasproject', lookup_method='exact')
    industrys = RelationFilter(filterstr='industry', lookup_method='in', relationName='industry__is_deleted')
    currencys = RelationFilter(filterstr='currency', lookup_method='in', relationName='currency__is_deleted')
    orgname = RelationFilter(filterstr='orgnameC', lookup_expr='icontains')
    alias = RelationFilter(filterstr='org_orgalias__alias', lookup_expr='icontains', relationName='org_orgalias__is_deleted')
    users = RelationFilter(filterstr='org_users', lookup_method='in', relationName='org_users__is_deleted')
    orgtransactionphases = RelationFilter(filterstr='orgtransactionphase',lookup_method='in',relationName='org_orgTransactionPhases__is_deleted')
    orgtypes = RelationFilter(filterstr='orgtype',lookup_method='in', relationName='orgtype__is_deleted')
    orgstatus = RelationFilter(filterstr='orgstatus',lookup_method='in', relationName='orgstatus__is_deleted')
    area = RelationFilter(filterstr='org_users__orgarea',lookup_method='in',relationName='org_users__is_deleted')
    trader = RelationFilter(filterstr='org_users__investor_relations__traderuser',lookup_method='in',relationName='org_users__investor_relations__is_deleted')
    class Meta:
        model = organization
        fields = ['orgname', 'alias', 'proj','orgfullname', 'orgstatus','currencys','industrys','orgtransactionphases','orgtypes','area','trader','stockcode','stockshortname','issub','investoverseasproject', 'ids']

class OrganizationView(viewsets.ModelViewSet):
    """
    list:获取机构列表
    create:新增机构
    retrieve:查看机构详情
    update:修改机构信息
    destroy:删除机构
    """
    filter_backends = (MySearchFilter,filters.DjangoFilterBackend,)
    queryset = organization.objects.filter(is_deleted=False)
    filter_class = OrganizationFilter
    search_fields = ('orgnameC','orgnameE','stockcode', 'orgfullname', 'org_orgalias__alias')
    serializer_class = OrgDetailSerializer
    redis_key = 'organization'

    def get_object(self, pk=None):
        if pk:
            obj = read_from_cache(self.redis_key + '_%s' % pk)
            if not obj:
                try:
                    obj = self.get_queryset().get(id=pk)
                except organization.DoesNotExist:
                    raise InvestError(code=5002, msg='获取机构失败', detail='机构不存在')
                else:
                    write_to_cache(self.redis_key + '_%s' % pk, obj)
        else:
            lookup_url_kwarg = 'pk'
            obj = read_from_cache(self.redis_key + '_%s' % self.kwargs[lookup_url_kwarg])
            if not obj:
                try:
                    obj = self.get_queryset().get(id=self.kwargs[lookup_url_kwarg])
                except organization.DoesNotExist:
                    raise InvestError(code=5002, msg='获取机构失败', detail='机构不存在')
                else:
                    write_to_cache(self.redis_key + '_%s' % self.kwargs[lookup_url_kwarg], obj)
        return obj


    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            setrequestuser(request)
            checkrequestpagesize(request)
            queryset = self.filter_queryset(self.get_queryset())
            tags = request.GET.get('tags', None)
            if tags:
                tags = tags.split(',')
                queryset = queryset.filter(Q(org_users__tags__in=tags, org_users__tags__is_deleted=False) | Q(org_orgtags__tag__in=tags, org_orgtags__tag__is_deleted=False)).distinct()
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = mySortQuery(queryset, sortfield, desc)
            if request.user.is_anonymous:
                serializerclass = OrgCommonSerializer
            else:
                serializerclass = OrgListSerializer
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializerclass(queryset, many=True).data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable(['org.admin_manageorg', 'usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        if not data.get('createuser'):
            data['createuser'] = request.user.id
        data['datasource'] = request.user.datasource.id
        try:
            with transaction.atomic():
                orgTransactionPhases = data.pop('orgtransactionphase', None)
                orgserializer = OrgCreateSerializer(data=data)
                if orgserializer.is_valid():
                    org = orgserializer.save()
                    if orgTransactionPhases and isinstance(orgTransactionPhases,list):
                        orgTransactionPhaselist = []
                        for transactionPhase in orgTransactionPhases:
                            orgTransactionPhaselist.append(orgTransactionPhase(org=org, transactionPhase_id=transactionPhase,createuser=request.user,createdtime=datetime.datetime.now()))
                        org.org_orgTransactionPhases.bulk_create(orgTransactionPhaselist)
                    tags = data.pop('tags', None)
                    if tags:
                        orgtaglist = []
                        for tag in tags:
                            orgtaglist.append(orgTags(org=org, tag_id=tag, createdtime=datetime.datetime.now()))
                        org.org_orgtags.bulk_create(orgtaglist)
                else:
                    raise InvestError(20071, msg='新增机构失败', detail='%s' % orgserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(OrgDetailSerializer(org).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            org = self.get_object()
            lang = request.GET.get('lang')
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, org):
                orgserializer = OrgDetailSerializer
            elif request.user == org.createuser or request.user.org == org:
                orgserializer = OrgDetailSerializer
            else:
                orgserializer = OrgListSerializer
            serializer = orgserializer(org)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        data['lastmodifyuser'] = request.user.id
        try:
            org = self.get_object()
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, org):
                pass
            elif request.user == org.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='修改机构信息失败')
            with transaction.atomic():
                orgTransactionPhases = data.pop('orgtransactionphase', None)
                tags = data.pop('tags', None)
                orgupdateserializer = OrgUpdateSerializer(org, data=data)
                if orgupdateserializer.is_valid():
                    org = orgupdateserializer.save()
                    if orgTransactionPhases is not None:
                        transactionPhaselist = TransactionPhases.objects.filter(is_deleted=False).in_bulk(orgTransactionPhases)
                        addlist = [item for item in transactionPhaselist if item not in org.orgtransactionphase.all()]
                        removelist = [item for item in org.orgtransactionphase.all() if item not in transactionPhaselist]
                        org.org_orgTransactionPhases.filter(transactionPhase__in=removelist, is_deleted=False).delete()
                        usertaglist = []
                        for transactionPhase in addlist:
                            usertaglist.append(orgTransactionPhase(org=org, transactionPhase_id=transactionPhase, createuser=request.user,createdtime=datetime.datetime.now()))
                        org.org_orgTransactionPhases.bulk_create(usertaglist)
                    if tags is not None:
                        org.org_orgtags.all().delete()
                        orgtaglist = []
                        for tag in tags:
                            orgtaglist.append(orgTags(org=org, tag_id=tag, createdtime=datetime.datetime.now()))
                        org.org_orgtags.bulk_create(orgtaglist)
                else:
                    raise InvestError(20071, msg='修改机构信息失败', detail='%s' % orgupdateserializer.error_messages)
                cache_delete_key(self.redis_key + '_%s' % org.id)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(OrgDetailSerializer(org).data,lang)))
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
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='删除机构失败')
            with transaction.atomic():
                for link in ['org_users','org_orgTransactionPhases','org_remarks','org_unreachuser','org_orgBDs','org_orgInvestEvent'
                             'org_orgManageFund','fund_fundManager','org_orgcontact','org_cooperativeRelationship','cooperativeorg_Relationship'
                             'org_buyout','buyoutorg_buyoutorg','org_OrgBdBlacks']:
                    if link in ['org_users', 'org_orgBDs']:
                        manager = getattr(instance, link, None)
                        if not manager:
                            continue
                        # one to one
                        if isinstance(manager, models.Model):
                            if hasattr(manager, 'is_deleted') and not manager.is_deleted:
                                raise InvestError(code=2010, msg='删除机构失败', detail='{} 上有关联数据'.format(link))
                        else:
                            try:
                                manager.model._meta.get_field('is_deleted')
                                if manager.all().filter(is_deleted=False).count():
                                    raise InvestError(code=2010, msg='删除机构失败', detail='{} 上有关联数据'.format(link))
                            except FieldDoesNotExist:
                                if manager.all().count():
                                    raise InvestError(code=2010, msg='删除机构失败', detail='{} 上有关联数据，且没有is_deleted字段'.format(link))
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
                instance.deletetime = datetime.datetime.utcnow()
                instance.save()
                cache_delete_key(self.redis_key + '_%s' % instance.id)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(OrgDetailSerializer(instance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class orgRemarksFilter(FilterSet):
    id = RelationFilter(filterstr='id', lookup_method='in')
    org = RelationFilter(filterstr='org', lookup_method='in')
    createuser = RelationFilter(filterstr='createuser',lookup_method='in')
    stime = RelationFilter(filterstr='createdtime', lookup_method='gte')
    etime = RelationFilter(filterstr='createdtime', lookup_method='lt')
    stimeM = RelationFilter(filterstr='lastmodifytime', lookup_method='gte')
    etimeM = RelationFilter(filterstr='lastmodifytime', lookup_method='lt')
    class Meta:
        model = orgRemarks
        fields = ('id','org','createuser', 'stime', 'etime', 'stimeM', 'etimeM')

class OrgRemarkView(viewsets.ModelViewSet):
    """
    list:获取机构备注列表
    create:新增机构备注
    retrieve:查看机构某条备注详情（id）
    update:修改机构备注信息（id）
    destroy:删除机构备注 （id）
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = orgRemarks.objects.filter(is_deleted=False)
    filter_class = orgRemarksFilter
    serializer_class = OrgRemarkCreateSerializer


    def get_object(self, pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk)
            except orgRemarks.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构备注失败', detail='机构备注不存在')
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'])
            except orgRemarks.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构备注失败', detail='机构备注不存在')
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='获取机构备注失败')
        return obj

    def get_org(self,orgid):
        if self.request.user.is_anonymous:
            raise InvestError(code=8889, msg='用户未登陆', detail='用户未登陆')
        try:
            org = organization.objects.get(id=orgid,is_deleted=False)
        except organization.DoesNotExist:
            raise InvestError(code=5002, msg='获取机构备注失败', detail='机构不存在')
        else:
            return org

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=request.user.datasource)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = OrgRemarkDetailSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            if not data.get('createuser'):
                data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            with transaction.atomic():
                orgremarkserializer = OrgRemarkCreateSerializer(data=data)
                if orgremarkserializer.is_valid():
                    orgremarkserializer.save()
                else:
                    raise InvestError(20071, msg='新增机构备注失败', detail='%s' % orgremarkserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(orgremarkserializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            orgremark = self.get_object()
            serializer = OrgRemarkDetailSerializer(orgremark)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            lang = request.GET.get('lang')
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='编辑机构备注信息失败')
            data = request.data
            data['lastmodifyuser'] = request.user.id
            with transaction.atomic():
                orgserializer = OrgRemarkCreateSerializer(instance, data=data)
                if orgserializer.is_valid():
                    orgserializer.save()
                else:
                    raise InvestError(20071, msg='编辑机构备注信息失败', detail='%s' % orgserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(orgserializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='删除机构备注信息失败')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(OrgRemarkDetailSerializer(instance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class orgaliasFilter(FilterSet):
    org = RelationFilter(filterstr='org', lookup_method='in', relationName='org__is_deleted')
    alias = RelationFilter(filterstr='alias')
    class Meta:
        model = orgalias
        fields = ('org', 'alias')

class orgaliasView(viewsets.ModelViewSet):
    """
    list:获取机构别名列表
    create:新增机构别名
    destroy:删除机构别名 （id）
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = orgalias.objects.filter(is_deleted=False)
    filter_class = orgaliasFilter
    serializer_class = orgaliasCreateSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            queryset = self.filter_queryset(self.get_queryset())
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = orgaliasSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data': serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            with transaction.atomic():
                insserializer = orgaliasCreateSerializer(data=data)
                if insserializer.is_valid():
                    insserializer.save()
                else:
                    raise InvestError(20071, msg='新增机构别名失败', detail='%s' % insserializer.error_messages)
                return JSONResponse(SuccessResponse(insserializer.data))
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
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse({'is_deleted': True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



class OrgContactView(viewsets.ModelViewSet):
    """
    list:获取机构联系方式
    create:新增机构联系方式
    retrieve:查看机构某条联系方式详情（id）
    update:修改机构联系方式（id）
    destroy:删除机构联系方式（id）
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = orgContact.objects.filter(is_deleted=False).filter(org__is_deleted=False)
    filter_fields = ('id','org','createuser')
    serializer_class = OrgContactSerializer
    models = orgContact

    def get_object(self, pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk)
            except self.models.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构联系方式失败', detail='机构联系方式不存在')
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'])
            except self.models.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构联系方式失败', detail='机构联系方式不存在')
        return obj

    def get_org(self,orgid):
        if self.request.user.is_anonymous:
            raise InvestError(code=8889, msg='用户未登录', detail='用户未登录')
        try:
            org = organization.objects.get(id=orgid,is_deleted=False)
        except organization.DoesNotExist:
            raise InvestError(code=5002, msg='获取机构联系方式失败', detail='机构不存在')
        else:
            return org

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            orgid = request.GET.get('org', None)
            if not orgid:
                raise InvestError(20072, msg='获取机构联系方式失败', detail='机构（org）不能为空')
            queryset = self.filter_queryset(self.get_queryset())
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        orgid = data.get('org',None)
        if orgid:
            org = self.get_org(orgid=orgid)
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, org):
                pass
            elif request.user.org == org or request.user == org.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='新增机构联系方式失败')
        else:
            raise InvestError(code=20072, msg='新增机构联系方式失败', detail='机构（org）不能为空')
        data['createuser'] = request.user.id
        try:
            with transaction.atomic():
                instanceserializer = OrgContactCreateSerializer(data=data)
                if instanceserializer.is_valid():
                    instance = instanceserializer.save()
                else:
                    raise InvestError(20071, msg='新增机构联系方式失败', detail='%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
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
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            lang = request.GET.get('lang')
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='修改机构联系方式失败')
            data = request.data
            data['lastmodifytime'] = datetime.datetime.now()
            with transaction.atomic():
                instanceserializer = OrgContactCreateSerializer(instance, data=data)
                if instanceserializer.is_valid():
                    newinstance = instanceserializer.save()
                else:
                    raise InvestError(20071, msg='修改机构联系方式失败', detail='%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(newinstance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='删除机构联系方式失败', detail='没有权限')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class OrgManageFundFilter(FilterSet):
    id = RelationFilter(filterstr='id', lookup_method='in')
    org = RelationFilter(filterstr='org', lookup_method='in')
    fund = RelationFilter(filterstr='fund',lookup_method='in')
    createuser = RelationFilter(filterstr='createuser',lookup_method='in')
    class Meta:
        model = orgManageFund
        fields = ('id', 'org', 'fund', 'createuser')


class OrgManageFundView(viewsets.ModelViewSet):
    """
    list:获取机构管理基金
    create:新增机构管理基金
    retrieve:查看机构某条管理基金详情（id）
    update:修改机构管理基金（id）
    destroy:删除机构管理基金id）
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = orgManageFund.objects.filter(is_deleted=False, org__is_deleted=False, fund__is_deleted=False)
    filter_class = OrgManageFundFilter
    serializer_class = OrgManageFundSerializer
    models = orgManageFund

    def get_object(self, pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk)
            except self.models.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构管理基金失败', detail='管理基金不存在')
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'])
            except self.models.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构管理基金失败', detail='管理基金不存在')
        return obj

    def get_org(self,orgid):
        if self.request.user.is_anonymous:
            raise InvestError(code=8889, msg='用户未登录', detail='用户未登录')
        try:
            org = organization.objects.get(id=orgid,is_deleted=False)
        except organization.DoesNotExist:
            raise InvestError(code=5002, msg='获取机构管理基金失败', detail='机构不存在')
        else:
            return org

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            orgid = request.GET.get('org', None)
            if not orgid:
                raise InvestError(20072, msg='获取机构管理基金失败', detail='机构（org）不能为空')
            queryset = self.filter_queryset(self.get_queryset()).order_by('-fundraisedate')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        orgid = data.get('org',None)
        if orgid:
            org = self.get_org(orgid=orgid)
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, org):
                pass
            elif request.user.org == org or request.user == org.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='新增机构管理基金失败')
        else:
            raise InvestError(code=20072, msg='新增机构管理基金失败', detail='机构（org）不能为空')
        data['createuser'] = request.user.id
        try:
            with transaction.atomic():
                instanceserializer = OrgManageFundCreateSerializer(data=data)
                if instanceserializer.is_valid():
                    instance = instanceserializer.save()
                else:
                    raise InvestError(20071, msg='新增机构管理基金失败', detail='%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
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
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            lang = request.GET.get('lang')
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='修改机构管理基金信息失败')
            data = request.data
            data['lastmodifytime'] = datetime.datetime.now()
            with transaction.atomic():
                instanceserializer = OrgManageFundCreateSerializer(instance, data=data)
                if instanceserializer.is_valid():
                    newinstance = instanceserializer.save()
                else:
                    raise InvestError(20071, msg='修改机构管理基金信息失败', detail='%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(newinstance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='删除机构管理基金信息失败')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class OrgInvestEventView(viewsets.ModelViewSet):
    """
    list:获取机构投资事件
    create:新增机构投资事件
    retrieve:查看机构某条投资事件详情（id）
    update:修改机构投资事件（id）
    destroy:删除机构投资事件id）
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = orgInvestEvent.objects.filter(is_deleted=False).filter(org__is_deleted=False)
    filter_fields = ('id','org','createuser')
    serializer_class = OrgInvestEventSerializer
    models = orgInvestEvent

    def get_object(self, pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk)
            except self.models.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构投资经历失败', detail='投资经历不存在')
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'])
            except self.models.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构投资经历失败', detail='投资经历不存在')
        return obj

    def get_org(self,orgid):
        if self.request.user.is_anonymous:
            raise InvestError(code=8889, msg='用户未登录', detail='用户未登录')
        try:
            org = organization.objects.get(id=orgid,is_deleted=False)
        except organization.DoesNotExist:
            raise InvestError(code=5002, msg='获取机构投资经历失败', detail='机构不存在')
        else:
            return org

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            orgid = request.GET.get('org', None)
            if not orgid:
                raise InvestError(20072, msg='获取机构投资经历失败', detail='机构不能为空')
            else:
                orginstace = self.get_org(orgid)
            queryset = self.filter_queryset(self.get_queryset()).order_by('-investDate')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        orgid = data.get('org',None)
        if orgid:
            org = self.get_org(orgid=orgid)
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, org):
                pass
            elif request.user.org == org or request.user == org.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='新增机构投资经历失败')
        else:
            raise InvestError(code=20072, msg='新增机构投资经历失败', detail='机构不能为空')
        data['createuser'] = request.user.id
        industrytype = data.get('industrytype', None)
        Pindustrytype = data.get('Pindustrytype', None)
        try:
            with transaction.atomic():
                instanceserializer = OrgInvestEventCreateSerializer(data=data)
                if instanceserializer.is_valid():
                    instance = instanceserializer.save()
                    useP = False
                    if industrytype:
                        for tag_id in TagContrastTable.objects.filter(cat_name=industrytype).values_list('tag_id'):
                            useP = True
                            if not orgTags.objects.filter(org_id=orgid, tag_id=tag_id[0]).exists():
                                orgTags(org_id=orgid, tag_id=tag_id[0]).save()
                    if not useP:
                        if Pindustrytype:
                            for tag_id in TagContrastTable.objects.filter(cat_name=Pindustrytype).values_list('tag_id'):
                                if not orgTags.objects.filter(org_id=orgid, tag_id=tag_id[0]).exists():
                                    orgTags(org_id=orgid, tag_id=tag_id[0]).save()
                else:
                    raise InvestError(20071, msg='新增机构投资经历失败', detail='投资经历不存在''%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
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
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            lang = request.GET.get('lang')
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='修改机构投资经历失败')
            data = request.data
            data['lastmodifytime'] = datetime.datetime.now()
            industrytype = data.get('industrytype', None)
            Pindustrytype = data.get('Pindustrytype', None)
            with transaction.atomic():
                instanceserializer = OrgInvestEventCreateSerializer(instance, data=data)
                if instanceserializer.is_valid():
                    newinstance = instanceserializer.save()
                    useP = False
                    if industrytype:
                        for tag_id in TagContrastTable.objects.filter(cat_name=industrytype).values_list('tag_id'):
                            useP = True
                            if not orgTags.objects.filter(org_id=newinstance.org_id, tag_id=tag_id[0]).exists():
                                orgTags(org_id=newinstance.org_id, tag_id=tag_id[0]).save()
                    if not useP:
                        if Pindustrytype:
                            for tag_id in TagContrastTable.objects.filter(cat_name=Pindustrytype).values_list('tag_id'):
                                if not orgTags.objects.filter(org_id=newinstance.org_id, tag_id=tag_id[0]).exists():
                                    orgTags(org_id=newinstance.org_id, tag_id=tag_id[0]).save()
                else:
                    raise InvestError(20071, msg='修改机构投资经历失败', detail='%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(newinstance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='删除机构投资经历失败')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class OrgCooperativeRelationshipView(viewsets.ModelViewSet):
    """
    list:获取机构合作关系
    create:新增机构合作关系
    retrieve:查看机构某条合作关系详情（id）
    update:修改机构合作关系（id）
    destroy:删除机构合作关系id）
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = orgCooperativeRelationship.objects.filter(is_deleted=False).filter(org__is_deleted=False, cooperativeOrg__is_deleted=False)
    filter_fields = ('id', 'createuser', 'org')
    serializer_class = OrgCooperativeRelationshipSerializer
    models = orgCooperativeRelationship

    def get_object(self, pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk)
            except self.models.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构合作关系失败', detail='合作关系不存在')
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'])
            except self.models.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构合作关系失败', detail='合作关系不存在')
        return obj

    def get_org(self,orgid):
        if self.request.user.is_anonymous:
            raise InvestError(code=8889, msg='用户未登录', detail='用户未登录')
        try:
            org = organization.objects.get(id=orgid,is_deleted=False)
        except organization.DoesNotExist:
            raise InvestError(code=5002, msg='获取机构合作关系失败', detail='机构不存在')
        else:
            return org

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            orgid = request.GET.get('org', None)
            if not orgid:
                raise InvestError(20072, msg='获取机构合作关系失败', detail='机构不能为空')
            queryset = self.filter_queryset(self.get_queryset()).order_by('-investDate')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        orgid = data.get('org',None)
        if orgid:
            org = self.get_org(orgid=orgid)
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, org):
                pass
            elif request.user.org == org or request.user == org.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='新增机构合作关系失败')
        else:
            raise InvestError(code=20072, msg='新增机构合作关系失败', detail='机构不能为空')
        data['createuser'] = request.user.id
        try:
            with transaction.atomic():
                instanceserializer = OrgCooperativeRelationshipCreateSerializer(data=data)
                if instanceserializer.is_valid():
                    instance = instanceserializer.save()
                else:
                    raise InvestError(20071, msg='新增机构合作关系失败', detail='%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
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
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            lang = request.GET.get('lang')
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='修改机构合作关系失败')
            data = request.data
            data['lastmodifytime'] = datetime.datetime.now()
            with transaction.atomic():
                instanceserializer = OrgCooperativeRelationshipCreateSerializer(instance, data=data)
                if instanceserializer.is_valid():
                    newinstance = instanceserializer.save()
                else:
                    raise InvestError(20071, msg='修改机构合作关系失败', detail='%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(newinstance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='删除机构合作关系失败')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class OrgBuyoutView(viewsets.ModelViewSet):
    """
    list:获取机构退出分析
    create:新增机构退出分析
    retrieve:查看机构某条退出分析详情（id）
    update:修改机构退出分析（id）
    destroy:删除机构退出分析（id）
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = orgBuyout.objects.filter(is_deleted=False).filter(org__is_deleted=False, buyoutorg__is_deleted=False)
    filter_fields = ('id','org','createuser')
    serializer_class = OrgBuyoutSerializer
    models = orgBuyout

    def get_object(self, pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk)
            except self.models.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构退出经历失败', detail='退出经历不存在')
        else:
            try:
                obj = self.queryset.get(id=self.kwargs['pk'])
            except self.models.DoesNotExist:
                raise InvestError(code=5002, msg='获取机构退出经历失败', detail='退出经历不存在')
        return obj

    def get_org(self,orgid):
        if self.request.user.is_anonymous:
            raise InvestError(code=8889, msg='用户未登录', detail='用户未登录')
        try:
            org = organization.objects.get(id=orgid,is_deleted=False)
        except organization.DoesNotExist:
            raise InvestError(code=5002, msg='获取机构退出经历失败', detail='机构不存在')
        else:
            return org

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            orgid = request.GET.get('org', None)
            if not orgid:
                raise InvestError(20072, msg='获取机构退出经历失败', detail='机构不能为空')
            queryset = self.filter_queryset(self.get_queryset()).order_by('-buyoutDate')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        orgid = data.get('org', None)
        if orgid:
            org = self.get_org(orgid=orgid)
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, org):
                pass
            elif request.user.org == org or request.user == org.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='新增机构退出经历失败')
        else:
            raise InvestError(code=20072, msg='新增机构退出经历失败', detail='机构不能为空')
        if not data.get('createuser'):
            data['createuser'] = request.user.id
        try:
            with transaction.atomic():
                instanceserializer = OrgBuyoutCreateSerializer(data=data)
                if instanceserializer.is_valid():
                    instance = instanceserializer.save()
                else:
                    raise InvestError(20071, msg='新增机构退出经历失败', detail='%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
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
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            lang = request.GET.get('lang')
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='修改机构退出经历失败')
            data = request.data
            data['lastmodifytime'] = datetime.datetime.now()
            with transaction.atomic():
                instanceserializer = OrgBuyoutCreateSerializer(instance, data=data)
                if instanceserializer.is_valid():
                    newinstance = instanceserializer.save()
                else:
                    raise InvestError(20071, msg='修改机构退出经历失败', detail='%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(newinstance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='删除机构退出经历失败')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))




class OrgExportExcelTaskView(viewsets.ModelViewSet):
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = orgExportExcelTask.objects.filter(is_deleted=False)
    filter_fields = ('status', 'filename', 'createuser')
    serializer_class = OrgExportExcelTaskSerializer
    redis_key = 'orgExportExcleTask'

    def expireTasks(self):
        task_qs = self.get_queryset().filter(status__in=[3, 4, 5], is_deleted=False,
                                                    completetime__lt=(
                                                    datetime.datetime.now() - datetime.timedelta(days=1)))

        if task_qs.exists():
            for task in task_qs:
                fullpath = APILOG_PATH['orgExportPath'] + task.filename
                if os.path.exists(fullpath):
                    os.remove(fullpath)
                task.delete()

    @loginTokenIsAvailable(['org.export_org',])
    def list(self, request, *args, **kwargs):
        try:
            self.expireTasks()
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset()).order_by('-createdtime')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = OrgExportExcelTaskDetailSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count, 'data':returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['org.export_org',])
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                data = request.data
                orglist = data.get('org')
                taglist = data.get('tag')
                if len(orglist) > 0:
                    path = str(datetime.datetime.now())[:19].replace(' ', 'T') + '.xls'
                    data = {
                        'orglist': orglist,
                        'taglist': taglist,
                        'filename': path,
                        'createuser': request.user.id,
                    }
                else:
                    raise InvestError(20071, msg='新增机构导出任务失败', detail='org 不能为空')
                instanceserializer = OrgExportExcelTaskSerializer(data=data)
                if instanceserializer.is_valid():
                    instance = instanceserializer.save()
                    makeExportOrgExcel()
                else:
                    raise InvestError(20071, msg='新增机构导出任务失败', detail='%s' % instanceserializer.error_messages)
                return JSONResponse(SuccessResponse(self.serializer_class(instance).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def downExcel(self, request, *args, **kwargs):
        try:
            user = checkrequesttoken(request.GET.get('token', None))
            if not user.has_perm('org.export_org'):
                raise InvestError(2009, msg='下载机构导出excel失败')
            rootdirpath = APILOG_PATH['orgExportPath']
            instance = self.get_object()
            fullpath = rootdirpath + instance.filename
            if os.path.exists(fullpath) and instance.status == 5:
                fn = open(fullpath, 'rb')
                response = StreamingHttpResponse(file_iterator(fn))
                response['Content-Type'] = 'application/octet-stream'
                response["content-disposition"] = 'attachment;filename=%s' % instance.filename
            else:
                raise InvestError(8002, msg='下载机构导出excel失败', detail='文件不存在或者已过期')
            return response
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['org.export_org',])
    def destroy(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            with transaction.atomic():
                fullpath = APILOG_PATH['orgExportPath'] + instance.filename
                if os.path.exists(fullpath):
                    os.remove(fullpath)
                instance.delete()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class OrgAttachmentFilter(FilterSet):
    org = RelationFilter(filterstr='org', lookup_method='in')
    stime = RelationFilter(filterstr='createdtime', lookup_method='gte')
    etime = RelationFilter(filterstr='createdtime', lookup_method='lt')
    stimeM = RelationFilter(filterstr='lastmodifytime', lookup_method='gte')
    etimeM = RelationFilter(filterstr='lastmodifytime', lookup_method='lt')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')

    class Meta:
        model = orgAttachments
        fields = ('org', 'stime', 'etime', 'stimeM', 'etimeM', 'createuser')

class OrgAttachmentView(viewsets.ModelViewSet):
    """
            list: 机构附件列表
            create: 新建机构附件
            update: 修改机构附件信息
            destroy: 删除机构附件
            """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = orgAttachments.objects.all().filter(is_deleted=False)
    filter_class = OrgAttachmentFilter
    serializer_class = OrgAttachmentSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = mySortQuery(queryset, sortfield, desc)
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

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        if not data.get('createuser'):
            data['createuser'] = request.user.id
        try:
            with transaction.atomic():
                attachmentserializer = self.serializer_class(data=data)
                if attachmentserializer.is_valid():
                    attachmentserializer.save()
                else:
                    raise InvestError(20071, msg='新增机构附件失败', detail='%s' %  attachmentserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(attachmentserializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='修改机构附件失败', detail='非机构投资人交易师或该条记录创建者')
            lang = request.GET.get('lang')
            data = request.data
            data['createuser'] = request.user.id
            with transaction.atomic():
                serializer = self.serializer_class(instance, data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    raise InvestError(20071, msg='修改机构附件失败', detail='%s' % serializer.error_messages)
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('org.admin_manageorg') or is_orgUserTrader(request.user, instance.org):
                pass
            elif request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='删除机构附件失败', detail='非机构投资人交易师或该条记录创建者')
            with transaction.atomic():
                instance.is_deleted = True
                deleteqiniufile(instance.bucket, instance.key)
                if instance.key != instance.realkey:
                    deleteqiniufile(instance.bucket, instance.realkey)
                instance.delete()
                return JSONResponse(SuccessResponse({'isdeleted': True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


def checkOrgUserContactInfoTruth(org, datasource):
    user_qs = org.org_users.all().filter(is_deleted=False, datasource=datasource)
    count = user_qs.filter(Q(mobile__regex=china_mobile, mobileAreaCode=86) | Q(mobile__regex=hongkong_mobile, mobileAreaCode=852) | Q(mobile__regex=hongkong_telephone, mobileAreaCode=852)).count()
    return count


def makeExportOrgExcel():
    markfilepath = APILOG_PATH['markFilePath']
    class startdotaskthread(threading.Thread):

        def getTask(self):
            task_qs = orgExportExcelTask.objects.filter(status=3, is_deleted=False).order_by('id')
            if task_qs.exists():
                return task_qs
            else:
                return None

        def getStarMobile(self, mobile):
            if mobile and mobile not in ['', u'']:
                length = len(mobile)
                if length > 4:
                    center = str(mobile)[0: (length - 4) // 2] + '****' + str(mobile)[(length - 4) // 2 + 4:]
                else:
                    center = '****'
                return center
            else:
                return None
        def getStarEmail(self, email):
            if email and email not in ['', u'']:
                index = str(email).find('@')
                if index >= 0:
                    center = '****' + str(email)[index:]
                else:
                    center = '****'
                return center
            else:
                return None

        def executeTask(self, task_qs):
            for exporttask in task_qs:
                exporttask.status = 4
                exporttask.save()
                try:
                    starUserMobile = True
                    if exporttask.createuser.has_perm('usersys.admin_manageuser'):
                        starUserMobile = False
                    taskdatasource = exporttask.createuser.datasource
                    orgidliststr = exporttask.orglist
                    tagidliststr = exporttask.taglist
                    tagidlist = tagidliststr.split(',') if tagidliststr else None
                    if len(orgidliststr) > 0 and exporttask.filename:
                        orgidlist = orgidliststr.split(',')
                        org_qs = organization.objects.filter(is_deleted=False).filter(id__in=orgidlist)[:300]
                        if org_qs.exists():
                            fullpath = APILOG_PATH['orgExportPath'] + exporttask.filename
                            if not os.path.exists(fullpath):
                                wb = xlwt.Workbook(encoding='utf-8')
                                style = xlwt.XFStyle()  # 初始化样式
                                style.font.height = 20 * 14
                                style.alignment.horz = xlwt.Alignment.HORZ_CENTER
                                style.alignment.vert = xlwt.Alignment.VERT_CENTER
                                style.alignment.wrap = xlwt.Alignment.WRAP_AT_RIGHT
                                ws_org = wb.add_sheet('机构列表', cell_overwrite_ok=True)
                                ws_org.write(0, 0, '机构简称', style)
                                ws_org.write(0, 1, '机构全称', style)
                                ws_org.write(0, 2, '描述', style)
                                ws_org.col(2).width = 256 * 60
                                ws_org.write(0, 3, '合伙人/投委会成员', style)
                                ws_org.write(0, 4, '标签', style)
                                ws_org.col(4).width = 256 * 40
                                ws_org.write(0, 5, '投资事件', style)
                                ws_org.col(5).width = 256 * 120
                                ws_org.write(0, 6, '机构投资人', style)
                                ws_org.col(6).width = 256 * 100
                                ws_org_hang = 1

                                for org in org_qs:
                                    tags = org.tags.all()
                                    tagnamelist = []
                                    for tag in tags:
                                        tagnamelist.append(tag.nameC)
                                    tagstr = '、'.join(tagnamelist)
                                    investevents = org.org_orgInvestEvent.all().filter(is_deleted=False).order_by('-investDate')
                                    event_list = []
                                    com_list = []
                                    for event in investevents:
                                        com_list.append(event.com_id)
                                        if len(event_list) < 30:  # 最多写入30条投资历史
                                            event_list.append('项目名称：%s, 行业：%s , 投资日期：%s , 投资轮次：%s, 投资金额：%s' %
                                                              (event.comshortname, event.industrytype,
                                                               str(event.investDate)[:10],
                                                               event.investType if event.investType else '暂无',
                                                               event.investSize if event.investSize else '暂无'))
                                    eventstr = '\n\r'.join(event_list)
                                    if len(eventstr) > 30000:
                                        eventstr = eventstr[:30000] + '......'
                                    userData_list = []
                                    investorList = org.org_users.all().filter(is_deleted=False, datasource=taskdatasource)
                                    if isinstance(tagidlist, list) and len(tagidlist) > 0:
                                        investorList = investorList.filter(tags__in=tagidlist)
                                    relation_qs = UserRelation.objects.filter(investoruser__in=investorList, is_deleted=False)
                                    for investor in investorList:
                                        if starUserMobile:
                                            mobile = self.getStarMobile(investor.mobile)
                                            email = self.getStarEmail(investor.email)
                                        else:
                                            mobile = investor.mobile
                                            email = investor.email
                                        title = investor.title.nameC if investor.title else '暂无'
                                        usertags = investor.tags.filter(tag_usertags__is_deleted=False)
                                        usertagnamelist = []
                                        for tag in usertags:
                                            usertagnamelist.append(tag.nameC)
                                        usertagstr = '、'.join(usertagnamelist) if len(usertagnamelist) > 0 else '暂无'
                                        traderRelations = relation_qs.filter(investoruser_id=investor.id)
                                        traderList = []
                                        for relationinstance in traderRelations:
                                            traderList.append('%s(%s)' % (relationinstance.traderuser.usernameC, relationinstance.familiar.score))
                                        traderStr = '、'.join(traderList) if len(traderList) > 0 else '暂无'
                                        userData_list.append('投资人：%s,手机：%s,邮箱：%s,职位：%s,标签：%s --交易师：%s' % (
                                            investor.usernameC, mobile, email, title, usertagstr, traderStr))
                                    userDataStr = '\n\r'.join(userData_list)
                                    ws_org.write(ws_org_hang, 0, str(org.orgnameC), style)  # 简称
                                    ws_org.write(ws_org_hang, 1, str(org.orgfullname), style)  # 全称
                                    ws_org.write(ws_org_hang, 2, str(org.description) if org.description else '暂无',
                                                 style)  # 描述
                                    ws_org.write(ws_org_hang, 3, str(
                                        org.partnerOrInvestmentCommiterMember) if org.partnerOrInvestmentCommiterMember else '暂无',
                                                 style)  # 合伙人/投委会
                                    ws_org.write(ws_org_hang, 4, tagstr if len(tagstr) > 0 else '暂无', style)  # 标签
                                    ws_org.write(ws_org_hang, 5, eventstr if len(eventstr) > 0 else '暂无', style)  # 投资事件
                                    ws_org.write(ws_org_hang, 6, userDataStr if len(userDataStr) > 0 else '暂无', style)  # 机构投资人
                                    com_list = ProjectData.objects.filter(com_id__in=com_list)
                                    if len(com_list) > 0:
                                        com_sheet = wb.add_sheet(org.orgfullname, cell_overwrite_ok=True)
                                        com_sheet.write(0, 0, '全称', style)
                                        com_sheet.write(0, 1, '简介', style)
                                        com_sheet.write(0, 2, '网址', style)
                                        com_sheet.write(0, 3, '电话', style)
                                        com_sheet.write(0, 4, '邮箱', style)
                                        com_sheet.write(0, 5, '地址', style)
                                        com_sheet.write(0, 6, '融资历史', style)
                                        com_sheet.col(0).width = 256 * 20
                                        com_sheet.col(1).width = 256 * 50
                                        com_sheet.col(2).width = 256 * 20
                                        com_sheet.col(3).width = 256 * 20
                                        com_sheet.col(4).width = 256 * 20
                                        com_sheet.col(5).width = 256 * 10
                                        com_sheet.col(6).width = 256 * 80
                                        ws_com_hang = 1
                                        for com in com_list:
                                            com_events = MergeFinanceData.objects.filter(com_id=com.com_id)
                                            com_event_list = []
                                            for com_event in com_events:
                                                if com_event.investormerge == 1:
                                                    invest_with_list = []
                                                    if hasattr(com_event.invsest_with, '__iter__'):
                                                        for invesdic in com_event.invsest_with:
                                                            if invesdic:
                                                                if isinstance(invesdic, dict):
                                                                    invest_with_list.append(invesdic.get('invst_name', ''))
                                                                if isinstance(invesdic, str):
                                                                    invest_with_list.append(invesdic)
                                                    invest_with_str = ','.join(invest_with_list)
                                                else:
                                                    invest_with_str = com_event.merger_with
                                                com_event_list.append('轮次：%s, 行业：%s->%s , 日期：%s , 投资方：%s, 投资金额：%s' % (
                                                    com_event.round, com_event.com_sub_cat_name, com_event.com_cat_name,
                                                    com_event.date,
                                                    invest_with_str, com_event.money))
                                            com_eventstr = '\n\r'.join(com_event_list)
                                            com_sheet.write(ws_com_hang, 0, str(com.com_name), style)  # 全称
                                            com_sheet.write(ws_com_hang, 1, str(com.com_des) if com.com_des else '暂无',
                                                            style)  # 简介
                                            com_sheet.write(ws_com_hang, 2, str(com.com_web) if com.com_web else '暂无',
                                                            style)  # 网址
                                            com_sheet.write(ws_com_hang, 3, str(com.mobile) if com.mobile else '暂无',
                                                            style)  # 电话
                                            com_sheet.write(ws_com_hang, 4, str(com.email) if com.email else '暂无',
                                                            style)  # 邮箱
                                            com_sheet.write(ws_com_hang, 5, str(com.com_addr) if com.com_addr else '暂无',
                                                            style)  # 地址
                                            com_sheet.write(ws_com_hang, 6, com_eventstr if len(com_eventstr) > 0 else '暂无',
                                                            style)  # 融资历史
                                            ws_com_hang += 1
                                    ws_org_hang += 1
                                wb.save(fullpath)
                            exporttask.status = 5
                            exporttask.completetime=datetime.datetime.now()
                            exporttask.save()
                        else:
                            self.deleteTask(exporttask)
                    else:
                        self.deleteTask(exporttask)
                except Exception:
                    logexcption()
                    print(traceback.format_exc())
                    exporttask.status = 1
                    exporttask.save()

        def deleteTask(self, task):
            fullpath = APILOG_PATH['orgExportPath'] + task.filename
            if os.path.exists(fullpath):
                os.remove(fullpath)
            task.delete()

        def doTask(self):
            task_qs = self.getTask()
            if task_qs:
                self.executeTask(task_qs)
                self.doTask()


        def run(self):
            self.doTask()
            os.remove(markfilepath)

    if not os.path.exists(markfilepath):
        f = open(markfilepath, 'w')
        f.close()
        d = startdotaskthread()
        d.start()



# 检索机构
@api_view(['GET'])
@checkRequestToken()
def fulltextsearch(request):
    try:
        page_index = int(request.GET.get('page_index', 1))
        page_size = int(request.GET.get('page_size', 10))
        lang = request.GET.get('lang', 'cn')
        queryset = organization.objects.filter(is_deleted=False)
        queryset = OrganizationFilter(request.query_params, queryset=queryset, request=request).qs
        q = Q()
        q.connector = 'or'
        searchText = request.GET.get('text', None)
        if searchText:  # 匹配机构备注和附件内容
            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "bool": {
                                    "must": {"terms": {"django_ct": ["org.orgremarks", "org.orgattachments"]}}
                                },
                            },
                            {
                                "bool": {
                                    "should": [
                                        {"match_phrase": {"remark": searchText}},
                                        {"match_phrase": {"fileContent": searchText}}
                                    ]
                                }
                            }
                        ]
                    }
                },
                "_source": ["id", "org", "django_ct"]
            }

            results = getEsScrollResult(search_body)
            orgId_list = set()
            for source in results:
                orgid = source['_source'].get('org')
                if orgid:
                    orgId_list.add(orgid)
            q.children.append(('id__in', orgId_list))
        searchname = request.GET.get('search', None)
        if searchname:  # 匹配机构名称和机构代码
            q.children.append(('orgnameC__icontains', searchname))
            q.children.append(('orgnameE__icontains', searchname))
            q.children.append(('stockcode__icontains', searchname))
            q.children.append(('orgfullname__icontains', searchname))
        tags = request.GET.get('tags', None)
        tags_type = request.GET.get('tags_type', 'and')
        if tags:  # 匹配机构标签和机构下用户标签
            tags = tags.split(',')
            if tags_type == 'and':
                user_queryset = MyUser.objects.filter(user_usertags__tag__in=tags, user_usertags__is_deleted=False).annotate(num_tags=Count('tags', distinct=True)).filter(num_tags=len(tags))
            else:
                user_queryset = MyUser.objects.filter(user_usertags__tag__in=tags, user_usertags__is_deleted=False)
            q.children.append(('id__in', user_queryset.values_list('org_id', flat=True)))
        org_qs = queryset.filter(q).distinct()
        try:
            count = org_qs.count()
            org_qs = Paginator(org_qs, page_size)
            org_qs = org_qs.page(page_index)
        except EmptyPage:
            return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
        return JSONResponse(SuccessResponse({'count': count, 'data': returnListChangeToLanguage(OrgListSerializer(org_qs, many=True).data, lang)}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



def downloadOrgAttachments(start):
    attachment_qs = orgAttachments.objects.filter(is_deleted=False, key__isnull=False, org__is_deleted=False, createdtime__gt=start)
    for attInstance in attachment_qs:
        attachmentPath = APILOG_PATH['orgAttachmentsPath'] + attInstance.key
        if not os.path.exists(attachmentPath):
            downloadFileToPath(key=attInstance.key, bucket=attInstance.bucket, path=attachmentPath)
            attInstance.save()


def get_Org_By_Alia(alia_text):
    queryset = orgalias.objects.filter(is_deleted=False, alias=alia_text)
    print('搜索1:******* %s ' % len(queryset))
    if queryset.exists():
        return queryset.first().org
    else:
        queryset = organization.objects.filter(is_deleted=False, orgfullname=alia_text)
        print('搜索2: ----------%s ' % len(queryset))
        if queryset.exists():
            return queryset.first()
    return None

def get_Org_By_Alias(alias_text):
    alia_list = alias_text.split('\\')
    for name in alia_list:
        print('机构名称：=========%s' % name)
        org = get_Org_By_Alia(name)
        if org:
            return org
    return None