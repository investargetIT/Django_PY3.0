#coding=utf-8
import traceback

from django.core.paginator import Paginator, EmptyPage
from django.db import models
from django.db import transaction
from django.db.models import Q,QuerySet, FieldDoesNotExist
from django.db.models.fields.reverse_related import ForeignObjectRel
from rest_framework import filters, viewsets

from timeline.models import timeline, timelineTransationStatu, timelineremark
from timeline.serializer import TimeLineSerializer, TimeLineStatuSerializer, TimeLineCreateSerializer, \
    TimeLineStatuCreateSerializer, TimeLineRemarkSerializer, TimeLineListSerializer_admin, TimeLineUpdateSerializer, \
    TimeLineListSerializer_anonymous
from utils.customClass import InvestError, JSONResponse
from utils.sendMessage import sendmessage_timelineauditstatuchange
from utils.util import read_from_cache, write_to_cache, returnListChangeToLanguage, loginTokenIsAvailable, \
    returnDictChangeToLanguage, catchexcption, cache_delete_key, SuccessResponse, InvestErrorResponse, ExceptionResponse, \
    add_perm, mySortQuery
import datetime

class TimelineView(viewsets.ModelViewSet):
    """
    list:时间轴列表
    create:新建时间轴
    retrieve:查看某一时间轴信息
    update:修改时间轴信息
    destroy:删除时间轴
    """
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    queryset = timeline.objects.all().filter(is_deleted=False)
    filter_fields = ('proj', 'investor','trader','isClose')
    search_fields = ('investor__usernameC', 'investor__usernameE', 'trader__usernameE', 'trader__usernameC', 'proj__projtitleC', 'proj__projtitleE')
    serializer_class = TimeLineSerializer
    redis_key = 'timeline'
    Model = timeline

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

    def get_object(self,pk=None):
        if pk:
            obj = read_from_cache(self.redis_key + '_%s' % pk)
            if not obj:
                try:
                    obj = self.Model.objects.get(id=pk, is_deleted=False)
                except self.Model.DoesNotExist:
                    raise InvestError(code=6002, msg='timeline with this "%s" is not exist' % pk)
                else:
                    write_to_cache(self.redis_key + '_%s' % pk, obj)
        else:
            lookup_url_kwarg = 'pk'
            obj = read_from_cache(self.redis_key + '_%s' % self.kwargs[lookup_url_kwarg])
            if not obj:
                try:
                    obj = self.Model.objects.get(id=self.kwargs[lookup_url_kwarg], is_deleted=False)
                except self.Model.DoesNotExist:
                    raise InvestError(code=6002,msg='timeline with this "%s" is not exist' % self.kwargs[lookup_url_kwarg])
                else:
                    write_to_cache(self.redis_key + '_%s' % self.kwargs[lookup_url_kwarg], obj)
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888)
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')  # 从第一页开始
            lang = request.GET.get('lang')
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=request.user.datasource)
            if request.user.has_perm('timeline.admin_getline'):
                pass
            else:
                queryset = queryset.filter(Q(proj__proj_traders__user=request.user, proj__proj_traders__is_deleted=False) | Q(investor=request.user) | Q(trader=request.user) | Q(createuser=request.user))
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data':[]}))
            responselist = []
            for instance in queryset:
                actionlist = {'get': True, 'change': False, 'delete': False}
                if instance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                    actionlist['change'] = True
                    actionlist['delete'] = True
                if request.user.has_perm('timeline.admin_changeline') or request.user.has_perm('timeline.user_changeline', instance) or request.user == instance.trader:
                    actionlist['change'] = True
                if request.user.has_perm('timeline.admin_deleteline') or request.user.has_perm('timeline.user_deleteline', instance) or request.user == instance.trader:
                    actionlist['delete'] = True
                instancedata = TimeLineListSerializer_admin(instance).data
                instancedata['action'] = actionlist
                responselist.append(instancedata)
            return JSONResponse(SuccessResponse({'count': count, 'data': returnListChangeToLanguage(responselist, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def basiclist(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')  # 从第一页开始
            lang = request.GET.get('lang')
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=request.user.datasource)
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            return JSONResponse(
                SuccessResponse({'count': count, 'data': returnListChangeToLanguage(TimeLineListSerializer_anonymous(queryset, many=True).data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['timeline.admin_addline','timeline.user_addline'])
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            timelinedata = data.pop('timelinedata', None)
            statudata = data.pop('statusdata', None)
            lang = request.GET.get('lang')
            if not timelinedata.get('createuser', None):
                timelinedata['createuser'] = request.user.id
            timelinedata['datasource'] = request.user.datasource_id
            if timelinedata.get('isClose', None) in ['true','True','1',1,'Yes','yes']:
                timelinedata['closeDate'] = datetime.datetime.now()
            with transaction.atomic():
                timelineserializer = TimeLineCreateSerializer(data=timelinedata)
                if timelineserializer.is_valid():
                    newtimeline = timelineserializer.save()
                    if statudata:
                        statudata['timeline'] = newtimeline.id
                        statudata['datasource'] = request.user.datasource_id
                        timelinestatu = TimeLineStatuCreateSerializer(data=statudata)
                        if timelinestatu.is_valid():
                           timelinestatu.save()
                        else:
                            raise InvestError(code=20071,msg=timelinestatu.errors)
                    else:
                        statudata = {
                            'createuser' : request.user.id,
                            'createdtime': datetime.datetime.now(),
                            'timeline' : newtimeline.id,
                            'isActive' : True,
                            'transationStatus' : 1,
                            'datasource' : 1,
                        }
                        timelinestatu = TimeLineStatuCreateSerializer(data=statudata)
                        if timelinestatu.is_valid():
                            timelinestatu.save()
                        else:
                            raise InvestError(code=20071, msg=timelinestatu.errors)
                else:
                    raise InvestError(code=20071,msg=timelineserializer.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(TimeLineSerializer(newtimeline).data, lang)))
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
            if request.user.has_perm('timeline.admin_getline'):
                serializerclass = TimeLineSerializer
            elif request.user.has_perm('timeline.user_getline',instance) or instance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                serializerclass = TimeLineSerializer
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
    def update(self, request, *args, **kwargs):
        try:
            timeline = self.get_object()
            if request.user.has_perm('timeline.admin_changeline') or request.user.has_perm('timeline.user_changeline',timeline) or timeline.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009,msg='没有相应权限')
            data = request.data
            lang = request.GET.get('lang')
            timelinedata = data.pop('timelinedata',None)
            statudata = data.pop('statusdata',None)
            sendmessage = False
            with transaction.atomic():
                newactivetimelinestatu = None
                if statudata:
                    timelinetransationStatus = statudata.get('transationStatus')
                    if timelinetransationStatus:
                        statudata['lastmodifyuser'] = request.user.id
                        statudata['lastmodifytime'] = datetime.datetime.now()
                        statudata['timeline'] = timeline.id
                        statudata['isActive'] = True
                        timelinestatus = timeline.timeline_transationStatus.all().filter(transationStatus__id=timelinetransationStatus,is_deleted=False)
                        if timelinestatus.exists():
                            activetimelinestatu = timelinestatus.first()
                            if not activetimelinestatu.isActive:
                                sendmessage = True
                        else:
                            activetimelinestatu = None
                            sendmessage = True
                        timeline.timeline_transationStatus.all().delete()
                        timelinestatu = TimeLineStatuCreateSerializer(activetimelinestatu,data=statudata)
                        if timelinestatu.is_valid():
                            newactivetimelinestatu = timelinestatu.save()
                        else:
                            raise InvestError(code=20071, msg=timelinestatu.errors)
                if timelinedata:
                    timelinedata['lastmodifyuser'] = request.user.id
                    timelinedata['lastmodifytime'] = datetime.datetime.now()
                    timelinedata['datasource'] = request.user.datasource_id
                    timelinedata['proj'] = timeline.proj_id
                    timelinedata['investor'] = timeline.investor_id
                    if timelinedata.get('trader',None) is None:
                        timelinedata['trader'] = timeline.trader_id
                    if timelinedata.get('isClose', None) in ['true','True','1',1,'Yes','yes']:
                        timelinedata['closeDate'] = datetime.datetime.now()
                    else:
                        timelinedata['closeDate'] = None
                    timelineseria = TimeLineUpdateSerializer(timeline,data=timelinedata)
                    if timelineseria.is_valid():
                        timeline = timelineseria.save()
                    else:
                        raise InvestError(code=20071, msg=timelineseria.errors)
                cache_delete_key(self.redis_key + '_%s' % timeline.id)
                # if sendmessage:
                #     sendmessage_timelineauditstatuchange(newactivetimelinestatu, timeline.proj.takeUser, ['app', 'email', 'webmsg'], sender=request.user)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(TimeLineSerializer(timeline).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    # delete
    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            timelineidlist = request.data.get('timelines')
            timelinelist = []
            lang = request.GET.get('lang')
            if not timelineidlist or not  isinstance(timelineidlist,list):
                raise InvestError(code=20071, msg='except a not null list')
            with transaction.atomic():
                for timelineid in timelineidlist:
                    instance = self.get_object(timelineid)
                    if not (request.user.has_perm('timeline.admin_deleteline') or request.user.has_perm(
                            'timeline.user_deleteline', instance)  or instance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists()):
                        raise InvestError(2009, msg='没有相应权限')
                    for link in ['timeline_transationStatus','timeline_remarks']:
                        if link in []:
                            manager = getattr(instance, link, None)
                            if not manager:
                                continue
                            # one to one
                            if isinstance(manager, models.Model):
                                if hasattr(manager, 'is_deleted') and not manager.is_deleted:
                                    raise InvestError(code=2010,msg=u'{} 上有关联数据'.format(link))
                            else:
                                try:
                                    manager.model._meta.get_field('is_deleted')
                                    if manager.all().filter(is_deleted=False).count():
                                        raise InvestError(code=2010,msg=u'{} 上有关联数据'.format(link))
                                except FieldDoesNotExist:
                                    if manager.all().count():
                                        raise InvestError(code=2010,msg=u'{} 上有关联数据'.format(link))
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
                    instance.deletedtime = datetime.datetime.now()
                    instance.save()
                    instance.timeline_transationStatus.all().update(is_deleted=True)
                    instance.timeline_remarks.all().update(is_deleted=True)
                    cache_delete_key(self.redis_key + '_%s' % instance.id)
                    timelinelist.append(TimeLineSerializer(instance).data)
                return JSONResponse(SuccessResponse(returnListChangeToLanguage(timelinelist, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))




class TimeLineRemarkView(viewsets.ModelViewSet):
    """
        list:时间轴备注列表
        create:新建时间轴备注
        retrieve:查看某一时间轴信息
        update:修改时间轴信息
        destroy:删除时间轴
        """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = timelineremark.objects.all().filter(is_deleted=False)
    filter_fields = ('timeline',)
    serializer_class = TimeLineStatuSerializer


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
        lookup_url_kwarg = 'pk'
        try:
            obj = self.get_queryset().get(id=self.kwargs[lookup_url_kwarg])
        except timelineremark.DoesNotExist:
            raise InvestError(code=60021, msg='remark with this "%s" is not exist' % self.kwargs[lookup_url_kwarg])
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888)
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')  # 从第一页开始
            lang = request.GET.get('lang')
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.filter_queryset(self.get_queryset())
            sort = request.GET.get('sort')
            if sort not in ['True', 'true', True, 1, 'Yes', 'yes', 'YES', 'TRUE']:
                queryset = queryset.order_by('-lastmodifytime', '-createdtime')
            else:
                queryset = queryset.order_by('lastmodifytime', 'createdtime')
            if request.user.has_perm('timeline.admin_getlineremark'):
                queryset = queryset
            else:
                timelineid = request.GET.get('timeline', None)
                if timelineid:
                    timelineobj = self.get_timeline(timelineid)
                    if timelineobj.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                        queryset = queryset
                else:
                    queryset = queryset.filter(createuser_id=request.user.id)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = TimeLineRemarkSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def get_timeline(self,id):
        if self.request.user.is_anonymous:
            raise InvestError(code=8889)
        try:
            line = timeline.objects.get(id=id,is_deleted=False,datasource=self.request.user.datasource)
        except timeline.DoesNotExist:
            raise InvestError(code=5002)
        else:
            return line

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        data = request.data
        lang = request.GET.get('lang')
        timelineid = data.get('timeline', None)
        if timelineid:
            line = self.get_timeline(timelineid)
            if request.user.has_perm('timeline.admin_addlineremark'):
                pass
            elif request.user.has_perm('timeline.user_getline', line) or line.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(code=2009)
        else:
            raise InvestError(code=20072)
        data['createuser'] = request.user.id
        data['datasource'] = request.user.datasource.id
        try:
            with transaction.atomic():
                timeLineremarkserializer = TimeLineRemarkSerializer(data=data)
                if timeLineremarkserializer.is_valid():
                    timeLineremark = timeLineremarkserializer.save()
                else:
                    raise InvestError(code=20071,
                                      msg='data有误_%s\n%s' % (
                                          timeLineremarkserializer.error_messages, timeLineremarkserializer.errors))
                if timeLineremark.createuser:
                    add_perm('timeline.user_getlineremark', timeLineremark.createuser, timeLineremark)
                    add_perm('timeline.user_changelineremark', timeLineremark.createuser, timeLineremark)
                    add_perm('timeline.user_deletelineremark', timeLineremark.createuser, timeLineremark)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(timeLineremarkserializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            remark = self.get_object()
            if request.user.has_perm('timeline.admin_getlineremark'):
                timeLineremarkserializer = TimeLineRemarkSerializer
            elif request.user.has_perm('timeline.user_getlineremark', remark):
                timeLineremarkserializer = TimeLineRemarkSerializer
            else:
                raise InvestError(code=2009)
            serializer = timeLineremarkserializer(remark)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            remark = self.get_object()
            lang = request.GET.get('lang')
            if request.user.has_perm('timeline.admin_changelineremark'):
                pass
            elif request.user.has_perm('timeline.user_changelineremark', remark):
                pass
            else:
                raise InvestError(code=2009)
            data = request.data
            data['lastmodifyuser'] = request.user.id
            data['lastmodifytime'] = datetime.datetime.now()
            with transaction.atomic():
                serializer = TimeLineRemarkSerializer(remark, data=data)
                if serializer.is_valid():
                    newremark = serializer.save()
                else:
                    raise InvestError(code=20071,
                                      msg='data有误_%s\n%s' % (serializer.error_messages, serializer.errors))
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(TimeLineRemarkSerializer(newremark).data, lang)))
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

            if request.user.has_perm('timeline.admin_deletelineremark'):
                pass
            elif request.user.has_perm('timeline.user_deletelineremark', instance):
                pass
            else:
                raise InvestError(code=2009, msg='没有权限')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(TimeLineRemarkSerializer(instance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))