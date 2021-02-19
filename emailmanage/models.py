#coding=utf-8
from __future__ import unicode_literals

import datetime
from django.db import models

# Create your models here.
from utils.customClass import MyModel


# events = {
#     'opened': '打开邮件',
#     'marked_as_spam': '标记为垃圾邮件',
#     'clicked': '点击超链接',
#     'report_as_spam': '举报为垃圾邮件',
# }


class emailgroupsendlist(MyModel):
    proj = models.IntegerField(blank=True, null=True, help_text='项目')
    projtitle = models.TextField(blank=True, null=True)
    send_id = models.CharField(max_length=200, blank=True, null=True, help_text='由submail返回')
    user = models.IntegerField(blank=True, null=True, help_text='用户')
    username = models.CharField(max_length=64, blank=True, null=True)
    userMobile = models.CharField(max_length=64, blank=True, null=True)
    userEmail = models.CharField(max_length=64, blank=True, null=True)
    isRead = models.BooleanField(blank=True, default=False, help_text='用户是否已读')
    readtime = models.DateTimeField(blank=True, null=True)
    isSend = models.BooleanField(blank=True, default=False, help_text='是否发送邮件成功')
    sendtime = models.DateTimeField(blank=True, null=True)
    errmsg = models.TextField(blank=True, null=True, help_text='发送失败原因')
    events = models.CharField(max_length=64, blank=True, null=True)
    email = models.CharField(max_length=64, blank=True, null=True)
    app = models.CharField(max_length=64, blank=True, null=True)
    tag = models.CharField(max_length=64, blank=True, null=True)
    ip = models.CharField(max_length=64, blank=True, null=True)
    agent = models.TextField(max_length=64, blank=True, null=True)
    platform = models.CharField(max_length=64, blank=True, null=True)
    device = models.CharField(max_length=64, blank=True, null=True)
    country_code = models.CharField(max_length=16, blank=True, null=True)
    country = models.CharField(max_length=64, blank=True, null=True)
    province = models.CharField(max_length=64, blank=True, null=True)
    city = models.CharField(max_length=64, blank=True, null=True)
    latitude = models.CharField(max_length=64, blank=True, null=True)
    longitude = models.CharField(max_length=64, blank=True, null=True)
    timestamp = models.CharField(max_length=64, blank=True, null=True)
    token = models.CharField(max_length=64, blank=True, null=True)
    signature = models.CharField(max_length=64, blank=True, null=True)
    datasource = models.IntegerField(blank=True, null=True)

    class Meta:
        permissions = (
            ('getemailmanage', '查看邮件管理'),
        )

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.sendtime:
            self.sendtime = datetime.datetime.now()
        super(emailgroupsendlist, self).save(force_insert, force_update, using, update_fields)