from django.db.models import Q
from rest_framework import serializers

from BD.models import ProjectBDComments, ProjectBD, OrgBDComments, OrgBD, OrgBDBlack, ProjectBDManagers, \
    WorkReport, WorkReportProjInfo, OKR, OKRResult, WorkReportMarketMsg
from org.serializer import OrgCommonSerializer
from proj.models import project
from proj.serializer import ProjSimpleSerializer, ProjCommonSerializer
from sourcetype.serializer import BDStatusSerializer, orgAreaSerializer, tagSerializer, currencyTypeSerializer
from sourcetype.serializer import titleTypeSerializer
from third.models import QiNiuFileUploadRecord
from third.serializer import QiNiuFileUploadRecordSerializer
from third.views.qiniufile import getUrlWithBucketAndKey
from usersys.serializer import UserCommenSerializer, UserRemarkSimpleSerializer, UserAttachmentSerializer, \
    UserSimpleSerializer
from utils.logicJudge import is_projBDManager, is_userInvestor


class ProjectBDCommentsCreateSerializer(serializers.ModelSerializer):
    uploadstatus = serializers.SerializerMethodField()
    class Meta:
        model = ProjectBDComments
        fields = '__all__'
    def get_uploadstatus(self, obj):
        if obj.bucket and obj.key:
            qs = QiNiuFileUploadRecord.objects.filter(key=obj.key, is_deleted=False)
            if qs.exists():
                return QiNiuFileUploadRecordSerializer(qs, many=True).data
        return None

class ProjectBDCommentsSerializer(serializers.ModelSerializer):
    createuserobj = serializers.SerializerMethodField()
    uploadstatus = serializers.SerializerMethodField()
    class Meta:
        model = ProjectBDComments
        exclude = ('deleteduser', 'deletedtime', 'datasource', 'is_deleted')

    def get_createuserobj(self, obj):
        if obj.createuser:
            photourl = None
            if obj.createuser.photoKey:
                photourl = getUrlWithBucketAndKey(obj.createuser.photoBucket, obj.createuser.photoKey)
            return {'id': obj.createuser.id, 'usernameC': obj.createuser.usernameC, 'usernameE': obj.createuser.usernameE, 'photourl': photourl}
        else:
            return None
    def get_uploadstatus(self, obj):
        if obj.bucket and obj.key:
            qs = QiNiuFileUploadRecord.objects.filter(key=obj.key, is_deleted=False)
            if qs.exists():
                return QiNiuFileUploadRecordSerializer(qs, many=True).data
        return None

class ProjectBDManagersCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectBDManagers
        fields = '__all__'

class ProjectBDManagersSerializer(serializers.ModelSerializer):
    manager = UserCommenSerializer()
    class Meta:
        model = ProjectBDManagers
        exclude = ('deleteduser', 'deletedtime', 'datasource', 'is_deleted')

class ProjectBDCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectBD
        fields = '__all__'


class ProjectBDSerializer(serializers.ModelSerializer):
    BDComments = serializers.SerializerMethodField()
    location = orgAreaSerializer()
    usertitle = titleTypeSerializer()
    bd_status = BDStatusSerializer()
    manager = serializers.SerializerMethodField()
    contractors = UserCommenSerializer()
    financeCurrency = currencyTypeSerializer()

    class Meta:
        model = ProjectBD
        exclude = ('deleteduser', 'deletedtime', 'datasource', 'is_deleted')

    def get_manager(self, obj):
        qs = obj.ProjectBD_managers.filter(is_deleted=False)
        if qs.exists():
            return ProjectBDManagersSerializer(qs, many=True).data
        return None

    def get_BDComments(self, obj):
        user_id = self.context.get('user_id')
        manage = self.context.get('manage')
        indGroup_id = self.context.get('indGroup_id')
        if manage or is_projBDManager(user_id, obj) or (obj.indGroup and obj.indGroup.id == indGroup_id):
            qs = obj.ProjectBD_comments.filter(is_deleted=False).order_by('-createdtime')
            if qs.exists():
                return ProjectBDCommentsSerializer(qs, many=True).data
        return None


class OrgBDCommentsCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgBDComments
        fields = '__all__'


class OrgBDCommentsSerializer(serializers.ModelSerializer):
    createuser = UserSimpleSerializer()

    class Meta:
        model = OrgBDComments
        fields = ('comments','id','createdtime','orgBD', 'createuser', 'isPMComment')


class OrgBDCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgBD
        fields = '__all__'


