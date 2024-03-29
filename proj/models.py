#coding=utf8
from __future__ import unicode_literals

import datetime

import binascii
import os

from django.db import models

# Create your models here.

from sourcetype.models import ProjectStatus, CurrencyType, Tag, Country, TransactionType, Industry, \
    DataSource, CharacterType, Service, IndustryGroup, DidiOrderType, OrgBdResponse
from usersys.models import MyUser

from utils.customClass import InvestError, MyForeignKey, MyModel
from utils.util import rem_perm



class project(MyModel):
    id = models.AutoField(primary_key=True)
    indGroup = MyForeignKey(IndustryGroup, null=True, blank=True, help_text='项目所属行业组')
    lastProject = MyForeignKey('self', blank=True, null=True, related_name='relate_projects')
    projectBD = MyForeignKey('BD.ProjectBD', blank=True, null=True, related_name='relate_projectBD')
    projtitleC = models.CharField(max_length=128,db_index=True,default='标题')
    projtitleE = models.CharField(max_length=256,blank=True,null=True,db_index=True)
    projstatus = MyForeignKey(ProjectStatus,help_text='项目状态',default=2)
    response = MyForeignKey(OrgBdResponse, blank=True, null=True, related_name='proj_response')
    realname = models.CharField(max_length=128,default='名称',blank=True,null=True)
    c_descriptionC = models.TextField(blank=True, null=True, default='公司介绍')
    c_descriptionE = models.TextField(blank=True, null=True, default='company description')
    p_introducteC = models.TextField(blank=True, null=True, default='项目介绍')
    p_introducteE = models.TextField(blank=True, null=True, default='project introduction')
    isoverseasproject = models.BooleanField(blank=True,default=True,help_text='是否是海外项目')
    supportUser = MyForeignKey(MyUser,blank=True,null=True,related_name='usersupport_projs',help_text='项目方(上传方)')
    PM = MyForeignKey(MyUser, blank=True, null=True, related_name='userPM_projs', help_text='项目PM')
    feishuurl = models.CharField(max_length=200, blank=True, null=True)
    isHidden = models.BooleanField(blank=True,default=False)
    financeAmount = models.BigIntegerField(blank=True,null=True)
    financeAmount_USD = models.BigIntegerField(blank=True,null=True)
    companyValuation = models.BigIntegerField(help_text='公司估值', blank=True, null=True)
    companyValuation_USD = models.BigIntegerField(help_text='公司估值', blank=True, null=True)
    companyYear = models.SmallIntegerField(help_text='公司年限', blank=True, null=True)
    financeIsPublic = models.BooleanField(blank=True, default=True)
    code = models.CharField(max_length=128, blank=True, null=True)
    currency = MyForeignKey(CurrencyType,default=1,on_delete=models.SET_NULL,null=True,blank=True)
    tags = models.ManyToManyField(Tag, through='projectTags', through_fields=('proj', 'tag'),blank=True)
    industries = models.ManyToManyField(Industry, through='projectIndustries', through_fields=('proj', 'industry'),blank=True)
    transactionType = models.ManyToManyField(TransactionType, through='projectTransactionType',through_fields=('proj', 'transactionType'),blank=True)
    service = models.ManyToManyField(Service, through='projServices',through_fields=('proj', 'service'), blank=True)
    contactPerson = models.CharField(help_text='联系人',max_length=64,blank=True,null=True)
    phoneNumber = models.CharField(max_length=32,blank=True,null=True)
    email = models.EmailField(help_text='联系人邮箱', max_length=48, db_index=True,blank=True,null=True)
    country = MyForeignKey(Country,blank=True,null=True,db_index=True)
    targetMarketC = models.TextField(help_text='目标市场', blank=True, null=True)
    targetMarketE = models.TextField(blank=True, null=True)
    character = MyForeignKey(CharacterType,blank=True,null=True,help_text='我的角色')
    productTechnologyC = models.TextField(help_text='核心技术', blank=True, null=True)
    productTechnologyE = models.TextField(blank=True, null=True)
    businessModelC = models.TextField(help_text='商业模式', blank=True, null=True)
    businessModelE = models.TextField(blank=True, null=True)
    brandChannelC = models.TextField(help_text='品牌渠道', blank=True, null=True)
    brandChannelE = models.TextField(null=True, blank=True)
    managementTeamC = models.TextField(help_text='管理团队', blank=True, null=True)
    managementTeamE = models.TextField(blank=True, null=True)
    BusinesspartnersC = models.TextField(help_text='商业伙伴', null=True, blank=True)
    BusinesspartnersE = models.TextField(null=True, blank=True)
    useOfProceedC = models.TextField(help_text='资金用途', blank=True, null=True)
    useOfProceedE = models.TextField(blank=True, null=True)
    financingHistoryC = models.TextField(help_text='融资历史', blank=True, null=True)
    financingHistoryE = models.TextField(blank=True, null=True)
    operationalDataC = models.TextField(help_text='经营数据', blank=True, null=True)
    operationalDataE = models.TextField(blank=True, null=True)
    publishDate = models.DateTimeField(blank=True, null=True,help_text='终审发布日期')
    isSendEmail = models.BooleanField(blank=True,default=False,help_text='是否发送邮件')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_projects')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_projects')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_projects')
    datasource = MyForeignKey(DataSource, help_text='数据源')


    def __str__(self):
        return self.projtitleC
    class Meta:
        db_table = 'project'
        permissions = (
            ('admin_manageproj','管理项目'),
            ('get_secretinfo','查看项目保密信息')
        )
    def save(self, *args, **kwargs):
        if not self.datasource or not self.createuser or self.datasource != self.createuser.datasource:
            raise InvestError(code=8888,msg='项目datasource不合法')
        if self.lastProject and (self.lastProject == self.pk or self.lastProject.is_deleted):
            raise InvestError(20071, msg='关联项目不能为自身或者已删除项目')
        if self.pk:
            if self.is_deleted:
                rem_perm('proj.user_getproj',self.createuser,self)
                rem_perm('proj.user_changeproj', self.createuser, self)
                rem_perm('proj.user_deleteproj', self.createuser, self)
        if self.projstatus_id >= 4 and self.is_deleted == False:
            self.checkProjInfo()
        if self.supportUser is None:
            self.supportUser = self.createuser
        if self.code is None:
            self.code = 'P' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        if not self.is_deleted and self.isHidden and self.isSendEmail:
            raise InvestError(20071, msg='该项目为隐藏项目， 无法发送群发邮件')
        super(project,self).save(*args, **kwargs)

    def checkProjInfo(self):
        fieldlist = ['contactPerson', 'financeAmount', 'financeAmount_USD', 'email', 'phoneNumber']
        for aa in fieldlist:
            if getattr(self, aa) is None:
                raise InvestError(4007,msg='项目信息未完善—%s'%aa)

