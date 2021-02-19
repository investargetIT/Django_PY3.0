#coding=utf-8
from __future__ import unicode_literals

from itertools import chain
from django.utils.encoding import force_text
from django.db.models import CASCADE
from guardian.backends import ObjectPermissionBackend, check_support
from guardian.shortcuts import remove_perm, assign_perm
from guardian.utils import get_group_obj_perms_model, get_user_obj_perms_model
from pypinyin import slug as hanzizhuanpinpin
import binascii
import os
from guardian.compat import get_user_model
from guardian.core import ObjectPermissionChecker, _get_pks_model_and_ctype
from guardian.ctypes import get_content_type
from guardian.exceptions import WrongAppError
import datetime
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin, Permission
from django.db import models
from django.db.models import Q

from APIlog.models import userinfoupdatelog
from sourcetype.models import AuditStatus, ClientType, TitleType, School, Specialty, Tag, DataSource, Country, OrgArea, \
    FamiliarLevel, IndustryGroup
from utils.customClass import InvestError, MyForeignKey, MyModel
from utils.somedef import makeAvatar


registersourcechoice = (
    (1,'ios'),
    (2,'android'),
    (3,'web'),
    (4,'wechat'),
    (5,'unknown'),
    (6,'wxbot'),
    (7,'excelImport'),
    (8,'traderAdd')
)

class MyUserBackend(ModelBackend):
    def authenticate(self, username=None, password=None, datasource=None):
        try:
            if '@' not in username:
                user = MyUser.objects.get(mobile=username,is_deleted=False,datasource=datasource)
            else:
                user = MyUser.objects.get(email=username,is_deleted=False,datasource=datasource)
        except MyUser.DoesNotExist:
            raise InvestError(code=2002)
        except Exception as err:
            raise InvestError(code=9999,msg='MyUserBackend/authenticate模块验证失败\n,%s'%err)
        else:
            if user.check_password(password):
                return user
        return None

    def get_user(self, user_id):
        try:
            user = MyUser._default_manager.get(pk=user_id)
        except MyUser.DoesNotExist:
            return None
        return user if not user.is_deleted else None

    def _get_permissions(self, user_obj, obj, from_name):
        """
        Returns the permissions of `user_obj` from `from_name`. `from_name` can
        be either "group" or "user" to return permissions from
        `_get_group_permissions` or `_get_user_permissions` respectively.
        """
        if user_obj.is_anonymous or obj is not None:
            return set()

        perm_cache_name = '_%s_perm_cache' % from_name
        if not hasattr(user_obj, perm_cache_name):
            if user_obj.is_superuser:
                perms = Permission.objects.all()
            else:
                perms = getattr(self, '_get_%s_permissions' % from_name)(user_obj)
            perms = perms.values_list('content_type__app_label', 'codename').order_by()
            setattr(user_obj, perm_cache_name, set("%s.%s" % (ct, name) for ct, name in perms))
        return getattr(user_obj, perm_cache_name)

    def get_all_permissions(self, user_obj, obj=None):
        if user_obj.is_anonymous or obj is not None:
            return set()
        if not hasattr(user_obj, '_perm_cache'):
            user_obj._perm_cache = self.get_user_permissions(user_obj)
            user_obj._perm_cache.update(self.get_group_permissions(user_obj))
        return user_obj._perm_cache

    def has_perm(self, user_obj, perm, obj=None):
        # if not user_obj.is_active:
        #     return False
        return perm in self.get_all_permissions(user_obj, obj)

    def has_module_perms(self, user_obj, app_label):
        """
        Returns True if user_obj has any permissions in the given app_label.
        """
        for perm in self.get_all_permissions(user_obj):
            if perm[:perm.index('.')] == app_label:
                return True
        return False

