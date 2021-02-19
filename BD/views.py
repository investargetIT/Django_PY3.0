#coding=utf8

import traceback
from django.core.paginator import Paginator, EmptyPage
from django.db import transaction
from django.db.models import QuerySet, Q, Count, Max
from django.shortcuts import render_to_response
from django_filters import FilterSet
import datetime
import json
from django.core.serializers.json import DjangoJSONEncoder
from elasticsearch import Elasticsearch
from rest_framework import filters, viewsets
from BD.models import ProjectBD, ProjectBDComments, OrgBDComments, OrgBD, MeetingBD, MeetBDShareToken, OrgBDBlack, \
    ProjectBDManagers, WorkReport, WorkReportProjInfo, OKR, OKRResult, WorkReportMarketMsg
from BD.serializers import ProjectBDSerializer, ProjectBDCreateSerializer, ProjectBDCommentsCreateSerializer, \
    ProjectBDCommentsSerializer, OrgBDCommentsSerializer, OrgBDCommentsCreateSerializer, OrgBDCreateSerializer, \
    OrgBDSerializer, MeetingBDSerializer, MeetingBDCreateSerializer, OrgBDBlackSerializer, OrgBDBlackCreateSerializer, \
    ProjectBDManagersCreateSerializer, WorkReportCreateSerializer, WorkReportSerializer, \
    WorkReportProjInfoCreateSerializer, WorkReportProjInfoSerializer, OKRSerializer, OKRCreateSerializer, \
    OKRResultCreateSerializer, OKRResultSerializer, orgBDProjSerializer, WorkReportMarketMsgCreateSerializer, \
    WorkReportMarketMsgSerializer
from invest.settings import cli_domain, HAYSTACK_CONNECTIONS
from msg.views import deleteMessage
from proj.models import project
from proj.views import isProjectTrader
from third.views.qiniufile import deleteqiniufile
from timeline.models import timeline
from timeline.models import timelineremark
from usersys.models import MyUser
from utils.customClass import RelationFilter, InvestError, JSONResponse, MyFilterSet
from utils.sendMessage import sendmessage_orgBDMessage, sendmessage_orgBDExpireMessage, sendmessage_workReportDonotWrite
from utils.util import loginTokenIsAvailable, SuccessResponse, InvestErrorResponse, ExceptionResponse, \
    returnListChangeToLanguage, catchexcption, returnDictChangeToLanguage, mySortQuery, add_perm, rem_perm, \
    read_from_cache, write_to_cache, cache_delete_key, logexcption, cache_delete_patternKey, checkSessionToken


class ProjectBDFilter(FilterSet):
    com_name = RelationFilter(filterstr='com_name',lookup_method='icontains')
    location = RelationFilter(filterstr='location', lookup_method='in')
    isimportant = RelationFilter(filterstr='isimportant')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')
    contractors = RelationFilter(filterstr='contractors', lookup_method='in')
    indGroup = RelationFilter(filterstr='indGroup', lookup_method='in')
    country = RelationFilter(filterstr='country', lookup_method='in')
    bduser = RelationFilter(filterstr='bduser', lookup_method='in')
    username = RelationFilter(filterstr='username', lookup_method='icontains')
    usermobile = RelationFilter(filterstr='usermobile', lookup_method='contains')
    source = RelationFilter(filterstr='source',lookup_method='icontains')
    bd_status = RelationFilter(filterstr='bd_status', lookup_method='in')
    source_type = RelationFilter(filterstr='source_type', lookup_method='in')
    stime = RelationFilter(filterstr='createdtime', lookup_method='gt')
    etime = RelationFilter(filterstr='createdtime', lookup_method='lt')
    class Meta:
        model = ProjectBD
        fields = ('com_name', 'createuser', 'location', 'contractors', 'isimportant', 'bduser', 'indGroup', 'country', 'username', 'usermobile', 'source', 'bd_status', 'source_type', 'stime', 'etime')