class projTraders(MyModel):
    proj = MyForeignKey(project, blank=True, null=True, related_name='proj_traders')
    user = MyForeignKey(MyUser, blank=True, null=True, related_name='user_projects')
    type = models.PositiveSmallIntegerField(blank=True, null=True, help_text='承揽0、承做1、承做-PM2、承做-参与人员3、承销-主要人员4、承销-参与人员5')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_projTraders')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_projTraders')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)

    class Meta:
        db_table = "project_traders"

    def save(self, *args, **kwargs):
        self.datasource = self.user.datasource
        if self.user.datasource != self.proj.datasource:
            raise InvestError(code=8888,msg='项目用户datasource不合法')
        if not self.is_deleted:
            traders = projTraders.objects.exclude(pk=self.pk).filter(is_deleted=False, proj=self.proj, user=self.user, type=self.type)
            if traders.exists():
                raise InvestError(20071, msg='该交易师已存在一条相同记录了')
        super(projTraders, self).save(*args, **kwargs)

class projServices(MyModel):
    id = models.AutoField(primary_key=True)
    proj = MyForeignKey(project,blank=True,null=True,related_name='proj_services')
    service = MyForeignKey(Service, related_name='service_projects')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_projservices')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_projservices')

    class Meta:
        db_table = "project_services"