class MyObjectPermissionChecker(ObjectPermissionChecker):
    def has_perm(self, perm, obj):
        if self.user and self.user.is_superuser:
            return True
        perm = perm.split('.')[-1]
        return perm in self.get_perms(obj)
    def get_perms(self, obj):
        ctype = get_content_type(obj)
        key = self.get_local_cache_key(obj)
        if key not in self._obj_perms_cache:
            if self.user and self.user.is_superuser:
                perms = list(chain(*Permission.objects
                                   .filter(content_type=ctype)
                                   .values_list("codename")))
            elif self.user:
                # Query user and group permissions separately and then combine
                # the results to avoid a slow query
                user_perms = self.get_user_perms(obj)
                group_perms = self.get_group_perms(obj)
                perms = list(set(chain(user_perms, group_perms)))
            else:
                group_filters = self.get_group_filters(obj)
                perms = list(set(chain(*Permission.objects
                                       .filter(content_type=ctype)
                                       .filter(**group_filters)
                                       .values_list("codename"))))
            self._obj_perms_cache[key] = perms
        return self._obj_perms_cache[key]
    def prefetch_perms(self, objects):
        User = get_user_model()
        pks, model, ctype = _get_pks_model_and_ctype(objects)

        if self.user and self.user.is_superuser:
            perms = list(chain(
                *Permission.objects
                .filter(content_type=ctype)
                .values_list("codename")))

            for pk in pks:
                key = (ctype.id, force_text(pk))
                self._obj_perms_cache[key] = perms

            return True

        group_model = get_group_obj_perms_model(model)

        if self.user:
            fieldname = 'group__%s' % (
                User.groups.field.related_query_name(),
            )
            group_filters = {fieldname: self.user}
        else:
            group_filters = {'group': self.group}

        if group_model.objects.is_generic():
            group_filters.update({
                'content_type': ctype,
                'object_pk__in': pks,
            })
        else:
            group_filters.update({
                'content_object_id__in': pks
            })

        if self.user:
            model = get_user_obj_perms_model(model)
            user_filters = {
                'user': self.user,
            }

            if model.objects.is_generic():
                user_filters.update({
                    'content_type': ctype,
                    'object_pk__in': pks
                })
            else:
                user_filters.update({
                    'content_object_id__in': pks
                })

            # Query user and group permissions separately and then combine
            # the results to avoid a slow query
            user_perms_qs = model.objects.filter(**user_filters).select_related('permission')
            group_perms_qs = group_model.objects.filter(**group_filters).select_related('permission')
            perms = chain(user_perms_qs, group_perms_qs)
        else:
            perms = chain(
                *(group_model.objects.filter(**group_filters).select_related('permission'),)
            )

        # initialize entry in '_obj_perms_cache' for all prefetched objects
        for obj in objects:
            key = self.get_local_cache_key(obj)
            if key not in self._obj_perms_cache:
                self._obj_perms_cache[key] = []

        for perm in perms:
            if type(perm).objects.is_generic():
                key = (ctype.id, perm.object_pk)
            else:
                key = (ctype.id, force_text(perm.content_object_id))

            self._obj_perms_cache[key].append(perm.permission.codename)

        return True
class MyObjectPermissionBackend(ObjectPermissionBackend):
    def has_perm(self, user_obj, perm, obj=None):
        support, user_obj = check_support(user_obj, obj)
        if not support:
            return False

        if '.' in perm:
            app_label, perm = perm.split('.')
            if app_label != obj._meta.app_label:
                # Check the content_type app_label when permission
                # and obj app labels don't match.
                ctype = get_content_type(obj)
                if app_label != ctype.app_label:
                    raise WrongAppError("Passed perm has app label of '%s' while "
                                        "given obj has app label '%s' and given obj"
                                        "content_type has app label '%s'" %
                                        (app_label, obj._meta.app_label, ctype.app_label))

        check = MyObjectPermissionChecker(user_obj)
        return check.has_perm(perm, obj)

    def get_all_permissions(self, user_obj, obj=None):
        """
        Returns a set of permission strings that the given ``user_obj`` has for ``obj``
        """
        # check if user_obj and object are supported
        support, user_obj = check_support(user_obj, obj)
        if not support:
            return set()

        check = MyObjectPermissionChecker(user_obj)
        return check.get_perms(obj)


