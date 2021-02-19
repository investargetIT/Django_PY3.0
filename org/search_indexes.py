#coding=utf-8
import base64
import datetime
import os

import chardet

from invest.settings import APILOG_PATH
from utils.somedef import getPdfWordContent, BaiDuAipGetImageWord
from haystack import indexes
import subprocess

from utils.util import logexcption
from .models import orgRemarks, orgAttachments
import docx

class orgRemarksIndex(indexes.SearchIndex, indexes.Indexable):
    """
        orgRemark索引类
    """
    # text表示被查询的字段，用户搜索的是这些字段的值，具体被索引的字段写在另一个文件里。
    text = indexes.CharField(document=True, use_template=True)

    # # 保存在索引库中的字段
    id = indexes.IntegerField(model_attr='id')
    org = indexes.IntegerField(model_attr='org_id', null=True)
    remark = indexes.CharField(model_attr='remark', null=True)
    createuser = indexes.IntegerField(model_attr='createuser_id', null=True)
    createdtime = indexes.DateTimeField(model_attr='createdtime', null=True)

    def get_model(self):
        """返回建立索引的模型类"""
        return orgRemarks

    def get_updated_field(self):
        return 'lastmodifytime'

    def index_queryset(self, using=None):
        """返回要建立索引的数据查询集"""
        return self.get_model().objects.filter(is_deleted=False)



class orgAttachmentsIndex(indexes.SearchIndex, indexes.Indexable):
    """
        orgRemark索引类
    """
    # text表示被查询的字段，用户搜索的是这些字段的值，具体被索引的字段写在另一个文件里。
    text = indexes.CharField(document=True, use_template=True)

    # # 保存在索引库中的字段
    id = indexes.IntegerField(model_attr='id')
    org = indexes.IntegerField(model_attr='org_id', null=True)
    bucket = indexes.CharField(model_attr='bucket', null=True)
    key = indexes.CharField(model_attr='key', null=True)
    realkey = indexes.CharField(model_attr='realkey', null=True)
    filename = indexes.CharField(model_attr='filename', null=True)
    fileContent = indexes.CharField(null=True)
    createuser = indexes.IntegerField(model_attr='createuser_id', null=True)
    createdtime = indexes.DateTimeField(model_attr='createdtime', null=True)

    def get_model(self):
        """返回建立索引的模型类"""

        return orgAttachments

    def get_updated_field(self):
        return 'lastmodifytime'

    def prepare_fileContent(self, obj):
        filecontent = None
        if obj.key:
            file_path = APILOG_PATH['orgAttachmentsPath'] + obj.key
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
            except Exception:
                logexcption(msg='机构附件内容提取失败')
        return filecontent

    def index_queryset(self, using=None):
        """返回要建立索引的数据查询集"""
        return self.get_model().objects.filter(is_deleted=False, org__is_deleted=False)