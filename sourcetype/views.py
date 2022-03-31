#coding=utf-8
import traceback
from functools import reduce
from django.db import transaction
from rest_framework import filters
from rest_framework import viewsets

from sourcetype.models import Tag, TitleType, DataSource, Country, Industry, TransactionType, \
    TransactionPhases, OrgArea, CurrencyType, OrgType, CharacterType, ProjectStatus, orgtitletable, \
    webmenu, Service, OrgAttribute, BDStatus, AndroidAppVersion, OrgBdResponse, OrgLevelType, FamiliarLevel, \
    IndustryGroup, DidiOrderType, Education, PerformanceAppraisalLevel, TrainingType, TrainingStatus
from sourcetype.serializer import tagSerializer, countrySerializer, industrySerializer, \
    titleTypeSerializer, DataSourceSerializer, orgAreaSerializer, transactionTypeSerializer, \
    transactionPhasesSerializer, \
    currencyTypeSerializer, orgTypeSerializer, characterTypeSerializer, ProjectStatusSerializer, \
    OrgtitletableSerializer, WebMenuSerializer, serviceSerializer, orgAttributeSerializer, \
    BDStatusSerializer, AndroidAppSerializer, OrgBdResponseSerializer, OrgLevelTypeSerializer, FamiliarLevelSerializer, \
    industryGroupSerializer, PerformanceAppraisalLevelSerializer, EducationSerializer, TrainingTypeSerializer, \
    TrainingStatusSerializer
from utils.customClass import  JSONResponse, InvestError
from utils.util import SuccessResponse, InvestErrorResponse, ExceptionResponse, returnListChangeToLanguage, \
    catchexcption, loginTokenIsAvailable, removeDuclicates


class TagView(viewsets.ModelViewSet):
    """
        list:获取所有标签
        create:新增标签
        update:修改标签
        destroy:删除标签
    """
    queryset = Tag.objects.all().filter(is_deleted=False)
    serializer_class = tagSerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            source = request.META.get('HTTP_SOURCE', 1)
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource_id=source)
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable(['usersys.as_trader'])
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                data = request.data
                data['datasource'] = request.user.datasource_id
                if not data.get('nameC') and data.get('nameE'):
                    data['nameC'] = data['nameE']
                elif not data.get('nameE') and data.get('nameC'):
                    data['nameE'] = data['nameC']
                elif not data.get('nameC') and not data.get('nameE'):
                    raise InvestError(20071, msg='新建标签失败，名称不能为空', detail='新建标签名称不能为空')
                serializer = self.serializer_class(data=data)
                if serializer.is_valid():
                    instance = serializer.save()
                else:
                    raise InvestError(20071, msg='%s' % serializer.error_messages)
                return JSONResponse(SuccessResponse(self.serializer_class(instance).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.as_trader'])
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            with transaction.atomic():
                data = request.data
                serializer = self.serializer_class(instance, data=data)
                if serializer.is_valid():
                    instance = serializer.save()
                else:
                    raise InvestError(20071, msg='%s' % serializer.error_messages)
                return JSONResponse(SuccessResponse(self.serializer_class(instance).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['usersys.as_trader'])
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted'])
            return JSONResponse(SuccessResponse({'is_deleted': instance.is_deleted}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



class OrgBdResponseView(viewsets.ModelViewSet):
    """
        list:获取所有反馈结果类型
    """

    queryset = OrgBdResponse.objects.all().filter(is_deleted=False)
    serializer_class = OrgBdResponseSerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset()).order_by('sort')
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class FamiliarLevelView(viewsets.ModelViewSet):
    """
        list:获取所有反馈结果类型
    """

    queryset = FamiliarLevel.objects.all().filter(is_deleted=False)
    serializer_class = FamiliarLevelSerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class OrgLevelTypeView(viewsets.ModelViewSet):
    """
        list:获取所有反馈结果类型
    """

    queryset = OrgLevelType.objects.all().filter(is_deleted=False)
    serializer_class = OrgLevelTypeSerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



class ProjectStatusView(viewsets.ModelViewSet):
    """
        list:获取所有标签
        create:新增标签
        update:修改标签
        destroy:删除标签
    """
    queryset = ProjectStatus.objects.all().filter(is_deleted=False)
    serializer_class = ProjectStatusSerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class ServiceView(viewsets.ModelViewSet):
    """
        list:获取所有service
        create:新增service
        update:修改service
        destroy:删除service
    """
    queryset = Service.objects.all().filter(is_deleted=False)
    serializer_class = serviceSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    # def destroy(self, request, *args, **kwargs):
    #     try:
    #         instance = self.get_object()
    #         instance.is_deleted = True
    #         instance.save(update_fields=['is_deleted'])
    #         return JSONResponse(SuccessResponse({'is_deleted':instance.is_deleted}))
    #     except InvestError as err:
    #         return JSONResponse(InvestErrorResponse(err))
    #     except Exception:
    #         return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class CountryView(viewsets.ModelViewSet):
    """
        list:获取所有国家
        create:新增国家
        update:修改国家
        destroy:删除国家
    """
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    filter_fields = ('level', 'parent', 'countryC')
    search_fields = ('countryC', 'countryE', 'areaCode')
    queryset = Country.objects.all().filter(is_deleted=False)
    serializer_class = countrySerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            source = int(request.META.get('HTTP_SOURCE', '1'))
            if source > 2:
                source = 1
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource_id=source).order_by('-sortweight')
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    # def destroy(self, request, *args, **kwargs):
    #     try:
    #         instance = self.get_object()
    #         instance.is_deleted = True
    #         instance.save(update_fields=['is_deleted'])
    #         return JSONResponse(SuccessResponse({'is_deleted':instance.is_deleted}))
    #     except InvestError as err:
    #         return JSONResponse(InvestErrorResponse(err))
    #     except Exception:
    #         return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class CharacterTypeView(viewsets.ModelViewSet):
    """
        list:获取所有角色类型
        create:新增角色类型
        update:修改角色类型
        destroy:删除角色类型
    """
    # permission_classes = (IsSuperUser,)
    queryset = CharacterType.objects.all().filter(is_deleted=False)
    serializer_class = characterTypeSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class IndustryView(viewsets.ModelViewSet):
    """
        list:获取所有行业
        create:新增行业
        update:修改行业
        destroy:删除行业
    """
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('isPindustry','Pindustry')
    queryset = Industry.objects.all().filter(is_deleted=False)
    serializer_class = industrySerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            source = request.META.get('HTTP_SOURCE', 1)
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource_id=source)
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class TitleView(viewsets.ModelViewSet):
    """
        list:获取所有职位
        create:新增职位
        update:修改职位
        destroy:删除职位
    """
    filter_backends = (filters.SearchFilter,)
    search_fields = ('nameC', 'nameE')
    queryset = TitleType.objects.all().filter(is_deleted=False)
    serializer_class = titleTypeSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class BDStatusView(viewsets.ModelViewSet):
    """
        list:获取所有BD状态
        create:新增BD状态
        update:修改BD状态
        destroy:删除BD状态
    """
    queryset = BDStatus.objects.all().filter(is_deleted=False)
    serializer_class = BDStatusSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset()).order_by('sort')
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class DatasourceView(viewsets.ModelViewSet):
    """
        list:获取所有datasource
        create:新增datasource
        update:修改datasource
        destroy:删除datasource
    """
    queryset = DataSource.objects.all().filter(is_deleted=False)
    serializer_class = DataSourceSerializer


    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



class OrgAreaView(viewsets.ModelViewSet):
    """
        list:获取所有机构地区
        create:新增机构地区
        update:修改机构地区
        destroy:删除机构地区
    """
    queryset = OrgArea.objects.all().filter(is_deleted=False)
    serializer_class = orgAreaSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))