class MyUserManager(BaseUserManager):
    def create_user(self,email,mobile=None,password=None,**extra_fields):
        if not email:
            raise InvestError(code=20071)
        user = self.model(
            mobile=mobile,
            email=MyUserManager.normalize_email(email),
            is_superuser=False,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, mobile, password):
        user = self.create_user(email,
                                mobile,
                                password,
                                )
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

# 在settings里面指定这个User类为AUTH_USER_MODEL
class MyUser(AbstractBaseUser, PermissionsMixin,MyModel):
    """
    groups : 作为权限组
    """
    id = models.AutoField(primary_key=True)
    userlevel = models.PositiveSmallIntegerField(blank=True,default=0,help_text='用户服务级别')
    usercode = models.CharField(max_length=128,blank=True, unique=True)
    photoBucket = models.CharField(max_length=32, blank=True, null=True)
    photoKey = models.CharField(max_length=128,blank=True,null=True)
    cardBucket = models.CharField(max_length=32, blank=True, null=True)
    cardKey = models.CharField(max_length=128,blank=True,null=True)
    wechat = models.CharField(max_length=64,blank=True,null=True)
    country = MyForeignKey(Country,blank=True,null=True)
    department = models.CharField(max_length=64,blank=True,null=True,help_text='部门')
    orgarea = MyForeignKey(OrgArea,blank=True,null=True,help_text='机构地区')
    userstatus = MyForeignKey(AuditStatus,help_text='审核状态',blank=True,default=1)
    org = MyForeignKey('org.organization',help_text='所属机构',blank=True,null=True,related_name='org_users')
    usernameC = models.CharField(help_text='姓名',max_length=128,db_index=True,blank=True,null=True,)
    usernameE = models.CharField(help_text='name',max_length=128,db_index=True,blank=True,null=True)
    mobileAreaCode = models.CharField(max_length=10,blank=True,null=True,default='86')
    mobile = models.CharField(help_text='手机',max_length=32,db_index=True,blank=True,null=True)
    description = models.TextField(help_text='简介',blank=True, null=True, default='description')
    tags = models.ManyToManyField(Tag, through='userTags', through_fields=('user', 'tag'), blank=True,related_name='tag_users')
    email = models.EmailField(help_text='邮箱', max_length=128,db_index=True,blank=True,null=True)
    title = MyForeignKey(TitleType,blank=True,null=True,related_name='title_users')
    indGroup = MyForeignKey(IndustryGroup, null=True, blank=True, help_text='所属行业组')
    gender = models.BooleanField(blank=True, default=False, help_text=('False=男，True=女'))
    onjob = models.BooleanField(blank=True, default=True, help_text='是否在职')
    remark = models.TextField(help_text='用户个人备注',blank=True,null=True)
    school = MyForeignKey(School,help_text='院校',blank=True,null=True,related_name='school_users')
    specialty = MyForeignKey(Specialty,help_text='专业',blank=True,null=True,related_name='profession_users')
    targetdemand = models.TextField(help_text='标的需求',blank=True, null=True, default='标的需求')
    mergedynamic = models.TextField(help_text='并购动态', blank=True, null=True, default='并购动态')
    ishasfundorplan = models.TextField(help_text='是否有产业基金或成立计划', blank=True, null=True, default='是否有产业基金或成立计划')
    registersource = models.SmallIntegerField(help_text='注册来源',choices=registersourcechoice,default=1)
    lastmodifyuser = MyForeignKey('self',help_text='修改者',blank=True,null=True,related_name='usermodify_users')
    is_staff = models.BooleanField(help_text='登录admin', default=False, blank=True,)
    hasIM = models.BooleanField(help_text='是否已注册环信聊天账号', default=False, blank=True)
    page = models.SmallIntegerField(blank=True, default=10, null=True, help_text='分页条数')
    is_active = models.BooleanField(help_text='是否活跃', default=True, blank=True,)
    deleteduser = MyForeignKey('self',blank=True,null=True,related_name='userdelete_users')
    createuser = MyForeignKey('self',blank=True,null=True,related_name='usercreate_users')
    datasource = MyForeignKey(DataSource,help_text='数据源',blank=True,null=True)
    USERNAME_FIELD = 'usercode'
    REQUIRED_FIELDS = ['email']


    objects = MyUserManager()  # 在这里关联自定义的UserManager
    def get_full_name(self):
        return self.usernameC
    def get_short_name(self):
        return self.usernameC
    def __str__(self):
        return self.usernameC
    class Meta:
        db_table = "user"
        permissions = (
            ('as_investor', u'投资人身份类型'),
            ('as_trader', u'交易师身份类型'),
            ('as_admin', u'管理员身份类型'),

            ('user_adduser', u'用户新增用户'),
            ('user_deleteuser', u'用户删除用户(obj级别)'),
            ('user_changeuser', u'用户修改用户(obj级别)'),
            ('user_getuser', u'用户查看用户(obj级别)'),
            ('user_getuserbase', u'用户查看用户基本信息'),

            ('getProjReport', u'获取项目报表'),

            ('admin_adduser', u'管理员新增用户'),
            ('admin_deleteuser', u'管理员删除用户'),
            ('admin_changeuser', u'管理员修改用户基本信息'),
            ('admin_getuser', u'管理员查看用户'),

            ('user_addfavorite', '用户主动推荐favorite(obj级别——给交易师的)'),
            ('user_getfavorite', '用户查看favorite(obj级别——给交易师的)'),
            ('user_interestproj', '用户主动联系favorite(obj级别——给投资人的)'),

            ('admin_getmongoprojremark', u'管理员查看mongo项目备注'),
            ('admin_deletemongoprojremark', u'管理员删除mongo项目备注'),
            ('admin_manageWXChatData', u'管理员管理微信消息'),
        )
    def save(self, *args, **kwargs):
        if not self.usercode:
            self.usercode = str(datetime.datetime.now())
        if not self.datasource:
            raise InvestError(code=8888,msg='datasource有误')
        if self.pk and self.groups.exists() and self.groups.first().datasource != self.datasource:
            raise InvestError(code=8888,msg='group 与 user datasource不同')
        # if self.country:
        #     if self.country.datasource != self.datasource:
        #         raise InvestError(8888)
        try:
            if not self.mobileAreaCode:
                self.mobileAreaCode = '86'
            if self.mobile:
                self.mobile = self.mobile.replace(' ', '')
            if self.email:
                self.email = self.email.replace(' ', '')
            if not self.email or not self.mobile:
                raise InvestError(code=2007)
            if not self.mobile.isdigit():
                raise InvestError(2007, msg='mobile 必须是纯数字')
            if not self.mobileAreaCode.isdigit():
                raise InvestError(2007, msg='mobileAreaCode 必须是纯数字')
            if self.email:
                filters = Q(email=self.email)
                if self.mobile:
                    filters = Q(mobile=self.mobile) | Q(email=self.email)
            else:
                filters = Q(mobile=self.mobile)
            if self.pk:
                MyUser.objects.exclude(pk=self.pk).get(Q(is_deleted=False,datasource=self.datasource),filters)
            else:
                MyUser.objects.get(Q(is_deleted=False,datasource=self.datasource),filters)
        except MyUser.DoesNotExist:
            pass
        else:
            raise InvestError(code=2004)
        if not self.usernameC and self.usernameE:
            self.usernameC = self.usernameE
        if not self.usernameE and self.usernameC:
            self.usernameE = hanzizhuanpinpin(self.usernameC,separator='')
        if not self.createdtime:
            self.createdtime = datetime.datetime.now()
        if self.pk:
            olduser = MyUser.objects.get(pk=self.pk,datasource=self.datasource)
            if not self.is_deleted:
                if olduser.org and self.org and olduser.org != self.org:
                    remove_perm('org.user_getorg',self,olduser.org)
                    assign_perm('org.user_getorg',self,self.org)
                elif olduser.org and not self.org:
                    remove_perm('org.user_getorg', self, olduser.org)
                elif not olduser.org and self.org:
                    assign_perm('org.user_getorg', self, self.org)
                if not olduser.createuser and self.createuser:
                    assign_perm('usersys.user_deleteuser', self.createuser, self)
                if olduser.mobile != self.mobile and self.lastmodifyuser:
                    userinfoupdatelog(user_id=self.pk, user_name=self.usernameC.encode(encoding='utf-8'), type='mobile', before=olduser.mobile,
                                      after=self.mobile,
                                      requestuser_id=self.lastmodifyuser_id,
                                      requestuser_name=self.lastmodifyuser.usernameC.encode(encoding='utf-8'),
                                      datasource=self.datasource_id).save()
                if olduser.wechat != self.wechat and self.lastmodifyuser:
                    userinfoupdatelog(user_id=self.pk, user_name=self.usernameC.encode(encoding='utf-8'), type='wechat', before=olduser.wechat,
                                      after=self.wechat,
                                      requestuser_id=self.lastmodifyuser_id,
                                      requestuser_name=self.lastmodifyuser.usernameC.encode(encoding='utf-8'),
                                      datasource=self.datasource_id).save()
                if olduser.email != self.email and self.lastmodifyuser:
                    userinfoupdatelog(user_id=self.pk, user_name=self.usernameC.encode(encoding='utf-8'), type='email', before=olduser.email,
                                      after=self.email,
                                      requestuser_id=self.lastmodifyuser_id,
                                      requestuser_name=self.lastmodifyuser.usernameC.encode(encoding='utf-8'),
                                      datasource=self.datasource_id).save()
                if olduser.org != self.org and self.lastmodifyuser:
                    oldOrgName = olduser.org.orgfullname.encode(encoding='utf-8') if olduser.org else ''
                    newOrgName = self.org.orgfullname.encode(encoding='utf-8') if self.org else ''
                    userinfoupdatelog(user_id=self.pk, user_name=self.usernameC.encode(encoding='utf-8'), type='organization',
                                      before=oldOrgName, after=newOrgName, requestuser_id=self.lastmodifyuser_id,
                                      requestuser_name=self.lastmodifyuser.usernameC.encode(encoding='utf-8'),
                                      datasource=self.datasource_id).save()
            else:
                if olduser.org:
                    remove_perm('org.user_getorg', self, olduser.org)
                if olduser.createuser:
                    remove_perm('usersys.user_getuser', olduser.createuser, self)
                    remove_perm('usersys.user_changeuser', olduser.createuser, self)
                    remove_perm('usersys.user_deleteuser', olduser.createuser, self)

        if not self.photoKey:
            if self.usernameC:
                self.photoKey = makeAvatar(self.usernameC[0:1])
        self.exchangeUnreachuserToMyUser()
        super(MyUser,self).save(*args,**kwargs)

    def exchangeUnreachuserToMyUser(self):
        unreachuser_qs = UnreachUser.objects.filter(title=self.title, org=self.org, name=self.usernameC,
                                                    is_deleted=False, datasource=self.datasource)
        if unreachuser_qs.exists():
            unreachuser = unreachuser_qs.first()
            unreachuser.is_deleted = True
            unreachuser.deletedtime = datetime.datetime.now()
            unreachuser.save()

