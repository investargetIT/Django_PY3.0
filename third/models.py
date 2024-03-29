#coding=utf-8
from __future__ import unicode_literals

import datetime

import binascii
import os
import random

from django.db import models

# Create your models here.
from utils.customClass import InvestError


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
        permissions = (
            ('addaudiotranslatetask', u'新建语音转换任务'),
        )

    def save(self, *args, **kwargs):
        if not self.createTime:
            self.createTime = datetime.datetime.now()
        return super(AudioTranslateTaskRecord, self).save(*args, **kwargs)


taskstatuschoice = (
    (1, '未开始'),
    (2, '正在进行'),
    (3, '已完成'),
)

class QiNiuFileUploadRecord(models.Model):
    filename = models.CharField(max_length=80, blank=True, null=True)
    filesize = models.IntegerField(blank=True, null=True, help_text='文件大小')
    fileMD5 = models.TextField(blank=True, null=True, help_text='文件MD5值')
    key = models.CharField(max_length=128, blank=True)
    bucket = models.CharField(max_length=40, blank=True)
    convertToPDF = models.BooleanField(blank=True, default=False)
    convertKey = models.CharField(max_length=128, blank=True, null=True)
    status = models.PositiveSmallIntegerField(blank=True, choices=taskstatuschoice, default=1, help_text='上传任务当前状态')
    msg = models.TextField(blank=True, null=True, help_text='上传任务当前状态信息')
    success1 = models.BooleanField(blank=True, default=False, help_text='原文件上传结果')
    success2 = models.BooleanField(blank=True, default=False, help_text='转换文件上传结果')
    info1 = models.TextField(blank=True, null=True, help_text='原文件上传返回信息')
    info2 = models.TextField(blank=True, null=True, help_text='转换文件上传返回信息')
    starttime = models.DateTimeField(blank=True, null=True, help_text='任务开始时间')
    endtime = models.DateTimeField(blank=True, null=True, help_text='任务结束时间')
    cretateUserId = models.BigIntegerField(blank=True, null=True, help_text='上传任务创建人id')
    createTime = models.DateTimeField(blank=True, null=True, help_text='上传任务创建时间')
    is_deleted = models.BooleanField(blank=True, default=False)

    def save(self,  *args, **kwargs):
        if self.filename and len(self.filename) > 80:
            raise InvestError(8300, msg='文件名称长度超限', detail='文件名称长度超限， 最大长度80, 当前为%s' % len(self.filename))
        if not self.is_deleted:
            if not self.createTime:
                self.createTime = datetime.datetime.now()
        if QiNiuFileUploadRecord.objects.exclude(pk=self.pk).filter(key=self.key, is_deleted=False).exists():
            raise InvestError(8300, msg='上传文件key已存在', detail='已存在相同key的上传记录')
        super(QiNiuFileUploadRecord, self).save(*args, **kwargs)
