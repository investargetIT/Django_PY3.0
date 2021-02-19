#coding=utf-8
from __future__ import unicode_literals

import datetime
from django.db import models
from proj.models import project
from usersys.models import MyUser, UserRelation
from sourcetype.models import TransactionStatus, DataSource
from utils.customClass import InvestError, MyForeignKey, MyModel
from utils.util import add_perm, rem_perm


class timeline(MyModel):
    id = models.AutoField(primary_key=True)
    proj = MyForeignKey(project,related_name='proj_timelines',blank=True, null=True)
    investor = MyForeignKey(MyUser,related_name='investor_timelines', blank=True, null=True)
    trader = MyForeignKey(MyUser,related_name='trader_timelines', blank=True, null=True)
    isClose = models.BooleanField(blank=True,default=False)
    closeDate = models.DateTimeField(blank=True,null=True,)
    contractedServiceTime = models.DateTimeField(blank=True,null=True)
    turnoverTime = models.DateTimeField(blank=True,null=True)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_timelines',on_delete=models.SET_NULL)
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_timelines',on_delete=models.SET_NULL)
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_timelines',on_delete=models.SET_NULL)
    datasource = MyForeignKey(DataSource, help_text='数据源')
    class Meta:
        db_table = 'timeline'
        permissions = (
            ('admin_getline','管理员查看时间轴'),
            ('admin_changeline', '管理员修改时间轴'),
            ('admin_deleteline', '管理员删除时间轴'),
            ('admin_addline', '管理员添加时间轴'),

            ('user_addline', '用户添加时间轴'),
            ('user_getline','用户查看时间轴(obj级别)'),
            ('user_changeline', '用户修改时间轴(obj级别)'),
            ('user_deleteline','用户删除时间轴(obj级别)'),
        )
    def get_timelinestatus(self):
        return self.timeline_transationStatus.all().filter(isActive=True,is_deleted=False)
    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.datasource:
            raise InvestError(20071,msg='datasource/proj/investor/trader cannot be null')
        if self.proj.projstatus_id < 4:
            raise InvestError(5003,msg='项目尚未终审发布')
        if self.trader.userstatus_id != 2:
            raise InvestError(2022)
        try:
            if self.pk:
                timeline.objects.exclude(pk=self.pk).get(is_deleted=False,datasource=self.datasource,proj=self.proj,investor=self.investor,trader=self.trader)
            else:
                timeline.objects.get(is_deleted=False,datasource=self.datasource,proj=self.proj,investor=self.investor,trader=self.trader)
        except timeline.DoesNotExist:
            pass
        else:
            raise InvestError(code=6003)
        super(timeline,self).save(force_insert, force_update, using, update_fields)


class timelineTransationStatu(MyModel):
    id = models.AutoField(primary_key=True)
    timeline = MyForeignKey(timeline,blank=True,null=True,related_name='timeline_transationStatus')
    transationStatus = MyForeignKey(TransactionStatus,default=1)
    isActive = models.BooleanField(blank=True,default=False)
    alertCycle = models.SmallIntegerField(blank=True,null=True,help_text='提醒周期')
    inDate = models.DateTimeField(blank=True,null=True,help_text='提醒到期时间')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_timelinestatus',on_delete=models.SET_NULL)
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_timelinestatus',on_delete=models.SET_NULL)
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_timelinestatus',on_delete=models.SET_NULL)

    class Meta:
        db_table = 'timelineTransationStatus'
    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.is_deleted and self.isActive:
            if self.alertCycle:
                self.inDate = datetime.datetime.now() + datetime.timedelta(hours=self.alertCycle * 24)
        super(timelineTransationStatu, self).save(force_insert, force_update, using, update_fields)

class timelineremark(MyModel):
    id = models.AutoField(primary_key=True)
    timeline = MyForeignKey(timeline,related_name='timeline_remarks',blank=True,null=True)
    remark = models.TextField(blank=True,null=True)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_timelineremarks',on_delete=models.SET_NULL)
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_timelineremarks',on_delete=models.SET_NULL)
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_timelineremarks', on_delete=models.SET_NULL)
    datasource = MyForeignKey(DataSource, help_text='数据源',default=1)

    class Meta:
        db_table = 'timelineremarks'
        permissions = (
            ('admin_addlineremark','管理员添加时间轴备注'),
            ('admin_getlineremark', '管理员查看时间轴备注'),
            ('admin_changelineremark', '管理员修改时间轴备注'),
            ('admin_deletelineremark', '管理员删除时间轴备注'),

            ('user_getlineremark', '用户查看时间轴备注（obj级别)'),
            ('user_changelineremark', '用户修改时间轴备注（obj级别)'),
            ('user_deletelineremark','用户删除时间轴备注（obj级别)'),
        )

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if self.pk:
            if self.is_deleted:
                rem_perm('timeline.user_getlineremark', self.createuser, self)
                rem_perm('timeline.user_changelineremark', self.createuser, self)
                rem_perm('timeline.user_deletelineremark', self.createuser, self)
        if not self.pk:
            if self.timeline.timeline_transationStatus.all().filter(is_deleted=False, isActive=True).exists():
                self.timeline.timeline_transationStatus.all().filter(is_deleted=False, isActive=True).first().save()
        super(timelineremark, self).save(force_insert, force_update, using, update_fields)