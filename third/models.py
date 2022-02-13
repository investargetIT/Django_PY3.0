#coding=utf-8
from __future__ import unicode_literals

import datetime

import binascii
import os
import random

from django.db import models

# Create your models here.
class MobileAuthCode(models.Model):
    mobileareacode = models.CharField(max_length=8,blank=True,default='86')
    mobile = models.CharField(help_text='手机号',max_length=32)
    token = models.CharField(help_text='验证码token',max_length=32)
    code = models.CharField(help_text='验证码',max_length=32)
    createTime = models.DateTimeField(blank=True,null=True)
    is_deleted = models.BooleanField(blank=True,default=False)
    def isexpired(self):
        return datetime.datetime.now() - self.createTime >=  datetime.timedelta(minutes=30)
    def __str__(self):
        return self.code
    class Meta:
        db_table = "mobileAuthCode"
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = binascii.hexlify(os.urandom(16)).decode()
        if not self.code:
            self.code = self.getRandomCode()
        if not self.pk:
            self.createTime = datetime.datetime.now()
        return super(MobileAuthCode, self).save(*args, **kwargs)
    def getRandomCode(self):
        code_list = [0,1,2,3,4,5,6,7,8,9]
        myslice = random.sample(code_list, 6)
        code = ''.join(str(i) for i in myslice)
        return code


class AudioTranslateTaskRecord(models.Model):
    task_id = models.CharField(help_text='task_id', max_length=32, blank=True)
    file_key = models.CharField(help_text='filekey', max_length=32, blank=True)
    file_name = models.TextField(help_text='filename', null=True, blank=True)
    speaker_number = models.SmallIntegerField(default=0, blank=True)
    onebest = models.TextField(help_text='识别内容', blank=True, null=True)
    taskStatus = models.TextField(help_text='转写任务状态', blank=True, null=True)
    cretateUserId = models.BigIntegerField(blank=True, null=True, help_text='转换任务创建人id')
    createTime = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(blank=True, default=False)

    class Meta:
        db_table = 'audiotranslaterecord'
        ordering = ['-createTime']

    def save(self, *args, **kwargs):
        if not self.createTime:
            self.createTime = datetime.datetime.now()
        return super(AudioTranslateTaskRecord, self).save(*args, **kwargs)