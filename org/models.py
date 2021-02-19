#coding=utf-8
from __future__ import unicode_literals

from django.db import models
import sys

from django.db.models import Q
from guardian.shortcuts import assign_perm, remove_perm
from sourcetype.models import AuditStatus, OrgType , TransactionPhases,CurrencyType, Industry, DataSource, OrgAttribute, Country, \
    Tag, OrgLevelType
from usersys.models import MyUser
from utils.customClass import InvestError, MyForeignKey, MyModel
reload(sys)
sys.setdefaultencoding('utf-8')
# Create your models here.

class organization(MyModel):
    id = models.AutoField(primary_key=True)
    orglevel = MyForeignKey(OrgLevelType, blank=True, default=3, help_text='机构级别')
    description = models.TextField(blank=True,null=True)
    investoverseasproject = models.BooleanField(blank=True, default=False, help_text='海外机构')
    orgtransactionphase = models.ManyToManyField(TransactionPhases, through='orgTransactionPhase',through_fields=('org','transactionPhase'), blank=True)
    currency = MyForeignKey(CurrencyType,blank=True, default=1)
    decisionCycle = models.SmallIntegerField(blank=True,null=True)
    decisionMakingProcess = models.TextField(blank=True,null=True)
    establishedDate = models.DateTimeField(blank=True, null=True, help_text='成立时间')
    orgfullname = models.CharField(max_length=128,blank=True,null=True, help_text='全称')
    orgnameC = models.CharField(max_length=128,blank=True,null=True, help_text='中文简称')
    orgnameE = models.CharField(max_length=128,blank=True,null=True, help_text='英文简称')
    stockcode = models.CharField(max_length=128,blank=True,null=True,help_text='证券代码')
    stockshortname = models.CharField(max_length=128,blank=True,null=True,help_text='证券简称')
    managerName = models.CharField(max_length=128,blank=True,null=True,help_text='基金管理人名称')
    IPOdate = models.DateTimeField(blank=True,null=True,help_text='上市日期')
    marketvalue = models.BigIntegerField(blank=True,null=True,help_text='总市值')
    orgattribute = MyForeignKey(OrgAttribute,blank=True,null=True,help_text='机构属性（国有、民营、地方、中央）')
    businessscope = models.TextField(blank=True,null=True,help_text='经营范围')
    mainproductname = models.TextField(blank=True,null=True,help_text='主营产品名称')
    mainproducttype = models.TextField(blank=True,null=True,help_text='主营产品类别')
    totalemployees = models.IntegerField(blank=True,null=True,help_text='员工总数')
    address = models.TextField(blank=True, null=True)
    investmentStrategy = models.TextField(blank=True, null=True, help_text='投资策略')
    orgtype = MyForeignKey(OrgType,blank=True,null=True,help_text='机构类型（基金、证券、上市公司）')
    transactionAmountF = models.BigIntegerField(blank=True,null=True)
    transactionAmountT = models.BigIntegerField(blank=True,null=True)
    weChat = models.CharField(max_length=32,blank=True,null=True)
    fundSize = models.BigIntegerField(blank=True,null=True)
    issub = models.BooleanField(blank=True, default=False, help_text='是否是子基金')
    typicalCase = models.TextField(blank=True,null=True)
    tags = models.ManyToManyField(Tag, through='orgTags', through_fields=('org', 'tag'), blank=True)
    fundSize_USD = models.BigIntegerField(blank=True,null=True)
    transactionAmountF_USD = models.BigIntegerField(blank=True,null=True)
    transactionAmountT_USD = models.BigIntegerField(blank=True,null=True)
    partnerOrInvestmentCommiterMember = models.TextField(blank=True,null=True)
    mobile = models.CharField(max_length=100,blank=True,null=True)
    mobileCode = models.CharField(max_length=8, blank=True, null=True, help_text='电话区号')
    mobileAreaCode = models.CharField(max_length=10, blank=True, null=True, default='86',help_text='电话国家号')
    industry = MyForeignKey(Industry,help_text='机构行业',blank=True,null=True)
    webSite = models.CharField(max_length=128,blank=True,null=True)
    companyEmail = models.EmailField(blank=True,null=True,max_length=50)
    orgstatus = MyForeignKey(AuditStatus, blank=True, default=1)
    auditUser = MyForeignKey(MyUser, blank=True, null=True, related_name='useraudit_orgs')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True,related_name='userdelete_orgs')
    createuser = MyForeignKey(MyUser, blank=True, null=True,related_name='usercreate_orgs')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True,related_name='usermodify_orgs')
    datasource = MyForeignKey(DataSource,help_text='数据源')

    def __str__(self):
        return self.orgnameC
    class Meta:
        db_table = "org"
        permissions = (
            ('admin_addorg','管理员新增机构'),
            ('admin_changeorg','管理员修改机构'),
            ('admin_deleteorg','管理员删除机构'),
            ('admin_getorg','管理员查看机构信息'),

            ('user_addorg', '用户新增机构'),
            ('user_changeorg', '用户修改机构(obj级别)'),
            ('user_deleteorg', '用户删除机构(obj级别)'),
            ('user_getorg', '用户查看机构（obj级别）'),

            ('export_org', '导出机构Excel'),
        )


    def save(self, *args, **kwargs):
        if not self.orgnameC and not self.orgnameE:
            raise InvestError(2007,msg='机构名称不能为空')
        if self.orgnameC and not self.orgnameE:
            self.orgnameE = self.orgnameC
        if self.orgnameE and not self.orgnameC:
            self.orgnameC = self.orgnameE
        if not self.orgfullname:
            self.orgfullname = self.orgnameC
        if self.mobileCode:
            if not self.mobileCode.isdigit():
                raise InvestError(2007, msg='区号 必须是纯数字')
        if self.mobileAreaCode:
            if not self.mobileAreaCode.isdigit():
                raise InvestError(2007, msg='国家号 必须是纯数字')
        if self.pk:
            oldorg = organization.objects.get(pk=self.pk)
            if self.orgfullname:
                if organization.objects.exclude(pk=self.pk).filter(is_deleted=False,orgfullname=self.orgfullname).exists():
                    raise InvestError(code=5001,msg='同名机构已存在,无法修改')
            if self.is_deleted and oldorg.createuser:
                remove_perm('org.user_getorg', oldorg.createuser, self)
                remove_perm('org.user_changeorg', oldorg.createuser, self)
                remove_perm('org.user_deleteorg', oldorg.createuser, self)
        else:
            if self.orgfullname:
                if organization.objects.filter(is_deleted=False,orgfullname=self.orgfullname).exists():
                    raise InvestError(code=5001,msg='同名机构已存在，无法新增')
        super(organization,self).save(*args, **kwargs)

