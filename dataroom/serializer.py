from rest_framework import serializers

from dataroom.models import dataroom, dataroomdirectoryorfile, dataroom_User_file, dataroom_User_template, \
    dataroomUserSeeFiles, dataroom_user_discuss, dataroom_user_readFileRecord
from proj.serializer import ProjCommonSerializer
from third.models import QiNiuFileUploadRecord
from third.serializer import QiNiuFileUploadRecordSerializer
from third.views.qiniufile import getUrlWithBucketAndKey
from usersys.serializer import UserInfoSerializer, UserSimpleSerializer, UserOrgInfoSerializer


class DataroomCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = dataroom
        fields = '__all__'


class DataroomSerializer(serializers.ModelSerializer):
    proj = ProjCommonSerializer()
    class Meta:
        model = dataroom
        exclude = ('is_deleted', 'deleteduser', 'deletedtime', 'lastmodifyuser', 'lastmodifytime',)

class DataroomdirectoryorfileCreateSerializer(serializers.ModelSerializer):
    uploadstatus = serializers.SerializerMethodField()
    class Meta:
        model = dataroomdirectoryorfile
        fields = '__all__'

    def get_uploadstatus(self, obj):
        if obj.bucket and obj.key:
            qs = QiNiuFileUploadRecord.objects.filter(key=obj.key, is_deleted=False)
            if qs.exists():
                return QiNiuFileUploadRecordSerializer(qs, many=True).data
        return None

class DataroomdirectoryorfileUpdateSerializer(serializers.ModelSerializer):
    uploadstatus = serializers.SerializerMethodField()

    class Meta:
        model = dataroomdirectoryorfile
        fields = '__all__'
        read_only_fields = ('datasource','createuser','createtime','isFile','dataroom','key')

    def get_uploadstatus(self, obj):
        if obj.bucket and obj.key:
            qs = QiNiuFileUploadRecord.objects.filter(key=obj.key, is_deleted=False)
            if qs.exists():
                return QiNiuFileUploadRecordSerializer(qs, many=True).data
        return None


class DataroomdirectoryorfileSerializer(serializers.ModelSerializer):
    fileurl = serializers.SerializerMethodField()
    uploadstatus = serializers.SerializerMethodField()
    class Meta:
        model = dataroomdirectoryorfile
        exclude = ('is_deleted', 'deleteduser', 'deletedtime', 'lastmodifyuser', 'lastmodifytime',)

    def get_fileurl(self, obj):
        if obj.bucket and obj.key:
            return getUrlWithBucketAndKey(obj.bucket, obj.key)
        else:
            return None
    def get_uploadstatus(self, obj):
        if obj.bucket and obj.key:
            qs = QiNiuFileUploadRecord.objects.filter(key=obj.key, is_deleted=False)
            if qs.exists():
                return QiNiuFileUploadRecordSerializer(qs, many=True).data
        return None

class DataroomdirectoryorfilePathSerializer(serializers.ModelSerializer):
    fileurl = serializers.SerializerMethodField()
    filepath = serializers.SerializerMethodField()
    uploadstatus = serializers.SerializerMethodField()
    class Meta:
        model = dataroomdirectoryorfile
        exclude = ('is_deleted', 'deleteduser', 'deletedtime', 'lastmodifyuser', 'lastmodifytime',)

    def get_fileurl(self, obj):
        if obj.bucket and obj.key:
            return getUrlWithBucketAndKey(obj.bucket, obj.key)
        else:
            return None

    def get_filepath(self, obj):
        if obj.parent:
            return self.get_filepath(obj.parent) + '/' + obj.filename
        else:
            return obj.filename

    def get_uploadstatus(self, obj):
        if obj.bucket and obj.key:
            qs = QiNiuFileUploadRecord.objects.filter(key=obj.key, is_deleted=False)
            if qs.exists():
                return QiNiuFileUploadRecordSerializer(qs, many=True).data
        return None

class User_DataroomfileCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = dataroom_User_file
        fields = '__all__'

class User_DataroomSerializer(serializers.ModelSerializer):
    user = UserOrgInfoSerializer()

    class Meta:
        model = dataroom_User_file
        fields = ('id', 'dataroom', 'user', 'lastgettime', 'lastdowntime', 'lastdownsize')

class User_DataroomfileSerializer(serializers.ModelSerializer):
    files = serializers.SerializerMethodField()

    class Meta:
        model = dataroom_User_file
        fields = ('id', 'dataroom', 'user', 'files', 'lastgettime', 'lastdowntime', 'lastdownsize')

    def get_files(self, obj):
        seefiles = dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile=obj)
        if seefiles.exists():
            files = dataroomdirectoryorfile.objects.filter(id__in=seefiles.values_list('file_id'))
            return DataroomdirectoryorfileSerializer(files, many=True).data
        else:
            return None

class User_DataroomfileFileIdsSerializer(serializers.ModelSerializer):
    files = serializers.SerializerMethodField()
    class Meta:
        model = dataroom_User_file
        fields = ('id', 'dataroom', 'user', 'files', 'lastgettime', 'lastdowntime', 'lastdownsize')
    def get_files(self, obj):
        seefiles = dataroomUserSeeFiles.objects.filter(is_deleted=False, dataroomUserfile=obj)
        if seefiles.exists():
            return seefiles.values_list('file_id', flat=True)
        else:
            return None

class User_DataroomTemplateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = dataroom_User_template
        fields = '__all__'

class User_DataroomSeefilesCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = dataroomUserSeeFiles
        fields = '__all__'

class User_DataroomSeefilesSerializer(serializers.ModelSerializer):
    file = DataroomdirectoryorfileSerializer()
    class Meta:
        model = dataroomUserSeeFiles
        fields = ('id', 'file', 'createdtime')

class User_DataroomTemplateSerializer(serializers.ModelSerializer):
    dataroomUserfile = User_DataroomfileFileIdsSerializer()

    class Meta:
        model = dataroom_User_template
        fields = ('id', 'dataroom', 'user', 'dataroomUserfile', 'password')


class DataroomUserDiscussCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = dataroom_user_discuss
        exclude = ('trader', 'answertime', 'answer')

class DataroomUserDiscussUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = dataroom_user_discuss
        exclude = ('user', 'asktime', 'question')


class DataroomUserDiscussSerializer(serializers.ModelSerializer):
    file = DataroomdirectoryorfileSerializer()
    user = UserSimpleSerializer()
    trader = UserSimpleSerializer()

    class Meta:
        model = dataroom_user_discuss
        exclude = ('is_deleted', 'deleteduser', 'deletedtime', 'lastmodifyuser', 'lastmodifytime',)


class DataroomUserReadFileRecordSerializer(serializers.ModelSerializer):

    class Meta:
        model = dataroom_user_readFileRecord
        exclude = ('is_deleted', 'deleteduser', 'deletedtime', 'lastmodifyuser', 'lastmodifytime',)