#coding=utf8
from __future__ import unicode_literals

import datetime

import binascii
import os

from django.db import models

# Create your models here.
from django.db.models import Q

from org.models import organization
from proj.models import project
from sourcetype.models import BDStatus, OrgArea, Country, OrgBdResponse, DataSource, CurrencyType, IndustryGroup
from sourcetype.models import TitleType
from usersys.models import MyUser, UserRemarks
from utils.customClass import MyForeignKey, InvestError, MyModel
from utils.util import logexcption

bd_sourcetype = (
    (0,'全库搜索'),
    (1,'其他')
)


class ProjectBD(MyModel):
    country = MyForeignKey(Country, blank=True, null=True, help_text='项目国家')
    location = MyForeignKey(OrgArea, blank=True, null=True, help_text='项目地区')
    com_name = models.TextField(blank=True,null=True,help_text='公司名称/项目名称')
    usertitle = MyForeignKey(TitleType,blank=True,null=True,help_text='职位')
    username = models.CharField(max_length=64,blank=True,null=True,help_text='姓名')
    usermobile = models.CharField(max_length=64,blank=True,null=True,help_text='电话')
    useremail = models.CharField(max_length=64, blank=True, null=True, help_text='邮箱')
    bduser = MyForeignKey(MyUser, blank=True, null=True, help_text='bd对象id')
    source = models.TextField(blank=True,null=True,help_text='来源')
    source_type = models.IntegerField(blank=True,null=True,choices=bd_sourcetype)
    manager = MyForeignKey(MyUser,blank=True,null=True,help_text='负责人',related_name='user_projBDs')
    contractors = MyForeignKey(MyUser, blank=True, null=True, help_text='签约负责人/项目发起人', related_name='contractors_projBDs')
    financeAmount = models.BigIntegerField(blank=True, null=True, help_text='融资金额')
    isimportant = models.BooleanField(blank=True, default=False, help_text='是否重点BD')
    financeCurrency = MyForeignKey(CurrencyType, default=1, null=True, blank=True, help_text='融资金额货币类型')
    expirationtime = models.DateTimeField(blank=True, null=True, help_text='BD过期时间')
    indGroup = MyForeignKey(IndustryGroup, null=True, blank=True, help_text='所属行业组')
    bd_status = MyForeignKey(BDStatus,blank=True,null=True,help_text='bd状态')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_ProjectBD')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_ProjectBD')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_ProjectBD')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)

    class Meta:
        permissions = (
            ('manageProjectBD', '管理员管理项目BD'),
        )

    def save(self, *args, **kwargs):
        if self.manager is None:
            raise InvestError(20071,msg='manager can`t be null')
        self.datasource = self.createuser.datasource
        if not self.is_deleted:
            if ProjectBD.objects.exclude(pk=self.pk).filter(is_deleted=False, com_name=self.com_name).exists():
                raise InvestError(5006, msg='同名项目bd已存在')
        if self.bduser:
            self.username = self.bduser.usernameC
            self.usermobile = self.bduser.mobile
            self.usertitle = self.bduser.title
            self.useremail = self.bduser.email
        self.datasource = self.manager.datasource
        if not self.source:
            if self.source_type == 0:
                self.source = '全库搜索'
        if not self.pk and not self.manager.onjob:
            raise InvestError(2024)
        kwargs['automodifytime'] = False
        return super(ProjectBD, self).save(*args, **kwargs)


class ProjectBDManagers(MyModel):
    manager = MyForeignKey(MyUser, blank=True, default=False, help_text='负责人', related_name='managers_ProjectBD')
    projectBD = MyForeignKey(ProjectBD,blank=True, null=True, help_text='bd项目', related_name='ProjectBD_managers')
    type = models.PositiveSmallIntegerField(blank=True, default=0, help_text='线索提供2、主要人员3、参与或材料提供人员4')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_ProjectBDManagers')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_ProjectBDManagers')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)


    def save(self, *args, **kwargs):
        if self.projectBD is None:
            raise InvestError(20071,msg='projectBD can`t be null')
        if not self.is_deleted:
            if ProjectBDManagers.objects.exclude(pk=self.pk).filter(is_deleted=False, manager=self.manager, projectBD=self.projectBD).exists():
                raise InvestError(20071, msg='负责人已存在')
        self.datasource = self.projectBD.datasource
        if self.projectBD and not self.projectBD.is_deleted:
            self.projectBD.lastmodifytime = self.lastmodifytime if self.lastmodifytime else datetime.datetime.now()
            self.projectBD.save(update_fields=['lastmodifytime',])
        kwargs['automodifytime'] = False
        return super(ProjectBDManagers, self).save(*args, **kwargs)

