#coding=utf-8
from haystack import indexes
from .models import WorkReport, WorkReportMarketMsg


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