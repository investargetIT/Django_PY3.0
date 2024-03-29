#coding:utf-8
import json
import traceback

import datetime
import time
# Create your views here.
from django.core.paginator import Paginator, EmptyPage
from django.db import transaction
from mongoengine import Q
from rest_framework import viewsets
from bson.objectid import ObjectId
from mongoDoc.models import GroupEmailData, ProjectData, MergeFinanceData, CompanyCatData, ProjRemark, \
    WXChatdata, ProjectNews, ProjIndustryInfo, CompanySearchName, OpenAiChatData, OpenAiChatTopicData, DiscordImageData, \
    OpenAiZillizChatData
from mongoDoc.serializers import GroupEmailDataSerializer, ProjectDataSerializer, \
    MergeFinanceDataSerializer, CompanyCatDataSerializer, ProjRemarkSerializer, WXChatdataSerializer, \
    ProjectNewsSerializer, ProjIndustryInfoSerializer, GroupEmailListSerializer, CompanySearchNameSerializer, \
    OpenAiChatDataSerializer, OpenAiChatTopicDataSerializer, DiscordImageDataSerializer, OpenAiZillizChatDataSerializer
from utils.customClass import JSONResponse, InvestError, AppEventRateThrottle
from utils.util import SuccessResponse, InvestErrorResponse, ExceptionResponse, catchexcption, logexcption, \
    loginTokenIsAvailable, read_from_cache, write_to_cache

ChinaList = ['北京','上海','广东','浙江','江苏','天津','福建','湖北','湖南','四川','河北','山西','内蒙古',
             '辽宁','吉林','黑龙江','安徽','江西','山东','河南','广西','海南','重庆','贵州','云南','西藏',
             '陕西','甘肃','青海','宁夏','新疆','香港','澳门','台湾']
RoundList = ['尚未获投','种子轮','天使轮','Pre-A轮','A轮','A+轮','Pre-B轮','B轮','B+轮','C轮','C+轮','D轮',
             'D+轮','E轮','F轮-上市前','已上市','新三板','战略投资','已被收购','不明确']

