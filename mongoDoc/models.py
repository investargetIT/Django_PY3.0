#coding:utf-8
from __future__ import unicode_literals

import datetime
from mongoengine import *
from invest.settings import groupemailMongoTableName, projectDataMongoTableName, \
    mergeandfinanceeventMongoTableName, com_catMongoTableName, projremarkMongoTableName, wxchatdataMongoTableName, \
    projectNewsMongoTableName, projIndustryInfoMongoTableName, companysearchMongoTableName, \
    openAiChatDataMongoTableName, openAiChatTopicDataMongoTableName
from utils.customClass import InvestError


class CompanyCatData(Document):
    p_cat_id = IntField(null=True)
    p_cat_name = StringField(null=True)
    cat_id = IntField(null=True)
    cat_name= StringField(null=True)
    meta = {"collection": com_catMongoTableName}


class ProjectData(Document):
    com_id = IntField()      #公司id
    com_name = StringField()   #公司名称
    com_status = StringField(null=True)  #公司运营状态
    com_scale= StringField(null=True)    #公司规模
    com_web = StringField(null=True)   #公司网站
    invse_round_id = StringField(null=True)  #公司获投状态
    com_cat_name = StringField(null=True)  #行业
    com_sub_cat_name = StringField(null=True) #子行业
    com_born_date = StringField(null=True)   #成立日期
    invse_detail_money = StringField(null=True)  #最新融资金额
    guzhi = StringField(null=True)          #估值
    invse_date = StringField(null=True)   #最新融资日期
    com_logo_archive = StringField(null=True)   #公司logo
    com_fund_needs_name = StringField(null=True) #融资需求
    com_des = StringField(null=True)   #公司介绍
    invse_total_money = StringField(null=True)  #融资总额
    com_addr = StringField(null=True)   #公司所在地
    com_city = StringField(null=True)  # 公司所在地
    mobile = StringField(null=True)  # 公司联系方式
    email = StringField(null=True)  # 公司邮箱
    detailaddress = StringField(null=True)  # 公司地址
    tags = ListField(null=True)   #公司标签
    source = IntField(null=True)  #来源类型
    meta = {'collection': projectDataMongoTableName,
            'indexes': ['com_id', 'com_cat_name', 'com_sub_cat_name', 'invse_round_id', 'com_name']
        }

    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if self.pk is None:
            if len(ProjectData.objects.filter(com_id=self.com_id)) > 0:
                raise InvestError(8001,msg='数据重复')
        super(ProjectData,self).save(force_insert,validate,clean,write_concern,cascade,cascade_kwargs,_refs,save_condition,signal_kwargs,**kwargs)

class MergeFinanceData(Document):

    com_id = IntField(null=True)  #公司id
    com_logo = StringField(null=True)  # 公司logo
    com_name = StringField(null=True)  # 公司名称
    currency= StringField(null=True)    #货币类型
    com_cat_name = StringField(null=True) #行业
    com_sub_cat_name = StringField(null=True)  # 子行业
    com_addr = StringField(null=True, default='其他')  # 公司所在地
    money = StringField(null=True)  #金额
    date = StringField(null=True)  #日期

    invsest_with = ListField(null=True)  # 投资方
    invse_id = IntField(null=True)  # 投资事件id
    round = StringField(null=True, default='不明确')   #公司融资轮次

    merger_equity_ratio = StringField(null=True)  #股权比例
    merger_with = StringField(null=True)   #并购方名称
    merger_id = IntField(null=True)   #并购事件id

    investormerge = IntField(default=1)   #并购事件（2）or 投资事件（1）
    meta = {'collection': mergeandfinanceeventMongoTableName,
            'indexes': ['com_id', 'com_name', 'date', 'invse_id', 'merger_id','investormerge']
            }

    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if not self.com_addr:
            self.com_addr = '其他'
        super(MergeFinanceData,self).save(force_insert,validate,clean,write_concern,cascade,cascade_kwargs,_refs,save_condition,signal_kwargs,**kwargs)


class ProjectNews(Document):
    com_id = IntField(null=True)      #公司id
    com_name = StringField(null=True)   #公司名称
    title = StringField(null=True)  #行业
    linkurl = StringField(null=True) #子行业
    newsdate = StringField(null=True)   #成立日期
    meta = {'collection': projectNewsMongoTableName,'indexes': ['com_id','linkurl']}

    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if len(ProjectNews.objects.filter(com_id=self.com_id,linkurl=self.linkurl)) > 0:
            raise InvestError(8001, msg='数据重复')
        super(ProjectNews,self).save(force_insert,validate,clean,write_concern,cascade,cascade_kwargs,_refs,save_condition,signal_kwargs,**kwargs)


class ProjIndustryInfo(Document):     #工商信息
    com_id = IntField(null=True)  # 公司id
    indus_base = DictField(null=True)  # 基本信息
    indus_member = ListField(null=True)  #主要成员
    indus_shareholder = ListField(null=True)  # 股权信息
    indus_foreign_invest = ListField(null=True)   # 公司对外投资信息
    indus_busi_info = ListField(null=True)    # 工商变更信息
    date = DateTimeField(null=True)
    meta = {'collection': projIndustryInfoMongoTableName,
            'indexes': ['com_id',]
            }
    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if self.date is None:
            self.date = datetime.datetime.now()
        super(ProjIndustryInfo, self).save(force_insert, validate, clean, write_concern, cascade, cascade_kwargs, _refs,
                                      save_condition, signal_kwargs, **kwargs)




