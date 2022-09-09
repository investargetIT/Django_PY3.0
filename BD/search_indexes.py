#coding=utf-8
from haystack import indexes
import os
from invest.settings import APILOG_PATH
from mongoDoc.models import ProjectData
from third.views.audioTransfer import getAudioFileTranslateTaskResult
from .models import WorkReport, WorkReportMarketMsg, ProjectBDComments, ProjectBD
import chardet
from utils.somedef import getPdfWordContent, BaiDuAipGetImageWord
from haystack import indexes
import subprocess
from utils.util import logexcption
import docx

class ProjectBDIndex(indexes.SearchIndex, indexes.Indexable):
    """
        WorkReport索引类
    """
    text = indexes.CharField(document=True, use_template=True)

    # # 保存在索引库中的字段
    id = indexes.IntegerField(model_attr='id')
    projectBD = indexes.IntegerField(model_attr='id', null=True)
    projectDesc = indexes.CharField(null=True)
    com_name = indexes.CharField(model_attr='com_name', null=True)
    createuser = indexes.IntegerField(model_attr='createuser_id', null=True)

    def get_model(self):
        """返回建立索引的模型类"""
        return ProjectBD

    def get_updated_field(self):
        return 'lastmodifytime'

    def prepare_projectDesc(self, obj):
        projectDesc = None
        if obj.source_type == 0:
            try:
                if len(ProjectData.objects.all().filter(**{'%s__%s' % ('com_name', 'icontains'): self.com_name})) >= 1:
                   mongo_project = ProjectData.objects.filter(com_name__contains=self.com_name).first()
                   projectDesc = mongo_project.com_des
            except Exception:
                logexcption(msg='行动计划全库项目介绍提取失败')
        return projectDesc

    def index_queryset(self, using=None):
        """返回要建立索引的数据查询集"""
        return self.get_model().objects.filter(is_deleted=False)


class ProjectBDCommentsIndex(indexes.SearchIndex, indexes.Indexable):
    """
        WorkReport索引类
    """
    text = indexes.CharField(document=True, use_template=True)

    # # 保存在索引库中的字段
    id = indexes.IntegerField(model_attr='id')
    comments = indexes.CharField(model_attr='comments', null=True)
    projectBD = indexes.IntegerField(model_attr='projectBD_id', null=True)
    fileContent = indexes.CharField(null=True)
    createuser = indexes.IntegerField(model_attr='createuser_id', null=True)

    def get_model(self):
        """返回建立索引的模型类"""
        return ProjectBDComments

    def get_updated_field(self):
        return 'lastmodifytime'

    def prepare_fileContent(self, obj):
        filecontent = None
        if obj.key:
            file_path = APILOG_PATH['projectBDCommentFilePath'] + obj.key
            try:
                if os.path.exists(file_path):
                    filename, type = os.path.splitext(file_path)
                    if type == '.docx':
                        doc = docx.Document(file_path)
                        filecontent = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
                    elif type == '.doc':
                        filecontent = subprocess.check_output(["antiword", file_path])
                    elif type == '.pdf':
                        filecontent = getPdfWordContent(file_path)
                    elif type in ['.png', '.jpg', '.jpeg']:
                        filecontent = BaiDuAipGetImageWord(file_path)
                    elif type == '.txt':
                        with open(file_path, "r") as f:
                            text = f.read()
                            type = chardet.detect(text)
                            filecontent = text.decode(type["encoding"], 'ignore')
                    elif type in ['.mp3', '.wav', '.flac', '.opus', '.m4a'] and obj.transid:
                        filecontent = getAudioFileTranslateTaskResult(obj.transid)
            except Exception:
                logexcption(msg='行动计划附件内容提取失败')
        return filecontent

    def index_queryset(self, using=None):
        """返回要建立索引的数据查询集"""
        return self.get_model().objects.filter(is_deleted=False, projectBD__is_deleted=False)



class WorkReportIndex(indexes.SearchIndex, indexes.Indexable):
    """
        WorkReport索引类
    """
    text = indexes.CharField(document=True, use_template=True)

    # # 保存在索引库中的字段
    id = indexes.IntegerField(model_attr='id')
    marketMsg = indexes.CharField(model_attr='marketMsg', null=True)
    report = indexes.IntegerField(model_attr='id', null=True)
    createuser = indexes.IntegerField(model_attr='createuser_id', null=True)

    def get_model(self):
        """返回建立索引的模型类"""
        return WorkReport

    def get_updated_field(self):
        return 'lastmodifytime'


    def index_queryset(self, using=None):
        """返回要建立索引的数据查询集"""
        return self.get_model().objects.filter(is_deleted=False, user__isnull=False)


class WorkReportMarketMsgIndex(indexes.SearchIndex, indexes.Indexable):
    """
        WorkReportMarketMsg索引类
    """
    text = indexes.CharField(document=True, use_template=True)

    # # 保存在索引库中的字段
    id = indexes.IntegerField(model_attr='id')
    marketMsg = indexes.CharField(model_attr='marketMsg', null=True)
    report = indexes.IntegerField(model_attr='report_id', null=True)
    createuser = indexes.IntegerField(model_attr='createuser_id', null=True)

    def get_model(self):
        """返回建立索引的模型类"""
        return WorkReportMarketMsg

    def get_updated_field(self):
        return 'lastmodifytime'


    def index_queryset(self, using=None):
        """返回要建立索引的数据查询集"""
        return self.get_model().objects.filter(is_deleted=False, report__is_deleted=False)