class UserRemarks(MyModel):
    id = models.AutoField(primary_key=True)
    user = MyForeignKey(MyUser, related_name='user_remarks', blank=True, null=True, on_delete=CASCADE)
    remark = models.TextField(blank=True, null=True)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_userremarks')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_userremarks')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_userremarks')
    datasource = MyForeignKey(DataSource, help_text='数据源', default=1)

    class Meta:
        db_table = 'user_remarks'
        permissions = (
            ('get_userremark', u'查看所有用户备注'),
            ('update_userremark', u'修改所有用户备注'),
            ('delete_userremark', u'删除所有用户备注'),
        )


class UnreachUser(MyModel):
    name = models.CharField(max_length=128,blank=True,null=True)
    title = MyForeignKey(TitleType,blank=True,null=True)
    org = MyForeignKey('org.organization',blank=True,null=True,related_name='org_unreachuser',on_delete=CASCADE)
    mobile = models.CharField(max_length=32,blank=True,null=True)
    email = models.CharField(max_length=32,blank=True,null=True)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_unreachUsers')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_unreachUsers')
    datasource = MyForeignKey(DataSource, blank=True,default=1)

    class Meta:
        db_table = "unreachuser"

    def save(self, *args, **kwargs):
        return super(UnreachUser, self).save(*args, **kwargs)


