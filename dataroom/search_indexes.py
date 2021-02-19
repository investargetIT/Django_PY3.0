#coding=utf-8
import os
from invest.settings import APILOG_PATH
from utils.somedef import getPdfWordContent
from haystack import indexes
from utils.util import logexcption
from .models import dataroomdirectoryorfile


class dataroomdirectoryorfileIndex(indexes.SearchIndex, indexes.Indexable):
    """
        dataroomdirectoryorfile索引类
    """
    text = indexes.CharField(document=True, use_template=True)

    # # 保存在索引库中的字段
    id = indexes.IntegerField(model_attr='id')
    dataroom = indexes.IntegerField(model_attr='dataroom_id', null=True)
    bucket = indexes.CharField(model_attr='bucket', null=True)
    parent = indexes.IntegerField(model_attr='parent_id', null=True)
    orderNO = indexes.IntegerField(model_attr='orderNO', null=True)
    size = indexes.IntegerField(model_attr='size', null=True)
    filename = indexes.CharField(model_attr='filename', null=True)
    realfilekey = indexes.CharField(model_attr='realfilekey', null=True)
    key = indexes.CharField(model_attr='key', null=True)
    isFile = indexes.BooleanField(null=True)
    fileContent = indexes.CharField(null=True)
    createuser = indexes.IntegerField(model_attr='createuser_id', null=True)

    def get_model(self):
        """返回建立索引的模型类"""

        return dataroomdirectoryorfile

    def get_updated_field(self):
        return 'lastmodifytime'

    def prepare_fileContent(self, obj):
        """obj 是django里的model实例"""
        filecontent = None
        if obj.isFile and obj.realfilekey:
            dataroomPath = os.path.join(APILOG_PATH['es_dataroomPDFPath'], 'dataroom_{}'.format(obj.dataroom_id))
            file_path = os.path.join(dataroomPath, obj.realfilekey)
            try:
                if os.path.exists(file_path):
                    filename, type = os.path.splitext(file_path)
                    if type == '.pdf':
                        filecontent = getPdfWordContent(file_path)
            except Exception:
                logexcption(msg='dataroom文件pdf内容提取失败')
        return filecontent

    def index_queryset(self, using=None):
        """返回要建立索引的数据查询集"""
        return self.get_model().objects.filter(is_deleted=False, dataroom__is_deleted=False, isFile=True)