class ProjRemark(Document):
    com_id = IntField(null=True)  # 公司id
    com_name = StringField(null=True)  # 公司名称
    remark = StringField(null=True)
    createuser_id = IntField()
    datasource = IntField()
    date = DateTimeField()
    meta = {'collection': projremarkMongoTableName,
            'indexes': ['com_id', 'com_name']
            }
    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if self.date is None:
            self.date = datetime.datetime.now()
        super(ProjRemark, self).save(force_insert, validate, clean, write_concern, cascade, cascade_kwargs, _refs,
                                      save_condition, signal_kwargs, **kwargs)


class GroupEmailData(Document):
    users = ListField(DictField())
    projtitle = StringField()
    proj = DictField()
    savetime = DateTimeField()
    datasource = IntField()
    meta = {"collection": groupemailMongoTableName}

    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if self.savetime is None:
            self.savetime = datetime.datetime.now()
        super(GroupEmailData, self).save(force_insert, validate, clean, write_concern, cascade, cascade_kwargs, _refs,
                                      save_condition, signal_kwargs, **kwargs)


class WXChatdata(Document):
    content = StringField()
    createtime = DateTimeField()
    name = StringField()
    group_name = StringField()
    isShow = BooleanField(default=True)
    meta = {"collection": wxchatdataMongoTableName}
    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if self.createtime is None:
            self.createtime = datetime.datetime.now()
        super(WXChatdata, self).save(force_insert, validate, clean, write_concern, cascade, cascade_kwargs, _refs,
                                      save_condition, signal_kwargs, **kwargs)


class CompanySearchName(Document):
    com_name = StringField(null=True)
    createtime = DateTimeField(null=True)
    searchuser_id = IntField(null=True)
    meta = {"collection": companysearchMongoTableName}
    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if self.createtime is None:
            self.createtime = datetime.datetime.now()
        if len(CompanySearchName.objects.filter(com_name=self.com_name)) == 0:
            super(CompanySearchName, self).save(force_insert, validate, clean, write_concern, cascade, cascade_kwargs, _refs,
                                      save_condition, signal_kwargs, **kwargs)


class OpenAiChatTopicData(Document):
    topic_name = StringField(null=True)
    create_time = DateTimeField(null=True)
    type = IntField(null=True) #    (1 gptchat)(2 discord image)(3 zilliz chat)(4 pdffile chat)
    lastchat_time = DateTimeField(null=True)
    user_id = IntField(null=True)
    meta = {"collection": openAiChatTopicDataMongoTableName}
    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if self.create_time is None:
            self.create_time = datetime.datetime.now()
        if self.lastchat_time is None:
            self.lastchat_time = datetime.datetime.now()
        super(OpenAiChatTopicData, self).save(force_insert, validate, clean, write_concern, cascade, cascade_kwargs, _refs,
                                      save_condition, signal_kwargs, **kwargs)




class OpenAiChatData(Document):
    topic_id = StringField(null=True)
    user_id = IntField(null=True)
    content = StringField(null=True)
    isAI = BooleanField(default=False)
    isreset = BooleanField(default=False)
    msgtime = DateTimeField(null=True)
    meta = {"collection": openAiChatDataMongoTableName}
    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if self.msgtime is None:
            self.msgtime = datetime.datetime.now()
        super(OpenAiChatData, self).save(force_insert, validate, clean, write_concern, cascade, cascade_kwargs, _refs,
                                      save_condition, signal_kwargs, **kwargs)


class OpenAiZillizChatData(Document):
    topic_id = StringField(null=True)
    user_id = IntField(null=True)
    ai_content = StringField(null=True)
    user_content = StringField(default=False)
    file_key = StringField(null=True)
    isreset = BooleanField(default=False)
    msgtime = DateTimeField(null=True)
    meta = {"collection": 'openaizillizchatdata'}
    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if self.msgtime is None:
            self.msgtime = datetime.datetime.now()
        super(OpenAiZillizChatData, self).save(force_insert, validate, clean, write_concern, cascade, cascade_kwargs, _refs,
                                      save_condition, signal_kwargs, **kwargs)



class DiscordImageData(Document):
    topic_id = StringField(null=True)
    user_id = IntField(null=True)
    message_id = StringField(null=True)      # 消息id
    channel_id = StringField(null=True)      # 频道id
    guild_id = StringField(null=True)        # 服务器id
    attachment = DictField(null=True)        # 附件信息
    url = StringField(null=True)             # 附件url
    proxy_url = StringField(null=True)       # 附件proxy_url
    content_type = StringField(null=True)    # 附件类型
    completed = BooleanField(default=False)  # 已完成画图任务
    prompt = StringField(null=True)          # 文字画图片内容  prompt
    content = StringField(null=True)         # 图片内容 message.content
    promtime = DateTimeField(null=True)      # 文字画图片内容创建时间
    attatime = DateTimeField(null=True)      # 附件时间
    meta = {"collection": 'discordimage'}
    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, save_condition=None, signal_kwargs=None, **kwargs):
        if self.promtime is None:
            self.promtime = datetime.datetime.now()
        super(DiscordImageData, self).save(force_insert, validate, clean, write_concern, cascade, cascade_kwargs, _refs,
                                      save_condition, signal_kwargs, **kwargs)