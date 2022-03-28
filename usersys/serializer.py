#coding=utf-8
from django.contrib.auth.models import Group, Permission
from rest_framework import serializers
from dataroom.models import dataroomdirectoryorfile
from mongoDoc.models import MergeFinanceData
from org.serializer import OrgCommonSerializer
from sourcetype.serializer import tagSerializer, countrySerializer, titleTypeSerializer, \
    PerformanceAppraisalLevelSerializer, TrainingStatusSerializer, TrainingTypeSerializer, industryGroupSerializer, \
    EducationSerializer, AuditStatusSerializer
from third.views.qiniufile import getUrlWithBucketAndKey
from utils.util import checkMobileTrue
from .models import MyUser, UserRelation, UnreachUser, UserRemarks, userAttachments, userEvents, \
    UserPerformanceAppraisalRecord, UserPersonnelRelations, UserTrainingRecords, UserMentorTrackingRecords, \
    UserWorkingPositionRecords, UserGetStarInvestor


class UnreachUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnreachUser
        fields = '__all__'


class PermissionSerializer(serializers.ModelSerializer):
    codename = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ('id', 'name', 'content_type', 'codename')

    def get_codename(self, obj):
        return str(obj.content_type.app_label) + '.' + obj.codename

# 用户基本信息
class UserNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyUser
        fields = ('id', 'usernameC', 'usernameE')

