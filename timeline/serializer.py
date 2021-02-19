import datetime
from rest_framework import serializers

from proj.serializer import ProjSimpleSerializer
from sourcetype.serializer import transactionStatuSerializer
from timeline.models import timeline,timelineremark,timelineTransationStatu
from usersys.serializer import UserCommenSerializer


class TimeLineStatuCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = timelineTransationStatu
        fields = '__all__'


class TimeLineStatuSerializer(serializers.ModelSerializer):
    transationStatus = transactionStatuSerializer()
    remainingAlertDay = serializers.SerializerMethodField()

    class Meta:
        model = timelineTransationStatu
        fields = ('transationStatus','timeline','isActive','id','inDate','alertCycle','remainingAlertDay')

    def get_remainingAlertDay(self,obj):
        if obj.inDate:
            day = (obj.inDate - datetime.datetime.now()) / 3600 / 24
        else:
            day = None
        return day


class TimeLineSerializer(serializers.ModelSerializer):
    transationStatu = serializers.SerializerMethodField()

    class Meta:
        model = timeline
        fields = ('id', 'proj', 'investor','trader','isClose','closeDate','transationStatu')

    def get_transationStatu(self, obj):
        qs = obj.timeline_transationStatus.all().filter(is_deleted=False,isActive=True)
        if qs.exists():
            return TimeLineStatuSerializer(qs.first()).data
        return None


class TimeLineCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = timeline
        # fields = '__all__'
        exclude = ('is_deleted','deleteduser','deletedtime','lastmodifyuser','lastmodifytime',)


class TimeLineUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = timeline
        fields = ('isClose', 'closeDate', 'is_deleted','deleteduser','deletedtime','lastmodifyuser','lastmodifytime', 'trader')


class TimeLineRemarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = timelineremark
        fields = '__all__'


class TimeLineListSerializer_admin(serializers.ModelSerializer):
    investor = UserCommenSerializer()
    trader = UserCommenSerializer()
    proj = ProjSimpleSerializer()
    transationStatu = serializers.SerializerMethodField()
    supportor = serializers.SerializerMethodField()

    class Meta:
        model = timeline
        # fields = '__all__'
        exclude = ('is_deleted','deleteduser','deletedtime','lastmodifyuser','lastmodifytime','createuser','createdtime')


    def get_supportor(self, obj):
        user = obj.proj.supportUser
        if user.is_deleted:
            return None
        return UserCommenSerializer(user).data
    def get_transationStatu(self, obj):
        qs = obj.timeline_transationStatus.all().filter(is_deleted=False,isActive=True)
        if qs.exists():
            return TimeLineStatuSerializer(qs.first()).data
        return None


class TimeLineListSerializer_anonymous(serializers.ModelSerializer):
    proj = ProjSimpleSerializer()
    investor = UserCommenSerializer()
    transationStatu = serializers.SerializerMethodField()

    class Meta:
        model = timeline
        # fields = '__all__'
        exclude = ('is_deleted','deleteduser','deletedtime','lastmodifyuser','lastmodifytime','createuser','createdtime')

    def get_transationStatu(self, obj):
        qs = obj.timeline_transationStatus.all().filter(is_deleted=False,isActive=True)
        if qs.exists():
            return TimeLineStatuSerializer(qs.first()).data
        return None