class orgTags(MyModel):
    org = MyForeignKey(organization,related_name='org_orgtags')
    tag = MyForeignKey(Tag, related_name='tag_orgtags')


    class Meta:
        db_table = "org_tags"
        unique_together = ('org', 'tag')

    def save(self, *args, **kwargs):
        return super(orgTags, self).save(*args, **kwargs)


class orgTransactionPhase(MyModel):
    org = MyForeignKey(organization,null=True,blank=True,related_name='org_orgTransactionPhases')
    transactionPhase = MyForeignKey(TransactionPhases,null=True,blank=True,related_name='transactionPhase_orgs',on_delete=models.SET_NULL)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_orgTransactionPhases',on_delete=models.SET_NULL)
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_orgTransactionPhase',on_delete=models.SET_NULL)

    class Meta:
        db_table = "org_TransactionPhase"


class orgContact(MyModel):
    org = MyForeignKey(organization,null=True,blank=True, db_index=True, related_name='org_orgcontact')
    address = models.TextField(null=True,blank=True,help_text='联系地址')
    postcode = models.CharField(max_length=48,null=True,blank=True,help_text='邮政编码')
    countrycode = models.CharField(max_length=16,blank=True,null=True,default='86',help_text='国家号')
    areacode = models.CharField(max_length=16,blank=True,null=True,default='86',help_text='地区号')
    numbercode = models.CharField(max_length=32,db_index=True,blank=True,null=True,help_text='电话')
    faxcode = models.CharField(max_length=32, blank=True,null=True,help_text='传真')
    email = models.EmailField(max_length=128, blank=True,null=True,help_text='邮箱')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True,related_name='userdelete_orgcontact')
    createuser = MyForeignKey(MyUser, blank=True, null=True,related_name='usercreate_orgcontact')

    class Meta:
        db_table = "org_contact"

    def save(self,  *args, **kwargs):
        if not self.org:
            raise InvestError(code=2007,msg='机构不能为空')
        super(orgContact,self).save(*args, **kwargs)


