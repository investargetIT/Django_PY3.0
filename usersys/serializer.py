#coding=utf-8
import re

from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

from mongoDoc.models import MergeFinanceData
from org.serializer import OrgCommonSerializer
from sourcetype.serializer import tagSerializer, countrySerializer, titleTypeSerializer
from third.views.qiniufile import getUrlWithBucketAndKey
from utils.util import checkMobileTrue
from .models import MyUser, UserRelation, UserFriendship, UnreachUser, UserRemarks, userAttachments, userEvents


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
class UserCommenSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    photourl = serializers.SerializerMethodField()
    title = titleTypeSerializer()
    mobile = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    org = OrgCommonSerializer()

    class Meta:
        model = MyUser
        fields = ('id', 'usernameC', 'usernameE', 'tags', 'userstatus', 'photourl', 'title', 'onjob', 'mobile', 'email',
                  'is_active', 'org')
        depth = 1

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

    class Meta:
        model = MyUser
        fields = ('usernameC', 'usernameE', 'org', 'department', 'mobile', 'mobileAreaCode', 'mobiletrue', 'email', 'wechat', 'title',
                  'id', 'tags', 'userstatus', 'photourl', 'is_active', 'orgarea', 'country', 'onjob', 'hasIM', 'last_login')
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
        fields = ('usernameC', 'usernameE', 'org', 'department', 'mobile', 'mobileAreaCode', 'mobiletrue', 'email', 'wechat', 'title',
                  'id', 'tags', 'userstatus', 'photourl', 'is_active', 'orgarea', 'country', 'onjob', 'last_login', 'familiar')
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


# 用户好友关系基本信息
class UserFriendshipSerializer(serializers.ModelSerializer):
    user = UserInfoSerializer()
    friend = UserInfoSerializer()

    class Meta:
        model = UserFriendship
        fields = ('id', 'user', 'friend', 'isaccept', 'datasource')
        read_only_fields = ('datasource',)


# 用户好友关系全部信息
class UserFriendshipDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFriendship
        fields = '__all__'


# 用户好友关系修改信息
class UserFriendshipUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFriendship
        fields = '__all__'
        read_only_fields = ('id', 'datasource', 'user', 'friend', 'createdtime', 'createuser', 'is_deleted')


# 权限组全部权限信息
class GroupDetailSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True)
    class Meta:
        model = Group
        fields = ('id', 'name', 'permissions')


# 用户全部信息
class UserSerializer(serializers.ModelSerializer):
    groups = GroupSerializer(MyUser.groups,many=True)
    tags = serializers.SerializerMethodField()
    photourl = serializers.SerializerMethodField()

    class Meta:
        model = MyUser
        exclude = ('usercode', 'is_staff', 'is_superuser', 'createuser', 'createdtime', 'deletedtime', 'deleteduser',
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
    mobiletrue = serializers.SerializerMethodField()
    trader_relation = serializers.SerializerMethodField()
    photourl = serializers.SerializerMethodField()

    class Meta:
        model = MyUser
        fields = ('id','groups','tags','country', 'department', 'usernameC', 'usernameE', 'mobile', 'mobileAreaCode','mobiletrue', 'indGroup',
                  'email', 'title', 'userstatus', 'org', 'trader_relation', 'photourl','is_active', 'hasIM', 'wechat')

    def get_mobiletrue(self, obj):
        return checkMobileTrue(obj.mobile, obj.mobileAreaCode)

    def get_trader_relation(self, obj):
        usertrader = obj.investor_relations.filter(relationtype=True, is_deleted=False)
        if usertrader.exists():
            return UserTraderSimpleSerializer(usertrader.first()).data
        return None

    def get_photourl(self, obj):
        if obj.photoKey:
            return getUrlWithBucketAndKey('image',obj.photoKey)
        else:
            return None


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

class UserTraderSimpleSerializer(serializers.ModelSerializer):
    traderuser = UserSimpleSerializer()

    class Meta:
        model = UserRelation
        fields = ('id', 'traderuser', 'familiar')

# 用户基本信息
class UserListCommenSerializer(serializers.ModelSerializer):
    photourl = serializers.SerializerMethodField()
    mobile = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    mobiletrue = serializers.SerializerMethodField()
    org = OrgCommonSerializer()

    class Meta:
        model = MyUser
        fields = ('id', 'usernameC', 'usernameE', 'tags', 'userstatus', 'photourl', 'title', 'onjob', 'mobile', 'mobileAreaCode',
                  'mobiletrue', 'email', 'is_active', 'org', 'indGroup')


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
