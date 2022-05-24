#coding=utf-8
from rest_framework import serializers

from third.models import QiNiuFileUploadRecord


class QiNiuFileUploadRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = QiNiuFileUploadRecord
        exclude = ('is_deleted',)