class ProjectBDComments(MyModel):
    comments = models.TextField(blank=True, default=False, help_text='内容')
    event_date = models.DateTimeField(blank=True, null=True)
    key = models.CharField(max_length=128, blank=True, null=True, help_text='文件路径')
    bucket = models.CharField(max_length=128, blank=True, null=True, help_text='文件所在空间')
    filename =  models.CharField(max_length=128, blank=True, null=True, help_text='文件名')
    transid = models.TextField('third.AudioTranslateTaskRecord', blank=True, null=True, help_text='语音转写任务id')
    projectBD = MyForeignKey(ProjectBD, blank=True, null=True, help_text='bd项目', related_name='ProjectBD_comments')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_ProjectBDComments')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_ProjectBDComments')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)


    def save(self, *args, **kwargs):
        if self.projectBD is None:
            raise InvestError(20071,msg='projectBD can`t be null')
        self.datasource = self.projectBD.datasource
        if self.event_date is None:
            self.event_date = datetime.datetime.now()
        if self.projectBD and not self.projectBD.is_deleted:
            self.projectBD.lastmodifytime = self.lastmodifytime if self.lastmodifytime else datetime.datetime.now()
            self.projectBD.save(update_fields=['lastmodifytime',])
        kwargs['automodifytime'] = False
        return super(ProjectBDComments, self).save(*args, **kwargs)


class OrgBD(MyModel):
    org = MyForeignKey(organization,blank=True,null=True,help_text='BD机构',related_name='org_orgBDs')
    proj = MyForeignKey(project,blank=True,null=True,help_text='项目名称',related_name='proj_orgBDs')
    usertitle = MyForeignKey(TitleType,blank=True,null=True,help_text='职位')
    username = models.CharField(max_length=64,blank=True,null=True,help_text='姓名')
    usermobile = models.CharField(max_length=64,blank=True,null=True,help_text='电话')
    bduser = MyForeignKey(MyUser,blank=True,null=True,help_text='bd对象id')
    manager = MyForeignKey(MyUser,blank=True,null=True,help_text='负责人',related_name='user_orgBDs')
    isimportant = models.IntegerField(blank=True, default=0, help_text='是否重点BD')
    expirationtime = models.DateTimeField(blank=True,null=True,help_text='BD过期时间')
    response = MyForeignKey(OrgBdResponse, blank=True, null=True, related_name='OrgBD_response')
    material = models.CharField(max_length=64, blank=True, null=True, help_text='数位表示是否有材料')
    isSolved = models.BooleanField(blank=True, default=False, help_text='BD是否已处理')
    isRead = models.BooleanField(blank=True, default=False, help_text='是否已读')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_OrgBD')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_OrgBD')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_OrgBD')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)

    class Meta:
        permissions = (
            ('manageOrgBD', '管理机构BD'),

        )

    def save(self, *args, **kwargs):
        if self.manager is None:
            raise InvestError(20071,msg='manager can`t be null')
        if self.bduser:
            self.username = self.bduser.usernameC
            self.usermobile = self.bduser.mobile
            self.usertitle = self.bduser.title
        self.datasource = self.manager.datasource
        if not self.pk and not self.manager.onjob:
            raise InvestError(2024)
        if not self.is_deleted:
            if self.bduser:
                bds = OrgBD.objects.exclude(pk=self.pk).filter(is_deleted=False, proj=self.proj, datasource=self.datasource, bduser=self.bduser, manager=self.manager)
                if bds.exists():
                    raise InvestError(5006, msg='该用户已存在一条BD记录了')
            else:
                bds = OrgBD.objects.exclude(pk=self.pk).filter(is_deleted=False, proj=self.proj, datasource=self.datasource, bduser=self.bduser, manager=self.manager, org=self.org)
                if bds.exists():
                    raise InvestError(5006, msg='该机构已存在一条空BD记录了')
        if self.response:
            self.isSolved = True
        if self.is_deleted is False:
            if self.proj:
                if self.proj.projstatus.id < 4:
                    raise InvestError(5003,msg='项目尚未终审发布')
        kwargs['automodifytime'] = False
        return super(OrgBD, self).save(*args, **kwargs)