# 用户基本信息
class UserCommenSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    photourl = serializers.SerializerMethodField()
    title = titleTypeSerializer()
    mobile = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    org = OrgCommonSerializer()
    education = EducationSerializer()
    directSupervisor = UserNameSerializer()
    mentor = UserNameSerializer()
    userstatus = AuditStatusSerializer()
    indGroup = industryGroupSerializer

    class Meta:
        model = MyUser
        fields = ('id', 'usernameC', 'usernameE', 'tags', 'userstatus', 'photourl', 'title', 'onjob', 'mobile', 'workType',
                  'mobileAreaCode', 'email', 'is_active', 'org', 'indGroup', 'entryTime', 'bornTime', 'isMarried',
                  'directSupervisor', 'mentor', 'school', 'specialty', 'education', 'specialtyhobby', 'others')

    def get_tags(self, obj):
        qs = obj.tags.filter(tag_usertags__is_deleted=False)
        if qs.exists():
            return tagSerializer(qs, many=True).data
        return None

    def get_photourl(self, obj):
        if obj.photoKey:
            return getUrlWithBucketAndKey('image', obj.photoKey)
        else:
            return None

    def get_mobile(self, obj):
        if obj.mobile and obj.mobile not in ['', u'']:
            length = len(obj.mobile)
            if length > 4:
                center = str(obj.mobile)[0: (length - 4) // 2] + '****' + str(obj.mobile)[(length - 4) // 2 + 4:]
            else:
                center = '****'
            return center
        else:
            return None

    def get_email(self, obj):
        if obj.email and obj.email not in ['', u'']:
            index = str(obj.email).find('@')
            if index >= 0:
                center = '****' + str(obj.email)[index:]
            else:
                center = '****'
            return center
        else:
            return None

# 权限组基本信息
class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name')

# 权限组信息
class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'


class UserInfoSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    photourl = serializers.SerializerMethodField()
    mobiletrue = serializers.SerializerMethodField()
    country = countrySerializer()
    org = OrgCommonSerializer()

    class Meta:
        model = MyUser
        fields = ('usernameC', 'usernameE', 'org', 'department', 'mobile', 'mobileAreaCode', 'mobiletrue', 'email', 'wechat', 'title', 'workType',
                  'id', 'tags', 'userstatus', 'photourl', 'is_active', 'orgarea', 'country', 'onjob', 'hasIM', 'last_login', 'entryTime', 'bornTime', 'isMarried')
        depth = 1

    def get_tags(self, obj):
        qs = obj.tags.filter(tag_usertags__is_deleted=False)
        if qs.exists():
            return tagSerializer(qs,many=True).data
        return None

    def get_mobiletrue(self, obj):
        return checkMobileTrue(obj.mobile, obj.mobileAreaCode)

    def get_photourl(self, obj):
        if obj.photoKey:
            return getUrlWithBucketAndKey('image', obj.photoKey)
        else:
            return None

class InvestorUserSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    photourl = serializers.SerializerMethodField()
    mobiletrue = serializers.SerializerMethodField()
    country = countrySerializer()
    familiar = serializers.SerializerMethodField()

    class Meta:
        model = MyUser
        fields = ('usernameC', 'usernameE', 'org', 'department', 'mobile', 'mobileAreaCode', 'mobiletrue', 'email', 'wechat', 'title', 'workType',
                  'id', 'tags', 'userstatus', 'photourl', 'is_active', 'orgarea', 'country', 'onjob', 'last_login', 'familiar', 'entryTime', 'bornTime', 'isMarried')
        depth = 1

    def get_tags(self, obj):
        qs = obj.tags.filter(tag_usertags__is_deleted=False)
        if qs.exists():
            return tagSerializer(qs,many=True).data
        return None

    def get_mobiletrue(self, obj):
        return checkMobileTrue(obj.mobile, obj.mobileAreaCode)

    def get_photourl(self, obj):
        if obj.photoKey:
            return getUrlWithBucketAndKey('image', obj.photoKey)
        else:
            return None

    def get_familiar(self, obj):
        traderuser_id = self.context.get('traderuser_id')
        relations = obj.investor_relations.filter(traderuser_id=traderuser_id, is_deleted=False)
        if relations.exists():
            return relations.first().familiar_id
        return None


class UserAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = userAttachments
        fields = '__all__'


class UserEventSerializer(serializers.ModelSerializer):
    round = serializers.SerializerMethodField()
    class Meta:
        model = userEvents
        fields = '__all__'

    def get_round(self, obj):
        if obj.round:
            return obj.round
        else:
            if obj.com_id and obj.investDate:
                event_qs = MergeFinanceData.objects.all().filter(com_id=obj.com_id, date=str(obj.investDate)[:10])
                if event_qs.count() > 0:
                    event = event_qs.first()
                    return event.round
            return None

class UserRemarkCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRemarks
        fields = '__all__'


class UserRemarkSerializer(serializers.ModelSerializer):
    createuser = UserCommenSerializer()
    class Meta:
        model = UserRemarks
        fields = ('id', 'user', 'remark', 'createdtime', 'lastmodifytime', 'createuser')


class UserRemarkSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRemarks
        fields = ('id', 'remark', 'createdtime')


# 投资人交易师关系基本信息
class UserRelationSerializer(serializers.ModelSerializer):
    investoruser = UserInfoSerializer()
    traderuser = UserInfoSerializer()

    class Meta:
        model = UserRelation
        fields = ('id', 'investoruser', 'traderuser', 'relationtype', 'familiar')


# 用户关系全部信息
class UserRelationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRelation
        fields = '__all__'


# 权限组全部权限信息
class GroupDetailSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True)
    class Meta:
        model = Group
        fields = ('id', 'name', 'permissions')


class UserSimpleSerializer(serializers.ModelSerializer):
    org = OrgCommonSerializer()
    photourl = serializers.SerializerMethodField()

    class Meta:
        model = MyUser
        fields = ('id', 'usernameC', 'usernameE', 'org', 'photourl')

    def get_photourl(self, obj):
        if obj.photoKey:
            return getUrlWithBucketAndKey('image',obj.photoKey)
        else:
            return None