class TransactionTypeView(viewsets.ModelViewSet):
    """
        list:获取所有交易类型
        create:新增交易类型
        update:修改交易类型
        destroy:删除交易类型
    """
    queryset = TransactionType.objects.all().filter(is_deleted=False)
    serializer_class = transactionTypeSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class TransactionPhasesView(viewsets.ModelViewSet):
    """
        list:获取所有机构轮次
        create:新增机构轮次
        update:修改机构轮次
        destroy:删除机构轮次
    """
    queryset = TransactionPhases.objects.all().filter(is_deleted=False)
    serializer_class = transactionPhasesSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class EducationView(viewsets.ModelViewSet):
    """
        list:获取所有学历
        create:新增学历
        update:修改学历
        destroy:删除学历
    """
    queryset = Education.objects.all().filter(is_deleted=False)
    serializer_class = EducationSerializer
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class PerformanceAppraisalLevelView(viewsets.ModelViewSet):
    """
        list:获取所有绩效考核等级
        create:新增绩效考核等级
        update:修改绩效考核等级
        destroy:删除绩效考核等级
    """
    queryset = PerformanceAppraisalLevel.objects.all().filter(is_deleted=False)
    serializer_class = PerformanceAppraisalLevelSerializer
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class DidiOrderTypeView(viewsets.ModelViewSet):
    """
        list:获取所有Didi订单类型
    """

    queryset = DidiOrderType.objects.all().filter(is_deleted=False)
    serializer_class = OrgBdResponseSerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset()).order_by('sort')
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class OrgTypeView(viewsets.ModelViewSet):
    """
        list:获取所有机构类型
        create:新增机构类型
        update:修改机构类型
        destroy:删除机构类型
    """
    queryset = OrgType.objects.all().filter(is_deleted=False)
    serializer_class = orgTypeSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = orgTypeSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class CurrencyTypeView(viewsets.ModelViewSet):
    """
        list:获取所有货币类型
        create:新增货币类型
        update:修改货币类型
        destroy:删除货币类型
    """
    queryset = CurrencyType.objects.all().filter(is_deleted=False)
    serializer_class = currencyTypeSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class OrgAttributeView(viewsets.ModelViewSet):
    """
        list:获取所有机构属性
        create:新增机构属性
    """
    queryset = OrgAttribute.objects.all().filter(is_deleted=False)
    serializer_class = orgAttributeSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class OrgtitletableView(viewsets.ModelViewSet):
    """
        list:获取所有机构类型职位对照
        create:新增机构类型职位对照
        update:修改机构类型职位对照
        destroy:删除机构类型职位对照
    """
    queryset = orgtitletable.objects.all().filter(is_deleted=False)
    serializer_class = OrgtitletableSerializer
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class IndustryGroupView(viewsets.ModelViewSet):
    """
        list:获取所有标签
        create:新增标签
        update:修改标签
        destroy:删除标签
    """
    queryset = IndustryGroup.objects.all().filter(is_deleted=False)
    serializer_class = industryGroupSerializer

    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset()).filter(datasource=request.user.datasource)
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class TrainingTypeView(viewsets.ModelViewSet):
    """
        list:获取所有培训方式
    """

    queryset = TrainingType.objects.all().filter(is_deleted=False)
    serializer_class = TrainingTypeSerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class TrainingStatusView(viewsets.ModelViewSet):
    """
        list:获取所有培训状态
    """

    queryset = TrainingStatus.objects.all().filter(is_deleted=False)
    serializer_class = TrainingStatusSerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class AndroidAppVersionView(viewsets.ModelViewSet):

    queryset = AndroidAppVersion.objects.all().filter(is_deleted=False)
    serializer_class = AndroidAppSerializer

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            if not request.user.is_superuser:
                raise InvestError(2009, msg='没有操作权限')
            with transaction.atomic():
                data = request.data
                serializer = self.serializer_class(data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    raise InvestError(20071, msg='%s' % serializer.error_messages)
                return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if not request.user.is_superuser:
                raise InvestError(2009, msg='没有操作权限')
            with transaction.atomic():
                data = request.data
                serializer = self.serializer_class(instance, data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    raise InvestError(20071, msg='%s' % serializer.error_messages)
                return JSONResponse(SuccessResponse(serializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise InvestError(2009, msg='没有操作权限')
        try:
            instance = self.get_object()
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted'])
            return JSONResponse(SuccessResponse({'is_deleted': instance.is_deleted}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class WebmenuView(viewsets.ModelViewSet):
    """
        list:获取所有菜单
    """

    queryset = webmenu.objects.all().filter(is_deleted=False)
    serializer_class = WebMenuSerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse(returnListChangeToLanguage(serializer.data,lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



def getmenulist(user):
    allmenuobj = webmenu.objects.all()
    if user.has_perm('dataroom.onlydataroom') and not user.is_superuser:
        return WebMenuSerializer(allmenuobj.filter(id__in=[6, 8, 14, 30]),many=True).data   # 14：修改密码  8：用户中心  6：dataroom管理  30：普通dataroom
    qslist = [1, 6, 7, 8, 10, 14, 16, 21, 24, 26, 28, 30]
    if user.has_perm('usersys.admin_manageuser'):
        qslist.extend([5])
    if not user.has_perm('usersys.as_investor') or user.is_superuser:
        qslist.extend([27, 28, 33])
    if user.has_perm('usersys.as_trader') and not user.is_superuser:
        qslist.extend([12])
    if user.has_perm('usersys.as_trader'):
        qslist.extend([34, 35, 15, 41])                        # 周报、OKR、个人中心、基本设置
    if user.has_perm('emailmanage.getemailmanage'):
        qslist.extend([3])
    if user.has_perm('usersys.as_trader') or user.has_perm('BD.manageProjectBD'): # 项目bd管理
        qslist.extend([22, 23])
    if user.has_perm('usersys.as_trader') or user.has_perm('BD.manageOrgBD'):         # 机构bd管理
        qslist.extend([2, 37, 23])
    if user.has_perm('APILog.manage_userinfolog'):#日志查询
        qslist.extend([9])
    if user.is_superuser:
        qslist.extend([17])
    if user.has_perm('dataroom.get_companydataroom'):
        qslist.extend([31])
    if user.has_perm('org.export_org'):
        qslist.extend([32])
    if user.has_perm('usersys.admin_managepersonnelrelation'):
        qslist.extend([38])      # 人事管理菜单
    if user.has_perm('usersys.admin_manageindgroupinvestor'):
        qslist.extend([39, 5])        # 管理行业组离职交易师所属投资人
    if user.has_perm('usersys.manageusermenu'):
        qslist.extend([40, 5])         # 全库用户管理 菜单
    qsres = allmenuobj.filter(id__in=removeDuclicates(qslist), is_deleted=False).order_by('index')
    return WebMenuSerializer(qsres,many=True).data