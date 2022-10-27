#coding=utf-8
from __future__ import unicode_literals

import datetime
from django.contrib.contenttypes.models import ContentType
from django.db import models

# Create your models here.
from django.db.models import CASCADE, F

from proj.models import project
from sourcetype.models import DataSource, Country, OrgArea
from usersys.models import MyUser

#站内信
from utils.customClass import InvestError, MyForeignKey, MyModel
scheduleChoice = (
    (1,'路演会议'),
    (2,'约见公司'),
    (3,'约见投资人'),
    (4,'视频会议'),
)

class message(MyModel):
    content = models.TextField(verbose_name='站内信详细内容',blank=True,null=True)
    type = models.IntegerField(blank=True,default=1,help_text='消息类型')
    messagetitle = models.CharField(max_length=128,verbose_name='消息标题',blank=True,null=True)
    sender = MyForeignKey(MyUser,blank=True,null=True,related_name='usersend_msgs')
    receiver = MyForeignKey(MyUser,related_name='userreceive_msgs',blank=True,null=True,on_delete=CASCADE)
    isRead = models.BooleanField(verbose_name='是否已读',default=False,blank=True)
    sourcetype = models.CharField(max_length=32,blank=True,null=True,help_text='资源类型')
    sourceid = models.IntegerField(blank=True,null=True,help_text='关联资源id')
    readtime = models.DateTimeField(blank=True,null=True)
    datasource = MyForeignKey(DataSource, help_text='数据源',blank=True,default=1)
    def save(self, *args, **kwargs):
        if not self.receiver:
            raise InvestError(code=2018)
        self.datasource = self.receiver.datasource
        return super(message, self).save(*args, **kwargs)
    def __str__(self):
        return self.messagetitle
    class Meta:
        db_table = 'msg'

class webexMeeting(MyModel):
    startDate = models.DateTimeField(blank=True, null=True, help_text='会议预定时间',)
    duration = models.PositiveIntegerField(blank=True, default=60, help_text='会议持续时间（单位：分钟）')
    endDate = models.DateTimeField(blank=True, null=True, help_text='会议结束时间')
    title = models.CharField(max_length=128, blank=True, null=True, help_text='会议标题')
    agenda = models.TextField(blank=True, null=True, help_text='会议议程')
    password = models.CharField(max_length=32, blank=True, null=True, help_text='会议密码')
    meetingKey = models.CharField(max_length=32, blank=True, null=True)
    url_host = models.CharField(max_length=200, blank=True, null=True)
    url_attendee = models.CharField(max_length=200, blank=True, null=True)
    guestToken = models.CharField(max_length=64, blank=True, null=True)
    hostKey = models.CharField(max_length=16, blank=True, null=True)
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_webexMeeting')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_webexMeeting')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)
    class Meta:
        db_table = 'webexMeeting'
        ordering = ['startDate']
        permissions = (
            ('manageMeeting', '管理视频会议'),
            ('getMeeting', '查看视频会议'),
            ('createMeeting', '创建视频会议'),
        )

    def save(self, *args, **kwargs):
        self.endDate = self.startDate + datetime.timedelta(minutes=self.duration)
        if not self.is_deleted:
            if self.createuser is None:
                raise InvestError(20071, msg='createuser can`t be null')
            if self.pk:
                QS = webexMeeting.objects.exclude(pk=self.pk).filter(is_deleted=False)
            else:
                QS = webexMeeting.objects.filter(is_deleted=False)
            laterMeetingQS = QS.filter(startDate__gte=self.startDate)
            earlierMeetingQS = QS.filter(startDate__lte=self.startDate)
            if laterMeetingQS.exists():
                laterMeeting = laterMeetingQS.order_by('startDate').first()
                if self.endDate > laterMeeting.startDate:
                    raise InvestError(8006, msg='视频会议时间冲突，已存在开始时间处于本次创建会议持续期间的会议')
            if earlierMeetingQS.exists():
                earlierMeeting = earlierMeetingQS.order_by('startDate').last()
                if earlierMeeting.endDate > self.startDate:
                    raise InvestError(8006, msg='视频会议时间冲突，已存在结束时间处于本次创建会议持续期间的会议')
        self.datasource = self.createuser.datasource
        return super(webexMeeting, self).save(*args, **kwargs)


class schedule(MyModel):
    type = models.SmallIntegerField(blank=True, default=3, help_text='日程类别',choices=scheduleChoice)
    user = MyForeignKey(MyUser,blank=True,null=True,help_text='日程对象',related_name='user_beschedule',on_delete=CASCADE)
    manager = MyForeignKey(MyUser, blank=True, null=True, help_text='日程归属人', related_name='manager_beschedule')
    scheduledtime = models.DateTimeField(blank=True,null=True,help_text='日程预定时间',)
    comments = models.TextField(blank=True, null=True, help_text='内容')
    address = models.TextField(blank=True, null=True, help_text='具体地址')
    country = MyForeignKey(Country,blank=True,null=True,help_text='国家')
    location = MyForeignKey(OrgArea, blank=True, null=True, help_text='地区')
    meeting = MyForeignKey(webexMeeting, blank=True, null=True, related_name='meeting_schedule', help_text='视频会议')
    proj = MyForeignKey(project,blank=True,null=True,help_text='日程项目',related_name='proj_schedule')
    projtitle = models.CharField(max_length=128,blank=True,null=True)
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_schedule')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_schedule')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)
    class Meta:
        db_table = 'schedule'
        permissions = (
            ('admin_manageSchedule', '管理员管理日程'),
        )

    def save(self, *args, **kwargs):
        if not self.is_deleted:
            if self.createuser is None:
                raise InvestError(20071,msg='createuser can`t be null')
            if self.proj:
                self.projtitle = self.proj.projtitleC
        if not self.is_deleted and self.meeting and self.manager:
            if schedule.objects.exclude(pk=self.pk).filter(is_deleted=False, manager=self.manager, meeting=self.meeting).exists():
                return
        self.datasource = self.createuser.datasource
        return super(schedule, self).save(*args, **kwargs)


class webexUser(MyModel):
    meeting = MyForeignKey(webexMeeting, blank=True, null=True, related_name='meeting_webexUser', help_text='视频会议')
    url_address = models.TextField(blank=True, null=True, help_text='参会链接')
    meetingKey = models.CharField(max_length=32, blank=True, null=True)
    user = MyForeignKey(MyUser, blank=True, null=True, related_name='user_webexUser', help_text='参会人员')
    email = models.EmailField(max_length=128, blank=True, null=True, help_text='参会人员邮箱')
    name = models.CharField(max_length=128, blank=True, null=True, help_text='参会人员姓名')
    meetingRole = models.BooleanField(blank=True, default=False, help_text='参会人员角色(主持人/参会人)')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_webexUser')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_webexUser')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)
    class Meta:
        db_table = 'webexUser'

    def save(self, *args, **kwargs):
        if self.user:
            self.name = self.user.usernameC
            self.email = self.user.email
        self.datasource = self.createuser.datasource
        if self.meetingRole and not self.is_deleted and webexUser.objects.exclude(pk=self.pk).filter(is_deleted=False, meeting=self.meeting, meetingRole=True).exists():
            raise InvestError(20071, msg='只能有一个主持人')
        return super(webexUser, self).save(*args, **kwargs)
