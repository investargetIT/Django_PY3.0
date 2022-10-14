from rest_framework import serializers

from sourcetype.models import TransactionType, TransactionPhases, OrgArea, Tag, Industry, \
    CurrencyType, \
    AuditStatus, ProjectStatus, OrgType, ClientType, TitleType, Country, \
    DataSource, webmenu, CharacterType, orgtitletable, Service, OrgAttribute, BDStatus, \
    AndroidAppVersion, OrgBdResponse, \
    OrgLevelType, FamiliarLevel, IndustryGroup, DidiOrderType, Education, PerformanceAppraisalLevel, TrainingType, \
    TrainingStatus, ProjProgressContrastTable
from third.views.qiniufile import getUrlWithBucketAndKey


class AuditStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditStatus
        exclude = ('is_deleted',)


class ProjectStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectStatus
        exclude = ('is_deleted',)


class OrgBdResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgBdResponse
        exclude = ('is_deleted',)

class DidiOrderTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DidiOrderType
        exclude = ('is_deleted',)


class OrgLevelTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgLevelType
        exclude = ('is_deleted',)


class FamiliarLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamiliarLevel
        exclude = ('is_deleted',)


class orgTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgType
        exclude = ('is_deleted',)


class BDStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = BDStatus
        exclude = ('is_deleted',)


class characterTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CharacterType
        exclude = ('is_deleted',)

class clientTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientType
        exclude = ('is_deleted',)


class titleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TitleType
        exclude = ('is_deleted',)


class countrySerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Country
        exclude = ('is_deleted','datasource')

    def get_url(self, obj):
        if not obj.key:
            return None
        return getUrlWithBucketAndKey('image', obj.key)

class countryWithContinentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    parent = countrySerializer()

    class Meta:
        model = Country
        exclude = ('is_deleted','datasource')

    def get_url(self, obj):
        if not obj.key:
            return None
        return getUrlWithBucketAndKey('image', obj.key)

class orgAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgAttribute
        exclude = ('is_deleted',)


class currencyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyType
        exclude = ('is_deleted',)


class industrySerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Industry
        exclude = ('is_deleted','datasource')

    def get_url(self, obj):
        if not obj.key:
            return getUrlWithBucketAndKey('image', '040.jpg')
        return getUrlWithBucketAndKey('image', obj.key)


class industryWithPIndustrySerializer(serializers.ModelSerializer):
    Pindustry = industrySerializer()

    class Meta:
        model = Industry
        exclude = ('is_deleted','datasource')


class tagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        exclude = ('is_deleted','datasource')

class industryGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndustryGroup
        exclude = ('is_deleted',)


class serviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        exclude = ('is_deleted',)

class projProgressContrastTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjProgressContrastTable
        exclude = ('is_deleted',)


class orgAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgArea
        exclude = ('is_deleted',)


class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        exclude = ('is_deleted',)

class PerformanceAppraisalLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceAppraisalLevel
        exclude = ('is_deleted',)


class transactionPhasesSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionPhases
        exclude = ('is_deleted',)


class transactionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionType
        exclude = ('is_deleted',)


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        exclude = ('is_deleted',)


class WebMenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = webmenu
        exclude = ('is_deleted',)

class OrgtitletableSerializer(serializers.ModelSerializer):
    class Meta:
        model = orgtitletable
        exclude = ('is_deleted',)
        depth = 1

class TrainingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingType
        exclude = ('is_deleted',)

class TrainingStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingStatus
        exclude = ('is_deleted',)


class AndroidAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = AndroidAppVersion
        exclude = ('is_deleted',)