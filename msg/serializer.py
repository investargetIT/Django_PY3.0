#coding=utf-8
import datetime

from django.shortcuts import render_to_response
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from dataroom.models import dataroom_User_file
from msg.models import message, schedule, webexUser, webexMeeting, InternOnlineTest
from proj.serializer import ProjCommonSerializer
from sourcetype.serializer import countrySerializer, orgAreaSerializer
from third.thirdconfig import webEX_webExID, webEX_password
from usersys.serializer import UserCommenSerializer,UserInfoSerializer


class MsgSerializer(serializers.ModelSerializer):
    html = serializers.SerializerMethodField()

    class Meta:
        model = message
        fields = '__all__'

    def get_html(self, objc):
        if objc.type == 12:
            try:
                dataroom_user_file = dataroom_User_file.objects.get(id=objc.sourceid, is_deleted=False, user__isnull=False)
            except Exception:
                return None
            vars = {'name': dataroom_user_file.user.usernameC,
                    'cli_domain': dataroom_user_file.datasource.domain,
                    'user_url': '%s/app/user/%s' % (dataroom_user_file.datasource.domain, objc.receiver.id),
                    'projectC': dataroom_user_file.dataroom.proj.projtitleC,
                    'projectE': dataroom_user_file.dataroom.proj.projtitleE,
                    'dataroom_url': '%s/app/dataroom/detail?id=%s&isClose=false&projectID=%s' % (
                        dataroom_user_file.datasource.domain, dataroom_user_file.dataroom.id, dataroom_user_file.dataroom.proj.id)}
            html = render_to_response('dataroomEmail_template_cn.html', vars).content
        else:
            html = None
        return html


class WebEXMeetingSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    class Meta:
        model = webexMeeting
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime')

    def get_url(self, objc):
        return 'https://investarget.webex.com.cn/investarget/p.php?AT=LI&WID={}&PW={}'.format(webEX_webExID, webEX_password)

    def get_status(self, objc):
        now = datetime.datetime.now()
        if objc.endDate <= now:
            return {'status': 0, 'msg': '已结束'}
        elif objc.startDate < now and objc.endDate > now:
            return {'status': 1, 'msg': '正在进行'}
        elif objc.startDate > now and (objc.startDate < (now + datetime.timedelta(hours=24))):
            return {'status': 2, 'msg': '即将开始'}
        else:
            return {'status': 3, 'msg': '暂未开始'}


class ScheduleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = schedule
        fields = '__all__'

class ScheduleMeetingSerializer(serializers.ModelSerializer):
    meeting = WebEXMeetingSerializer()
    class Meta:
        model = schedule
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime')


class ScheduleSerializer(serializers.ModelSerializer):
    user = UserInfoSerializer()
    createuser = UserCommenSerializer()
    country = countrySerializer()
    proj = ProjCommonSerializer()
    location = orgAreaSerializer()
    meeting = WebEXMeetingSerializer()
    class Meta:
        model = schedule
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime')


class WebEXUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = webexUser
        fields = '__all__'
        validators = [
            UniqueTogetherValidator(
                queryset=webexUser.objects.filter(is_deleted=False),
                fields=('meeting', 'email')
            )
        ]
class InternOnlineTestCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = InternOnlineTest
        fields = '__all__'

class InternOnlineTestSerializer(serializers.ModelSerializer):
    user = UserCommenSerializer()
    createuser = UserCommenSerializer()

    class Meta:
        model = InternOnlineTest
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime')