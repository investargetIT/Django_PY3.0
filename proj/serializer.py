from rest_framework import serializers

from proj.models import project, finance, attachment, projServices, projectIndustries, projTraders, \
    projectDiDiRecord, projcomments
from sourcetype.serializer import tagSerializer, transactionTypeSerializer, serviceSerializer, countrySerializer, \
    industryWithPIndustrySerializer, countryWithContinentSerializer, DidiOrderTypeSerializer, currencyTypeSerializer, \
    ProjectStatusSerializer
from third.models import QiNiuFileUploadRecord
from third.serializer import QiNiuFileUploadRecordSerializer
from third.views.qiniufile import getUrlWithBucketAndKey
from usersys.serializer import UserCommenSerializer, UserNameSerializer


class ProjSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = project
        fields = ('id', 'projtitleC', 'projtitleE', 'realname', 'financeAmount', 'financeAmount_USD', 'country', 'projstatus', 'isHidden', 'lastProject', 'publishDate','projectBD')


class ProjTradersCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = projTraders
        fields = '__all__'

class ProjTradersSerializer(serializers.ModelSerializer):
    user = UserCommenSerializer()
    class Meta:
        model = projTraders
        fields = '__all__'

class ProjTradersListSerializer(serializers.ModelSerializer):

    class Meta:
        model = projTraders
        exclude = ('datasource', 'is_deleted', 'deletedtime', 'deleteduser')


class ProjIndustrySerializer(serializers.ModelSerializer):
    nameC = serializers.SerializerMethodField()
    nameE = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    industry  = industryWithPIndustrySerializer()

    class Meta:
        model = projectIndustries
        fields = ('industry','bucket','key','url','nameC','nameE')

    def get_url(self, obj):
        if obj.key:
            return  getUrlWithBucketAndKey('image', obj.key)
        return None

    def get_nameC(self, obj):
        if obj.industry.industryC:
            return obj.industry.industryC
        return None

    def get_nameE(self, obj):
        if obj.industry.industryE:
            return obj.industry.industryE
        return None


class ProjIndustryListSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = projectIndustries
        fields = ('id', 'industry', 'bucket', 'key', 'url')

    def get_url(self, obj):
        if obj.key:
            return  getUrlWithBucketAndKey('image', obj.key)
        return None

class ProjIndustryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = projectIndustries
        fields = '__all__'


class FinanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = finance
        fields = '__all__'
        # exclude = ('id','proj','deleteduser','deletedtime','createuser','createdtime','lastmodifyuser','lastmodifytime','is_deleted')


class FinanceChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = finance
        exclude = ('datasource',)


class FinanceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = finance
        fields = '__all__'


class ProjServiceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = projServices
        fields = '__all__'


class ProjFinanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = finance
        exclude = ('deleteduser','deletedtime','createuser','createdtime','lastmodifyuser','lastmodifytime',)


class ProjAttachmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = attachment
        fields = '__all__'


class ProjAttachmentSerializer(serializers.ModelSerializer):
    uploadstatus = serializers.SerializerMethodField()
    class Meta:
        model = attachment
        exclude = ('deleteduser', 'deletedtime', 'createuser', 'createdtime', 'lastmodifyuser', 'lastmodifytime',)

    def get_uploadstatus(self, obj):
        if obj.bucket and obj.key:
            qs = QiNiuFileUploadRecord.objects.filter(key=obj.key, is_deleted=False)
            if qs.exists():
                return QiNiuFileUploadRecordSerializer(qs, many=True).data
        return None
class ProjSerializer(serializers.ModelSerializer):
    supportUser = UserCommenSerializer()
    PM = UserCommenSerializer()
    projTraders = serializers.SerializerMethodField()
    proj_finances = ProjFinanceSerializer(many=True)
    proj_attachment = ProjAttachmentSerializer(many=True)
    lastProject = ProjSimpleSerializer()

    class Meta:
        model = project
        exclude = ('isSendEmail','datasource',)
        depth = 1

    def get_projTraders(self, obj):
        qs = obj.proj_traders.filter(is_deleted=False, user__isnull=False)
        if qs.exists():
            return ProjTradersSerializer(qs, many=True).data
        return None


class ProjCommonSerializer(serializers.ModelSerializer):
    country = countrySerializer()
    tags = serializers.SerializerMethodField()
    industries = serializers.SerializerMethodField()
    lastProject = ProjSimpleSerializer()
    PM = UserNameSerializer()
    createuser = UserNameSerializer()
    projTraders = serializers.SerializerMethodField()
    currency = currencyTypeSerializer()
    projstatus = ProjectStatusSerializer()

    class Meta:
        model = project
        fields = ('id','industries','projtitleC','projtitleE','tags', 'realname', 'currency', 'financeAmount','financeAmount_USD','country','projstatus','isHidden', 'PM', 'createuser','projTraders','lastProject','publishDate','createdtime','projectBD')

    def get_tags(self, obj):
        qs = obj.tags.filter(tag_projects__is_deleted=False, is_deleted=False)
        if qs.exists():
            return tagSerializer(qs,many=True).data
        return None

    def get_industries(self, obj):
        qs = obj.project_industries.filter(is_deleted=False)
        if qs.exists():
            return ProjIndustrySerializer(qs,many=True).data
        return None
    def get_projTraders(self, obj):
        qs = obj.proj_traders.filter(is_deleted=False, user__isnull=False)
        if qs.exists():
            return ProjTradersSerializer(qs, many=True).data
        return None


class ProjCreatSerializer(serializers.ModelSerializer):
    class Meta:
        model = project
        fields = '__all__'



# list
class ProjListSerializer(serializers.ModelSerializer):
    industries = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    projTraders = serializers.SerializerMethodField()

    class Meta:
        model = project
        fields = ('id','industries','projtitleC','projtitleE', 'realname', 'currency','financeAmount','financeAmount_USD', 'tags', 'country','projstatus','isHidden','publishDate','createdtime','PM','createuser','projTraders','projectBD')

    def get_industries(self, obj):
        qs = obj.project_industries.filter(is_deleted=False)
        if qs.exists():
            return ProjIndustryListSerializer(qs,many=True).data
        return None

    def get_tags(self, obj):
        qs = obj.project_tags.filter(is_deleted=False, tag__is_deleted=False)
        if qs.exists():
            return qs.values_list('tag', flat=True)
        return None

    def get_projTraders(self, obj):
        qs = obj.proj_traders.filter(is_deleted=False, user__isnull=False)
        if qs.exists():
            return ProjTradersListSerializer(qs, many=True).data
        return None

