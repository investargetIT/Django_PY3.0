#coding=utf-8
from __future__ import unicode_literals
from django.db import models
from utils.customClass import MyModel


class APILog(MyModel):
    IPaddress = models.CharField(max_length=32,blank=True,null=True)
    URL = models.CharField(max_length=128,blank=True,null=True)
    method = models.CharField(max_length=16,blank=True,null=True)
    requestbody = models.TextField()
    requestuser_id = models.IntegerField(blank=True,null=True)
    requestuser_name = models.CharField(max_length=64,blank=True, null=True)
    modeltype = models.CharField(max_length=32,blank=True,null=True)
    model_id = models.IntegerField(blank=True,null=True)
    model_name = models.TextField(blank=True,null=True)
    request_before = models.TextField(blank=True,null=True)
    request_after = models.TextField(blank=True,null=True)
    datasource = models.PositiveSmallIntegerField(blank=True,default=1)
    class Meta:
        db_table = 'API_LOG'

class loginlog(MyModel):
    user = models.IntegerField(blank=True,null=True)
    ipaddress = models.CharField(max_length=20,blank=True,null=True)
    loginaccount = models.CharField(max_length=40,blank=True,null=True)
    logintime = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    logintype = models.PositiveSmallIntegerField(blank=True,null=True)
    datasource = models.PositiveSmallIntegerField(blank=True, default=1)
    class Meta:
        db_table = 'LOG_login'

class userviewprojlog(MyModel):
    user = models.IntegerField(blank=True,null=True)
    proj = models.IntegerField(blank=True,null=True)
    viewtime = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    source = models.PositiveSmallIntegerField(blank=True,null=True)
    datasource = models.PositiveSmallIntegerField(blank=True, default=1)
    class Meta:
        db_table = 'LOG_userviewproject'

class userinfoupdatelog(MyModel):
    user_id = models.IntegerField(blank=True,null=True)
    type = models.CharField(max_length=64,blank=True,null=True)
    user_name = models.CharField(max_length=64,blank=True,null=True)
    before = models.CharField(max_length=128,blank=True,null=True)
    after = models.CharField(max_length=128,blank=True,null=True)
    requestuser_id = models.IntegerField(blank=True, null=True)
    requestuser_name = models.CharField(max_length=64, blank=True, null=True)
    updatetime = models.DateTimeField(auto_now_add=True,blank=True,null=True)
    datasource = models.PositiveSmallIntegerField(blank=True, default=1)
    class Meta:
        db_table = 'LOG_userinfoupdate'
        permissions = (
            ('manage_userinfolog', u'查询用户信息修改日志'),
        )