class CompanyCatDataView(viewsets.ModelViewSet):
    queryset = CompanyCatData.objects.all()
    serializer_class = CompanyCatDataSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            p_cat_name = request.GET.get('p_cat_name')
            queryset = self.queryset
            if p_cat_name:
                queryset = queryset(p_cat_name__icontains=p_cat_name)
            count = queryset.count()
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            serializer = self.serializer_class(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                raise InvestError(4012, msg='新增行业类别失败', detail=serializer.error_messages)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class MergeFinanceDataView(viewsets.ModelViewSet):
    throttle_classes = (AppEventRateThrottle,)
    queryset = MergeFinanceData.objects.all()
    serializer_class = MergeFinanceDataSerializer
    filter_class = {'com_name': 'icontains',
                    'currency': 'in',
                    'date': 'startswith',
                    'invsest_with': 'in',
                    'round': 'in',
                    'merger_with': 'icontains',
                    'com_id':'in'}

    def filterqueryset(self, request, queryset):
        for key, method in self.filter_class.items():
            value = request.GET.get(key)
            if value:
                if method == 'in':
                    value = value.split(',')
                queryset = queryset.filter(**{'%s__%s' % (key, method): value})
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')  # 从第一页开始
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.filterqueryset(request, self.queryset)
            sort = request.GET.get('sort')
            if sort not in ['True', 'true', True, 1, 'Yes', 'yes', 'YES', 'TRUE']:
                queryset = queryset.order_by('-date',)
            else:
                queryset = queryset.order_by('date',)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            if data['investormerge'] == 1:
                MergeFinanceData_qs = MergeFinanceData.objects.filter(invse_id=data['invse_id'])
                if MergeFinanceData_qs.count() > 0:
                    serializer = self.serializer_class(MergeFinanceData_qs.first(), data=data)
                else:
                    serializer = self.serializer_class(data=data)
            elif data['investormerge'] == 2:
                MergeFinanceData_qs = MergeFinanceData.objects.filter(merger_id=data['merger_id'])
                if MergeFinanceData_qs.count() > 0:
                    serializer = self.serializer_class(MergeFinanceData_qs.first(), data=data)
                else:
                    serializer = self.serializer_class(data=data)
            else:
                raise InvestError(8001, msg='新增投融资经历失败', detail='未知的类型')
            if serializer.is_valid():
                event = serializer.save()
                proj = ProjectData.objects(com_id=data['com_id'])
                if proj.count() > 0:
                    proj = proj.first()
                    if event.investormerge == 1:
                        if not proj.invse_date or proj.invse_date < event.date:
                            proj.update(invse_date=event.date)
                            proj.update(invse_detail_money=event.money)
                            proj.update(invse_round_id=event.round)
                    event.update(com_cat_name=proj.com_cat_name)
                    event.update(com_sub_cat_name=proj.com_sub_cat_name)
                    event.update(com_addr=proj.com_addr)
            else:
                raise InvestError(4012, msg='新增投融资经历失败', detail=serializer.error_messages)
            return JSONResponse(SuccessResponse(self.serializer_class(event).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            id = request.GET.get('id')
            instance = self.queryset.get(id=ObjectId(id))
            proj = ProjectData.objects(com_id=instance.com_id).first()
            instance.update(com_cat_name=proj.com_cat_name)
            instance.update(com_sub_cat_name=proj.com_sub_cat_name)
            instance.update(com_addr=proj.com_addr)
            data = request.data
            serializer = self.serializer_class(instance, data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                raise InvestError(20071, msg='修改投融资经历失败', detail='%s'%serializer.error_messages)
            return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def getCount(self,request, *args, **kwargs):
        try:
            type = request.GET.get('type')
            if type == 'com':
                result = self.companyCountByCat()
            elif type == 'evecat':
                result = self.eventCountByCat()
            elif type == 'everound':
                result = self.eventCountByRound()
            elif type == 'eveaddr':
                result = self.eventCountByAddress()
            else:
                raise InvestError(20071, msg='获取投融资经历统计数据失败', detail='统计类别有误')
            return JSONResponse(SuccessResponse(result))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def companyCountByCat(self):
        allCat = CompanyCatData.objects.all().filter(p_cat_name=None)
        countDic = read_from_cache('countCompanyByCat')
        if not countDic:
            countDic = {}
            for cat in allCat:
                count = ProjectData.objects.all().filter(com_cat_name=cat.cat_name).count()
                countDic[cat.cat_name] = count
            write_to_cache('countCompanyByCat', countDic)
        return countDic

    def eventCountByCat(self):
        allCat = CompanyCatData.objects.all().filter(p_cat_name=None)
        countDic = read_from_cache('countEventByCat')
        if not countDic:
            countDic = {}
            for cat in allCat:
                count = self.queryset.filter(com_cat_name=cat.cat_name).count()
                countDic[cat.cat_name] = count
            write_to_cache('countEventByCat', countDic)
        return countDic

    def eventCountByRound(self):
        year = datetime.datetime.now().year
        timelist = [str(i) for i in range(year - 10, year + 1)]
        countList = read_from_cache('countEventByRound')
        if not countList:
            countList = {}
            for year in timelist:
                qs = self.queryset.filter(date__startswith=year)
                countDic = {}
                for cat in RoundList:
                    count = qs.filter(round=cat).count()
                    countDic[cat] = count
                countList[year] = countDic
            write_to_cache('countEventByRound', countList)
        return countList

    def eventCountByAddress(self):
        countDic = read_from_cache('countEventByAddress')
        if not countDic:
            countDic = {}
            for cat in ChinaList:
                count = self.queryset.filter(com_addr=cat).count()
                countDic[cat] = count
            write_to_cache('countEventByAddress', countDic)
        return countDic

class ProjectDataView(viewsets.ModelViewSet):
    throttle_classes = (AppEventRateThrottle,)
    queryset = ProjectData.objects.all()
    serializer_class = ProjectDataSerializer
    filter_class = {'com_id': 'in',
                    'com_name':'icontains',
                    'com_cat_name': 'in',
                    'com_sub_cat_name': 'in',
                    'com_fund_needs_name': 'in',
                    'invse_round_id': 'in',
                    'com_status': 'in',
                    'source': 'in',
                    'com_born_date':'startswith',}

    def filterqueryset(self, request, queryset):
        for key, method in self.filter_class.items():
            value = request.GET.get(key)
            if value:
                if method == 'in':
                    value = value.split(',')
                queryset = queryset.filter(**{'%s__%s' % (key, method): value})
        return queryset

    def namelist(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)  # 从第一页开始
            queryset = self.filterqueryset(request, self.queryset)
            com_addr = request.GET.get('com_addr')
            finance_date = request.GET.get('finance_date')
            if finance_date:
                finance_date_list = finance_date.split(',')
                filters = Q(date__startswith=finance_date)
                for finance_date in finance_date_list:
                    filters = filters | Q(date__startswith=finance_date)
                comid_QS = MergeFinanceData.objects.all().filter(filters).values_list('com_id').distinct('com_id')
                queryset = queryset.filter(com_id__in=comid_QS)
            if com_addr:
                com_addr = com_addr.split(',')
                if '其他' in com_addr:
                    queryset = queryset.filter(Q(com_addr__nin=ChinaList) | Q(com_addr__in=com_addr))
                else:
                    queryset = queryset(Q(com_addr__in=com_addr))
            sortfield = request.GET.get('sort')
            if sortfield:
                queryset = queryset.order_by(sortfield)
            else:
                queryset = queryset.order_by('-id')
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
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)  # 从第一页开始
            queryset = self.filterqueryset(request, self.queryset)
            com_addr = request.GET.get('com_addr')
            finance_date = request.GET.get('finance_date')
            if finance_date:
                finance_date_list = finance_date.split(',')
                filters = Q(date__startswith=finance_date)
                for finance_date in finance_date_list:
                    filters = filters | Q(date__startswith=finance_date)
                comid_QS = MergeFinanceData.objects.all().filter(filters).values_list('com_id').distinct('com_id')
                queryset = queryset.filter(com_id__in=comid_QS)
            if com_addr:
                com_addr = com_addr.split(',')
                if '其他' in com_addr:
                    queryset = queryset.filter(Q(com_addr__nin=ChinaList)|Q(com_addr__in=com_addr))
                else:
                    queryset = queryset(Q(com_addr__in=com_addr))
            sortfield = request.GET.get('sort')
            if sortfield:
                queryset = queryset.order_by(sortfield)
            else:
                queryset = queryset.order_by('-id')
            count = queryset.count()
            if count == 0:
                if request.GET.get('com_name', None):
                    searchuser_id = None
                    if not request.user.is_anonymous:
                        searchuser_id = request.user.id
                    saveCompanySearchName(request.GET.get('com_name'), searchuser_id)
            try:
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    def excellist(self, request, *args, **kwargs):
        try:
            data = request.data
            idlist = data.get('com_ids')
            if idlist in (None, '', u'', []) or not isinstance(idlist, list):
                raise InvestError(20071, msg='获取全库公司列表数据失败', detail='except a non-empty array')
            queryset = self.queryset.filter(com_id__in=idlist)
            projserializer = self.serializer_class(queryset,many=True)
            eventserializer = MergeFinanceDataSerializer(MergeFinanceData.objects.all().filter(com_id__in=idlist), many=True)
            return JSONResponse(SuccessResponse({'event':eventserializer.data,'proj':projserializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            com_qs = ProjectData.objects.filter(com_id=data['com_id'])
            if com_qs.count() > 0:
                com_name = data.get('com_name', None)
                if com_name and (u'...' in com_name or u'403' in com_name or u'www.itjuzi.com' in com_name):
                    data.pop('com_name', None)
                serializer = self.serializer_class(com_qs.first(),data=data)
            else:
                serializer = self.serializer_class(data=data)
            if serializer.is_valid():
                proj= serializer.save()
                event_qs = MergeFinanceData.objects.filter(com_id=proj.com_id)
                if event_qs.count():
                    event_qs.update(com_cat_name=proj.com_cat_name)
                    event_qs.update(com_sub_cat_name=proj.com_sub_cat_name)
                    event_qs.update(com_addr=proj.com_addr)
            else:
                raise InvestError(4012, msg='新增全库项目失败', detail=serializer.error_messages)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            data = request.data
            com_id = data.get('com_id')
            instance = self.queryset.get(com_id=com_id)
            instance.delete()
            MergeFinanceData.objects.all().filter(com_id=com_id).delete()
            ProjIndustryInfo.objects.all().filter(com_id=com_id).delete()
            ProjectNews.objects.all().filter(com_id=com_id).delete()
            ProjRemark.objects.all().filter(com_id=com_id).delete()
            return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class ProjectIndustryInfoView(viewsets.ModelViewSet):
    throttle_classes = (AppEventRateThrottle,)
    queryset = ProjIndustryInfo.objects.all()
    serializer_class = ProjIndustryInfoSerializer



    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            com_id = request.GET.get('com_id', None)
            if not com_id:
                raise InvestError(20072, msg='获取项目公司工商信息失败', detail='公司 不能为空')
            com_qs = self.queryset.filter(com_id=com_id)
            if com_qs.count() > 0:
                instance = com_qs.first()
                response = self.serializer_class(instance).data
            else:
                response = None
            return JSONResponse(SuccessResponse(response))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            com_qs = ProjIndustryInfo.objects.filter(com_id=data['com_id'])
            if com_qs.count() > 0:
                serializer = self.serializer_class(com_qs.first(),data=data)
            else:
                serializer = self.serializer_class(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                raise InvestError(4012, msg='新增项目公司工商信息失败', detail=serializer.error_messages)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class ProjectNewsView(viewsets.ModelViewSet):

    throttle_classes = (AppEventRateThrottle,)
    queryset = ProjectNews.objects.all()
    serializer_class = ProjectNewsSerializer
    filter_class = {'com_id': 'in', 'com_name':'icontains',}

    def filterqueryset(self, request, queryset):
        for key, method in self.filter_class.items():
            value = request.GET.get(key)
            if value:
                if method == 'in':
                    value = value.split(',')
                queryset = queryset.filter(**{'%s__%s' % (key, method): value})
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')  # 从第一页开始
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.filterqueryset(request, self.queryset)
            queryset = queryset.order_by('-newsdate')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:

                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            serializer = self.serializer_class(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                raise InvestError(4012, msg='新增项目公司新闻消息失败', detail=serializer.error_messages)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class ProjectSearchNameView(viewsets.ModelViewSet):
    '''
        list: 获取项目搜索列表
    '''
    queryset = CompanySearchName.objects.all()
    serializer_class = CompanySearchNameSerializer

    filter_class = {'com_name': 'in', 'createtime': 'gt',}

    def filterqueryset(self, request, queryset):
        for key, method in self.filter_class.items():
            value = request.GET.get(key)
            if value:
                if method == 'in':
                    value = value.split(',')
                queryset = queryset.filter(**{'%s__%s' % (key, method): value})
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')  # 从第一页开始
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.filterqueryset(request,self.queryset)
            if request.user.has_perm('usersys.admin_managemongo'):
                pass
            else:
                queryset = queryset(searchuser_id=request.user.id)
            queryset = queryset.order_by('createtime')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            data['searchuser_id'] = request.user.id
            serializer = self.serializer_class(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                raise InvestError(4013, msg='新增项目公司搜索记录失败', detail=serializer.error_messages)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class ProjectRemarkView(viewsets.ModelViewSet):

    queryset = ProjRemark.objects.all()
    serializer_class = ProjRemarkSerializer

    filter_class = {'com_name': 'in',
                    'com_id': 'in',}

    def filterqueryset(self, request, queryset):
        for key, method in self.filter_class.items():
            value = request.GET.get(key)
            if value:
                if method == 'in':
                    value = value.split(',')
                queryset = queryset.filter(**{'%s__%s' % (key, method): value})
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')  # 从第一页开始
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.filterqueryset(request,self.queryset)
            if request.user.has_perm('usersys.admin_managemongo'):
                queryset = queryset(datasource=request.user.datasource_id)
            else:
                queryset = queryset(createuser_id=request.user.id)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            data['createuser_id'] = request.user.id
            data['datasource'] = request.user.datasource_id
            serializer = self.serializer_class(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                raise InvestError(4014, msg='新增项目公司备注信息失败', detail=serializer.error_messages)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            id = request.GET.get('id')
            instance = self.queryset.get(id=ObjectId(id))
            if instance.createuser_id == request.user.id:
                pass
            else:
                raise InvestError(2009, msg='修改项目公司备注信息失败')
            data = request.data
            data.pop('createuser_id',None)
            data.pop('datasource',None)
            serializer = self.serializer_class(instance,data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                raise InvestError(4014, msg='修改项目公司备注信息失败', detail=serializer.error_messages)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            id = request.GET.get('id')
            instance = self.queryset.get(id=ObjectId(id))
            if instance.createuser_id == request.user.id:
                pass
            elif request.user.has_perm('usersys.admin_managemongo'):
                pass
            else:
                raise InvestError(2009, msg='删除项目公司备注信息失败')
            instance.delete()
            return JSONResponse(SuccessResponse({'isDeleted':True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))




class GroupEmailDataView(viewsets.ModelViewSet):
    queryset = GroupEmailData.objects.all()
    serializer_class = GroupEmailListSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            projtitle = request.GET.get('title')
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')  # 从第一页开始
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.queryset(datasource=request.user.datasource_id)
            sort = request.GET.get('sort')
            if projtitle:
                queryset = queryset(projtitle__icontains=projtitle)
            if sort not in ['True', 'true', True, 1, 'Yes', 'yes', 'YES', 'TRUE']:
                queryset = queryset.order_by('-savetime',)
            else:
                queryset = queryset.order_by('savetime',)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class WXChatDataView(viewsets.ModelViewSet):
    queryset = WXChatdata.objects.all()
    serializer_class = WXChatdataSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')  # 从第一页开始
            isShow = request.GET.get('isShow',False)
            if isShow in ['True', 'true', True, 1, 'Yes', 'yes', 'YES', 'TRUE']:
                isShow = True
            else:
                isShow = False
                if not request.user.has_perm('usersys.admin_managemongo'):
                    isShow = True
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.queryset(isShow=isShow)
            sort = request.GET.get('sort')
            if sort not in ['True', 'true', True, 1, 'Yes', 'yes', 'YES', 'TRUE']:
                queryset = queryset.order_by('-createtime',)
            else:
                queryset = queryset.order_by('createtime',)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.admin_managemongo'])
    def update(self, request, *args, **kwargs):
        try:
            id = request.GET.get('id')
            instance = self.queryset.get(id=ObjectId(id))
            with transaction.atomic():
                data = {}
                data['isShow'] = not instance.isShow
                serializer = self.serializer_class(instance, data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    raise InvestError(4012, msg='修改市场消息是否展示失败', detail=serializer.error_messages)
                return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class OpenAiChatTopicDataView(viewsets.ModelViewSet):
    '''
            list: 获取ai聊天会话列表
            create： 创建聊天会话
            update； 修改会话name
            destroy： 删除聊天会话
        '''
    queryset = OpenAiChatTopicData.objects.all()
    serializer_class = OpenAiChatTopicDataSerializer
    filter_class = {'topic_name': 'icontains', 'type': 'in'}

    def filterqueryset(self, request, queryset):
        for key, method in self.filter_class.items():
            value = request.GET.get(key)
            if value:
                if method == 'in':
                    value = value.split(',')
                queryset = queryset.filter(**{'%s__%s' % (key, method): value})
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)  # 从第一页开始
            queryset = self.queryset(user_id=request.user.id)
            queryset = self.filterqueryset(request, queryset)
            queryset = queryset.order_by('-create_time')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count': count, 'data': serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            data['user_id'] = request.user.id
            serializer = self.serializer_class(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                raise InvestError(4014, msg='创建聊天会话失败', detail=serializer.error_messages)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            id = request.GET.get('id')
            instance = self.queryset.get(id=ObjectId(id))
            if instance.user_id == request.user.id:
                pass
            else:
                raise InvestError(2009, msg='无权限修改')
            with transaction.atomic():
                data = request.data
                serializer = self.serializer_class(instance, data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    raise InvestError(4012, msg='修改会话name失败', detail=serializer.error_messages)
                return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            id = request.GET.get('id')
            instance = self.queryset.get(id=ObjectId(id))
            if instance.user_id == request.user.id:
                pass
            else:
                raise InvestError(2009, msg='无权限删除')
            instance.delete()
            OpenAiChatData.objects.all().filter(topic_id=id).delete()
            return JSONResponse(SuccessResponse({'isDeleted': True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



class OpenAiChatDataView(viewsets.ModelViewSet):
    '''
                list: 获取ai聊天会话列表
                destroy： 删除聊天会话
            '''
    queryset = OpenAiChatData.objects.all()
    serializer_class = OpenAiChatDataSerializer
    filter_class = {'content': 'icontains', 'topic_id': 'in'}

    def filterqueryset(self, request, queryset):
        for key, method in self.filter_class.items():
            value = request.GET.get(key)
            if value:
                if method == 'in':
                    value = value.split(',')
                queryset = queryset.filter(**{'%s__%s' % (key, method): value})
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)  # 从第一页开始
            queryset = self.queryset(user_id=request.user.id)
            queryset = self.filterqueryset(request, queryset)
            queryset = queryset.order_by('-msgtime')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count, 'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            id = request.GET.get('id')
            instance = self.queryset.get(id=ObjectId(id))
            if instance.user_id == request.user.id:
                pass
            else:
                raise InvestError(2009, msg='无权限删除')
            instance.delete()
            return JSONResponse(SuccessResponse({'isDeleted': True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class OpenAiZillizChatDataView(viewsets.ModelViewSet):
    '''
                list: 获取ai聊天会话列表
                destroy： 删除聊天会话
            '''
    queryset = OpenAiZillizChatData.objects.all()
    serializer_class = OpenAiZillizChatDataSerializer
    filter_class = {'topic_id': 'in'}

    def filterqueryset(self, request, queryset):
        for key, method in self.filter_class.items():
            value = request.GET.get(key)
            if value:
                if method == 'in':
                    value = value.split(',')
                queryset = queryset.filter(**{'%s__%s' % (key, method): value})
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)  # 从第一页开始
            queryset = self.queryset(user_id=request.user.id)
            queryset = self.filterqueryset(request, queryset)
            queryset = queryset.order_by('-msgtime')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count, 'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            id = request.GET.get('id')
            instance = self.queryset.get(id=ObjectId(id))
            if instance.user_id == request.user.id:
                pass
            else:
                raise InvestError(2009, msg='无权限删除')
            instance.delete()
            return JSONResponse(SuccessResponse({'isDeleted': True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



def getOpenAiChatConversationDataChat(topic_id):
    queryset = OpenAiChatData.objects.all().filter(topic_id=topic_id).order_by('msgtime')
    chatdata = []
    if queryset.count() > 0:
        for instance in queryset:
            if instance.isreset or len(chatdata) >= 10:
                break
            content = json.loads(instance.content)
            if instance.isAI:
                chatdata.append(content)
            else:
                chatdata.extend(content)
    return chatdata

def getOpenAiZillizChatConversationDataChat(topic_id):
    queryset = OpenAiZillizChatData.objects.all().filter(topic_id=topic_id).order_by('msgtime')
    chatdata = []
    if queryset.count() > 0:
        for instance in queryset:
            if instance.isreset:
                break
            if instance.user_content and instance.ai_content:
                chatdata.append((instance.user_content, instance.ai_content))
            if len(chatdata) >= 5:
                break
    return chatdata


def updateOpenAiChatTopicChat(topic_id, data):
    instance = OpenAiChatTopicData.objects.all().get(id=ObjectId(topic_id))
    serializer = OpenAiChatTopicDataSerializer(instance, data=data)
    try:
        if serializer.is_valid():
            serializer.save()
        else:
            raise InvestError(4012, msg='更新GPTChat 聊天会话失败', detail=serializer.error_messages)
    except Exception as err:
        logexcption(err=err)

def saveOpenAiChatDataToMongo(data):
    serializer = OpenAiChatDataSerializer(data=data)
    try:
        if serializer.is_valid():
            serializer.save()
        else:
            raise InvestError(4012, msg='保存OpenAi 聊天记录失败', detail=serializer.error_messages)
    except Exception as err:
        logexcption(err=err)

def saveOpenAiZillizChatDataToMongo(data):
    serializer = OpenAiZillizChatDataSerializer(data=data)
    try:
        if serializer.is_valid():
            serializer.save()
        else:
            raise InvestError(4012, msg='保存OpenAi langchain 聊天记录失败', detail=serializer.error_messages)
    except Exception as err:
        logexcption(err=err)


def saveSendEmailDataToMongo(data):
    serializer = GroupEmailDataSerializer(data=data)
    try:
        if serializer.is_valid():
            serializer.save()
        else:
            raise InvestError(4012, msg='保存发送项目邮件记录失败', detail=serializer.error_messages)
    except Exception:
        logexcption()

def readSendEmailDataFromMongo():
    start = datetime.datetime.now() - datetime.timedelta(hours=23, minutes=59, seconds=59)
    queryset = GroupEmailData.objects.all()
    qs = queryset.filter(savetime__gt=start)
    return GroupEmailDataSerializer(qs,many=True).data




def saveCompanySearchName(com_name, searchuser_id):
    try:
        data = {'com_name':com_name,'searchuser_id':searchuser_id}
        serializer = CompanySearchNameSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
    except Exception:
        logexcption()



class DiscordImageDataView(viewsets.ModelViewSet):
    '''
            list: 获取ai 绘画图片地址
            create： 保存绘画图片地址
            update； 修改绘画图片地址
            destroy： 删除绘画图片地址
        '''
    queryset = DiscordImageData.objects.all()
    serializer_class = DiscordImageDataSerializer
    filter_class = {'prompt': 'exact',
                    'message_id': 'in',
                    'channel_id': 'in',
                    'guild_id': 'in',
                    'user_id': 'in',
                    'topic_id': 'in'
                    }

    def filterqueryset(self, request, queryset):
        for key, method in self.filter_class.items():
            value = request.GET.get(key)
            if value:
                if method == 'in':
                    value = value.split(',')
                queryset = queryset.filter(**{'%s__%s' % (key, method): value})
        return queryset

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)  # 从第一页开始
            completed = request.GET.get('completed')
            queryset = self.filterqueryset(request, self.queryset())
            if completed:
                if completed in ['True', 'true', True, 1, '1', 'Yes', 'yes', 'YES', 'TRUE']:
                    queryset = queryset(completed=True)
                else:
                    queryset = queryset(completed=False)
            queryset = queryset.order_by('-promtime')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset,many=True)
            return JSONResponse(SuccessResponse({'count':count, 'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            data['user_id'] = request.user.id
            serializer = self.serializer_class(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                raise InvestError(4014, msg='创建discord绘画任务失败', detail=serializer.error_messages)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            id = request.GET.get('id')
            instance = self.queryset.get(id=ObjectId(id))
            with transaction.atomic():
                data = request.data
                serializer = self.serializer_class(instance, data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    raise InvestError(4012, msg='保存绘画图片地址失败', detail=serializer.error_messages)
                return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            id = request.GET.get('id')
            instance = self.queryset.get(id=ObjectId(id))
            instance.delete()
            return JSONResponse(SuccessResponse({'isDeleted': True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))