#detail
class ProjDetailSerializer_withoutsecretinfo(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    service = serializers.SerializerMethodField()
    industries = serializers.SerializerMethodField()
    country = countryWithContinentSerializer()
    transactionType = serializers.SerializerMethodField()
    finance = serializers.SerializerMethodField()
    attachment = serializers.SerializerMethodField()
    linkpdfurl = serializers.SerializerMethodField()
    lastProject = ProjSimpleSerializer()
    PM = UserCommenSerializer()
    projTraders = serializers.SerializerMethodField()
    createuser = UserCommenSerializer()
    currency = currencyTypeSerializer()
    projstatus = ProjectStatusSerializer()

    class Meta:
        model = project
        exclude = ('supportUser', 'phoneNumber', 'email', 'contactPerson', 'lastmodifyuser', 'deleteduser', 'deletedtime', 'datasource','isSendEmail')


    def get_service(self, obj):
        qs = obj.service.filter(service_projects__is_deleted=False)
        if qs.exists():
            return serviceSerializer(qs, many=True).data
        return None

    def get_tags(self, obj):
        qs = obj.tags.filter(tag_projects__is_deleted=False, is_deleted=False)
        if qs.exists():
            return tagSerializer(qs,many=True).data
        return None

    def get_industries(self, obj):
        qs = obj.project_industries.filter(is_deleted=False)
        if qs.exists():
            return ProjIndustrySerializer(qs,many=True).data
        return None

    def get_transactionType(self, obj):
        qs = obj.transactionType.filter(transactionType_projects__is_deleted=False)
        if qs.exists():
            return transactionTypeSerializer(qs,many=True).data
        return None

    def get_finance(self, obj):
        if obj.financeIsPublic:
            usertrader = obj.proj_finances.filter(is_deleted=False)
            if usertrader.exists():
                return FinanceSerializer(usertrader, many=True).data
        return None

    def get_attachment(self, obj):
        usertrader = obj.proj_attachment.filter(is_deleted=False)
        if usertrader.exists():
            return ProjAttachmentSerializer(usertrader, many=True).data
        return None
    def get_linkpdfurl(self, obj):
        return None

    def get_projTraders(self, obj):
        qs = obj.proj_traders.filter(is_deleted=False, user__isnull=False)
        if qs.exists():
            return ProjTradersSerializer(qs, many=True).data
        return None

class ProjDetailSerializer_all(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    service = serializers.SerializerMethodField()
    industries = serializers.SerializerMethodField()
    transactionType = serializers.SerializerMethodField()
    finance = serializers.SerializerMethodField()
    attachment = serializers.SerializerMethodField()
    country = countryWithContinentSerializer()
    supportUser = UserCommenSerializer()
    PM = UserCommenSerializer()
    createuser = UserCommenSerializer()
    projTraders = serializers.SerializerMethodField()
    linkpdfurl = serializers.SerializerMethodField()
    lastProject = ProjSimpleSerializer()
    currency = currencyTypeSerializer()
    projstatus = ProjectStatusSerializer()

    class Meta:
        model = project
        exclude = ('lastmodifyuser', 'deleteduser', 'deletedtime', 'datasource','isSendEmail',)

    def get_service(self, obj):
        qs = obj.service.filter(service_projects__is_deleted=False)
        if qs.exists():
            return serviceSerializer(qs, many=True).data
        return None

    def get_projTraders(self, obj):
        qs = obj.proj_traders.filter(is_deleted=False, user__isnull=False)
        if qs.exists():
            return ProjTradersSerializer(qs, many=True).data
        return None

    def get_tags(self, obj):
        qs = obj.tags.filter(tag_projects__is_deleted=False, is_deleted=False)
        if qs.exists():
            return tagSerializer(qs,many=True).data
        return None

    def get_industries(self, obj):
        qs = obj.project_industries.filter(is_deleted=False)
        if qs.exists():
            return ProjIndustrySerializer(qs,many=True).data
        return None

    def get_transactionType(self, obj):
        qs = obj.transactionType.filter(transactionType_projects__is_deleted=False)
        if qs.exists():
            return transactionTypeSerializer(qs,many=True).data
        return None

    def get_finance(self, obj):
        usertrader = obj.proj_finances.filter(is_deleted=False)
        if usertrader.exists():
            return FinanceSerializer(usertrader, many=True).data
        return None

    def get_attachment(self, obj):
        usertrader = obj.proj_attachment.filter(is_deleted=False)
        if usertrader.exists():
            return ProjAttachmentSerializer(usertrader, many=True).data
        return None

    def get_linkpdfurl(self, obj):
        return None


class DiDiRecordSerializer(serializers.ModelSerializer):
    proj = ProjSimpleSerializer()
    orderType = DidiOrderTypeSerializer()
    class Meta:
        model = projectDiDiRecord
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime', 'lastmodifytime')

class TaxiRecordCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = projectDiDiRecord
        fields = '__all__'

class ProjCommentsSerializer(serializers.ModelSerializer):
    proj = ProjSimpleSerializer()
    class Meta:
        model = projcomments
        exclude = ('deleteduser', 'datasource', 'is_deleted', 'deletedtime')

class ProjCommentsCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = projcomments
        fields = '__all__'