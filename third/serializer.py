#coding=utf-8
from rest_framework import serializers

from third.models import AudioTranslateTaskRecord, QiNiuFileUploadRecord


class AudioTranslateTaskRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AudioTranslateTaskRecord
        fields = '__all__'


class QiNiuFileUploadRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = QiNiuFileUploadRecord
        exclude = ('is_deleted',)