class userTags(MyModel):
    user = MyForeignKey(MyUser,related_name='user_usertags',null=True,blank=True,on_delete=CASCADE)
    tag = MyForeignKey(Tag, related_name='tag_usertags',null=True, blank=True)
    deleteduser = MyForeignKey(MyUser,blank=True, null=True,related_name='userdelete_usertags')
    createuser = MyForeignKey(MyUser,blank=True, null=True,related_name='usercreate_usertags')

    class Meta:
        db_table = "user_tags"

    def save(self, *args, **kwargs):
        if self.tag and self.user:
            if self.tag.datasource != self.user.datasource:
                raise InvestError(8888, msg='标签来源不符')
        return super(userTags, self).save(*args, **kwargs)


class userAttachments(MyModel):
    user = MyForeignKey(MyUser,related_name='user_userAttachments', blank=True, on_delete=CASCADE)
    bucket = models.CharField(max_length=64, blank=True, null=True)
    key = models.CharField(max_length=128, blank=True, null=True)
    filename = models.CharField(max_length=128, blank=True, null=True)
    deleteduser = MyForeignKey(MyUser,blank=True, null=True,related_name='userdelete_userAttachments')
    createuser = MyForeignKey(MyUser,blank=True, null=True,related_name='usercreate_userAttachments')

    class Meta:
        db_table = "user_attachments"

    def save(self, *args, **kwargs):
        return super(userAttachments, self).save(*args, **kwargs)

