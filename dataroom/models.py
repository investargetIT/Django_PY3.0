#coding=utf-8
from __future__ import unicode_literals

import datetime
import os
import threading
from django.db import models

from invest.settings import APILOG_PATH
from proj.models import project
from sourcetype.models import DataSource
from third.views.qiniufile import downloadFileToPath
from usersys.models import MyUser
from utils.customClass import InvestError, MyForeignKey, MyModel
from utils.util import logexcption


class publicdirectorytemplate(MyModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64,blank=True,null=True)
    parent = MyForeignKey('self',blank=True,null=True)
    orderNO = models.PositiveSmallIntegerField()
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_publicdirectorytemplate')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_publicdirectorytemplate')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_publicdirectorytemplate')
    class Meta:
        db_table = 'dataroompublicdirectorytemplate'

class dataroom(MyModel):
    id = models.AutoField(primary_key=True)
    proj = MyForeignKey(project,related_name='proj_datarooms',help_text='dataroom关联项目')
    isClose = models.BooleanField(help_text='是否关闭',blank=True,default=False)
    closeDate = models.DateTimeField(blank=True,null=True,help_text='关闭日期')
    isCompanyFile = models.BooleanField(blank=True, default=False, help_text='公司相关文件')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_datarooms')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_datarooms')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_datarooms')
    datasource = MyForeignKey(DataSource, blank=True, null=True, help_text='数据源')
    class Meta:
        db_table = 'dataroom'
        permissions = (
            ('admin_getdataroom','管理员查看dataroom'),
            ('admin_changedataroom', '管理员修改dataroom里的文件/控制用户可见文件范围'),
            ('admin_deletedataroom', '管理员删除dataroom'),
            ('admin_adddataroom', '管理员添加dataroom'),
            ('admin_closedataroom', '管理员关闭dataroom'),
            ('downloadDataroom','打包下载dataroom'),
            ('downloadNoWatermarkFile', '下载无水印文件'),
            ('user_adddataroomfile', '用户上传dataroom文件'),
            ('user_deletedataroomfile', '用户删除dataroom文件'),

            ('onlydataroom', '单独查看dataroom权限'),
            ('get_companydataroom', '查看公司dataroom')
        )

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.proj:
            raise InvestError(code=7004,msg='proj缺失')
        if self.proj.projstatus_id < 4:
            raise InvestError(5003,msg='项目尚未终审发布')
        super(dataroom, self).save(force_insert, force_update, using, update_fields)

class dataroomdirectoryorfile(MyModel):
    id = models.AutoField(primary_key=True)
    dataroom = MyForeignKey(dataroom,related_name='dataroom_directories',help_text='目录或文件所属dataroom')
    parent = MyForeignKey('self',blank=True,null=True,related_name='asparent_directories',help_text='目录或文件所属目录id')
    orderNO = models.PositiveSmallIntegerField(help_text='目录或文件在所属目录下的排序位置',blank=True,default=0)
    size = models.IntegerField(blank=True,null=True,help_text='文件大小')
    filename = models.CharField(max_length=128,blank=True,null=True,help_text='文件名或目录名')
    realfilekey = models.CharField(max_length=128,blank=True,null=True,help_text='原文件key')
    key = models.CharField(max_length=128,blank=True,null=True,help_text='文件路径')
    bucket = models.CharField(max_length=128,blank=True,null=True,help_text='文件所在空间')
    isFile = models.BooleanField(blank=True,default=False,help_text='true/文件，false/目录')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_dataroomdirectories')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_dataroomdirectories')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_dataroomdirectories')
    datasource = MyForeignKey(DataSource, blank=True, null=True, help_text='数据源')
    class Meta:
        db_table = 'dataroomdirectoryorfile'

    def save(self, force_insert=False, force_update=False, using=None,update_fields=None):
        if self.isFile:
            try:
                if self.pk:
                    dataroomdirectoryorfile.objects.exclude(pk=self.pk).get(is_deleted=False, key=self.key)
                else:
                    dataroomdirectoryorfile.objects.get(is_deleted=False, key=self.key)
            except dataroomdirectoryorfile.DoesNotExist:
                pass
            else:
                raise InvestError(code=7001,msg='相同key文件已存在')
        if self.pk is None:
            if self.dataroom.isClose or self.dataroom.is_deleted:
                raise InvestError(7012, msg='dataroom已关闭/删除，无法添加文件/目录')
        if self.parent:
            if self.parent.isFile:
                raise InvestError(7007,msg='非目录结构不能存储文件')
        if self.filename is None:
            raise InvestError(2007,msg='名称不能为空')
        if not self.is_deleted and self.isFile and not self.pk:
            dataroomPath = os.path.join(APILOG_PATH['es_dataroomPDFPath'], 'dataroom_{}'.format(self.dataroom.id))
            if not os.path.exists(dataroomPath):
                os.makedirs(dataroomPath)
            file_path = os.path.join(dataroomPath, self.realfilekey)
            filename, type = os.path.splitext(file_path)
            if type == '.pdf' and not os.path.exists(file_path):
                threading.Thread(target=downloadPDFToPath, args=(self, self.realfilekey, self.bucket, file_path)).start()
        super(dataroomdirectoryorfile, self).save(force_insert, force_update, using, update_fields)

# 下载dataroom PDF到本地
def downloadPDFToPath(fileInstance, key, bucket, path):
    try:
        downloadFileToPath(key, bucket, path)
        fileInstance.save()
    except Exception:
        logexcption()