# 用户全部信息
class UserSerializer(serializers.ModelSerializer):
    groups = GroupSerializer(MyUser.groups,many=True)
    tags = serializers.SerializerMethodField()
    photourl = serializers.SerializerMethodField()
    resumeurl = serializers.SerializerMethodField()
    directSupervisor = UserSimpleSerializer()
    mentor = UserSimpleSerializer()

    class Meta:
        model = MyUser
        exclude = ('usercode', 'password', 'is_staff', 'is_superuser', 'createuser', 'createdtime', 'deletedtime', 'deleteduser',
                   'is_deleted', 'lastmodifyuser', 'lastmodifytime', 'registersource', 'datasource')
        depth = 1

    def get_tags(self, obj):
        qs = obj.tags.filter(tag_usertags__is_deleted=False)
        if qs.exists():
            return tagSerializer(qs,many=True).data
        return None

    def get_photourl(self, obj):
        if obj.photoKey:
            return getUrlWithBucketAndKey('image', obj.photoKey)
        else:
            return None

    def get_resumeurl(self, obj):
        if obj.resumeBucket and obj.resumeKey:
            return getUrlWithBucketAndKey(obj.resumeBucket, obj.resumeKey)
        else:
            return None


# 创建用户所需信息
class CreatUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyUser
        exclude = ('password',)


class UpdateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyUser
        exclude = ('password','datasource')


# 用户列表显示信息
class UserListSerializer(serializers.ModelSerializer):
    org = OrgCommonSerializer()
    indGroup = industryGroupSerializer()
    mobiletrue = serializers.SerializerMethodField()
    trader_relation = serializers.SerializerMethodField()
    trader_relations = serializers.SerializerMethodField()
    photourl = serializers.SerializerMethodField()
    directSupervisor = UserNameSerializer()
    mentor = UserNameSerializer()

    class Meta:
        model = MyUser
        fields = ('id','groups','tags','country', 'usernameC', 'usernameE', 'mobile', 'mobileAreaCode','mobiletrue', 'indGroup', 'trader_relations', 'workType',
                  'email', 'title', 'userstatus', 'org', 'trader_relation', 'photourl','is_active', 'wechat', 'directSupervisor', 'mentor', 'entryTime', 'bornTime', 'isMarried',
                  'school', 'specialty', 'education', 'specialtyhobby', 'others')

    def get_mobiletrue(self, obj):
        return checkMobileTrue(obj.mobile, obj.mobileAreaCode)

    def get_trader_relation(self, obj):
        usertrader = obj.investor_relations.filter(is_deleted=False, relationtype=True)
        if usertrader.exists():
            return UserTraderSimpleSerializer(usertrader.first()).data
        return None

    def get_trader_relations(self, obj):
        usertrader = obj.investor_relations.filter(is_deleted=False)
        if usertrader.exists():
            return UserTraderSimpleSerializer(usertrader, many=True).data
        return None

    def get_photourl(self, obj):
        if obj.photoKey:
            return getUrlWithBucketAndKey('image',obj.photoKey)
        else:
            return None


class UserTraderSimpleSerializer(serializers.ModelSerializer):
    traderuser = UserNameSerializer()

    class Meta:
        model = UserRelation
        fields = ('id', 'traderuser', 'familiar')