class userEvents(MyModel):
    user = MyForeignKey(MyUser,related_name='user_userEvents', blank=True, on_delete=CASCADE)
    com_id = models.BigIntegerField(blank=True, null=True, help_text='全库项目id')
    comshortname = models.CharField(max_length=64, blank=True, null=True)
    investDate = models.DateTimeField(blank=True, null=True)
    round = models.CharField(max_length=64, blank=True, null=True, help_text='轮次')
    deleteduser = MyForeignKey(MyUser,blank=True, null=True,related_name='userdelete_userEvents')
    createuser = MyForeignKey(MyUser,blank=True, null=True,related_name='usercreate_userEvents')

    class Meta:
        db_table = "user_events"

    def save(self, *args, **kwargs):
        if self.pk:
            if userEvents.objects.exclude(pk=self.pk).filter(is_deleted=False, user=self.user, com_id=self.com_id, investDate=self.investDate).exists():
                raise InvestError(2026, msg='已存在相同事件')
        else:
            if userEvents.objects.filter(is_deleted=False, user=self.user, com_id=self.com_id, investDate=self.investDate).exists():
                raise InvestError(2026, msg='已存在相同事件')
        return super(userEvents, self).save(*args, **kwargs)


class MyToken(models.Model):
    key = models.CharField('Key', max_length=48, primary_key=True)
    user = MyForeignKey(MyUser, related_name='user_token',verbose_name=("MyUser"),on_delete=CASCADE)
    created = models.DateTimeField(help_text="CreatedTime", auto_now_add=True,null=True)
    clienttype = MyForeignKey(ClientType,help_text='登录类型')
    is_deleted = models.BooleanField(help_text='是否已被删除',blank=True,default=False)
    class Meta:
        db_table = 'user_token'

    def timeout(self):
        if self.is_deleted:
            raise InvestError(3000, msg='token不存在')
        return self.created < (datetime.datetime.now() - datetime.timedelta(hours=24 * 1))

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(MyToken, self).save(*args, **kwargs)
    def generate_key(self):
        return binascii.hexlify(os.urandom(24)).decode()
    def __str__(self):
        return self.key