class dataroom_User_file(MyModel):
    dataroom = MyForeignKey(dataroom, blank=True, null=True, related_name='dataroom_users')
    user = MyForeignKey(MyUser, blank=True, null=True, related_name='user_datarooms', help_text='投资人')
    lastgettime = models.DateTimeField(blank=True, null=True, help_text='最近获取日期')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_userdatarooms')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_userdatarooms')
    datasource = MyForeignKey(DataSource, blank=True, null=True, help_text='数据源')

    class Meta:
        db_table = 'dataroom_user'

    def save(self, force_insert=False, force_update=False, using=None,update_fields=None):
        if not self.user:
            raise InvestError(2007, '投资人不能为空')
        if self.pk is None:
            if self.dataroom.isClose or self.dataroom.is_deleted:
                raise InvestError(7012,msg='dataroom已关闭/删除，无法添加用户')
            try:
                dataroom_User_file.objects.get(is_deleted=False, user=self.user, dataroom=self.dataroom)
            except dataroom_User_file.DoesNotExist:
                pass
            else:
                raise InvestError(code=2004, msg='用户已存在一个相同项目的dataroom了')
        if not self.user.is_active:
            self.user.is_active = True
            self.user.save()
        super(dataroom_User_file, self).save(force_insert, force_update, using, update_fields)


class dataroomUserSeeFiles(MyModel):
    file = MyForeignKey(dataroomdirectoryorfile, blank=True, null=True, related_name='file_userSeeFile', on_delete=models.CASCADE)
    dataroomUserfile = MyForeignKey(dataroom_User_file, blank=True, null=True, related_name='dataroomuser_seeFiles', help_text='用户dataroom记录')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_userdataroomseefiles')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_userdataroomseefiles')
    datasource = MyForeignKey(DataSource, blank=True, null=True, help_text='数据源')

    class Meta:
        db_table = 'dataroom_user_seefiles'

    def save(self, force_insert=False, force_update=False, using=None,update_fields=None):
        self.datasource = self.file.datasource
        if self.pk is None:
            if self.dataroomUserfile.dataroom.isClose or self.dataroomUserfile.dataroom.is_deleted:
                raise InvestError(7012,msg='dataroom已关闭/删除，无法添加可见用户')
            try:
                dataroomUserSeeFiles.objects.get(is_deleted=False, file=self.file, dataroomUserfile=self.dataroomUserfile)
            except dataroomUserSeeFiles.DoesNotExist:
                pass
            else:
                raise InvestError(code=2004, msg='用户已存在一个相同的可见文件了')
        if not self.file:
            self.is_deleted = True
        super(dataroomUserSeeFiles, self).save(force_insert, force_update, using, update_fields)

class dataroom_User_template(MyModel):
    dataroom = MyForeignKey(dataroom, blank=True, null=True, related_name='dataroom_userTemp')
    user = MyForeignKey(MyUser, blank=True, null=True, related_name='user_dataroomTemp', help_text='投资人')
    password = models.CharField(max_length=64, blank=True, null=True, help_text='打包下载pdf编辑密码')
    dataroomUserfile = MyForeignKey(dataroom_User_file, blank=True, null=True, related_name='user_dataroomTempFiles',
                                    help_text='用户可见文件列表')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_userdataroomTemp')
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_userdataroomTemp')
    datasource = MyForeignKey(DataSource, blank=True, null=True, help_text='数据源')

    class Meta:
        db_table = 'dataroom_User_template'

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if not self.user:
            raise InvestError(code=2004, msg='user 不能为空')
        try:
            dataroom_User_template.objects.exclude(pk=self.pk).get(is_deleted=False, user=self.user,
                                                                   dataroom=self.dataroom)
        except dataroom_User_template.DoesNotExist:
            pass
        else:
            raise InvestError(code=2004, msg='用户已存在一个相同dataroom的模板了')
        if self.user != self.dataroomUserfile.user:
            raise InvestError(code=2004, msg='用户与模板不匹配')
        super(dataroom_User_template, self).save(force_insert, force_update, using, update_fields)




class dataroom_user_discuss(MyModel):
    dataroom = MyForeignKey(dataroom, blank=True, related_name='dataroom_userdiscuss', on_delete=models.CASCADE)
    file = MyForeignKey(dataroomdirectoryorfile, blank=True, related_name='dataroomfile_userdiscuss', on_delete=models.CASCADE)
    question = models.TextField(help_text='提问', null=True, blank=True)
    answer = models.TextField(help_text='回复', null=True, blank=True)
    user = MyForeignKey(MyUser, blank=True, related_name='userask_dataroomdiscuss', on_delete=models.CASCADE)
    trader = MyForeignKey(MyUser, blank=True, null=True, related_name='traderanswer_dataroomdiscuss', on_delete=models.CASCADE)
    asktime = models.DateTimeField(blank=True, null=True)
    answertime = models.DateTimeField(blank=True, null=True)
    location = models.TextField(help_text='标注位置', blank=True, null=True)
    createuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usercreate_dataroomdiscuss')
    lastmodifyuser = MyForeignKey(MyUser, blank=True, null=True, related_name='usermodify_dataroomdiscuss')
    deleteduser = MyForeignKey(MyUser, blank=True, null=True, related_name='userdelete_dataroomdiscuss')
    datasource = MyForeignKey(DataSource, help_text='数据源', blank=True, default=1)

    class Meta:
        db_table = 'dataroom_user_discuss'

    def save(self, *args, **kwargs):
        if not self.is_deleted:
            if not self.datasource:
                raise InvestError(code=8888, msg='datasource有误')
            if not self.user:
                raise InvestError(code=2004, msg='user 不能为空')
            if not self.file.isFile:
                raise InvestError(code=2004, msg='必须是文件类型')
        return super(dataroom_user_discuss, self).save(*args, **kwargs)


