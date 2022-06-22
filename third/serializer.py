#coding=utf-8
from rest_framework import serializers

from third.models import AudioTranslateTaskRecord, QiNiuFileUploadRecord


class AudioTranslateTaskRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AudioTranslateTaskRecord
        fields = '__all__'

class AudioTranslateTaskRecordUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AudioTranslateTaskRecord
        fields = '__all__'
        read_only_fields = ('task_id', 'file_key', 'file_name', 'taskStatus', 'cretateUserId', 'createTime', 'is_deleted')


class QiNiuFileUploadRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = QiNiuFileUploadRecord
        exclude = ('is_deleted',)