class UserRelation(MyModel):
    investoruser = MyForeignKey(MyUser, related_name='investor_relations', blank=True, help_text=('作为投资人'))
    traderuser = MyForeignKey(MyUser, related_name='trader_relations', blank=True, help_text=('作为交易师'))
    relationtype = models.BooleanField(help_text='强弱关系', default=False, blank=True)
    familiar = MyForeignKey(FamiliarLevel, help_text='交易师熟悉度等级', default=99, blank=True)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_relations')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_relations')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_relations',)
    datasource = MyForeignKey(DataSource, blank=True, default=1, help_text='数据源')
    def save(self, *args, **kwargs):
        if not self.datasource:
            raise InvestError(code=8888,msg='datasource有误')
        if self.datasource !=self.traderuser.datasource or self.datasource != self.investoruser.datasource:
            raise InvestError(code=8888,msg='requestuser.datasource不匹配')
        if self.traderuser.userstatus_id != 2:
            raise InvestError(code=2022,msg='交易师尚未审核通过，无法建立联系')
        if not self.is_deleted:
            if self.investoruser.has_perm('usersys.as_investor') and self.traderuser.has_perm('usersys.as_trader'):
                pass
            else:
                raise InvestError(2009, msg='身份类型不符合条件')
        if self.pk:
            userrelation = UserRelation.objects.exclude(pk=self.pk).filter(is_deleted=False,datasource=self.datasource,investoruser=self.investoruser)
        else:
            userrelation = UserRelation.objects.filter(is_deleted=False,datasource=self.datasource, investoruser=self.investoruser)
        if userrelation.exists():
            if not self.is_deleted:
                if userrelation.filter(traderuser_id=self.traderuser_id).exists():
                    raise InvestError(code=2012,msg='关系已存在')
                elif userrelation.filter(relationtype=True).exists() and self.relationtype:
                    self.relationtype = False
        if self.investoruser.id == self.traderuser.id:
            raise InvestError(code=2014,msg='投资人和交易师不能是同一个人')
        if self.pk:
            if self.is_deleted:
                remove_perm('usersys.user_getuser', self.traderuser, self.investoruser)
                remove_perm('usersys.user_changeuser', self.traderuser, self.investoruser)
                remove_perm('usersys.user_deleteuser', self.traderuser, self.investoruser)

                remove_perm('usersys.user_getuserrelation', self.traderuser, self)
                remove_perm('usersys.user_changeuserrelation', self.traderuser, self)
                remove_perm('usersys.user_deleteuserrelation', self.traderuser, self)

                remove_perm('usersys.user_addfavorite', self.traderuser, self.investoruser)
                remove_perm('usersys.user_getfavorite', self.traderuser, self.investoruser)
                remove_perm('usersys.user_interestproj', self.investoruser, self.traderuser)
            else:
                oldrela = UserRelation.objects.get(pk=self.pk)
                if oldrela.traderuser != self.traderuser or oldrela.investoruser != self.investoruser:
                    remove_perm('usersys.user_getuser', oldrela.traderuser, oldrela.investoruser)
                    remove_perm('usersys.user_changeuser', oldrela.traderuser, oldrela.investoruser)
                    remove_perm('usersys.user_deleteuser', oldrela.traderuser, oldrela.investoruser)

                    remove_perm('usersys.user_getuserrelation', oldrela.traderuser, self)
                    remove_perm('usersys.user_changeuserrelation', oldrela.traderuser, self)
                    remove_perm('usersys.user_deleteuserrelation', oldrela.traderuser, self)

                    remove_perm('usersys.user_addfavorite', self.traderuser, self.investoruser)
                    remove_perm('usersys.user_getfavorite', self.traderuser, self.investoruser)
                    remove_perm('usersys.user_interestproj', self.investoruser, self.traderuser)

                    assign_perm('usersys.user_getuser', self.traderuser, self.investoruser)
                    assign_perm('usersys.user_changeuser', self.traderuser, self.investoruser)
                    assign_perm('usersys.user_deleteuser', self.traderuser, self.investoruser)

                    assign_perm('usersys.user_getuserrelation', self.traderuser, self)
                    assign_perm('usersys.user_changeuserrelation', self.traderuser, self)
                    assign_perm('usersys.user_deleteuserrelation', self.traderuser, self)

                    assign_perm('usersys.user_addfavorite', self.traderuser, self.investoruser)
                    assign_perm('usersys.user_getfavorite', self.traderuser, self.investoruser)
                    assign_perm('usersys.user_interestproj', self.investoruser, self.traderuser)
        else:
            assign_perm('usersys.user_getuser', self.traderuser, self.investoruser)
            assign_perm('usersys.user_changeuser', self.traderuser, self.investoruser)
            assign_perm('usersys.user_deleteuser', self.traderuser, self.investoruser)

            assign_perm('usersys.user_addfavorite', self.traderuser, self.investoruser)
            assign_perm('usersys.user_getfavorite', self.traderuser, self.investoruser)
            assign_perm('usersys.user_interestproj', self.investoruser, self.traderuser)
        super(UserRelation, self).save(*args, **kwargs)
    class Meta:
        db_table = "user_relation"
        permissions =  (
            ('admin_adduserrelation', u'管理员建立用户联系'),
            ('admin_changeuserrelation', u'管理员修改用户联系'),
            ('admin_deleteuserrelation', u'管理员删除用户联系'),
            ('admin_getuserrelation', u'管理员查看用户联系'),


            ('user_changeuserrelation', u'用户改用户联系（obj级别）'),
            ('user_deleteuserrelation', u'用户删除用户联系（obj级别）'),
            ('user_getuserrelation', u'用户查看用户联系（obj级别）'),

        )