# 用户基本信息
class UserListCommenSerializer(serializers.ModelSerializer):
    photourl = serializers.SerializerMethodField()
    mobile = serializers.SerializerMethodField()
    indGroup = industryGroupSerializer()
    directSupervisor = UserNameSerializer()
    mentor = UserNameSerializer()
    email = serializers.SerializerMethodField()
    mobiletrue = serializers.SerializerMethodField()
    org = OrgCommonSerializer()
    trader_relation = serializers.SerializerMethodField()
    trader_relations = serializers.SerializerMethodField()

    class Meta:
        model = MyUser
        fields = ('id', 'usernameC', 'usernameE', 'tags', 'userstatus', 'photourl', 'title', 'onjob', 'mobile', 'mobileAreaCode', 'trader_relation', 'trader_relations',
                  'mobiletrue', 'email', 'is_active', 'org', 'indGroup', 'entryTime', 'bornTime', 'isMarried', 'directSupervisor', 'mentor', 'workType')


    def get_photourl(self, obj):
        if obj.photoKey:
            return getUrlWithBucketAndKey('image', obj.photoKey)
        else:
            return None

    def get_mobiletrue(self, obj):
        return checkMobileTrue(obj.mobile, obj.mobileAreaCode)

    def get_mobile(self, obj):
        if obj.mobile and obj.mobile not in ['', u'']:
            length = len(obj.mobile)
            if length > 4:
                center = str(obj.mobile)[0: (length - 4) // 2] + '****' + str(obj.mobile)[(length - 4) // 2 + 4:]
            else:
                center = '****'
            return center
        else:
            return None

    def get_email(self, obj):
        if obj.email and obj.email not in ['', u'']:
            index = str(obj.email).find('@')
            if index >= 0:
                center = '****' + str(obj.email)[index:]
            else:
                center = '****'
            return center
        else:
            return None

    def get_trader_relation(self, obj):
        usertrader = obj.investor_relations.filter(is_deleted=False, relationtype=True)
        if usertrader.exists():
            return UserTraderSimpleSerializer(usertrader.first()).data
        return None


    def get_trader_relations(self, obj):
        usertrader = obj.investor_relations.filter(is_deleted=False)
        if usertrader.exists():
            return UserTraderSimpleSerializer(usertrader, many=True).data
        return None

class UserPersonnelRelationsCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserPersonnelRelations
        fields = '__all__'


class UserPersonnelRelationsSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer()
    supervisorOrMentor = UserSimpleSerializer()

    class Meta:
        model = UserPersonnelRelations
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime')



class UserPerformanceAppraisalRecordCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserPerformanceAppraisalRecord
        fields = '__all__'


class UserPerformanceAppraisalRecordSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer()
    level = PerformanceAppraisalLevelSerializer()
    performanceTableUrl = serializers.SerializerMethodField()

    class Meta:
        model = UserPerformanceAppraisalRecord
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime')

    def get_performanceTableUrl(self, obj):
        if obj.performanceTableBucket and obj.performanceTableKey:
            return getUrlWithBucketAndKey(obj.performanceTableBucket, obj.performanceTableKey)
        else:
            return None


class UserWorkingPositionRecordsCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserWorkingPositionRecords
        fields = '__all__'


class UserWorkingPositionRecordsSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer()
    indGroup = industryGroupSerializer()
    title = titleTypeSerializer()

    class Meta:
        model = UserWorkingPositionRecords
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime')


class UserTrainingRecordsCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserTrainingRecords
        fields = '__all__'

class trainingFileSerializer(serializers.ModelSerializer):
    fileurl = serializers.SerializerMethodField()
    class Meta:
        model = dataroomdirectoryorfile
        exclude = ('is_deleted', 'deleteduser', 'deletedtime', 'lastmodifyuser', 'lastmodifytime',)

    def get_fileurl(self, obj):
        if obj.bucket and obj.key:
            return getUrlWithBucketAndKey(obj.bucket, obj.key)
        else:
            return None

class UserTrainingRecordsSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer()
    trainingStatus = TrainingStatusSerializer()
    trainingType = TrainingTypeSerializer()
    trainingfileobj = serializers.SerializerMethodField()

    class Meta:
        model = UserTrainingRecords
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime')

    def get_trainingfileobj(self, obj):
        if obj.trainingFile:
            if dataroomdirectoryorfile.objects.all().filter(is_deleted=False, id=obj.trainingFile).exists():
                file = dataroomdirectoryorfile.objects.all().filter(is_deleted=False, id=obj.trainingFile).first()
                return trainingFileSerializer(file).data
            else:
                return None
        else:
            return None

class UserMentorTrackingRecordsCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserMentorTrackingRecords
        fields = '__all__'


class UserMentorTrackingRecordsSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer()
    communicateUser = UserSimpleSerializer()


    class Meta:
        model = UserMentorTrackingRecords
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime')


class UserGetStarInvestorCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserGetStarInvestor
        fields = '__all__'


class UserGetStarInvestorSerializer(serializers.ModelSerializer):
    user = UserCommenSerializer()
    investor = UserCommenSerializer()

    class Meta:
        model = UserGetStarInvestor
        fields = '__all__'