class OrgBDComments(MyModel):
    comments = models.TextField(blank=True, default=False, help_text='内容')
    event_date = models.DateTimeField(blank=True, null=True)
    isPMComment = models.BooleanField(blank=True, default=False, help_text='项目PM')
    orgBD = MyForeignKey(OrgBD,blank=True,null=True,help_text='机构BD',related_name='OrgBD_comments')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_OrgBDComments')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_OrgBDComments')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)

    def save(self, *args, **kwargs):
        if self.orgBD is None:
            raise InvestError(20071, msg='orgBD can`t be null')
        self.datasource = self.orgBD.datasource
        if self.event_date is None:
            self.event_date = datetime.datetime.now()
        if self.orgBD and not self.orgBD.is_deleted:
            self.orgBD.isSolved = True
            self.orgBD.lastmodifytime = self.lastmodifytime if self.lastmodifytime else datetime.datetime.now()
            self.orgBD.save(update_fields=['isSolved', 'lastmodifytime'])
        if not self.pk:
            try:
                if self.orgBD.bduser:
                    remark = '项目名称：%s \n\r备注信息：%s' % (self.orgBD.proj.projtitleC if self.orgBD.proj else '', self.comments if self.comments else '')
                    UserRemarks(user=self.orgBD.bduser, remark=remark, createuser=self.createuser, datasource=self.datasource).save()
            except Exception:
                logexcption(msg='同步备注到用户失败，OrgBD_id-%s ' % self.orgBD.id)
        kwargs['automodifytime'] = False
        return super(OrgBDComments, self).save(*args, **kwargs)


class OrgBDBlack(MyModel):
    proj = MyForeignKey(project, blank=True, null=True, help_text='黑名单针对的机构BD项目', related_name='proj_OrgBdBlacks')
    org = MyForeignKey(organization, blank=True, null=True, help_text='黑名单机构', related_name='org_OrgBdBlacks')
    reason = models.TextField(blank=True, null=True, help_text='加入黑名单原因')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_OrgBdBlacks')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_OrgBdBlacks')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)

    class Meta:
        permissions = (

        )

    def save(self, *args, **kwargs):
        if self.org is None or self.proj is None:
            raise InvestError(20072, msg='org/proj can`t be null')
        self.datasource = self.createuser.datasource
        if not self.reason:
            raise InvestError(20072, msg='加入原因 不能为空')
        if not self.is_deleted:
            if OrgBDBlack.objects.exclude(pk=self.pk).filter(is_deleted=False, org=self.org, proj=self.proj).exists():
                raise InvestError(20071, msg='该机构已经在黑名单中了')
        return super(OrgBDBlack, self).save(*args, **kwargs)



class WorkReport(MyModel):
    user = MyForeignKey(MyUser, blank=True, related_name='user_workreport', help_text='工作报表归属人')
    indGroup = MyForeignKey(IndustryGroup, blank=True, null=True, help_text='所属行业组')
    postType = models.CharField(max_length=32, blank=True, null=True, help_text='岗位类型')
    marketMsg = models.TextField(blank=True, null=True, help_text='市场信息和项目信息汇报')
    others = models.TextField(blank=True, null=True, help_text='其他事项/工作建议')
    startTime = models.DateTimeField(blank=True, null=True, help_text='报表统计起始时间')
    endTime = models.DateTimeField(blank=True, null=True, help_text='报表统计结束时间')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_workreport')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_workreport')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_workreport')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)

    class Meta:
        db_table = 'user_workreport'

    def save(self, *args, **kwargs):
        if not self.is_deleted:
            self.indGroup = self.user.indGroup
            if self.startTime >= self.endTime:
                raise InvestError(20071, msg='起始时间有误')
            QS = WorkReport.objects.exclude(pk=self.pk).filter(is_deleted=False, user=self.user, startTime__gte=self.startTime, endTime__lte=self.endTime)
            if QS.exists():
                raise InvestError(20071, msg='该时间段已存在一份周报了')
        if self.is_deleted:
            self.report_marketmsg.filter(is_deleted=False).update(is_deleted=True, deleteduser=self.deleteduser, deletedtime=datetime.datetime.now())
            self.report_projinfo.filter(is_deleted=False).update(is_deleted=True, deleteduser=self.deleteduser, deletedtime=datetime.datetime.now())
        return super(WorkReport, self).save(*args, **kwargs)