class UserContrastThirdAccount(MyModel):
    user = MyForeignKey(MyUser, blank=True, on_delete=CASCADE)
    wexinsmallapp = models.CharField(max_length=64, blank=True, null=True, unique=True, help_text='用户openid')

    class Meta:
        db_table = "user_contrastaccount"

class UserFriendship(MyModel):
    id = models.AutoField(primary_key=True)
    user = MyForeignKey(MyUser,related_name='user_friends',help_text='发起人',on_delete=CASCADE)
    friend = MyForeignKey(MyUser,related_name='friend_users',help_text='接收人',on_delete=CASCADE)
    isaccept = models.BooleanField(blank=True,default=False)
    accepttime = models.DateTimeField(blank=True,null=True)
    userallowgetfavoriteproj = models.BooleanField(blank=True,default=True,help_text='发起人允许好友查看自己的项目收藏')
    friendallowgetfavoriteproj = models.BooleanField(blank=True, default=True,help_text='接收人允许好友查看自己的项目收藏')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_userfriends',)
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_userfriends',)
    datasource = MyForeignKey(DataSource,blank=True,default=1, help_text='数据源')

    class Meta:
        db_table = "user_friendship"
        permissions =  (
            ('admin_addfriend', u'管理员建立用户好友关系'),
            ('admin_changefriend', u'管理员修改用户好友关系'),
            ('admin_deletefriend', u'管理员删除用户好友关系'),
            ('admin_getfriend', u'管理员查看用户好友关系'),

            ('user_addfriend', u'用户主动建立用户好友关系（未审核用户不要给）'),
        )

    def save(self, *args, **kwargs):
        if not self.datasource:
            raise InvestError(code=8888,msg='datasource有误')
        if self.datasource != self.user.datasource or self.datasource != self.friend.datasource:
            raise InvestError(code=8888,msg='user.datasource不匹配')
        if self.user == self.friend:
            raise InvestError(2016)
        if not self.accepttime and self.isaccept:
            self.accepttime = datetime.datetime.now()
        if not self.pk:
            if UserFriendship.objects.filter(Q(user=self.user,friend=self.friend,is_deleted=False) | Q(friend=self.user,user=self.friend,is_deleted=False)).exists():
                raise InvestError(2017)
        if self.pk:
            if self.isaccept is False:
                self.is_deleted = True
        if self.is_deleted is False:
            if self.isaccept and self.friendallowgetfavoriteproj:
                assign_perm('usersys.user_getfavorite', self.user, self.friend)
            else:
                remove_perm('usersys.user_getfavorite', self.user, self.friend)
            if self.isaccept and self.userallowgetfavoriteproj:
                assign_perm('usersys.user_getfavorite', self.friend, self.user)
            else:
                remove_perm('usersys.user_getfavorite', self.friend, self.user)
        super(UserFriendship,self).save(*args, **kwargs)