class finance(MyModel):
    id = models.AutoField(primary_key=True)
    proj = MyForeignKey(project, blank=True, null=True, related_name='proj_finances')
    revenue = models.BigIntegerField(blank=True, null=True, )
    netIncome = models.BigIntegerField(blank=True, null=True, )
    revenue_USD = models.BigIntegerField(blank=True, null=True, )
    netIncome_USD = models.BigIntegerField(blank=True, null=True, )
    EBITDA = models.BigIntegerField(blank=True, null=True, )
    grossProfit = models.BigIntegerField(blank=True, null=True, )
    totalAsset = models.BigIntegerField(blank=True, null=True, )
    stockholdersEquity = models.BigIntegerField(blank=True, null=True, )
    operationalCashFlow = models.BigIntegerField(blank=True, null=True, )
    grossMerchandiseValue = models.BigIntegerField(blank=True, null=True, )
    fYear = models.SmallIntegerField(blank=True, null=True, )
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, on_delete=models.SET_NULL,related_name='userdelete_finances')
    createuser = MyForeignKey(MyUser, blank=True, null=True, on_delete=models.SET_NULL, related_name='usercreate_finances')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, on_delete=models.SET_NULL,related_name='usermodify_finances')
    datasource = MyForeignKey(DataSource, help_text='数据源',blank=True,default=1)

    class Meta:
        db_table = 'projectFinance'
    def save(self, *args, **kwargs):
        if not self.datasource or self.datasource != self.proj.datasource:
            raise InvestError(code=8888,msg='项目财务信息datasource不合法')
        super(finance,self).save(*args, **kwargs)

class attachment(MyModel):
    proj = MyForeignKey(project,related_name='proj_attachment',blank=True,null=True)
    filename = models.CharField(max_length=128,blank=True,null=True)
    filetype = models.CharField(max_length=32,blank=True,null=True)
    bucket = models.CharField(max_length=32,blank=True,null=True)
    key = models.CharField(max_length=128,blank=True,null=True)
    realfilekey = models.CharField(max_length=128, blank=True, null=True)
    transid = models.TextField('third.AudioTranslateTaskRecord', blank=True, null=True, help_text='语音转写任务id')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, on_delete=models.SET_NULL,related_name='userdelete_projattachments')
    createuser = MyForeignKey(MyUser, blank=True, null=True, on_delete=models.SET_NULL, related_name='usercreate_projattachments')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, on_delete=models.SET_NULL,related_name='usermodify_projattachments')

    class Meta:
        db_table = 'projectAttachment'


class projectTags(MyModel):
    proj = MyForeignKey(project,related_name='project_tags' )
    tag = MyForeignKey(Tag, related_name='tag_projects')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_projtags')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_projtag')

    class Meta:
        db_table = "project_tags"

    def save(self, *args, **kwargs):
        if self.tag.datasource != self.proj.datasource:
            raise InvestError(8888, msg='标签来源不符')
        return super(projectTags, self).save(*args, **kwargs)


class projectIndustries(MyModel):
    proj = MyForeignKey(project,related_name='project_industries')
    industry = MyForeignKey(Industry, related_name='industry_projects')
    bucket = models.CharField(max_length=16,blank=True,null=True)
    key = models.TextField(blank=True,null=True)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_projIndustries')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_projIndustry')

    class Meta:
        db_table = "project_industries"
    def save(self, *args, **kwargs):
        if self.industry.datasource != self.proj.datasource:
            raise InvestError(8888, msg='行业来源不符')
        if not self.key:
            self.bucket = self.industry.bucket
            self.key = self.industry.key
        return super(projectIndustries, self).save(*args, **kwargs)