class WorkReportMarketMsg(MyModel):
    report = MyForeignKey(WorkReport, blank=True, null=True, related_name='report_marketmsg', help_text='工作报表归属人')
    marketMsg = models.TextField(blank=True, null=True, help_text='市场信息和项目信息汇报')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_workreportmarketmsg')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_workreportmarketmsg')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_workreportmarketmsg')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)

    class Meta:
        db_table = 'user_reportmarketmessage'


    def save(self, *args, **kwargs):
        if not self.is_deleted:
            if not self.report or not self.marketMsg:
                raise InvestError(20072, msg='参数不能为空')
        return super(WorkReportMarketMsg, self).save(*args, **kwargs)


class WorkReportProjInfo(MyModel):
    report = MyForeignKey(WorkReport, blank=True, null=True, related_name='report_projinfo', help_text='工作报表归属人')
    proj = MyForeignKey(project, blank=True, null=True, related_name='proj_reportinfo', help_text='平台项目')
    projTitle = models.TextField(blank=True, null=True, help_text='非平台项目')
    thisPlan = models.TextField(blank=True, null=True, help_text='本周计划')
    nextPlan = models.TextField(blank=True, null=True, help_text='下周计划')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_workreportproj')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_workreportproj')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_workreportproj')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)

    class Meta:
        db_table = 'user_reportprojinfo'
        permissions = (
            ('admin_getWorkReport', u'管理员查看用户工作报表'),

        )

    def save(self, *args, **kwargs):
        if not self.is_deleted:
            if not self.proj and not self.projTitle:
                raise InvestError(20072, msg='项目不能为空')
            if self.proj:
                self.projTitle = None
                filters = Q(proj=self.proj)
            else:
                self.proj = None
                filters = Q(projTitle=self.projTitle)
            if WorkReportProjInfo.objects.exclude(pk=self.pk).filter(Q(is_deleted=False, report=self.report), filters).exists():
                raise InvestError(20071, msg='该项目已经在报表中了')
        return super(WorkReportProjInfo, self).save(*args, **kwargs)



class OKR(MyModel):
    year = models.PositiveSmallIntegerField(blank=True, null=True, help_text='OKR目标年度')
    quarter = models.PositiveSmallIntegerField(blank=True, null=True, help_text='OKR目标季度')
    okrType = models.BooleanField(blank=True, default=False, help_text='0（季度）/1（年度）')
    target = models.TextField(blank=True, null=True, help_text='OKR目标')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_OKR')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_OKR')
    datasource = MyForeignKey(DataSource, blank=True, default=1, help_text='数据源')
    class Meta:
        db_table = 'OKR'

    def save(self, *args, **kwargs):
        if not self.is_deleted:
            if self.okrType:
                self.quarter = None
                filtertype = False
            else:
                filtertype = True
                if not self.quarter:
                    raise InvestError(20072, msg='季度日期不能为空')
                else:
                    if self.quarter > 4:
                        raise InvestError(20071, msg='季度日期不合法')
            if self.year and self.year > 2100:
                raise InvestError(20071, msg='年度日期不合法')
            if not self.target:
                raise InvestError(20072, msg='目标不能为空')
            if OKR.objects.exclude(pk=self.pk).filter(is_deleted=False, year=self.year, okrType=filtertype, createuser=self.createuser).exists():
                raise InvestError(20071, msg='该年度已存在季度/年度OKR')
        self.datasource = self.createuser.datasource
        return super(OKR, self).save(*args, **kwargs)


class OKRResult(MyModel):
    okr = MyForeignKey(OKR, blank=True, null=True, related_name='result_OKR')
    krs = models.TextField(blank=True, null=True, help_text='关键结果（KRs)')
    confidence = models.SmallIntegerField(blank=True, null=True, help_text='信心指数*100')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_OKRResult')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_OKRResult')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)
    class Meta:
        db_table = 'OKRResult'

    def save(self, *args, **kwargs):
        if not self.is_deleted:
            if not self.okr or self.okr.is_deleted:
                raise InvestError(20072, msg='okr字段 不能为空')
            if OKRResult.objects.exclude(pk=self.pk).filter(is_deleted=False, okr=self.okr, krs=self.krs).exists():
                raise InvestError(20071, msg='该OKR已存在相同的关键结果')
        self.datasource = self.createuser.datasource
        return super(OKRResult, self).save(*args, **kwargs)