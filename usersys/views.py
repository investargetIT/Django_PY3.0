#coding=utf-8
import traceback
import datetime
import threading
from django.contrib import auth
from django.contrib.auth.models import Group, Permission
from django.contrib.sessions.backends.cache import SessionStore
from django.core.exceptions import FieldDoesNotExist
from django.core.paginator import Paginator, EmptyPage
from django.db import transaction, models, connection
from django.db.models import Q, Count, QuerySet
from rest_framework import filters, viewsets
from rest_framework.decorators import api_view, detail_route, list_route
from APIlog.views import logininlog, apilog
from dataroom.models import dataroom
from org.models import organization
from sourcetype.views import getmenulist
from third.models import MobileAuthCode
from third.views.qimingpianapi import updatePersonTag
from third.views.qiniufile import deleteqiniufile
from third.views.weixinlogin import get_openid
from usersys.models import MyUser, UserRelation, userTags, MyToken, UnreachUser, UserRemarks, \
    userAttachments, userEvents, UserContrastThirdAccount, registersourcechoice, UserPerformanceAppraisalRecord, \
    UserPersonnelRelations, UserTrainingRecords, UserMentorTrackingRecords, UserWorkingPositionRecords, \
    UserGetStarInvestor, TraderNameIdContrast
from usersys.serializer import UserSerializer, UserListSerializer, UserRelationSerializer, \
    CreatUserSerializer, UserCommenSerializer, UserRelationCreateSerializer, GroupSerializer, GroupDetailSerializer, \
    GroupCreateSerializer, PermissionSerializer, \
    UpdateUserSerializer, UnreachUserSerializer, UserRemarkSerializer, UserRemarkCreateSerializer, \
    UserAttachmentSerializer, UserEventSerializer, UserSimpleSerializer, \
    InvestorUserSerializer, UserPerformanceAppraisalRecordSerializer, UserPerformanceAppraisalRecordCreateSerializer, \
    UserPersonnelRelationsSerializer, UserPersonnelRelationsCreateSerializer, UserTrainingRecordsSerializer, \
    UserTrainingRecordsCreateSerializer, UserMentorTrackingRecordsSerializer, UserMentorTrackingRecordsCreateSerializer, \
    UserWorkingPositionRecordsSerializer, UserWorkingPositionRecordsCreateSerializer, UserInfoSerializer, \
    UserGetStarInvestorCreateSerializer, UserGetStarInvestorSerializer, \
    UserListPersonnelSerializer
from sourcetype.models import Tag, DataSource, TagContrastTable, IndustryGroup
from utils.customClass import JSONResponse, InvestError, RelationFilter, MySearchFilter
from utils.logicJudge import is_userInvestor, is_userTrader, is_dataroomTrader
from utils.sendMessage import sendmessage_userauditstatuchange, sendmessage_userregister, sendmessage_traderadd
from utils.util import loginTokenIsAvailable, catchexcption, returnDictChangeToLanguage, returnListChangeToLanguage, \
    SuccessResponse, InvestErrorResponse, ExceptionResponse, mySortQuery, checkRequestToken
from django_filters import FilterSet


class UserFilter(FilterSet):
    id = RelationFilter(filterstr='id', lookup_method='in')
    groups = RelationFilter(filterstr='groups', lookup_method='in')
    org = RelationFilter(filterstr='org',lookup_method='in')
    # indGroup = RelationFilter(filterstr='indGroup', lookup_method='in')
    onjob = RelationFilter(filterstr='onjob')
    title = RelationFilter(filterstr='title', lookup_method='in')
    directSupervisor = RelationFilter(filterstr='directSupervisor', lookup_method='in')
    mentor = RelationFilter(filterstr='mentor', lookup_method='in')
    orgarea = RelationFilter(filterstr='orgarea', lookup_method='in')
    # tags = RelationFilter(filterstr='tags',lookup_method='in',relationName='user_usertags__is_deleted')
    userstatus = RelationFilter(filterstr='userstatus',lookup_method='in')
    currency = RelationFilter(filterstr='org__currency', lookup_method='in')
    orgtransactionphases = RelationFilter(filterstr='org__orgtransactionphase', lookup_method='in',relationName='org__org_orgTransactionPhases__is_deleted')
    trader = RelationFilter(filterstr='investor_relations__traderuser', lookup_method='in', relationName='investor_relations__is_deleted')
    investor = RelationFilter(filterstr='trader_relations__investoruser', lookup_method='in', relationName='trader_relations__is_deleted')
    class Meta:
        model = MyUser
        fields = ('id', 'onjob', 'groups', 'org','userstatus','currency','orgtransactionphases','orgarea','usercode','title','trader','investor','usernameC')