class projectTransactionType(MyModel):
    proj = MyForeignKey(project, related_name='project_TransactionTypes')
    transactionType = MyForeignKey(TransactionType, related_name='transactionType_projects')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_projtransactionTypes')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_projtransactionType')

    class Meta:
        db_table = "project_TransactionType"


class projectDiDiRecord(MyModel):
    proj = MyForeignKey(project, blank=True, null=True, related_name='project_DiDiRecords')
    projName = models.TextField(blank=True, null=True, help_text="项目名称")
    orderNumber = models.CharField(max_length=32, blank=True, help_text='专快订单号')
    orderDate = models.DateTimeField(blank=True, null=True, help_text='支付时间')
    orderType = MyForeignKey(DidiOrderType, blank=True, null=True, help_text='用车类型（对应用车权限）')
    orderPerm = models.CharField(max_length=64, blank=True, null=True, help_text='用车权限')
    city = models.CharField(max_length=64, blank=True, null=True, help_text='用车城市')
    startPlace = models.TextField(blank=True, null=True, help_text='实际出发地')
    endPlace = models.TextField(blank=True, null=True, help_text='实际目的地')
    money = models.FloatField(blank=True, null=True, help_text='企业实付金额')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_projDiDiRecords')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_projDiDiRecords')
    datasource = MyForeignKey(DataSource, blank=True, help_text='数据源')

    class Meta:
        db_table = "project_didiRecord"

    def save(self, *args, **kwargs):
        if self.proj:
            self.datasource = self.proj.datasource
        if not self.orderType and self.orderPerm:
            if DidiOrderType.objects.filter(nameC=self.orderPerm, is_deleted=False).exists():
                self.orderType = DidiOrderType.objects.filter(nameC=self.orderPerm, is_deleted=False).first()
        if not self.is_deleted:
            if projectDiDiRecord.objects.exclude(pk=self.pk).filter(orderNumber=self.orderNumber, is_deleted=False).exists():
                raise InvestError(4010, msg='订单号已存在')
            if not self.money or self.money < 0:
               raise InvestError(20071, msg='实际付款不符合条件')
        return super(projectDiDiRecord, self).save(*args, **kwargs)



class ShareToken(models.Model):
    key = models.CharField(max_length=50, primary_key=True,help_text='sharetoken')
    user = MyForeignKey(MyUser, related_name='user_sharetoken',help_text='用户的分享token')
    proj = MyForeignKey(project,related_name='proj_sharetoken',help_text='项目的分享token')
    created = models.DateTimeField(help_text="CreatedTime", auto_now_add=True,blank=True)
    is_deleted = models.BooleanField(help_text='是否已被删除', blank=True, default=False)

    class Meta:
        db_table = 'project_sharetoken'

    def timeout(self):
        return datetime.timedelta(hours=24 * 1) - (datetime.datetime.now() - self.created)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        if self.user.datasource != self.proj.datasource:
            raise InvestError(code=8888,msg='来源不匹配')
        return super(ShareToken, self).save(*args, **kwargs)

    def generate_key(self):
        return binascii.hexlify(os.urandom(25)).decode()

    def __str__(self):
        return self.key


# 项目进度
class projcomments(MyModel):
    comment = models.TextField(blank=True, null=True, help_text='项目进展')
    proj = MyForeignKey(project, related_name='proj_comments', help_text='项目的分享token')
    commenttime =  models.DateTimeField(blank=True, null=True, help_text="备注时间")
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_projcomments')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_projcomments')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_projcomments')
    datasource = MyForeignKey(DataSource, blank=True, help_text='数据源')

    class Meta:
        db_table = 'project_comments'


    def save(self, *args, **kwargs):
        if not self.commenttime:
            self.commenttime = datetime.datetime.now()
        self.datasource = self.proj.datasource
        return super(projcomments, self).save(*args, **kwargs)