class orgManageFund(MyModel):
    org = MyForeignKey(organization,null=True,blank=True,db_index=True,related_name='org_orgManageFund')
    fund = MyForeignKey(organization,null=True,blank=True,related_name='fund_fundManager')
    type = models.CharField(max_length=64,null=True,blank=True,help_text='基金类型')
    fundsource = models.CharField(max_length=64, null=True, blank=True, help_text='资本来源')
    fundraisedate = models.DateTimeField(null=True, blank=True, help_text='募集时间')
    fundsize = models.CharField(max_length=32, null=True, blank=True, help_text='募集规模')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True,related_name='userdelete_orgmanagefund')
    createuser = MyForeignKey(MyUser, blank=True, null=True,related_name='usercreate_orgmanagefund')

    class Meta:
        db_table = "org_managefund"

    def save(self,  *args, **kwargs):
        if not self.org or not self.fund:
            raise InvestError(code=2007,msg='机构/基金不能为空')
        super(orgManageFund,self).save(*args, **kwargs)


class orgInvestEvent(MyModel):
    org = MyForeignKey(organization,null=True, blank=True, db_index=True, related_name='org_orgInvestEvent')
    comshortname = models.CharField(max_length=128, null=True, blank=True, help_text='企业简称')
    com_id = models.BigIntegerField(null=True, blank=True, help_text='全库ID')
    industrytype = models.CharField(max_length=32, null=True, blank=True, help_text='行业分类')
    area = MyForeignKey(Country,blank=True, null=True, help_text='地区')
    investor =  models.CharField(max_length=128, null=True, blank=True, help_text='投资人')
    investDate = models.DateTimeField(blank=True, null=True, help_text='投资日期')
    investType = models.CharField(max_length=64, blank=True,null=True,help_text='投资性质（轮次）')
    investSize = models.CharField(max_length=32, blank=True, null=True, help_text='投资金额')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_orginvestevent')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_orginvestevent')

    class Meta:
        db_table = "org_investevent"

    def save(self,  *args, **kwargs):
        if not self.org or not self.comshortname:
            raise InvestError(code=2007,msg='机构/企业不能为空')
        if self.pk:
            if orgInvestEvent.objects.exclude(pk=self.pk).filter(is_deleted=False,comshortname=self.comshortname,investDate=self.investDate, org=self.org).exists():
                raise InvestError(code=5007,msg='相同投资事件已存在，无法修改')
        else:
            if orgInvestEvent.objects.filter(is_deleted=False,comshortname=self.comshortname,investDate=self.investDate, org=self.org).exists():
                raise InvestError(code=5007,msg='相同投资事件已存在，无法新增')
        super(orgInvestEvent,self).save(*args, **kwargs)


class orgCooperativeRelationship(MyModel):
    org = MyForeignKey(organization,null=True, blank=True, db_index=True, related_name='org_cooperativeRelationship')
    cooperativeOrg = MyForeignKey(organization,null=True, blank=True, db_index=True, help_text='合作机构', related_name='cooperativeorg_Relationship')
    comshortname = models.CharField(max_length=128, null=True, blank=True, help_text='企业简称')
    investDate = models.DateTimeField(blank=True, null=True)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_orgcooprelation')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_orgcooprelation')

    class Meta:
        db_table = "org_cooperativerelationship"

    def save(self,  *args, **kwargs):
        if not self.org or not self.cooperativeOrg or not self.comshortname:
            raise InvestError(code=2007, msg='机构/合作机构/企业不能为空')
        super(orgCooperativeRelationship,self).save(*args, **kwargs)


