#coding=utf-8
from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

from third.models import AudioTranslateTaskRecord


class AudioTranslateTaskRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AudioTranslateTaskRecord
        fields = '__all__'