class OrgBDSerializer(serializers.ModelSerializer):
    org = OrgCommonSerializer()
    proj = ProjSimpleSerializer()
    BDComments = serializers.SerializerMethodField()
    usertitle = titleTypeSerializer()
    cardurl = serializers.SerializerMethodField()
    userreamrk = serializers.SerializerMethodField()
    userattachment = serializers.SerializerMethodField()
    manager = UserSimpleSerializer()
    userinfo = serializers.SerializerMethodField()
    createuser = UserSimpleSerializer()

    class Meta:
        model = OrgBD
        exclude = ('deleteduser', 'deletedtime', 'datasource', 'is_deleted', 'usermobile')

    def get_BDComments(self, obj):
        qs = obj.OrgBD_comments.filter(is_deleted=False)
        if qs.exists():
            return OrgBDCommentsSerializer(qs,many=True).data
        return None

    def get_cardurl(self, obj):
        if obj.bduser:
            if obj.bduser.cardKey:
                return getUrlWithBucketAndKey('image', obj.bduser.cardKey)
        return None

    def get_userreamrk(self, obj):
        if obj.bduser:
            return UserRemarkSimpleSerializer(obj.bduser.user_remarks.all().filter(is_deleted=False), many=True).data
        return None

    def get_userattachment(self, obj):
        if obj.bduser:
            return UserAttachmentSerializer(obj.bduser.user_userAttachments.all().filter(is_deleted=False), many=True).data
        return None

    def get_userinfo(self, obj):
        user_id = self.context.get("user_id")
        info = {'email': None, 'mobile': None, 'wechat': None, 'tags':None, 'photourl': None, 'cardurl': None}
        if obj.bduser:
            tags = obj.bduser.tags.filter(tag_usertags__is_deleted=False)
            if tags.exists():
                info['tags'] = tagSerializer(tags, many=True).data
            if obj.bduser.photoKey:
                info['photourl'] = getUrlWithBucketAndKey('image', obj.bduser.photoKey)
            if obj.bduser.photoKey:
                info['cardurl'] = getUrlWithBucketAndKey('image', obj.bduser.cardKey)
            if user_id:
                if obj.manager.id == user_id or is_userInvestor(obj.bduser, user_id):
                    info['email'] = obj.bduser.email
                    info['mobile'] = obj.bduser.mobile
                    info['wechat'] = obj.bduser.wechat
        return info


class OrgBDBlackSerializer(serializers.ModelSerializer):
    org = OrgCommonSerializer()
    proj = ProjSimpleSerializer()
    createuser = UserCommenSerializer()

    class Meta:
        model = OrgBDBlack
        exclude = ('deleteduser', 'deletedtime', 'datasource', 'is_deleted')


class OrgBDBlackCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgBDBlack
        fields = '__all__'



class WorkReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkReport
        fields = '__all__'


class WorkReportSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer()
    marketMsgs =  serializers.SerializerMethodField()

    class Meta:
        model = WorkReport
        exclude = ('deleteduser', 'deletedtime', 'datasource', 'is_deleted', 'createuser')

    def get_marketMsgs(self, obj):
        return WorkReportMarketMsgSerializer(obj.report_marketmsg.filter(is_deleted=False), many=True).data


class WorkReportMarketMsgCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkReportMarketMsg
        fields = '__all__'


class WorkReportMarketMsgSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkReportMarketMsg
        exclude = ('deleteduser', 'deletedtime', 'datasource', 'is_deleted', 'createuser')


class WorkReportProjInfoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkReportProjInfo
        fields = '__all__'


class WorkReportProjInfoSerializer(serializers.ModelSerializer):
    proj = ProjSimpleSerializer()

    class Meta:
        model = WorkReportProjInfo
        exclude = ('deleteduser', 'deletedtime', 'datasource', 'is_deleted', 'createuser')


class OKRCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OKR
        fields = '__all__'


class OKRSerializer(serializers.ModelSerializer):
    class Meta:
        model = OKR
        exclude = ('deleteduser', 'deletedtime', 'datasource', 'is_deleted')


class OKRResultCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OKRResult
        fields = '__all__'


class OKRResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = OKRResult
        exclude = ('deleteduser', 'deletedtime', 'datasource', 'is_deleted', 'createuser')


class orgBDProjSerializer(serializers.ModelSerializer):
    proj = serializers.SerializerMethodField()
    count = serializers.IntegerField()
    created = serializers.DateTimeField()
    class Meta:
        model = OrgBD
        fields = ('proj', 'count', 'created')

    def get_proj(self, obj):
        if obj.get('proj'):
            proj = project.objects.get(id=obj['proj'])
            return ProjCommonSerializer(proj).data
        else:
            return None