class UserView(viewsets.ModelViewSet):
    """
    list:用户列表
    getIndGroupInvestor: 获取行业组共享投资人（非共享状态下仅返回自己对接的投资人）
    getIndGroupQuitTraderInvestor: 获取行业组交易师已离职的投资人
    create:注册用户
    adduser:新增用户
    retrieve:查看某一用户信息
    findpassword:找回密码
    changepassword:修改密码
    resetpassword:重置密码
    getAvaibleFalseMobileNumber:获取可用手机号
    update:修改用户信息
    destroy:删除用户
    """
    filter_backends = (MySearchFilter, filters.DjangoFilterBackend,)
    queryset = MyUser.objects.filter(is_deleted=False)
    search_fields = ('mobile','email','usernameC','usernameE','org__orgnameC','orgarea__nameC','org__orgfullname','investor_relations__traderuser__usernameC')
    serializer_class = UserSerializer
    filter_class = UserFilter
    Model = MyUser

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = self.queryset
        if self.request.user.is_authenticated:
            queryset = queryset.filter(datasource=self.request.user.datasource)
        else:
            queryset = queryset.all()
        return queryset

    def get_object(self,pk=None):
        if pk:
            try:
                obj = self.queryset.get(id=pk)
            except self.Model.DoesNotExist:
                raise InvestError(code=2002, msg='用户不存在')
        else:
            lookup_url_kwarg = 'pk'
            try:
                obj = self.queryset.get(id=self.kwargs[lookup_url_kwarg])
            except self.Model.DoesNotExist:
                raise InvestError(code=2002, msg='用户不存在')
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='查询用户失败')
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1) #从第一页开始
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            tags = request.GET.get('tags', None)
            tags_type = request.GET.get('tags_type', 'and')
            if tags:  # 匹配机构标签和机构下用户标签
                tags = tags.split(',')
                if tags_type == 'and':
                    queryset = queryset.filter(user_usertags__tag__in=tags, user_usertags__is_deleted=False).annotate(num_tags=Count('tags', distinct=True)).filter(num_tags=len(tags))
                else:
                    queryset = queryset.filter(user_usertags__tag__in=tags, user_usertags__is_deleted=False)
            indGroups = request.GET.get('indGroup', None)
            if indGroups:  # 匹配机构标签和机构下用户标签
                indGroups = indGroups.split(',')
                queryset = queryset.filter(Q(indGroup__in=indGroups) | Q(user_indgroups__indGroup__in=indGroups))
            queryset = queryset.distinct()
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = mySortQuery(queryset, sortfield, desc, True)
            count = queryset.count()
            try:
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            type = request.GET.get('type', 'alluser')
            if type == 'alluser':
                listserializerclass = UserListSerializer
            else:
                listserializerclass = UserListPersonnelSerializer
            responselist = listserializerclass(queryset, many=True).data
            return JSONResponse(SuccessResponse({'count': count, 'data': returnListChangeToLanguage(responselist, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def getIndGroupInvestor(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            if not page_size:
                page_size = 10
            else:
                page_size = 100 if int(page_size) > 100 else page_size
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            familiar = request.GET.get('familiar')
            if familiar:
                if request.user.indGroup and request.user.indGroup.shareInvestor:
                    queryset = queryset.filter(investor_relations__traderuser__indGroup=request.user.indGroup, investor_relations__is_deleted=False, investor_relations__familiar__in=familiar.split(',')).distinct()
                else:
                    queryset = queryset.filter(investor_relations__traderuser=request.user, investor_relations__is_deleted=False, investor_relations__familiar__in=familiar.split(',')).distinct()
            else:
                if request.user.indGroup and request.user.indGroup.shareInvestor:
                    queryset = queryset.filter(investor_relations__traderuser__indGroup=request.user.indGroup, investor_relations__is_deleted=False).distinct()
                else:
                    queryset = queryset.filter(investor_relations__traderuser=request.user, investor_relations__is_deleted=False).distinct()
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 0)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = InvestorUserSerializer(queryset, many=True, context={'traderuser_id': request.user.id})
            return JSONResponse(SuccessResponse({'count': count, 'data': returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.admin_manageindgroupinvestor'])
    def getIndGroupQuitTraderInvestor(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            sortfield = request.GET.get('sort', 'createdtime')
            indGroup = request.GET.get('indGroup')
            queryset = self.get_queryset()
            if indGroup:
                queryset = queryset.filter(investor_relations__traderuser__indGroup=indGroup,
                                           investor_relations__traderuser__onjob=False,
                                           investor_relations__is_deleted=False)
            else:
                queryset = queryset.filter(investor_relations__traderuser__onjob=False,
                                           investor_relations__is_deleted=False)
            queryset = queryset.exclude(investor_relations__traderuser__onjob=True, investor_relations__is_deleted=False).distinct()
            desc = request.GET.get('desc', 0)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = UserInfoSerializer(queryset, many=True)
            return JSONResponse(
                SuccessResponse({'count': count, 'data': returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



    #注册用户(新注册用户没有交易师)
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                data = request.data
                lang = request.GET.get('lang')
                mobilecode = data.get('mobilecode', None)
                mobilecodetoken = data.get('mobilecodetoken', None)
                mobile = data.get('mobile')
                email = data.get('email')
                source = request.META.get('HTTP_SOURCE')
                if source:
                    datasource = DataSource.objects.filter(id=source,is_deleted=False)
                    if datasource.exists():
                        userdatasource = datasource.first()
                    else:
                        raise InvestError(code=8888, msg='新用户创建失败', detail='source 不存在')
                else:
                    raise InvestError(code=8888, msg='新用户创建失败', detail='source 不能为空')
                if not mobile or not email:
                    raise InvestError(code=2006, msg='新用户创建失败', detail='mobile、email不能为空')

                if not mobilecodetoken or not mobilecode:
                    raise InvestError(code=20072, msg='新用户创建失败', detail='验证码缺失')
                try:
                    mobileauthcode = MobileAuthCode.objects.get(mobile=mobile, code=mobilecode, token=mobilecodetoken)
                except MobileAuthCode.DoesNotExist:
                    raise InvestError(code=2005, msg='新用户创建失败', detail='验证码有误')
                else:
                    if mobileauthcode.isexpired():
                        raise InvestError(code=20051, msg='新用户创建失败', detail='验证码过期')
                if self.queryset.filter(mobile=mobile,datasource=userdatasource).exists():
                    raise InvestError(code=20041, msg='新用户创建失败', detail='手机已存在')
                if self.queryset.filter(email=email,datasource=userdatasource).exists():
                    raise InvestError(code=20042, msg='新用户创建失败', detail='邮箱已存在')
                try:
                    groupname = None
                    type = data.get('type', None)
                    if type in ['trader', u'trader']:
                        groupname = '初级交易师'
                    elif type in ['investor', u'investor']:
                        groupname = '初级投资人'
                    if groupname:
                        group = Group.objects.get(name=groupname,datasource=userdatasource)
                    else:
                        group = Group.objects.get(id=type, datasource=userdatasource)
                except Exception:
                    raise InvestError(20071, msg='新用户创建失败', detail='用户类型不可用')
                data['groups'] = [group.id]
                orgname = data.get('orgname', None)
                if orgname:
                    filters = Q(orgfullname=orgname)
                    orgset = organization.objects.filter(filters,is_deleted=False)
                    if orgset.exists():
                        org = orgset.first()
                    else:
                        org = organization()
                        org.orgnameC = orgname
                        org.datasource= userdatasource
                        org.orgstatus_id = 1
                        org.createdtime = datetime.datetime.now()
                        org.save()
                    data['org'] = org.id
                user = MyUser(email=email,mobile=mobile,datasource=userdatasource)
                password = data.get('password', None)
                user.set_password(password)
                user.save()
                tags = data.pop('tags', None)
                userserializer = CreatUserSerializer(user, data=data)
                if userserializer.is_valid():
                    user = userserializer.save()
                    if tags:
                        usertaglist = []
                        for tag in tags:
                            usertaglist.append(userTags(user=user, tag_id=tag, createdtime=datetime.datetime.now()))
                        user.user_usertags.bulk_create(usertaglist)
                else:
                    raise InvestError(20071, msg='新用户创建失败', detail='%s' % userserializer.error_messages)
                returndic = CreatUserSerializer(user).data
                sendmessage_userregister(user,user,['email','webmsg','app'])
                apilog(request, 'MyUser', None, None, datasource=source)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(returndic,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))
    # 新增用户
    @loginTokenIsAvailable(['usersys.admin_manageuser', 'usersys.as_trader'])
    def adduser(self, request, *args, **kwargs):
        data = request.data
        try:
            lang = request.GET.get('lang')
            with transaction.atomic():
                email = data.get('email')
                mobile = data.get('mobile')
                data['is_active'] = False
                if not email or not mobile:
                    raise InvestError(code=2006, msg='新用户创建失败', detail='mobile、email不能为空')
                if self.get_queryset().filter(Q(mobile=mobile) | Q(email=email)).exists():
                    raise InvestError(code=2004, msg='新用户创建失败', detail='用户已存在')
                user = MyUser(email=email, mobile=mobile, datasource_id=request.user.datasource.id)
                data.pop('password', None)
                user.set_password('Aa123456')
                user.save()
                groupid = data.get('groups', [])
                if len(groupid) == 1:
                    try:
                        group = Group.objects.get(id=groupid[0])
                    except Exception:
                        catchexcption(request)
                        raise InvestError(20071, msg='新用户创建失败', detail='用户类型不可用')
                    if request.user.has_perm('usersys.admin_manageuser'):
                        pass
                    else:
                        if not group.permissions.filter(codename='as_investor').exists():
                            raise InvestError(2009, msg='新用户创建失败', detail='新增用户非投资人类型')
                    data['groups'] = [group.id]
                else:
                    raise InvestError(20072, msg='新用户创建失败', detail='新增用户没有分配可用组别')
                data['createuser'] = request.user.id
                data['createdtime'] = datetime.datetime.now()
                data['datasource'] = request.user.datasource.id
                tags = data.pop('tags', None)
                userserializer = CreatUserSerializer(user, data=data)
                if userserializer.is_valid():
                    user = userserializer.save()
                    if tags:
                        usertaglist = []
                        for tag in tags:
                            usertaglist.append(userTags(user=user, tag_id=tag, createuser=request.user))
                        user.user_usertags.bulk_create(usertaglist)
                else:
                    raise InvestError(20071, msg='新用户创建失败', detail='参数有误%s' % userserializer.error_messages)
                apilog(request, 'MyUser', None, None, datasource=request.user.datasource_id)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(UserSerializer(user).data,lang=lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def getUserSimpleInfo(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 100)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang')
            if int(page_size) > 1000:
                page_size = 1000
            queryset = self.filter_queryset(self.get_queryset())
            count = queryset.count()
            try:
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            return JSONResponse(SuccessResponse({'count': count, 'data': returnListChangeToLanguage(UserSimpleSerializer(queryset, many=True).data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    #get
    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            user = self.get_object()
            if request.user.has_perm('usersys.admin_manageuser'):
                userserializer = UserSerializer
            elif request.user == user.createuser or request.user == user:
                userserializer = UserSerializer
            elif is_userInvestor(request.user, user.id):
                userserializer = UserSerializer
            elif is_userTrader(request.user, user.id):
                userserializer = UserSerializer
            elif UserGetStarInvestor.objects.filter(is_deleted=False, user=request.user, investor=user).exists():
                userserializer = UserSerializer  # 显示
            elif request.user.has_perm('usersys.as_trader'):
                # 投资人有交易师 但交易师已离职
                if not UserRelation.objects.filter(investoruser=user, traderuser__onjob=True, is_deleted=False).exists() and UserRelation.objects.filter(
                        investoruser=user, is_deleted=False).exists():
                    userserializer = UserSerializer  # 显示
                else:
                    userserializer = UserCommenSerializer  # 隐藏
            else:
                userserializer = UserCommenSerializer
            serializer = userserializer(user)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    #put
    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            useridlist = request.data.get('userlist')
            userlist = []
            messagelist = []
            if not useridlist or not isinstance(useridlist, list):
                raise InvestError(20071, msg='用户信息修改失败', detail='except a non-empty array')
            with transaction.atomic():
                for userid in useridlist:
                    data = request.data.get('userdata')
                    if data is not None:
                        user = self.get_object(userid)
                        olduserdata = UserSerializer(user)
                        sendmsg = False
                        groupids = data.pop('groups', [])
                        if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, user.id):
                            if isinstance(groupids, list) and len(groupids) == 1:
                                try:
                                    groupinstance = Group.objects.get(id=groupids[0])
                                except Exception:
                                    raise InvestError(20071, msg='用户信息修改失败', detail='用户类型不可用')
                                if groupinstance not in user.groups.all():
                                    if user.has_perm('usersys.as_trader'):
                                        if Permission.objects.get(codename='as_trader',
                                                                  content_type__app_label='usersys') not in groupinstance.permissions.all():
                                            if user.trader_relations.all().filter(is_deleted=False).exists():
                                                raise InvestError(2010, msg='用户信息修改失败', detail='该用户有对接投资人，请先处理')
                                    if user.has_perm('usersys.as_investor'):
                                        if Permission.objects.get(codename='as_investor',
                                                                  content_type__app_label='usersys') not in groupinstance.permissions.all():
                                            if user.investor_relations.all().filter(is_deleted=False).exists():
                                                raise InvestError(2010, msg='用户信息修改失败', detail='该用户有对接交易师，请先处理')
                                    data['groups'] = [groupinstance.id]
                        elif request.user == user:
                            data.pop('userstatus', None)
                        else:
                            raise InvestError(2009, msg='用户信息修改失败', detail='没有修改权限')
                        data['lastmodifyuser'] = request.user.id
                        data['lastmodifytime'] = datetime.datetime.now()
                        tags = data.pop('tags', None)
                        if data.get('userstatus',None) and user.userstatus_id != data.get('userstatus',None):
                            sendmsg = True
                        userserializer = UpdateUserSerializer(user, data=data)
                        if userserializer.is_valid():
                            user = userserializer.save()
                            if tags is not None:
                                usertagids = user.user_usertags.filter(is_deleted=False, tag__is_deleted=False).values_list('tag_id', flat=True)
                                addset = set(tags).difference(set(usertagids))
                                removeset = set(usertagids).difference(set(tags))
                                user.user_usertags.filter(tag__in=list(removeset)).delete()
                                usertaglist = []
                                createuser = data.get('createuser', request.user.id)
                                for tag in addset:
                                    usertaglist.append(userTags(user=user, tag_id=tag, createuser_id=createuser, createdtime=datetime.datetime.now()))
                                user.user_usertags.bulk_create(usertaglist)
                                if user.org:  # 企名片投资人标签
                                    tag_qs = Tag.objects.filter(is_deleted=False, id__in=tags)
                                    if tag_qs.exists():
                                        threading.Thread(target=updatePersonTag, args=(user.mobile, tag_qs)).start()
                        else:
                            raise InvestError(20071, msg='用户信息修改失败', detail='%s' % userserializer.error_messages)
                        newuserdata = UserSerializer(user)
                        apilog(request, 'MyUser', olduserdata.data, newuserdata.data, modelID=userid, datasource=request.user.datasource_id)
                        userlist.append(newuserdata.data)
                        messagelist.append((user,sendmsg))
                    for user,sendmsg in messagelist:
                        if sendmsg:
                            sendmessage_userauditstatuchange(user,user,['app','email', 'sms','webmsg'],sender=request.user)
                return JSONResponse(SuccessResponse(returnListChangeToLanguage(userlist,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    #delete
    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            useridlist = request.data.get('users')
            userlist = []
            lang = request.GET.get('lang')
            if not useridlist or not isinstance(useridlist,list):
                raise InvestError(20071, msg='用户信息删除失败', detail='except a non-empty array')
            with transaction.atomic():
                for userid in useridlist:
                    if userid == request.user.id:
                        raise InvestError(20071, msg='删除失败, 不能删除自己', detail='不能删除自己')
                    instance = self.get_object(userid)
                    if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, instance.id):
                        pass
                    else:
                        raise InvestError(code=2009, msg='删除失败')
                    for link in ['investor_relations', 'trader_relations', 'usersupport_projs',
                                     'manager_beschedule', 'user_webexUser', 'user_dataroomTemp',
                                     'user_usertags', 'user_remarks', 'userreceive_msgs', 'user_workreport',
                                     'usersend_msgs', 'user_datarooms', 'user_userAttachments', 'user_userEvents',
                                     'user_sharetoken', 'user_projects',
                                     'user_beschedule', 'user_orgBDs', 'userPM_projs']:
                        if link in ['usersupport_projs', 'investor_relations', 'trader_relations', 'userPM_projs',
                                    'user_userEvents', 'user_orgBDs', 'user_projects', 'user_remarks',
                                    'user_userAttachments', 'user_dataroomTemp', 'user_datarooms']:
                            manager = getattr(instance, link, None)
                            if not manager:
                                continue
                            # one to one
                            if isinstance(manager, models.Model):
                                if hasattr(manager, 'is_deleted') and not manager.is_deleted:
                                    raise InvestError(code=2010, msg='删除失败，请先删除该用户的关联数据', detail=u'{} 上有关联数据'.format(link))
                            else:
                                try:
                                    manager.model._meta.get_field('is_deleted')
                                    if manager.all().filter(is_deleted=False).count():
                                        raise InvestError(code=2010, msg='删除失败，请先删除该用户的关联数据', detail=u'{} 上有关联数据'.format(link))
                                except FieldDoesNotExist:
                                    if manager.all().count():
                                        raise InvestError(code=2010, msg='删除失败，请先删除该用户的关联数据', detail=u'{} 上有关联数据'.format(link))
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
                    userlist.append({})
                    instance.delete()
                return JSONResponse(SuccessResponse(returnListChangeToLanguage(userlist,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @list_route(methods=['post'])
    def findpassword(self, request, *args, **kwargs):
        try:
            data = request.data
            mobilecode = data.pop('mobilecode', None)
            mobilecodetoken = data.pop('mobilecodetoken', None)
            mobile = data.get('mobile')
            password = data.get('password')
            source = request.META.get('HTTP_SOURCE')
            if source:
                datasource = DataSource.objects.filter(id=source, is_deleted=False)
                if datasource.exists():
                    userdatasource = datasource.first()
                else:
                    raise InvestError(code=8888, msg='重置密码失败')
            else:
                raise InvestError(code=8888, msg='重置密码失败')
            try:
                user = self.get_queryset().get(mobile=mobile, datasource=userdatasource)
            except MyUser.DoesNotExist:
                raise InvestError(code=2002, msg='重置密码失败', detail='用户不存在')
            try:
                mobileauthcode = MobileAuthCode.objects.get(mobile=mobile, code=mobilecode, token=mobilecodetoken)
            except MobileAuthCode.DoesNotExist:
                raise InvestError(code=2005, msg='重置密码失败', detail='验证码错误')
            else:
                if mobileauthcode.isexpired():
                    raise InvestError(code=20051, msg='重置密码失败', detail='验证码已过期')
            with transaction.atomic():
                user.set_password(password)
                user.save(update_fields=['password'])
                user.user_token.all().update(is_deleted=True)
                return JSONResponse(SuccessResponse(password))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def checkMobileSMSCode(self, request, *args, **kwargs):
        try:
            data = request.data
            mobile = data.get('mobile')
            mobilecode = data.pop('mobilecode', '86')
            mobilecodetoken = data.pop('mobilecodetoken', None)
            if not mobilecodetoken:
                raise InvestError(code=2005, msg='验证失败', detail='验证码token错误')
            try:
                mobileauthcode = MobileAuthCode.objects.get(mobile=mobile, code=mobilecode, token=mobilecodetoken)
            except MobileAuthCode.DoesNotExist:
                raise InvestError(code=2005, msg='验证失败', detail='验证码错误')
            else:
                if mobileauthcode.isexpired():
                    raise InvestError(code=20051, msg='验证失败', detail='验证码已过期')
            return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @detail_route(methods=['put'])
    @loginTokenIsAvailable()
    def changepassword(self, request, *args, **kwargs):
        try:
            data = request.data
            oldpassword = data.get('oldpassword','')
            password = data.get('newpassword','')
            user = self.get_object()
            if user == request.user:
                if not user.check_password(oldpassword):
                    raise InvestError(code=2051, msg='修改密码失败', detail='旧密码错误')
                if not password or not isinstance(password, str):
                    raise InvestError(code=2051, msg='修改密码失败', detail='新密码输入有误')
                if password == oldpassword:
                    raise InvestError(code=2051, msg='修改密码失败', detail='新旧密码不能相同')
                if len(password) < 6:
                    raise InvestError(code=2051, msg='修改密码失败', detail='密码长度至少6位')
            else:
                raise InvestError(code=2009, msg='修改密码失败')
            with transaction.atomic():
                user.set_password(password)
                user.save(update_fields=['password'])
                user.user_token.all().update(is_deleted=True)
                return JSONResponse(SuccessResponse(password))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @detail_route(methods=['get'])
    @loginTokenIsAvailable()
    def resetpassword(self,request, *args, **kwargs):
        try:
            user = self.get_object()
            if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, user.id):
                pass
            else:
                raise InvestError(code=2009, msg='重置密码失败')
            with transaction.atomic():
                user.set_password('Aa123456')
                user.save(update_fields=['password'])
                user.user_token.all().update(is_deleted=True)
                return JSONResponse(SuccessResponse('Aa123456'))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @list_route(methods=['get'])
    def checkUserAccountExist(self, request, *args, **kwargs):
        try:
            source = request.META.get('HTTP_SOURCE', 1)
            account = request.GET.get('account', None)
            lang = request.GET.get('lang', 'cn')
            if account:
                if self.queryset.filter(mobile=account, datasource_id=source).exists():
                    result = True
                    user = UserCommenSerializer(self.queryset.filter(mobile=account, datasource_id=source).first()).data
                elif self.queryset.filter(email=account, datasource_id=source).exists():
                    result = True
                    user = UserCommenSerializer(self.queryset.filter(email=account, datasource_id=source).first()).data
                else:
                    result = False
                    user = None
            else:
                raise InvestError(20072, msg='查询信息有误', detail='account 不能为空')
            return JSONResponse(SuccessResponse({'result':result,'user':returnDictChangeToLanguage(user,lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def getUserRegisterSource(self, request, *args, **kwargs):
        try:
            return JSONResponse(SuccessResponse(registersourcechoice))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def checkRequestTokenAvailable(self, request, *args, **kwargs):
        try:
            return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def getAvaibleFalseMobileNumber(self, request, *args, **kwargs):
        try:
            cursor = connection.cursor()
            cursor.execute('select getmaxmobilenumber()')
            row = cursor.fetchone()[0]
            return JSONResponse(SuccessResponse(str(row)))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @list_route(methods=['get'])
    @loginTokenIsAvailable()
    def getCount(self, request, *args, **kwargs):
        try:
            total_redisKey = 'user_totalcount_%s' % request.user.datasource_id
            totalcount = self.get_queryset().count()
            new_redisKey = 'user_newcount_%s' % request.user.datasource_id
            newcount = self.get_queryset().filter(createdtime__gte=datetime.datetime.now() - datetime.timedelta(days=1)).count()
            result = {'total': totalcount, 'new': newcount}
            return JSONResponse(SuccessResponse(result))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class UnReachUserView(viewsets.ModelViewSet):
    """
        list:获取unreachuser列表
        create:添加unreachuser
        retrieve:查看unreachuser详情
        update:修改unreachuser
        destroy:删除unreachuser
    """
    filter_backends = (filters.DjangoFilterBackend, MySearchFilter)
    filter_fields = ('org', 'name', 'title')
    search_fields = ('name', 'org__orgnameC', 'org__orgfullname', 'title__nameC', 'email', 'mobile')
    queryset = UnreachUser.objects.filter(is_deleted=False)
    serializer_class = UnreachUserSerializer

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

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            sort = request.GET.get('sort')
            if sort not in ['True', 'true', True, 1, 'Yes', 'yes', 'YES', 'TRUE']:
                queryset = queryset.order_by('-createdtime',)
            else:
                queryset = queryset.order_by('createdtime',)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            instancedata = UnreachUserSerializer(queryset,many=True).data
            return JSONResponse(
                SuccessResponse({'count': count, 'data': returnListChangeToLanguage(instancedata, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.admin_manageuser','usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            data['createuser'] = request.user.id
            data['createdtime'] = datetime.datetime.now()
            data['datasource'] = request.user.datasource.id
            with transaction.atomic():
                newinstance = UnreachUserSerializer(data=data)
                if newinstance.is_valid():
                    newinstance.save()
                else:
                    raise InvestError(20071, msg='新增UnReachUser失败', detail='%s' % newinstance.error_messages)
                return JSONResponse(SuccessResponse(newinstance.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = UnreachUserSerializer(instance).data
            return JSONResponse(SuccessResponse(serializer))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('usersys.admin_manageuser') or request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='修改UnReachUser失败')
            data = request.data
            with transaction.atomic():
                newinstance = UnreachUserSerializer(instance, data=data)
                if newinstance.is_valid():
                    newinstance.save()
                else:
                    raise InvestError(20071, msg='修改UnReachUser失败', detail='%s' % newinstance.error_messages)
                return JSONResponse(SuccessResponse(newinstance.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('usersys.admin_manageuser') or request.user == instance.createuser:
                pass
            else:
                raise InvestError(code=2009, msg='修改UnReachUser失败')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deletedtime = datetime.datetime.now()
                instance.deleteduser = request.user
                instance.save()
                return JSONResponse(SuccessResponse(UnreachUserSerializer(instance).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class UserAttachmentFilter(FilterSet):
    user = RelationFilter(filterstr='user', lookup_method='in')

    class Meta:
        model = userAttachments
        fields = ('user',)

class UserAttachmentView(viewsets.ModelViewSet):
    """
            list:用户附件列表
            create:新建用户附件
            update:修改附件信息
            destroy:删除用户附件
            """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = userAttachments.objects.all().filter(is_deleted=False)
    filter_class = UserAttachmentFilter
    serializer_class = UserAttachmentSerializer

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
            serializer = UserAttachmentSerializer(queryset, many=True)
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
        data['createuser'] = request.user.id
        data['datasource'] = request.user.datasource.id
        if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, data['user']):
            pass
        else:
            raise InvestError(code=2009, msg='新增用户附件失败')
        try:
            with transaction.atomic():
                attachmentserializer = UserAttachmentSerializer(data=data)
                if attachmentserializer.is_valid():
                    attachmentserializer.save()
                else:
                    raise InvestError(20071, msg='新增用户附件失败', detail='%s' %  attachmentserializer.error_messages)
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
            if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, instance.user.id):
                pass
            else:
                raise InvestError(code=2009, msg='新增用户附件失败')
            lang = request.GET.get('lang')
            data = request.data
            data.pop('createdtime',None)
            with transaction.atomic():
                serializer = UserAttachmentSerializer(instance, data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    raise InvestError(20071, msg='修改用户附件失败', detail='%s' % serializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, instance.user.id):
                pass
            else:
                raise InvestError(code=2009, msg='新增用户附件失败')
            with transaction.atomic():
                instance.is_deleted = True
                deleteqiniufile(instance.bucket, instance.key)
                instance.delete()
                return JSONResponse(SuccessResponse({'isdeleted': True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class UserEventView(viewsets.ModelViewSet):
    """
            list:用户投资经历列表
            create:新建用户投资经历
            update:修改用户投资经历
            destroy:删除用户投资经历
            """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = userEvents.objects.all().filter(is_deleted=False)
    filter_fields = ('user',)
    serializer_class = UserEventSerializer

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
            serializer = UserEventSerializer(queryset, many=True)
            return JSONResponse(
                SuccessResponse({'count': count, 'data': returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        data = request.data
        user_id = data.get('user', None)
        if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, user_id):
            pass
        else:
            raise InvestError(code=2009, msg='新增用户投资经历失败')
        lang = request.GET.get('lang')
        data['createuser'] = request.user.id
        industrytype = data.get('industrytype', None)
        Pindustrytype = data.get('Pindustrytype', None)
        try:
            with transaction.atomic():
                insserializer = UserEventSerializer(data=data)
                if insserializer.is_valid():
                    insserializer.save()
                    useP = False
                    if industrytype:
                        for tag_id in TagContrastTable.objects.filter(cat_name=industrytype).values_list('tag_id'):
                            useP = True
                            if not userTags.objects.filter(user_id=user_id, tag_id=tag_id[0], is_deleted=False).exists():
                                userTags(user_id=user_id, tag_id=tag_id[0], createuser=request.user).save()
                    if not useP:
                        if Pindustrytype:
                            for tag_id in TagContrastTable.objects.filter(cat_name=Pindustrytype).values_list('tag_id'):
                                if not userTags.objects.filter(user_id=user_id, tag_id=tag_id[0],
                                                               is_deleted=False).exists():
                                    userTags(user_id=user_id, tag_id=tag_id[0], createuser=request.user).save()
                else:
                    raise InvestError(20071, msg='新增用户投资经历失败', detail='%s' % insserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(insserializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, instance.user.id):
                pass
            else:
                raise InvestError(code=2009, msg='修改用户投资经历失败')
            lang = request.GET.get('lang')
            data = request.data
            industrytype = data.get('industrytype', None)
            Pindustrytype = data.get('Pindustrytype', None)
            with transaction.atomic():
                serializer = UserEventSerializer(instance, data=data)
                if serializer.is_valid():
                    newinstance = serializer.save()
                    useP = False
                    if industrytype:
                        for tag_id in TagContrastTable.objects.filter(cat_name=industrytype).values_list('tag_id'):
                            useP = True
                            if not userTags.objects.filter(user=instance.user, tag_id=tag_id[0], is_deleted=False).exists():
                                userTags(user=instance.user, tag_id=tag_id[0], createuser=request.user).save()
                    if not useP:
                        if Pindustrytype:
                            for tag_id in TagContrastTable.objects.filter(cat_name=Pindustrytype).values_list('tag_id'):
                                if not userTags.objects.filter(user=instance.user, tag_id=tag_id[0],
                                                               is_deleted=False).exists():
                                    userTags(user=instance.user, tag_id=tag_id[0], createuser=request.user).save()
                else:
                    raise InvestError(20071, msg='修改用户投资经历失败', detail='%s' % serializer.error_messages)
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(UserEventSerializer(newinstance).data, lang)))
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
            if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, instance.user.id):
                pass
            else:
                raise InvestError(code=2009, msg='删除用户投资经历失败')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(UserEventSerializer(instance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class UserRemarkFilter(FilterSet):
    id = RelationFilter(filterstr='id', lookup_method='in')
    user = RelationFilter(filterstr='user', lookup_method='in')
    createuser = RelationFilter(filterstr='createuser',lookup_method='in')

    class Meta:
        model = UserRemarks
        fields = ('id', 'user', 'createuser')

class UserRemarkView(viewsets.ModelViewSet):
    """
            list:用户备注列表
            create:新建用户备注
            retrieve:查看具体备注信息
            update:修改备注信息
            destroy:删除用户备注
            """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = UserRemarks.objects.all().filter(is_deleted=False)
    filter_class = UserRemarkFilter
    serializer_class = UserRemarkSerializer

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

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            user_id = request.GET.get('user', None)
            if request.user.has_perm('usersys.admin_manageuser'):
                pass
            elif user_id and request.user.has_perm('usersys.as_trader'):
                pass
            else:
                queryset = queryset.filter(createuser_id=request.user.id)
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
            serializer = UserRemarkSerializer(queryset, many=True)
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
            user_id = request.GET.get('user')
            if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, user_id):
                pass
            else:
                raise InvestError(code=2009, msg='新增用户备注失败')
            lang = request.GET.get('lang')
            if not data.get('createuser'):
                data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            with transaction.atomic():
                remarkserializer = UserRemarkCreateSerializer(data=data)
                if remarkserializer.is_valid():
                    remarkserializer.save()
                else:
                    raise InvestError(20071, msg='新增用户备注失败', detail='%s' %  remarkserializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(remarkserializer.data, lang)))
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
            if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, instance.user.id):
                pass
            elif instance.createuser == request.user:
                pass
            else:
                raise InvestError(code=2009, msg='查看该用户备注失败')
            serializer = UserRemarkSerializer(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
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
            if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, instance.user.id):
                pass
            elif instance.createuser == request.user:
                pass
            else:
                raise InvestError(code=2009, msg='修改用户备注失败')
            data = request.data
            data['lastmodifyuser'] = request.user.id
            with transaction.atomic():
                serializer = UserRemarkCreateSerializer(instance, data=data)
                if serializer.is_valid():
                    newremark = serializer.save()
                else:
                    raise InvestError(20071, msg='修改用户备注失败', detail='%s' % serializer.error_messages)
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(UserRemarkSerializer(newremark).data, lang)))
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
            if request.user.has_perm('usersys.admin_manageuser') or is_userTrader(request.user, instance.user.id):
                pass
            elif instance.createuser == request.user:
                pass
            else:
                raise InvestError(code=2009, msg='删除用户备注失败')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(
                    SuccessResponse(returnDictChangeToLanguage(UserRemarkSerializer(instance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class UserRelationFilter(FilterSet):
    investoruser = RelationFilter(filterstr='investoruser', lookup_method='in', relationName='investoruser__is_deleted')
    traderuser = RelationFilter(filterstr='traderuser',lookup_method='in', relationName='traderuser__is_deleted')
    relationtype = RelationFilter(filterstr='relationtype', lookup_method='in')
    familiar = RelationFilter(filterstr='familiar', lookup_method='in')
    tags = RelationFilter(filterstr='investoruser__tags', lookup_method='in')
    userstatus = RelationFilter(filterstr='investoruser__userstatus', lookup_method='in')
    currency = RelationFilter(filterstr='investoruser__org__currency', lookup_method='in')
    orgtransactionphases = RelationFilter(filterstr='investoruser__org__orgtransactionphase', lookup_method='in',
                                          relationName='investoruser__org__org_orgTransactionPhases__is_deleted')
    orgs = RelationFilter(filterstr='investoruser__org',lookup_method='in', relationName='investoruser__org__is_deleted')
    class Meta:
        model = UserRelation
        fields = ('investoruser', 'traderuser', 'relationtype','orgs','familiar', 'tags', 'userstatus', 'currency', 'orgtransactionphases')

class UserRelationView(viewsets.ModelViewSet):
    """
    list:获取用户业务关系联系人
    create:添加业务关系联系人
    retrieve:查看业务关系联系人详情
    update:修改业务关系联系人(批量)
    destroy:删除业务关系联系人(批量)
    """
    filter_backends = (filters.DjangoFilterBackend, MySearchFilter)
    filter_class = UserRelationFilter
    search_fields = ('investoruser__usernameC', 'investoruser__usernameE', 'traderuser__usernameC', 'traderuser__usernameE','investoruser__org__orgnameC')
    queryset = UserRelation.objects.filter(is_deleted=False)
    serializer_class = UserRelationSerializer

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

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            dataroom_id = request.GET.get('dataroom')
            if not page_size:
                page_size = 10
            else:
                page_size = 100 if int(page_size) > 100 else page_size
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if dataroom_id:
                dataroominstance = dataroom.objects.get(id=dataroom_id, is_deleted=False)
                if request.user.has_perm('usersys.admin_manageuserrelation') or request.user.has_perm('usersys.admin_manageindgroupinvestor') or is_dataroomTrader(request.user, dataroominstance):
                    queryset = queryset.filter(Q(traderuser__in=dataroominstance.proj.proj_traders.all().filter(is_deleted=False).values_list('user_id')) | Q(traderuser=dataroominstance.proj.PM)).distinct()
                else:
                    raise InvestError(2009, msg='查询失败', detail='没有权限查看该dataroom承揽承做对接投资人')
            else:
                if request.user.has_perm('usersys.admin_manageuserrelation') or request.user.has_perm('usersys.admin_manageindgroupinvestor'):
                    pass
                else:
                    queryset = queryset.filter(Q(traderuser=request.user) | Q(investoruser=request.user))
            countres = queryset.values_list('familiar').annotate(Count('familiar'))
            countlist = []
            for manager_count in countres:
                countlist.append({'familiar': manager_count[0], 'count': manager_count[1]})
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 0)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = UserRelationSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data,lang),'familiar_count':countlist}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            lang = request.GET.get('lang')
            try:
                traderuser = MyUser.objects.get(id=data.get('traderuser', None))
            except MyUser.DoesNotExist:
                raise InvestError(20071, msg='创建用户交易师关系失败', detail='交易师不存在')
            try:
                investoruser = MyUser.objects.get(id=data.get('investoruser', None))
            except MyUser.DoesNotExist:
                raise InvestError(20071, msg='创建用户交易师关系失败', detail='投资人不存在')
            if request.user.has_perm('usersys.admin_manageuserrelation') or request.user.has_perm('usersys.admin_manageindgroupinvestor'):
                pass
            else:
                if traderuser.id != request.user.id and investoruser.id != request.user.id:
                    projid = data.get('proj', None)
                    if projid:
                        if traderuser.user_projects.all().filter(proj_id=projid).exists():
                            pass
                        else:
                            raise InvestError(2009, msg='创建用户交易师关系失败')
                    else:
                        raise InvestError(2009, msg='创建用户交易师关系失败')
            with transaction.atomic():
                newrelation = UserRelationCreateSerializer(data=data)
                if newrelation.is_valid():
                    relation = newrelation.save()
                    sendmessage_traderadd(relation, relation.investoruser, ['app', 'sms', 'webmsg'], sender=request.user)
                else:
                    raise InvestError(20071, msg='创建用户交易师关系失败', detail='%s' % newrelation.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(UserRelationSerializer(relation).data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def get_object(self,pk=None):
        if pk:
            try:
                obj = UserRelation.objects.get(id=pk, is_deleted=False)
            except UserRelation.DoesNotExist:
                raise InvestError(code=2011, msg='用户交易师关系不存在', detail='用户交易师关系不存在')
        else:
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            assert lookup_url_kwarg in self.kwargs, (
                'Expected view %s to be called with a URL keyword argument '
                'named "%s". Fix your URL conf, or set the `.lookup_field` '
                'attribute on the view correctly.' %
                (self.__class__.__name__, lookup_url_kwarg)
            )
            try:
                obj = UserRelation.objects.get(id=self.kwargs[lookup_url_kwarg],is_deleted=False)
            except UserRelation.DoesNotExist:
                raise InvestError(code=2011, msg='用户交易师关系不存在', detail='用户交易师关系不存在')
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='查询用户交易师关系失败')
        return obj

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            userrelation = self.get_object()
            lang = request.GET.get('lang')
            if request.user.has_perm('usersys.admin_manageuserrelation') or request.user.has_perm('usersys.admin_manageindgroupinvestor'):
                pass
            elif request.user in [userrelation.traderuser, userrelation.investoruser]:
                pass
            else:
                raise InvestError(code=2009, msg='查询用户交易师关系失败')
            serializer = UserRelationSerializer(userrelation)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                lang = request.GET.get('lang')
                relationdatalist = request.data
                if not isinstance(relationdatalist,list) or not relationdatalist:
                    raise InvestError(20071, msg='修改用户交易师关系失败', detail='expect a non-empty array')
                newlist = []
                for relationdata in relationdatalist:
                    relation = self.get_object(relationdata['id'])
                    if request.user.has_perm('usersys.admin_manageuserrelation') or request.user.has_perm('usersys.admin_manageindgroupinvestor'):
                        pass
                    elif request.user == relation.traderuser:
                        relationdata.pop('relationtype', None)
                    else:
                        raise InvestError(code=2009, msg='修改用户交易师关系失败', detail='没有权限')
                    relationdata['lastmodifyuser'] = request.user.id
                    relationdata['lastmodifytime'] = datetime.datetime.now()
                    newrelationseria = UserRelationCreateSerializer(relation,data=relationdata)
                    if newrelationseria.is_valid():
                        newrelation = newrelationseria.save()
                    else:
                        raise InvestError(20071, msg='修改用户交易师关系失败', detail='%s' % newrelationseria.error_messages)
                    newlist.append(UserRelationSerializer(newrelation).data)
                return JSONResponse(SuccessResponse(returnListChangeToLanguage(newlist,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                relationidlist = request.data.get('relationlist',None)
                if not isinstance(relationidlist,list) or not relationidlist:
                    raise InvestError(20071, msg='删除用户交易师关系失败', detail='expect a not null relation id list')
                relationlist = self.get_queryset().filter(id__in=relationidlist)
                returnlist = []
                for userrelation in relationlist:
                    if request.user == userrelation.traderuser:
                        pass
                    elif request.user.has_perm('usersys.admin_manageuserrelation') or request.user.has_perm('usersys.admin_manageindgroupinvestor'):
                        pass
                    else:
                        raise InvestError(code=2009, msg='删除用户交易师关系失败', detail='没有权限')
                    userrelation.is_deleted = True
                    userrelation.deleteduser = request.user
                    userrelation.deletedtime = datetime.datetime.now()
                    userrelation.save()
                    returnlist.append(userrelation.id)
                return JSONResponse(SuccessResponse(returnlist))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def checkUserRelation(self, request, *args, **kwargs):
        try:
            trader = request.data.get('trader', None)
            investor = request.data.get('investor', None)
            if not trader or not investor:
                raise InvestError(20071, msg='查询用户交易师关系失败', detail='trader/investor 不能为空')
            qs = self.get_queryset().filter(Q(traderuser_id=trader,investoruser_id=investor,is_deleted=False) | Q(traderuser_id=investor,investoruser_id=trader,is_deleted=False))
            if qs.exists():
                res = True
            else:
                res = False
            return JSONResponse(SuccessResponse(res))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class UserPersonnelRelationsFilter(FilterSet):
    user = RelationFilter(filterstr='user', lookup_method='in')
    supervisorOrMentor = RelationFilter(filterstr='supervisorOrMentor', lookup_method='in')
    type = RelationFilter(filterstr='type', lookup_method='in')
    stime = RelationFilter(filterstr='supervisorStartDate', lookup_method='gte')
    etime = RelationFilter(filterstr='supervisorEndDate', lookup_method='lt')

    class Meta:
        model = UserPersonnelRelations
        fields = ('user', 'supervisorOrMentor', 'type', 'stime', 'etime')

class UserPersonnelRelationsView(viewsets.ModelViewSet):
    """
    list:获取用户人事关系记录
    create:添加用户人事关系记录
    update:修改用户人事关系记录
    destroy:删除用户人事关系记录
    """
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    filter_class = UserPersonnelRelationsFilter
    queryset = UserPersonnelRelations.objects.filter(is_deleted=False)
    serializer_class = UserPersonnelRelationsSerializer

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

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                queryset = queryset.filter(Q(user=request.user) | Q(supervisorOrMentor=request.user)| Q(user__directSupervisor=request.user)| Q(user__mentor=request.user)).distinct()
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

    def checkMentorAndDirectSupervisor(self, user):
        if UserPersonnelRelations.objects.filter(is_deleted=False, user=user, type=0).exists():
            personnelRelationsInstance = UserPersonnelRelations.objects.filter(is_deleted=False, user=user, type=0).order_by('-startDate').first()
            if user.directSupervisor != personnelRelationsInstance.supervisorOrMentor:
                user.directSupervisor = personnelRelationsInstance.supervisorOrMentor
                user.save()
        else:
            user.directSupervisor = None
            user.save()
        if UserPersonnelRelations.objects.filter(is_deleted=False, user=user, type=1).exists():
            personnelRelationsInstance = UserPersonnelRelations.objects.filter(is_deleted=False, user=user, type=1).order_by('-startDate').first()
            if user.mentor != personnelRelationsInstance.supervisorOrMentor:
                user.mentor = personnelRelationsInstance.supervisorOrMentor
                user.save()
        else:
            user.mentor = None
            user.save()


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                if data['supervisorOrMentor'] != request.user.id and data['user'] !=request.user.id:
                    raise InvestError(2009, msg='创建用户人事关系记录失败', detail='没有给其他人新建的权限')
            with transaction.atomic():
                instanceSerializer = UserPersonnelRelationsCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instance = instanceSerializer.save()
                else:
                    raise InvestError(2028, msg='创建用户人事关系记录失败', detail='新增失败--%s' % instanceSerializer.errors)
                self.checkMentorAndDirectSupervisor(user=instance.user)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(instanceSerializer.data, lang)))
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
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                if instance.supervisorOrMentor != request.user and instance.user !=request.user:
                    raise InvestError(2009, msg='修改用户人事关系记录失败', detail='没有给其他人修改的权限')
            with transaction.atomic():
                newinstanceSeria = UserPersonnelRelationsCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    instance = newinstanceSeria.save()
                else:
                    raise InvestError(2028, msg='修改用户人事关系记录失败', detail='修改失败——%s' % newinstanceSeria.errors)
                self.checkMentorAndDirectSupervisor(user=instance.user)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(newinstanceSeria.data, lang)))
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
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                if instance.supervisorOrMentor != request.user and instance.user !=request.user:
                    raise InvestError(2009, msg='删除用户人事关系记录失败', detail='没有给其他人删除的权限')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                self.checkMentorAndDirectSupervisor(user=instance.user)
                return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



class UserPerformanceAppraisalRecordFilter(FilterSet):
    user = RelationFilter(filterstr='user', lookup_method='in')
    level = RelationFilter(filterstr='level', lookup_method='in')
    stime = RelationFilter(filterstr='startDate', lookup_method='gte')
    etime = RelationFilter(filterstr='endDate', lookup_method='lt')
    class Meta:
        model = UserPerformanceAppraisalRecord
        fields = ('user', 'level', 'stime', 'etime')

class UserPerformanceAppraisalRecordView(viewsets.ModelViewSet):
    """
    list:获取用户绩效考核记录
    create:添加绩效考核记录
    update:修改绩效考核记录
    destroy:删除绩效考核记录
    """
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    filter_class = UserPerformanceAppraisalRecordFilter
    queryset = UserPerformanceAppraisalRecord.objects.filter(is_deleted=False)
    serializer_class = UserPerformanceAppraisalRecordSerializer

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

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                queryset = queryset.filter(Q(user=request.user)| Q(user__directSupervisor=request.user) | Q(user__mentor=request.user))
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
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                raise InvestError(2009, msg='没有权限给该用户新建绩效考核记录', detail='没有权限给员工新建记录')
            with transaction.atomic():
                instanceSerializer = UserPerformanceAppraisalRecordCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instanceSerializer.save()
                else:
                    raise InvestError(2027, msg='创建用户考核记录失败', detail='新增失败--%s' % instanceSerializer.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(instanceSerializer.data, lang)))
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
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                raise InvestError(2009, msg='没有权限编辑该用户绩效考核记录', detail='没有权限给员工编辑记录')
            with transaction.atomic():
                newinstanceSeria = UserPerformanceAppraisalRecordCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstanceSeria.save()
                else:
                    raise InvestError(2027, msg='修改用户考核记录失败', detail='修改失败——%s' % newinstanceSeria.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(newinstanceSeria.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                raise InvestError(2009, msg='没有权限给删除该用户绩效考核记录', detail='没有权限删除员工记录')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class UserWorkingPositionRecordsFilter(FilterSet):
    user = RelationFilter(filterstr='user', lookup_method='in')
    indGroup = RelationFilter(filterstr='indGroup', lookup_method='in')
    title = RelationFilter(filterstr='title', lookup_method='in')
    stime = RelationFilter(filterstr='startDate', lookup_method='gte')
    etime = RelationFilter(filterstr='endDate', lookup_method='lt')
    class Meta:
        model = UserWorkingPositionRecords
        fields = ('user', 'indGroup', 'title', 'stime', 'etime')

class UserWorkingPositionRecordsView(viewsets.ModelViewSet):
    """
    list:获取用户任职记录
    create:添加用户任职记录
    update:修改用户任职记录
    destroy:删除用户任职记录
    """
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    filter_class = UserWorkingPositionRecordsFilter
    search_fields = ('user__usernameC', 'user__usernameE')
    queryset = UserWorkingPositionRecords.objects.filter(is_deleted=False)
    serializer_class = UserWorkingPositionRecordsSerializer

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

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                queryset = queryset.filter(Q(user=request.user)| Q(user__directSupervisor=request.user) | Q(user__mentor=request.user))
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = mySortQuery(queryset, sortfield, desc, True)
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

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                raise InvestError(2009, msg='没有权限给该用户新建用户任职记录')
            with transaction.atomic():
                instanceSerializer = UserWorkingPositionRecordsCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instanceSerializer.save()
                else:
                    raise InvestError(2029, msg='创建用户任职记录失败', detail='新增失败--%s' % instanceSerializer.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(instanceSerializer.data, lang)))
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
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                raise InvestError(2009, msg='没有权限编辑该用户任职记录')
            with transaction.atomic():
                newinstanceSeria = UserWorkingPositionRecordsCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstanceSeria.save()
                else:
                    raise InvestError(2029, msg='修改用户任职记录失败', detail='修改失败——%s' % newinstanceSeria.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(newinstanceSeria.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                raise InvestError(2009, msg='没有权限删除该用户任职记录')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class UserTrainingRecordsFilter(FilterSet):
    user = RelationFilter(filterstr='user', lookup_method='in')
    trainingType = RelationFilter(filterstr='trainingType', lookup_method='in')
    trainingStatus = RelationFilter(filterstr='trainingType', lookup_method='in')
    stime = RelationFilter(filterstr='startDate', lookup_method='gte')
    etime = RelationFilter(filterstr='endDate', lookup_method='lt')
    class Meta:
        model = UserTrainingRecords
        fields = ('user', 'trainingType', 'trainingStatus', 'stime', 'etime')

class UserTrainingRecordsView(viewsets.ModelViewSet):
    """
    list:获取用户培训记录
    create:添加用户培训记录
    update:修改用户培训记录
    destroy:删除用户培训记录
    """
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    filter_class = UserTrainingRecordsFilter
    search_fields = ('user__usernameC', 'user__usernameE')
    queryset = UserTrainingRecords.objects.filter(is_deleted=False)
    serializer_class = UserTrainingRecordsSerializer

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

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                queryset = queryset.filter(Q(user=request.user)| Q(user__directSupervisor=request.user) | Q(user__mentor=request.user))
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = queryset.distinct()
            queryset = mySortQuery(queryset, sortfield, desc, True)
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
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            elif request.user.has_perm('usersys.as_trader'):
                if data['user'] != request.user.id or data['trainingType'] != 1:  # 普通交易师可以给自己创建线上培训记录
                    raise InvestError(2009, msg='没有权限新建用户培训记录')
            else:
                raise InvestError(2009, msg='没有权限给该用户新建用户培训记录')
            with transaction.atomic():
                instanceSerializer = UserTrainingRecordsCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instanceSerializer.save()
                else:
                    raise InvestError(2030, msg='创建用户培训记录失败', detail='新增失败--%s' % instanceSerializer.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(instanceSerializer.data, lang)))
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
            if request.user.has_perm('usersys.admin_managepersonnelrelation') or request.user == instance.createuser:
                pass
            else:
                raise InvestError(2009, msg='没有权限编辑该用户培训记录')
            with transaction.atomic():
                newinstanceSeria = UserTrainingRecordsCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstanceSeria.save()
                else:
                    raise InvestError(2030, msg='修改用户培训记录失败', detail='修改失败——%s' % newinstanceSeria.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(newinstanceSeria.data, lang)))
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
            if request.user.has_perm('usersys.admin_managepersonnelrelation') or request.user == instance.createuser:
                pass
            else:
                raise InvestError(2009, msg='没有权限删除给该用户培训记录')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class UserMentorTrackingRecordsFilter(FilterSet):
    user = RelationFilter(filterstr='user', lookup_method='in')
    communicateUser = RelationFilter(filterstr='communicateUser', lookup_method='in')
    stime = RelationFilter(filterstr='communicateDate', lookup_method='gte')
    etime = RelationFilter(filterstr='communicateDate', lookup_method='lt')
    class Meta:
        model = UserMentorTrackingRecords
        fields = ('user', 'communicateUser', 'stime', 'etime')

class UserMentorTrackingRecordsView(viewsets.ModelViewSet):
    """
    list:获取入职后导师计划跟踪记录
    create:添加入职后导师计划跟踪记录
    update:修改入职后导师计划跟踪记录
    destroy:删除入职后导师计划跟踪记录
    """
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)
    filter_class = UserMentorTrackingRecordsFilter
    search_fields = ('user__usernameC', 'user__usernameE', 'communicateUser__usernameC', 'communicateUser__usernameE', 'communicateType')
    queryset = UserMentorTrackingRecords.objects.filter(is_deleted=False)
    serializer_class = UserMentorTrackingRecordsSerializer

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

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                queryset = queryset.filter(Q(user=request.user)| Q(user__directSupervisor=request.user) | Q(user__mentor=request.user))
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = mySortQuery(queryset, sortfield, desc, True)
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
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            lang = request.GET.get('lang')
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                if request.user.id != data['user']:
                    raise InvestError(2009, msg='没有权限给该用户新建用户导师计划跟踪记录')
            with transaction.atomic():
                instanceSerializer = UserMentorTrackingRecordsCreateSerializer(data=data)
                if instanceSerializer.is_valid():
                    instanceSerializer.save()
                else:
                    raise InvestError(2031, msg='创建用户入职后导师计划跟踪记录失败', detail='新增失败--%s' % instanceSerializer.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(instanceSerializer.data, lang)))
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
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                if instance.user != request.user:
                    raise InvestError(2009, msg='没有权限编辑该用户培训记录')
            with transaction.atomic():
                newinstanceSeria = UserMentorTrackingRecordsCreateSerializer(instance, data=data)
                if newinstanceSeria.is_valid():
                    newinstanceSeria.save()
                else:
                    raise InvestError(2031, msg='修改入职后导师计划跟踪记录失败', detail='修改失败——%s' % newinstanceSeria.errors)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(newinstanceSeria.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('usersys.admin_managepersonnelrelation'):
                pass
            else:
                if instance.user != request.user:
                    raise InvestError(2009, msg='没有权限删除该用户培训记录')
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class GroupPermissionView(viewsets.ModelViewSet):
    """
    list:获取权限组列表
    create:新增权限组
    retrieve:查看权限组详情
    update:修改权限组信息
    delete:删除权限组
    """
    queryset = Group.objects.all().filter(is_deleted=False)
    serializer_class = GroupDetailSerializer

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

    #未登录用户不能访问
    def get_object(self):
        lookup_url_kwarg = 'pk'
        try:
            obj = self.get_queryset().get(id=self.kwargs[lookup_url_kwarg],is_deleted=False)
        except Group.DoesNotExist:
            raise InvestError(code=8892, msg='查询用户组失败', detail='用户组不存在')
        assert self.request.user.is_authenticated, (
            "user must be is_authenticated"
        )
        if obj.datasource != self.request.user.datasource:
            raise InvestError(code=8888, msg='查询用户组失败')
        return obj

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            queryset = self.get_queryset().filter(is_deleted=False)
            grouptype = request.GET.get('type', None)
            if grouptype in [u'trader','trader']:
                queryset = queryset.filter(permissions__codename__in=['as_trader'])
            if grouptype in [u'investor', 'investor']:
                queryset = queryset.filter(permissions__codename__in=['as_investor'])
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            if not request.user.is_superuser:
                serializerclass = GroupDetailSerializer
            else:
                serializerclass = GroupDetailSerializer
            serializer = serializerclass(queryset, many=True)
            return JSONResponse(
                SuccessResponse({'count': count, 'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            if not request.user.is_superuser:
                raise InvestError(2009, msg='新增用户组失败')
            data = request.data
            with transaction.atomic():
                data['datasource'] = request.user.datasource.id
                permissionsIdList = data.get('permissions',None)
                if not isinstance(permissionsIdList, list):
                    raise InvestError(20071, msg='新增用户组失败', detail='permissions must be a non-empty array')
                groupserializer = GroupCreateSerializer(data=data)
                if groupserializer.is_valid():
                    newgroup = groupserializer.save()
                    permissions = Permission.objects.filter(id__in=permissionsIdList)
                    newgroup.permissions = permissions
                else:
                    raise InvestError(20071, msg='新增用户组失败', detail='%s' % groupserializer.error_messages)
                return JSONResponse(SuccessResponse(groupserializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            if not request.user.is_superuser:
                raise InvestError(2009, msg='查询用户组失败')
            group = self.get_object()
            serializer = GroupDetailSerializer(group)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            if not request.user.is_superuser:
                raise InvestError(2009, msg='修改用户组失败')
            with transaction.atomic():
                group = self.get_object()
                data = request.data
                serializer = GroupCreateSerializer(group, data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    raise InvestError(20071, msg='修改用户组失败', detail='%s'%serializer.error_messages)
                return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            if not request.user.is_superuser:
                raise InvestError(2009, msg='删除用户组失败')
            with transaction.atomic():
                group = self.get_object()
                groupuserset = MyUser.objects.filter(is_deleted=False,groups__in=[group])
                if groupuserset.exists():
                    raise InvestError(2008, msg='删除用户组失败', detail='该组别下有用户存在，不能直接删除')
                else:
                    group.is_deleted = True
                    group.save()
                return JSONResponse(SuccessResponse(GroupSerializer(group).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class PermissionView(viewsets.ModelViewSet):
    """
    list:获取权限列表
    """
    queryset = Permission.objects.exclude(name__icontains='obj级别')
    serializer_class = PermissionSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            if not request.user.is_superuser:
                raise InvestError(2009, msg='获取权限列表失败')
            queryset = self.queryset
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


@api_view(['GET'])
@checkRequestToken()
def getSessionToken(request):
    """
    获取sessionToken
    """
    try:
        session_key = request.COOKIES.get('sid', None)
        if not session_key:
            session = SessionStore()
            session.create()
            session.update({'stoken': True})
            session.save()
        else:
            session = SessionStore(session_key)
            session['stoken'] = True
            session.save()
        res = JSONResponse(SuccessResponse({}))
        res.set_cookie('sid', session.session_key, httponly=True)
        return res
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

@api_view(['GET'])
@checkRequestToken()
def checkRequestSessionToken(request):
    """
    验证sessionToken
    """
    try:
        session_key = request.COOKIES.get('sid', None)
        session = SessionStore(session_key)
        session_data = session.load()
        if session_data.get('stoken', None):
            session.delete()
        else:
            raise InvestError(3008, msg='session验证失败')
        return JSONResponse(SuccessResponse({}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


@api_view(['POST'])
def login(request):
    """用户登录 """
    try:
        receive = request.data
        lang = request.GET.get('lang')
        clienttype = request.META.get('HTTP_CLIENTTYPE')
        username = receive['account']
        password = receive['password']
        union_id = receive.get('union_id', None)
        wxcode = receive.get('wxid', None)
        source = request.META.get('HTTP_SOURCE')
        if source:
            datasource = DataSource.objects.filter(id=source, is_deleted=False)
            if datasource.exists():
                userdatasource = datasource.first()
            else:
                raise InvestError(code=8888, msg='登录失败，未知source')
        else:
            raise InvestError(code=8888, msg='登录失败，未知source')
        if username and password:
            user = auth.authenticate(username=username, password=password, datasource=userdatasource)
            if not user or not clienttype:
                if not clienttype:
                    raise InvestError(code=2003, msg='登录失败，非法客户端', detail='登录类型不可用')
                else:
                    raise InvestError(code=2001, msg='登录失败，密码错误', detail='密码错误')
            if union_id:
                try:
                    thirdaccount = UserContrastThirdAccount.objects.get(thirdUnionID=union_id, is_deleted=False)
                except UserContrastThirdAccount.DoesNotExist:
                    UserContrastThirdAccount(thirdUnionID=union_id, user=user).save()
                else:
                    if thirdaccount.user.id != user.id:
                        raise InvestError(2048, msg='登录失败，该飞书账号已绑定过平台账号', detail='该飞书账号已绑定过平台账号')
            elif wxcode:
                openid = get_openid(wxcode)
                if openid:
                    try:
                        thirdaccount = UserContrastThirdAccount.objects.get(thirdUnionID=openid, is_deleted=False)
                    except UserContrastThirdAccount.DoesNotExist:
                        UserContrastThirdAccount(thirdUnionID=openid, user=user).save()
                    else:
                        if thirdaccount.user.id != user.id:
                            raise InvestError(2048, msg='登录失败，该微信号已绑定过其他账号')
                else:
                    raise InvestError(2048, msg='登录失败，获取小程序openid失败', detail='获取小程序openid失败')
        else:
            user = None
            if union_id:
                try:
                    thirdaccount = UserContrastThirdAccount.objects.get(thirdUnionID=union_id, is_deleted=False)
                except UserContrastThirdAccount.DoesNotExist:
                    raise InvestError(2009, msg='登录失败，用户未绑定账号', detail='用户未绑定账号')
                else:
                    user = thirdaccount.user
            elif wxcode:
                openid = get_openid(wxcode)
                if openid:
                    try:
                        thirdaccount = UserContrastThirdAccount.objects.get(thirdUnionID=openid, is_deleted=False)
                    except UserContrastThirdAccount.DoesNotExist:
                        raise InvestError(2009, msg='用户未绑定账号')
                    else:
                        user = thirdaccount.user
            if not user:
                raise InvestError(2009, msg='登录失败，快捷登录无效', detail='快捷登录无效')
        if user.userstatus_id == 3:
            raise InvestError(2022, msg='登录失败，用户审核未通过，如有疑问请咨询工作人员。', detail='用户审核未通过')
        user.last_login = datetime.datetime.now()
        if not user.is_active:
            user.is_active = True
        user.save()
        perimissions = user.get_all_permissions()
        menulist = getmenulist(user)
        response = maketoken(user, clienttype)
        response['permissions'] = perimissions
        response['menulist'] = menulist
        response['is_superuser'] = user.is_superuser
        if 'HTTP_X_FORWARDED_FOR' in request.META:
            ip = request.META['HTTP_X_FORWARDED_FOR']
        else:
            ip = request.META['REMOTE_ADDR']
        logininlog(loginaccount=username, logintypeid=clienttype, datasourceid=source,userid=user.id, ipaddress=ip)
        return JSONResponse(SuccessResponse(returnDictChangeToLanguage(response,lang)))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


@api_view(['POST'])
@checkRequestToken()
def bundThirdAccount(request):
    '''
     绑定 第三方账号
    '''
    try:
        data = request.data
        union_id = data.get('union_id', None)
        wxcode = data.get('wxid', None)
        if not union_id and not wxcode:
            raise InvestError(20071, msg='参数缺失', detail='id 不能为空')
        if wxcode:
            union_id = get_openid(wxcode)
            if not union_id:
                raise  InvestError(20071, msg='获取openid 失败')
        try:
            thirdaccount = UserContrastThirdAccount.objects.get(is_deleted=False, thirdUnionID=union_id)
        except UserContrastThirdAccount.DoesNotExist:
            UserContrastThirdAccount(thirdUnionID=union_id, user=request.user).save()
        else:
            thirdaccount.user = request.user
            thirdaccount.save()
        return JSONResponse(SuccessResponse({'success': True}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



def maketoken(user,clienttype):
    tokens = MyToken.objects.filter(user=user, clienttype_id=clienttype, is_deleted=False)
    if tokens.exists():
        tokens.update(is_deleted=True)
    token = MyToken.objects.create(user=user, clienttype_id=clienttype)
    serializer = UserSerializer(user)
    response = serializer.data
    return {'token': token.key,
        "user_info": response,
    }


def makeUserRelation(investor,trader):
    if investor and trader:
        if UserRelation.objects.filter(investoruser=investor,traderuser=trader,is_deleted=False).exists():
            return
        dic = {
            'investoruser':investor.id,
            'traderuser':trader.id,
            'relationtype':False,
            'datasource':investor.datasource_id
        }
        serializer = UserRelationCreateSerializer(data=dic)
        if serializer.is_valid():
            serializer.save()
        return


def makeUserRemark(user,remark,createuser):
    if user and remark and createuser:
        dic = {
            'user': user.id,
            'remark': remark,
            'datasource': createuser.datasource_id,
            'createuser' : createuser.id,
        }
        serializer = UserRemarkCreateSerializer(data=dic)
        if serializer.is_valid():
            serializer.save()
        return


class UserGetStarInvestorFilter(FilterSet):
    investor = RelationFilter(filterstr='investor', lookup_method='in')
    user = RelationFilter(filterstr='user',lookup_method='in')
    stime = RelationFilter(filterstr='getTime', lookup_method='gte')
    etime = RelationFilter(filterstr='getTime', lookup_method='lt')

    class Meta:
        model = UserGetStarInvestor
        fields = ('investor', 'user', 'stime', 'etime')

class UserGetStarInvestorView(viewsets.ModelViewSet):
    """
            list: 查看获取*用户列表
            create: 查看*用户
            getAvailableCount: 查看今日获取用户数
            """
    filter_backends = (filters.DjangoFilterBackend, MySearchFilter)
    queryset = UserGetStarInvestor.objects.all().filter(is_deleted=False)
    filter_class = UserGetStarInvestorFilter
    filter_fields = ('user',)
    serializer_class = UserGetStarInvestorSerializer

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

    @loginTokenIsAvailable(['usersys.admin_manageuser', 'usersys.as_trader'])
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset())
            if request.user.has_perm('usersys.admin_manageuser'):
                pass
            else:
                if IndustryGroup.objects.all().filter(is_deleted=False, manager=request.user.id).exists():
                    indGroups = IndustryGroup.objects.all().filter(is_deleted=False, manager=request.user.id)
                    queryset = queryset.filter(Q(user=request.user) | Q(user__indGroup__in=indGroups)).distinct()
                else:
                    queryset = queryset.filter(user=request.user)
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': [],}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count': count, 'data': returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            data = request.data
            data['user'] = request.user.id
            data['createuser'] = request.user.id
            data['datasource'] = request.user.datasource.id
            if self.get_queryset().filter(user_id=data['user'], investor_id=data['investor']).exists():
                instance = self.get_queryset().filter(user_id=data['user'], investor_id=data['investor']).first()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(UserGetStarInvestorCreateSerializer(instance).data, lang)))
            with transaction.atomic():
                serializer = UserGetStarInvestorCreateSerializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    raise InvestError(20071, msg='查询*用户信息失败', detail='%s' %  serializer.error_messages)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.admin_manageuser', 'usersys.as_trader'])
    def getAvailableCount(self, request, *args, **kwargs):
        try:
            user_id = request.GET.get('user', request.user.id)
            try:
                user = MyUser.objects.get(id=user_id, datasource=request.user.datasource, is_deleted=False)
            except MyUser.DoesNotExist:
                raise InvestError(code=2002, msg='查询用户不存在', detail='查询用户不存在')
            if user.indGroup:
                today = datetime.datetime.strptime(datetime.datetime.now().strftime("%Y-%m-%d"), "%Y-%m-%d")
                tomorrow = today + datetime.timedelta(days=1)
                if request.user.has_perm('usersys.admin_manageuser') or request.user.id == user.indGroup.manager:
                    getCount = self.get_queryset().filter(user=user, getTime__gte=today, getTime__lt=tomorrow).count()
                else:
                    getCount = self.get_queryset().filter(user=request.user, getTime__gte=today, getTime__lt=tomorrow).count()
                availableCount = user.indGroup.getUserCount - getCount
            else:
                raise InvestError(2052, msg='获取查看*用户统计失败，该交易师没有设置行业组', detail='该交易师没有行业组，无法统计剩余数量')
            return JSONResponse(SuccessResponse({"getCount": getCount, "availableCount": availableCount}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


def get_trader_by_name(name):
    if name and len(name) > 0:
        queryset = TraderNameIdContrast.objects.filter(is_deleted=False, name=name)
        if queryset.exists():
            return queryset.first().trader
        else:
            return None
    else:
        return None

def get_traders_by_names(names):
    traders = []
    if names and len(names) > 0:
        for name in names:
            trader = get_trader_by_name(name)
            if trader:
                traders.append(trader)
    return traders