class ProjectBDView(viewsets.ModelViewSet):
    """
    list:获取新项目BD
    create:增加新项目BD
    retrieve:查看新项目BD信息
    update:修改bd信息
    destroy:删除新项目BD
    """
    filter_backends = (filters.DjangoFilterBackend,filters.SearchFilter)
    queryset = ProjectBD.objects.filter(is_deleted=False)
    filter_class = ProjectBDFilter
    search_fields = ('com_name', 'username', 'source')
    serializer_class = ProjectBDSerializer

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



    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.GET.get('manager'):
                manager_list = request.GET['manager'].split(',')
                queryset = queryset.filter(Q(manager__in=manager_list) | Q(ProjectBD_managers__manager__in=manager_list, ProjectBD_managers__is_deleted=False) | Q(contractors__in=manager_list))
            if request.user.has_perm('BD.manageProjectBD') and request.user.has_perm('usersys.as_trader'):
                pass
            elif request.user.has_perm('BD.user_getProjectBD'):
                queryset = queryset.filter(Q(manager=request.user) | Q(createuser=request.user) | Q(contractors=request.user) | Q(ProjectBD_managers__manager=request.user, ProjectBD_managers__is_deleted=False)).distinct()
            else:
                raise InvestError(2009)
            sortfield = request.GET.get('sort', 'lastmodifytime')
            desc = request.GET.get('desc', 1)
            if desc in ('1', u'1', 1):
                sortfield = '-' + sortfield
            queryset = queryset.order_by('-isimportant', sortfield, '-lastmodifytime')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = ProjectBDSerializer(queryset, many=True, context={'user_id': request.user.id, 'manage': request.user.has_perm('BD.manageProjectBD')})
            return JSONResponse(SuccessResponse({'count': count, 'data': returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def countBd(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('BD.manageProjectBD') and request.user.has_perm('usersys.as_trader'):
                if request.GET.get('manager'):
                    manager_list = request.GET['manager'].split(',')
                    allQueryset = queryset.filter(Q(manager__in=manager_list) | Q(ProjectBD_managers__manager__in=manager_list, ProjectBD_managers__is_deleted=False) | Q(contractors__in=manager_list)).distinct()
                    relateManager_qs = ProjectBDManagers.objects.filter(is_deleted=False, projectBD__in=queryset.values_list('id'), manager__in=manager_list)
                    manager_qs = queryset.filter(manager__in=manager_list).distinct()
                    contractor_qs = queryset.filter(contractors__in=manager_list).distinct()
                else:
                    allQueryset = queryset
                    manager_qs = queryset
                    relateManager_qs = ProjectBDManagers.objects.filter(is_deleted=False, projectBD__in=queryset.values_list('id'))
                    contractor_qs = queryset
            elif request.user.has_perm('BD.user_getProjectBD'):
                allQueryset = queryset.filter(Q(manager_id=request.user.id) | Q(contractors_id=request.user.id) | Q(ProjectBD_managers__manager_id=request.user.id, ProjectBD_managers__is_deleted=False)).distinct()
                relateManager_qs = ProjectBDManagers.objects.filter(is_deleted=False, projectBD__in=queryset.values_list('id'), manager_id=request.user.id)
                manager_qs = queryset.filter(manager_id=request.user.id).distinct()
                contractor_qs = queryset.filter(contractors_id=request.user.id).distinct()
            else:
                raise InvestError(2009)
            count = allQueryset.count()
            countlist, relateCountlist, contractorsCountlist = [], [], []
            counts = manager_qs.values_list('manager').annotate(Count('manager'))
            for manager_count in counts:
                countlist.append({'manager': manager_count[0], 'count': manager_count[1]})
            relateCounts = relateManager_qs.values_list('manager').annotate(Count('manager'))
            for manager_count in relateCounts:
                relateCountlist.append({'manager': manager_count[0], 'count': manager_count[1]})
            contractorsCounts = contractor_qs.values_list('contractors').annotate(Count('contractors'))
            for manager_count in contractorsCounts:
                contractorsCountlist.append({'contractors': manager_count[0], 'count': manager_count[1]})
            return JSONResponse(SuccessResponse({'count': count, 'manager_count': countlist, 'relateManager_count': relateCountlist, 'contractorManager_count': contractorsCountlist}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            comments = data.get('comments',None)
            relateManagers = data.get('manager', None)
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            data['manager'] = relateManagers.pop(0) if relateManagers else request.user.id
            data['contractors'] = data['contractors'] if data.get('contractors') else request.user.id
            if request.user.has_perm('BD.manageProjectBD'):
                pass
            elif request.user.has_perm('BD.user_addProjectBD'):
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                projectBD = ProjectBDCreateSerializer(data=data)
                if projectBD.is_valid():
                    newprojectBD = projectBD.save()
                    if newprojectBD.manager:
                        add_perm('BD.user_manageProjectBD', newprojectBD.manager, newprojectBD)
                else:
                    raise InvestError(4009,msg='项目BD创建失败——%s'%projectBD.errors)
                if isinstance(relateManagers, list):
                    for relate_manager in relateManagers:
                        instance = ProjectBDManagersCreateSerializer(data={'projectBD': newprojectBD.id, 'manager':relate_manager, 'createuser':request.user.id})
                        if instance.is_valid():
                            instance.save()
                if comments:
                    data['projectBD'] = newprojectBD.id
                    commentinstance = ProjectBDCommentsCreateSerializer(data=data)
                    if commentinstance.is_valid():
                        commentinstance.save()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(ProjectBDSerializer(newprojectBD).data,lang)))
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
            if request.user.has_perm('BD.manageProjectBD'):
                pass
            elif request.user in [instance.manager, instance.contractors, instance.createuser]:
                pass
            elif instance.ProjectBD_managers.filter(manager=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
            serializer = self.serializer_class(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
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
            data.pop('datasource', None)
            if request.user.has_perm('BD.manageProjectBD'):
                pass
            elif request.user in [instance.manager, instance.contractors, instance.createuser]:
                pass
            elif instance.ProjectBD_managers.filter(manager=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                projectBD = ProjectBDCreateSerializer(instance,data=data)
                if projectBD.is_valid():
                    newprojectBD = projectBD.save()
                else:
                    raise InvestError(4009, msg='项目BD修改失败——%s' % projectBD.errors)
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(ProjectBDSerializer(newprojectBD).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('BD.manageProjectBD'):
                pass
            elif request.user in [instance.manager, instance.contractors, instance.createuser]:
                pass
            elif instance.ProjectBD_managers.filter(manager=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                instance.ProjectBD_managers.filter(is_deleted=False).update(is_deleted=True, deleteduser=request.user, deletedtime=datetime.datetime.now())
                instance.ProjectBD_comments.filter(is_deleted=False).update(is_deleted=True, deleteduser=request.user, deletedtime=datetime.datetime.now())
            return JSONResponse(SuccessResponse({'isDeleted': True,}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class ProjectBDManagersView(viewsets.ModelViewSet):
    """
    create:增加项目BDmanagers
    destroy:删除项目BDmanagers
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = ProjectBDManagers.objects.filter(is_deleted=False)
    filter_fields = ('projectBD', 'manager')
    serializer_class = ProjectBDManagersCreateSerializer

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = 'pk'
        assert lookup_url_kwarg in self.kwargs, (
                'Expected view %s to be called with a URL keyword argument '
                'named "%s". Fix your URL conf' %
                (self.__class__.__name__, lookup_url_kwarg)
        )
        try:
            obj = queryset.get(id=self.kwargs[lookup_url_kwarg])
        except ProjectBDManagers.DoesNotExist:
            raise InvestError(code=8892)
        return obj


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            if request.user.has_perm('BD.manageProjectBD'):
                pass
            elif request.user.has_perm('BD.user_addProjectBD'):
                pass
            else:
                raise InvestError(2009)
            lang = request.GET.get('lang')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            with transaction.atomic():
                instance = ProjectBDManagersCreateSerializer(data=data)
                if instance.is_valid():
                    instance.save()
                else:
                    raise InvestError(4009, msg='创建项目BDcomments失败--%s' % instance.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(instance.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('BD.manageProjectBD'):
                pass
            elif request.user.has_perm('BD.user_addProjectBD'):
                pass
            else:
                raise InvestError(2009)
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


class ProjectBDCommentsView(viewsets.ModelViewSet):
    """
    list:获取新项目BDcomments
    create:增加新项目BDcomments
    destroy:删除新项目BDcomments
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = ProjectBDComments.objects.filter(is_deleted=False)
    filter_fields = ('projectBD',)
    serializer_class = ProjectBDCommentsSerializer

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

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('BD.manageProjectBD'):
                pass
            elif request.user.has_perm('BD.user_getProjectBD'):
                queryset = queryset.filter(Q(projectBD__in=request.user.user_projBDs.all()) | Q(projectBD__in=request.user.contractors_projBDs.all())| Q(projectBD__in=request.user.managers_ProjectBD.filter(is_deleted=False).values_list('projectBD', flat=True)))
            else:
                raise InvestError(2009)
            queryset = queryset.order_by('-createdtime')
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = ProjectBDCommentsSerializer(queryset, many=True)
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
            bdinstance = ProjectBD.objects.get(id=int(data['projectBD']))
            if request.user.has_perm('BD.manageProjectBD'):
                pass
            elif request.user in [bdinstance.manager, bdinstance.contractors, bdinstance.createuser]:
                pass
            elif bdinstance.ProjectBD_managers.filter(manager=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
            lang = request.GET.get('lang')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            with transaction.atomic():
                commentinstance = ProjectBDCommentsCreateSerializer(data=data)
                if commentinstance.is_valid():
                    newcommentinstance = commentinstance.save()
                else:
                    raise InvestError(4009, msg='创建项目BDcomments失败--%s' % commentinstance.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(ProjectBDCommentsSerializer(newcommentinstance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('BD.manageProjectBD'):
                pass
            elif request.user in [instance.createuser, instance.projectBD.manager, instance.projectBD.contractors]:
                pass
            elif instance.projectBD.ProjectBD_managers.filter(manager=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
            lang = request.GET.get('lang')
            data = request.data
            with transaction.atomic():
                commentinstance = ProjectBDCommentsCreateSerializer(instance, data=data)
                if commentinstance.is_valid():
                    newcommentinstance = commentinstance.save()
                else:
                    raise InvestError(4009, msg='修改项目BDcomments失败--%s' % commentinstance.error_messages)
                return JSONResponse(SuccessResponse(
                    returnDictChangeToLanguage(ProjectBDCommentsSerializer(newcommentinstance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('BD.manageProjectBD'):
                pass
            elif request.user in [instance.createuser, instance.projectBD.manager, instance.projectBD.contractors]:
                pass
            elif instance.projectBD.ProjectBD_managers.filter(manager=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
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


class OrgBDFilter(MyFilterSet):
    manager = RelationFilter(filterstr='manager',lookup_method='in')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')
    org = RelationFilter(filterstr='org', lookup_method='in')
    response = RelationFilter(filterstr='response', lookup_method='in')
    proj = RelationFilter(filterstr='proj', lookup_method='in')
    bduser = RelationFilter(filterstr='bduser', lookup_method='in')
    isSolved = RelationFilter(filterstr='isSolved')
    isRead = RelationFilter(filterstr='isRead')
    isimportant = RelationFilter(filterstr='isimportant')
    stime = RelationFilter(filterstr='createdtime', lookup_method='gte')
    etime = RelationFilter(filterstr='createdtime', lookup_method='lt')
    stimeM = RelationFilter(filterstr='lastmodifytime', lookup_method='gte')
    etimeM = RelationFilter(filterstr='lastmodifytime', lookup_method='lt')
    class Meta:
        model = OrgBD
        fields = ('manager', 'createuser', 'org', 'proj', 'stime', 'etime', 'stimeM', 'etimeM', 'response', 'isimportant', 'isSolved', 'isRead', 'bduser')


class OrgBDView(viewsets.ModelViewSet):
    """
    countBDProjectOrg:统计机构BD项目机构
    countBDManager:统计机构BD负责人
    countBDProject:统计机构BD项目
    countBDResponse:统计机构BD状态
    list:获取机构BD
    create:增加机构BD
    retrieve:查看机构BD信息
    readBd:已读回执
    update:修改机构BD信息
    destroy:删除机构BD
    """
    filter_backends = (filters.DjangoFilterBackend,filters.SearchFilter)
    queryset = OrgBD.objects.filter(is_deleted=False)
    filter_class = OrgBDFilter
    search_fields = ('proj__projtitleC', 'username', 'usermobile', 'manager__usernameC', 'org__orgnameC', 'org__orgnameE')
    serializer_class = OrgBDSerializer
    redis_key = 'org_bd'

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = read_from_cache(self.redis_key)
        if not queryset:
            queryset = self.queryset
            write_to_cache(self.redis_key, queryset)
        if isinstance(queryset, QuerySet):
            if self.request.user.is_authenticated:
                queryset = queryset.filter(datasource_id=self.request.user.datasource_id)
            else:
                queryset = queryset
        else:
            raise InvestError(code=8890)
        return queryset

    def get_object(self):
        try:
            obj = self.queryset.get(id=self.kwargs['pk'])
        except OrgBD.DoesNotExist:
            raise InvestError(code=5008)
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888)
        return obj

    @loginTokenIsAvailable(['BD.manageOrgBD', 'BD.user_getOrgBD'])
    def countBDProjectOrg(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            sortfield = request.GET.get('sort', 'orgimportant')
            if request.GET.get('desc', 1) in ('1', u'1', 1):
                sortfield = '-' + sortfield
            queryset = queryset.annotate(orgimportant=Max('isimportant')).values('org','proj','orgimportant').annotate(orgcount=Count('org'),projcount=Count('proj')).order_by(sortfield)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = json.dumps(list(queryset), cls=DjangoJSONEncoder)
            return JSONResponse(SuccessResponse({'count': count, 'data': json.loads(serializer)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['BD.manageOrgBD', 'BD.user_getOrgBD'])
    def countBDProject(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            sortfield = request.GET.get('sort', 'created')
            if request.GET.get('desc', 1) in ('1', u'1', 1):
                sortfield = '-' + sortfield
            queryset = queryset.values('proj').annotate(count=Count('proj'), created=Max('createdtime')).order_by(sortfield)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = orgBDProjSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse( {'count':count,'data':returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable(['BD.manageOrgBD', 'BD.user_getOrgBD'])
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            query_string = request.META['QUERY_STRING']
            uriPath = str(request.path)
            cachekey = '{}_{}_{}'.format(uriPath, query_string, request.user.id)
            response = read_from_cache(cachekey)
            if response:
                return JSONResponse(SuccessResponse(response))
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            sortfield = request.GET.get('sort', 'createdtime')
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
            serializer = OrgBDSerializer(queryset, many=True, context={'user_id': request.user.id})
            response = {'count':count,'data':returnListChangeToLanguage(serializer.data,lang)}
            write_to_cache(cachekey, response)
            return JSONResponse(SuccessResponse(response))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['BD.manageOrgBD', 'BD.user_getOrgBD'])
    def countBDManager(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            count = queryset.count()
            queryset = queryset.values_list('manager').annotate(count=Count('manager'))
            serializer = json.dumps(list(queryset), cls=DjangoJSONEncoder)
            return JSONResponse(SuccessResponse({'count': count, 'manager_count': json.loads(serializer)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['BD.manageOrgBD', 'BD.user_getOrgBD'])
    def countBDResponse(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            count = queryset.count()
            queryset = queryset.values('response').annotate(count=Count('*'))
            serializer = json.dumps(list(queryset), cls=DjangoJSONEncoder)
            return JSONResponse(SuccessResponse({'count': count, 'response_count': json.loads(serializer)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            checkSessionToken(request)
            data = request.data
            lang = request.GET.get('lang')
            comments = data.get('comments',None)
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            if request.user.has_perm('BD.manageOrgBD'):
                pass
            else:
                proj = data.get('proj', None)
                if proj:
                    projinstance = project.objects.get(id=proj, is_deleted=False, datasource=request.user.datasource)
                    if request.user.has_perm('BD.user_addOrgBD'):
                        pass
                    elif projinstance.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                        pass
                    else:
                        raise InvestError(2009)
                else:
                    raise InvestError(2009)
            if self.checkOrgIsInBlackList(data['org'], data['proj']):
                raise InvestError(2007, msg='该机构在黑名单中，无法新增机构BD')
            with transaction.atomic():
                orgBD = OrgBDCreateSerializer(data=data)
                if orgBD.is_valid():
                    neworgBD = orgBD.save()
                    if neworgBD.manager:
                        if request.user != neworgBD.manager:
                            today = datetime.date.today()
                            if len(self.queryset.filter(createdtime__year=today.year, createdtime__month=today.month,
                                                        createdtime__day=today.day, manager_id=neworgBD.manager, proj=neworgBD.proj)) == 1:
                                sendmessage_orgBDMessage(neworgBD, receiver=neworgBD.manager, types=['app', 'webmsg', 'sms'], sender=request.user)
                else:
                    raise InvestError(5004,msg='机构BD创建失败——%s'%orgBD.error_messages)
                if comments:
                    data['orgBD'] = neworgBD.id
                    commentinstance = OrgBDCommentsCreateSerializer(data=data)
                    if commentinstance.is_valid():
                        commentinstance.save()
                cache_delete_key(self.redis_key)
                cache_delete_patternKey(key='/bd/orgbd*')
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(OrgBDSerializer(neworgBD, context={'user_id': request.user.id}).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def checkOrgIsInBlackList(self, org_id, proj_id):
        if org_id and proj_id:
            if OrgBDBlack.objects.filter(is_deleted=False, org=org_id, proj=proj_id).exists():
                return True
            else:
                return False
        else:
            raise InvestError(2007, msg='org/proj 不能是空' )

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('BD.manageOrgBD'):
                pass
            elif request.user in [instance.createuser, instance.manager]:
                pass
            else:
                raise InvestError(2009)
            serializer = self.serializer_class(instance, context={'user_id': request.user.id})
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def readBd(self, request, *args, **kwargs):
        try:
            data = request.data
            bdlist = data.get('bds')
            bdQuery = self.get_queryset().filter(manager_id=request.user.id, id__in=bdlist)
            count = 0
            if bdQuery.exists():
                count = bdQuery.count()
                bdQuery.update(isRead=True)
                cache_delete_patternKey(key='/bd/orgbd*')
            return JSONResponse(SuccessResponse({'count': count}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            data = request.data
            data['lastmodifyuser'] = request.user.id
            lang = request.GET.get('lang')
            instance = self.get_object()
            oldmanager = instance.manager
            data.pop('datasource', None)
            remark = data.get('remark', None)
            if request.user.has_perm('BD.manageOrgBD'):
                pass
            elif request.user in [instance.createuser, instance.manager]:
                pass
            elif instance.proj:
                if instance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                    pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                orgBD = OrgBDCreateSerializer(instance,data=data)
                if orgBD.is_valid():
                    neworgBD = orgBD.save()
                    cache_delete_patternKey(key='/bd/orgbd*')
                    if remark and remark.strip() != '' and neworgBD.response_id not in [4, 5, 6, None] and neworgBD.bduser and neworgBD.proj:
                        try:
                            timeline_qs = timeline.objects.filter(is_deleted=0, investor=neworgBD.bduser,
                                                                  proj=neworgBD.proj, trader=neworgBD.manager)
                            if timeline_qs.exists():
                                timelineremark(timeline=timeline_qs.first(), remark=remark,
                                               createuser=neworgBD.createuser, datasource=neworgBD.datasource).save()
                        except Exception:
                            logexcption(msg='同步备注失败，OrgBD_id-%s ' % neworgBD.id)
                    oldmanager_id = data.get('manager', None)
                    if oldmanager_id and oldmanager_id != oldmanager.id:
                        if request.user != neworgBD.manager:
                            today = datetime.date.today()
                            if len(self.queryset.filter(createdtime__year=today.year, createdtime__month=today.month,
                                                        createdtime__day=today.day, manager_id=neworgBD.manager, proj=neworgBD.proj)) == 1:
                                sendmessage_orgBDMessage(neworgBD, receiver=neworgBD.manager,
                                                         types=['app', 'webmsg', 'sms'], sender=request.user)
                else:
                    raise InvestError(5004, msg='机构BD修改失败——%s' % orgBD.error_messages)
                cache_delete_key(self.redis_key)
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(OrgBDSerializer(neworgBD, context={'user_id': request.user.id}).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('BD.manageOrgBD'):
                pass
            elif request.user in [instance.createuser, instance.manager]:
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                instance.OrgBD_comments.filter(is_deleted=False).update(is_deleted=True, deleteduser=request.user,
                                                                        deletedtime=datetime.datetime.now())
                deleteMessage(type=11, sourceid=instance.id)
            cache_delete_key(self.redis_key)
            cache_delete_patternKey(key='/bd/orgbd*')
            return JSONResponse(SuccessResponse({'isDeleted': True,}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class OrgBDBlackFilter(FilterSet):
    proj = RelationFilter(filterstr='proj',lookup_method='in')
    org = RelationFilter(filterstr='org', lookup_method='in')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')
    class Meta:
        model = OrgBDBlack
        fields = ('proj', 'org', 'createuser')


class OrgBDBlackView(viewsets.ModelViewSet):
    """
    list: 获取机构BD黑名单
    create: 增加机构BD黑名单
    update: 修改加入黑名单的原因
    destroy: 删除机构BD黑名单
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = OrgBDBlack.objects.filter(is_deleted=False)
    filter_class = OrgBDBlackFilter
    serializer_class = OrgBDBlackCreateSerializer

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



    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('BD.manageOrgBDBlack') or request.user.has_perm('BD.getOrgBDBlack'):
                queryset = queryset
            else:
                queryset = queryset.filter(Q(proj__proj_traders__user=request.user, proj__proj_traders__is_deleted=False))
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializers = OrgBDBlackSerializer(queryset, many=True)
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
            projid = data.get('proj', None)
            if projid:
                projinstance = project.objects.get(id=projid, is_deleted=False, datasource=request.user.datasource)
                if request.user.has_perm('BD.manageOrgBDBlack') or request.user.has_perm('BD.addOrgBDBlack'):
                    pass
                elif projinstance.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                    pass
                else:
                    raise InvestError(2009)
            else:
                raise InvestError(2007, msg='项目/机构不能为空')
            with transaction.atomic():
                instanceSerializer = OrgBDBlackCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instance = instanceSerializer.save()
                else:
                    raise InvestError(5004, msg='新增机构BD黑名单失败--%s' % instanceSerializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(OrgBDBlackSerializer(instance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            data = request.data
            data.pop('createuser', None)
            data.pop('org', None)
            data.pop('proj', None)
            lang = request.GET.get('lang')
            instance = self.get_object()
            projinstance = instance.proj
            if request.user.has_perm('BD.manageOrgBDBlack') or projinstance.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                newinstanceSeria = OrgBDBlackCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstance = newinstanceSeria.save()
                else:
                    raise InvestError(2009, msg='机构BD黑名单加入原因修改失败——%s' % newinstanceSeria.errors)
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(OrgBDBlackSerializer(newinstance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            projinstance = instance.proj
            if request.user.has_perm('BD.manageOrgBDBlack') or request.user.has_perm('BD.delOrgBDBlack'):
                pass
            elif projinstance.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
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

class OrgBDCommentsFilter(FilterSet):
    orgBD = RelationFilter(filterstr='orgBD',lookup_method='in')
    stime = RelationFilter(filterstr='createdtime', lookup_method='gte')
    etime = RelationFilter(filterstr='createdtime', lookup_method='lt')
    stimeM = RelationFilter(filterstr='lastmodifytime', lookup_method='gte')
    etimeM = RelationFilter(filterstr='lastmodifytime', lookup_method='lt')
    class Meta:
        model = OrgBDComments
        fields = ('orgBD', 'stime', 'etime', 'stimeM', 'etimeM')

class OrgBDCommentsView(viewsets.ModelViewSet):
    """
    list:获取机构BDcomments
    create:增加机构BDcomments
    destroy:删除机构BDcomments
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = OrgBDComments.objects.filter(is_deleted=False)
    filter_class = OrgBDCommentsFilter
    serializer_class = OrgBDCommentsSerializer

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



    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('BD.manageOrgBD'):
                pass
            elif request.user.has_perm('BD.user_getOrgBD'):
                queryset = queryset.filter(Q(orgBD__createuser=request.user) | Q(orgBD__in=request.user.user_orgBDs.all()) | Q(orgBD__proj__in=request.user.usertake_projs.all()) | Q(orgBD__proj__in=request.user.usermake_projs.all()))
            else:
                raise InvestError(2009)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = OrgBDCommentsSerializer(queryset, many=True)
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
            bdinstance = OrgBD.objects.get(id=int(data['orgBD']))
            if request.user.has_perm('BD.manageOrgBD'):
                pass
            elif request.user in [bdinstance.createuser, bdinstance.manager]:
                pass
            elif bdinstance.proj:
                if bdinstance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                    pass
            else:
                raise InvestError(2009)
            lang = request.GET.get('lang')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            with transaction.atomic():
                commentinstance = OrgBDCommentsCreateSerializer(data=data)
                if commentinstance.is_valid():
                    newcommentinstance = commentinstance.save()
                    cache_delete_patternKey(key='/bd/orgbd*')
                else:
                    raise InvestError(5004, msg='创建机构BDcomments失败--%s' % commentinstance.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(OrgBDCommentsSerializer(newcommentinstance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            data = request.data
            if request.user.has_perm('BD.manageOrgBD'):
                pass
            elif request.user in [instance.createuser, instance.orgBD.manager]:
                pass
            else:
                raise InvestError(2009)
            lang = request.GET.get('lang')
            with transaction.atomic():
                commentinstance = OrgBDCommentsCreateSerializer(instance, data=data)
                if commentinstance.is_valid():
                    newcommentinstance = commentinstance.save()
                    cache_delete_patternKey(key='/bd/orgbd*')
                else:
                    raise InvestError(5004, msg='修改机构BDcomments失败--%s' % commentinstance.error_messages)
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(OrgBDCommentsSerializer(newcommentinstance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('BD.manageOrgBD'):
                pass
            elif request.user.id == instance.createuser_id:
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                cache_delete_patternKey(key='/bd/orgbd*')
            return JSONResponse(SuccessResponse({'isDeleted': True, }))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class MeetBDFilter(FilterSet):
    username = RelationFilter(filterstr='username', lookup_method='icontains')
    usermobile = RelationFilter(filterstr='usermobile', lookup_method='contains')
    manager = RelationFilter(filterstr='manager', lookup_method='in')
    org = RelationFilter(filterstr='org', lookup_method='in')
    proj = RelationFilter(filterstr='proj', lookup_method='in')
    bduser = RelationFilter(filterstr='bduser', lookup_method='in')
    country = RelationFilter(filterstr='country', lookup_method='in')

    class Meta:
        model = MeetingBD
        fields = ('username', 'usermobile', 'manager', 'org', 'proj', 'bduser', 'country')


class MeetingBDView(viewsets.ModelViewSet):
    """
    list:获取会议BD
    create:增加会议BD
    retrieve:查看会议BD信息
    update:修改会议BD信息
    destroy:删除会议BD
    getShareMeetingBDdetail:根据sharetoken获取会议BD
    getShareMeetingBDtoken:获取会议BD分享sharetoken
    """
    filter_backends = (filters.DjangoFilterBackend,filters.SearchFilter)
    queryset = MeetingBD.objects.filter(is_deleted=False)
    filter_class = MeetBDFilter
    search_fields = ('proj__projtitleC', 'username','manager__usernameC')
    serializer_class = MeetingBDSerializer

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


    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('BD.manageMeetBD'):
                pass
            elif request.user.has_perm('BD.user_getMeetBD'):
                queryset = queryset.filter(Q(manager=request.user) | Q(createuser=request.user) | Q(proj__in=request.user.usertake_projs.all()) | Q(proj__in=request.user.usermake_projs.all()))
            else:
                raise InvestError(2009)
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = MeetingBDSerializer(queryset, many=True)
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
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            if request.user.has_perm('BD.manageMeetBD'):
                pass
            else:
                proj = data.get('proj', None)
                if proj:
                    projinstance = project.objects.get(id=proj, is_deleted=False, datasource=request.user.datasource)
                    if request.user.has_perm('BD.user_addMeetBD'):
                        pass
                    elif projinstance.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                        pass
                    else:
                        raise InvestError(2009)
                else:
                    raise InvestError(2009)
            with transaction.atomic():
                meetBD = MeetingBDCreateSerializer(data=data)
                if meetBD.is_valid():
                    newMeetBD = meetBD.save()
                    if newMeetBD.manager:
                        add_perm('BD.user_manageMeetBD', newMeetBD.manager, newMeetBD)
                else:
                    raise InvestError(5005,msg='会议BD创建失败——%s'%meetBD.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(MeetingBDSerializer(newMeetBD).data,lang)))
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
            if request.user.has_perm('BD.manageMeetBD'):
                pass
            elif request.user.has_perm('BD.user_manageMeetBD', instance):
                pass
            elif request.user.has_perm('BD.user_getMeetBD'):
                if not instance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                    raise InvestError(2009)
            else:
                raise InvestError(2009)
            serializer = self.serializer_class(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            data = request.data
            data.pop('datasource', None)
            lang = request.GET.get('lang')
            instance = self.get_object()
            oldmanager = instance.manager
            if request.user.has_perm('BD.manageMeetBD'):
                pass
            elif request.user.has_perm('BD.user_manageMeetBD', instance):
                # data = {'comments': data.get('comments', instance.comments),
                #         'attachment': data.get('attachment', instance.attachment),
                #         'attachmentbucket': data.get('attachmentbucket', instance.attachmentbucket),}
                pass
            elif instance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                meetBD = MeetingBDCreateSerializer(instance,data=data)
                if meetBD.is_valid():
                    newMeetBD = meetBD.save()
                    oldmanager_id = data.get('manager', None)
                    if oldmanager_id and oldmanager_id != oldmanager.id:
                        add_perm('BD.user_manageMeetBD', newMeetBD.manager, newMeetBD)
                        rem_perm('BD.user_manageMeetBD', oldmanager, newMeetBD)
                else:
                    raise InvestError(5005, msg='会议BD修改失败——%s' % meetBD.error_messages)
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(MeetingBDSerializer(newMeetBD).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def deleteAttachment(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('BD.manageMeetBD'):
                pass
            elif request.user.has_perm('BD.user_manageMeetBD', instance):
                pass
            elif instance.proj.proj_traders.all().filter(user=request.user, is_deleted=False).exists():
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                bucket = instance.attachmentbucket
                key = instance.attachment
                deleteqiniufile(bucket, key)
                instance.attachmentbucket = None
                instance.attachment = None
                instance.save()
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(MeetingBDSerializer(instance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['BD.manageMeetBD',])
    def destroy(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                instance = self.get_object()
                bucket = instance.attachmentbucket
                key = instance.attachment
                deleteqiniufile(bucket, key)
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
            return JSONResponse(SuccessResponse({'isDeleted': True,}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def getShareMeetingBDtoken(self, request, *args, **kwargs):
        try:
            data = request.data
            meetinglist = data.get('meetings', None)
            if not isinstance(meetinglist, (list, tuple)):
                raise InvestError(2007, msg='except string list')
            meetings = ','.join(map(str, meetinglist))
            with transaction.atomic():
                sharetokenset = MeetBDShareToken.objects.filter(user=request.user, meetings=meetings)
                if sharetokenset.exists():
                    sharetoken = sharetokenset.last()
                else:
                    sharetoken = MeetBDShareToken(user=request.user, meetings=meetings)
                    sharetoken.save()
                return JSONResponse(SuccessResponse(sharetoken.key))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def getShareMeetingBDdetail(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            tokenkey = request.GET.get('token')
            if tokenkey:
                token = MeetBDShareToken.objects.filter(key=tokenkey)
                if token.exists():
                    meetingstr = token.first().meetings
                    meetinglist = meetingstr.split(',')
                else:
                    raise InvestError(2009,msg='token无效')
            else:
                raise InvestError(2009, msg='token无效')
            serializer = MeetingBDSerializer(self.get_queryset().filter(id__in=meetinglist).order_by('-meet_date'), many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



def sendExpiredOrgBDEmail():
    expireday = datetime.date.today() + datetime.timedelta(days=2)
    expiretime_start = datetime.datetime.strptime(str(expireday), '%Y-%m-%d')
    expiretime_end = expiretime_start + datetime.timedelta(days=1)
    orgBD_qs = OrgBD.objects.all().filter(is_deleted=False, isSolved=False,
                                          expirationtime__lt=expiretime_end, expirationtime__gte=expiretime_start)
    managers = orgBD_qs.values_list('manager').annotate(Count('manager'))
    for manager in managers:
        manager_id = manager[0]
        managerbd_qs = orgBD_qs.filter(manager_id=manager_id)
        receiver = managerbd_qs.first().manager
        projs = managerbd_qs.values_list('proj').annotate(Count('proj')).order_by('-proj')
        projlist = []
        for proj in projs:
            projorglist = []
            proj_id = proj[0]
            managerprojbd_qs = managerbd_qs.filter(proj_id=proj_id)
            orgs = managerprojbd_qs.values_list('org').annotate(Count('org'))
            for org in orgs:
                org_id = org[0]
                managerprojorgbd_qs = managerprojbd_qs.filter(org_id=org_id)
                projorgtask = OrgBDSerializer(managerprojorgbd_qs, many=True).data
                if len(projorgtask) > 0:
                    projorgtask[0]['orgspan'] = len(projorgtask)
                projorglist.extend(projorgtask)
            if len(projorglist) > 0:
                projorglist[0]['projspan'] = len(projorglist)
            projlist.extend(projorglist)
        aaa = {'orgbd_qs': projlist, 'cli_domain' : cli_domain}
        html = render_to_response('OrgBDMail_template_cn.html', aaa).content
        sendmessage_orgBDExpireMessage(receiver, ['email'], html)

class WorkReportFilter(FilterSet):
    user = RelationFilter(filterstr='user',lookup_method='in')
    indGroup = RelationFilter(filterstr='indGroup', lookup_method='in')
    startTime = RelationFilter(filterstr='startTime', lookup_method='gte')
    endTime = RelationFilter(filterstr='endTime', lookup_method='lte')
    class Meta:
        model = WorkReport
        fields = ('user','indGroup', 'startTime', 'endTime')


class WorkReportView(viewsets.ModelViewSet):
    """
    list: 获取用户工作报表
    create: 增加用户工作报表
    retrieve: 查看报表
    update: 修改用户工作报表
    destroy: 删除用户工作报表
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = WorkReport.objects.filter(is_deleted=False)
    filter_class = WorkReportFilter
    serializer_class = WorkReportSerializer

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



    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('BD.admin_getWorkReport'):
                queryset = queryset
            else:
                queryset = queryset.filter(user=request.user)
            search = request.GET.get('search')
            if search:
                es = Elasticsearch({HAYSTACK_CONNECTIONS['default']['URL']})
                ret = es.search(index=HAYSTACK_CONNECTIONS['default']['INDEX_NAME'],
                                body={
                                    "_source": ["id", "report"],
                                    "query": {
                                        "bool": {
                                            "must": {"match_phrase": {"marketMsg": search}},
                                            "should": [
                                                    {"match_phrase": {"django_ct": "BD.WorkReport"}},
                                                    {"match_phrase": {"django_ct": "BD.WorkReportMarketMsg"}}
                                            ]
                                        }
                                    }
                                })
                searchIds = set()
                for source in ret["hits"]["hits"]:
                    if source['_source'].get('report'):
                        searchIds.add(source['_source']['report'])
                queryset = queryset.filter(id__in=searchIds)
            sortfield = request.GET.get('sort', 'createdtime')
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
            if not data.get('user'):
                raise InvestError(2007, msg='user 不能为空')
            if data['user'] != request.user.id and not request.user.is_superuser:
                raise InvestError(2009, msg='没有权限给别人建立工作报表')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            with transaction.atomic():
                instanceSerializer = WorkReportCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instance = instanceSerializer.save()
                else:
                    raise InvestError(20071, msg='新增用户工作报表失败--%s' % instanceSerializer.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data, lang)))
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
            if request.user.has_perm('BD.admin_getWorkReport') or request.user == instance.user:
                pass
            else:
                raise InvestError(2009)
            serializer = self.serializer_class(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            data = request.data
            data.pop('user')
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user != instance.user and not request.user.is_superuser:
                raise InvestError(2009, msg='没有权限修改该工作报表')
            with transaction.atomic():
                newinstanceSeria = WorkReportCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstance = newinstanceSeria.save()
                else:
                    raise InvestError(2009, msg='用户工作报表修改失败——%s' % newinstanceSeria.errors)
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
            if request.user != instance.user and not request.user.is_superuser:
                raise InvestError(2009, msg='没有权限修改该工作报表')
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


class WorkReportMarketMsgFilter(FilterSet):
    report = RelationFilter(filterstr='report',lookup_method='in')
    createuser = RelationFilter(filterstr='createuser', lookup_method='in')
    class Meta:
        model = WorkReportMarketMsg
        fields = ('report',  'createuser')


class WorkReportMarketMsgView(viewsets.ModelViewSet):
    """
    list: 获取用户工作报表项目工作信息
    create: 增加用户工作报表项目工作信息
    update: 修改用户工作报表项目工作信息
    destroy: 删除用户工作报表项目工作信息
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = WorkReportMarketMsg.objects.filter(is_deleted=False)
    filter_class = WorkReportMarketMsgFilter
    serializer_class = WorkReportMarketMsgSerializer

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


    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('BD.admin_getWorkReport'):
                queryset = queryset
            else:
                queryset = queryset.filter(report__user=request.user)
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
            reportInstance = WorkReport.objects.get(id=data['report'])
            if request.user != reportInstance.user and not request.user.is_superuser:
                raise InvestError(2009, msg='没有权限增加项目计划')
            with transaction.atomic():
                instanceSerializer = WorkReportMarketMsgCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instance = instanceSerializer.save()
                else:
                    raise InvestError(20071, msg='新增用户工作报表项目计划失败--%s' % instanceSerializer.error_messages)
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
            if request.user != instance.report.user and not request.user.is_superuser:
                raise InvestError(2009, msg='没有权限增加市场信息')
            with transaction.atomic():
                newinstanceSeria = WorkReportMarketMsgCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstance = newinstanceSeria.save()
                else:
                    raise InvestError(2009, msg='用户工作报表市场信息修改失败——%s' % newinstanceSeria.errors)
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
            if request.user != instance.report.user and not request.user.is_superuser:
                raise InvestError(2009, msg='没有权限删除市场信息')
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


class WorkReportProjInfoFilter(FilterSet):
    report = RelationFilter(filterstr='report',lookup_method='in')
    proj = RelationFilter(filterstr='proj', lookup_method='in')
    projTitle = RelationFilter(filterstr='projTitle', lookup_method='icontains')
    user = RelationFilter(filterstr='report__user', lookup_method='in')
    indGroup = RelationFilter(filterstr='report__indGroup', lookup_method='in')
    class Meta:
        model = WorkReportProjInfo
        fields = ('report', 'proj', 'user', 'indGroup')


class WorkReportProjInfoView(viewsets.ModelViewSet):
    """
    list: 获取用户工作报表项目工作信息
    create: 增加用户工作报表项目工作信息
    update: 修改用户工作报表项目工作信息
    destroy: 删除用户工作报表项目工作信息
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = WorkReportProjInfo.objects.filter(is_deleted=False)
    filter_class = WorkReportProjInfoFilter
    serializer_class = WorkReportProjInfoSerializer

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



    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('BD.admin_getWorkReport'):
                queryset = queryset
            else:
                queryset = queryset.filter(report__user=request.user)
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
            reportInstance = WorkReport.objects.get(id=data['report'])
            if request.user != reportInstance.user and not request.user.is_superuser:
                raise InvestError(2009, msg='没有权限增加项目计划')
            with transaction.atomic():
                instanceSerializer = WorkReportProjInfoCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instance = instanceSerializer.save()
                else:
                    raise InvestError(20071, msg='新增用户工作报表项目计划失败--%s' % instanceSerializer.error_messages)
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
            if request.user != instance.report.user and not request.user.is_superuser:
                raise InvestError(2009, msg='没有权限增加项目计划')
            with transaction.atomic():
                newinstanceSeria = WorkReportProjInfoCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstance = newinstanceSeria.save()
                else:
                    raise InvestError(2009, msg='用户工作报表项目计划修改失败——%s' % newinstanceSeria.errors)
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
            if request.user != instance.report.user and not request.user.is_superuser:
                raise InvestError(2009, msg='没有权限删除项目计划')
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



class OKRFilter(FilterSet):
    createuser = RelationFilter(filterstr='createuser',lookup_method='in')
    year = RelationFilter(filterstr='year',lookup_method='in')
    quarter = RelationFilter(filterstr='indGroup', lookup_method='in')
    okrType = RelationFilter(filterstr='okrType', lookup_method='in')
    class Meta:
        model = OKR
        fields = ('createuser', 'year', 'quarter', 'okrType')


class OKRView(viewsets.ModelViewSet):
    """
    list: 获取季度OKR列表
    create: 增加季度OKR
    retrieve: 查看某一季度OKR
    update: 修改某一季度OKR
    destroy: 删除某一季度OKR
    """
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    queryset = OKR.objects.filter(is_deleted=False)
    filter_class = OKRFilter
    search_fields = ('target',)
    serializer_class = OKRSerializer

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



    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            if request.user.has_perm('usersys.as_trader'):
                pass
            else:
                raise InvestError(2009)
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
            if request.user.has_perm('usersys.as_trader'):
                pass
            else:
                raise InvestError(2009)
            data = request.data
            lang = request.GET.get('lang')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            with transaction.atomic():
                instanceSerializer = OKRCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instance = instanceSerializer.save()
                else:
                    raise InvestError(20071, msg='新增OKR失败--%s' % instanceSerializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            if request.user.has_perm('usersys.as_trader'):
                pass
            else:
                raise InvestError(2009)
            instance = self.get_object()
            serializer = self.serializer_class(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
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
            if request.user == instance.createuser or request.user.is_superuser:
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                newinstanceSeria = OKRCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstance = newinstanceSeria.save()
                else:
                    raise InvestError(2009, msg='OKR修改失败——%s' % newinstanceSeria.errors)
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
            if request.user == instance.createuser or request.user.is_superuser:
                pass
            else:
                raise InvestError(2009, msg='没有权限删除该OKR')
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


class OKRResultFilter(FilterSet):
    okr = RelationFilter(filterstr='okr',lookup_method='in')
    confidence = RelationFilter(filterstr='confidence', lookup_method='in')
    class Meta:
        model = OKRResult
        fields = ('okr', 'confidence')


class OKRResultView(viewsets.ModelViewSet):
    """
    list: 获取季度OKR相关结果列表
    create: 增加季度OKR相关结果
    retrieve: 查看某一季度OKR相关结果
    update: 修改某一季度OKR相关结果
    destroy: 删除某一季度OKR相关结果
    """
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    queryset = OKRResult.objects.filter(is_deleted=False)
    filter_class = OKRResultFilter
    search_fields = ('krs',)
    serializer_class = OKRResultSerializer

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


    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            if request.user.has_perm('usersys.as_trader'):
                pass
            else:
                raise InvestError(2009)
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
            okrInstance = OKR.objects.get(is_deleted=False, id=data['okr'])
            if request.user == okrInstance.createuser or request.user.is_superuser:
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                instanceSerializer = OKRResultCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instance = instanceSerializer.save()
                else:
                    raise InvestError(20071, msg='新增用户工作报表项目计划失败--%s' % instanceSerializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            if request.user.has_perm('usersys.as_trader'):
                pass
            else:
                raise InvestError(2009)
            instance = self.get_object()
            serializer = self.serializer_class(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
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
            if request.user == instance.okr.createuser or request.user.is_superuser:
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                newinstanceSeria = OKRResultCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstance = newinstanceSeria.save()
                else:
                    raise InvestError(2009, msg='用户工作报表项目计划修改失败——%s' % newinstanceSeria.errors)
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
            if request.user == instance.okr.createuser or request.user.is_superuser:
                pass
            else:
                raise InvestError(2009)
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


def sendWorkReportMessage():
    user_qs = MyUser.objects.filter(is_deleted=False, groups__in=[2], userstatus_id=2, onjob=True)
    now = datetime.datetime.now()
    this_week_start = now - datetime.timedelta(days=now.weekday(), hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)
    this_week_end = now + datetime.timedelta(days=6 - now.weekday(), hours=23 - now.hour, minutes=59 - now.minute, seconds=59 - now.second, microseconds=999999 - now.microsecond)
    for user in user_qs:
        if not WorkReport.objects.filter(user=user, startTime__gte=this_week_start, startTime__lte=this_week_end, is_deleted=False).exists():
            sendmessage_workReportDonotWrite(user)