class orgBuyout(MyModel):
    org = MyForeignKey(organization, null=True, blank=True, db_index=True, related_name='org_buyout')
    buyoutorg = MyForeignKey(organization, null=True, blank=True, db_index=True, help_text='退出基金', related_name='buyoutorg_buyoutorg')
    comshortname = models.CharField(max_length=128, null=True, blank=True, help_text='企业简称')
    buyoutType = models.CharField(max_length=64, null=True, blank=True, help_text='退出方式')
    buyoutDate = models.DateTimeField(blank=True, null=True)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_orgbuyout')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_orgbuyout')

    class Meta:
        db_table = "org_buyout"
    def save(self, *args, **kwargs):
        if not self.org:
            raise InvestError(code=2007, msg='机构不能为空')
        super(orgBuyout,self).save(*args, **kwargs)

class orgRemarks(MyModel):
    id = models.AutoField(primary_key=True)
    org = MyForeignKey(organization,null=True,blank=True,related_name='org_remarks')
    remark = models.TextField(blank=True,null=True)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_orgremarks',on_delete=models.SET_NULL)
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_orgremarks',on_delete=models.SET_NULL)
    lastmodifyuser = MyForeignKey(MyUser,  blank=True, null=True,related_name='usermodify_orgremarks', related_query_name='orgremark_modifyuser',on_delete=models.SET_NULL)
    datasource = MyForeignKey(DataSource, blank=True, null=True, help_text='数据源')
    class Meta:
        db_table = "orgremark"
        permissions = (
            ('admin_getorgremark','管理员查看机构备注'),
            ('admin_changeorgremark', '管理员修改机构备注'),
            ('admin_addorgremark', '管理员增加机构备注'),
            ('admin_deleteorgremark', '管理员删除机构备注'),

            ('user_getorgremark', '用户查看机构备注（obj级别）'),
            ('user_changeorgremark', '用户修改机构备注（obj级别）'),
            ('user_addorgremark', '用户增加机构备注'),
            ('user_deleteorgremark','用户删除机构备注（obj级别）'),
        )
    def save(self, *args, **kwargs):
        self.datasource = self.createuser.datasource
        kwargs['automodifytime'] = False
        super(orgRemarks,self).save(*args, **kwargs)

taskstatuschoice = (
    (1, '已失败'),
    (3, '未开始'),
    (4, '正在进行'),
    (5, '已完成'),
)

class orgExportExcelTask(MyModel):
    orglist = models.TextField(blank=True, null=True)
    filename = models.CharField(max_length=40, blank=True, null=True)
    taglist = models.TextField(blank=True, null=True)
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_orgexporttasks', on_delete=models.SET_NULL)
    status = models.PositiveSmallIntegerField(blank=True, choices=taskstatuschoice, default=3, help_text='当前状态')
    completetime = models.DateTimeField(blank=True, null=True, help_text='完成时间')
    No = models.IntegerField(blank=True, null=True, help_text='排序')

    def save(self,  *args, **kwargs):
        if not self.orglist or not self.filename:
            raise InvestError(code=2007, msg='orglist, filename 不能为空')
        if '/' in self.filename or u'/' in self.filename:
            raise InvestError(code=2007, msg='filename 不能包含\'/\'')
        super(orgExportExcelTask, self).save(*args, **kwargs)



class orgAttachments(MyModel):
    org = MyForeignKey(organization, related_name='org_orgAttachments', blank=True)
    bucket = models.CharField(max_length=64, blank=True, null=True)
    key = models.CharField(max_length=128, blank=True, null=True, help_text='保存文件转换pdf后的key')
    realkey = models.CharField(max_length=128, blank=True, null=True, help_text='保存文件原始key')
    filename = models.CharField(max_length=128, blank=True, null=True)
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_orgAttachments')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_orgAttachments')

    class Meta:
        db_table = "org_attachments"
        permissions = (
            ('admin_manageorgattachment', '管理机构备注（增删改）'),
        )

    def save(self, *args, **kwargs):
        return super(orgAttachments, self).save(*args, **kwargs)




