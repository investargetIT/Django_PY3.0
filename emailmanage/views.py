#coding=utf8

import datetime


# Create your views here.
import threading
import traceback

from django.contrib.auth.models import Group
from django.core.paginator import Paginator, EmptyPage
from django.db import transaction
from django.db.models import Q
from django.forms.models import model_to_dict
from rest_framework import filters
from rest_framework import viewsets

from emailmanage.models import emailgroupsendlist
from emailmanage.serializers import Emailgroupsendlistserializer, Usergroupsendlistserializer
from mongoDoc.views import saveSendEmailDataToMongo, readSendEmailDataFromMongo
from proj.models import project
from sourcetype.models import Tag, TransactionType, Industry
from third.views.submail import xsendEmail, checkSubhookKey
from usersys.models import MyUser
from utils.customClass import InvestError, JSONResponse
from utils.util import loginTokenIsAvailable, SuccessResponse, InvestErrorResponse, ExceptionResponse, catchexcption, \
    logexcption, mySortQuery, checkEmailTrue

#邮件群发模板
Email_project_sign = 'y0dQe4'




#收集邮件群发任务名单
def getAllProjectsNeedToSendMail():
    try:
        proj_qs = project.objects.filter(isSendEmail=True, is_deleted=False, datasource_id=1, projstatus_id=4, isHidden=False)
        saveEmailGroupSendData(proj_qs)
        proj_qs.update(**{'isSendEmail': False})
    except Exception as err:
        logexcption()


def QStoList(qs):
    result_list = []
    for instance in qs:
        if instance[0]:
            resstr = str(instance[0])
            result_list.append(resstr)
    return result_list

def UserQSToList(user_qs):
    result_list = []
    for user in user_qs:
        dic = {}
        for key, value in user.items():
            dic[key] = value
        result_list.append(dic)
    return result_list



#保存邮件群发任务名单到mongo
def saveEmailGroupSendData(projs):
    for proj in projs:
        tags = proj.project_tags.all().filter(is_deleted=False).values('tag')
        tagsname = Tag.objects.filter(id__in=tags).values_list('nameC')
        industriesname = Industry.objects.filter(industry_projects__proj=proj, is_deleted=False, industry_projects__is_deleted=False).values_list('industryC')
        transactionTypeName = TransactionType.objects.filter(transactionType_projects__proj=proj, is_deleted=False, transactionType_projects__is_deleted=False).values_list('nameC')
        user_qs = Usergroupsendlistserializer(MyUser.objects.filter(Q(is_deleted=False, user_usertags__tag__in=tags, groups__in=Group.objects.filter(permissions__codename__in=['as_investor']), datasource_id=proj.datasource_id)
                                                                    | Q(is_deleted=False, userstatus_id=2, tags__isnull=True, groups__in=Group.objects.filter(permissions__codename__in=['as_investor']), datasource_id=proj.datasource_id))
                                              .exclude(email__contains='@investarget').distinct(), many=True).data
        datadic = {
            'projtitle': proj.projtitleC,
            'proj': {
                'id': proj.id,
                'Title': proj.projtitleC,
                'Tags': QStoList(tagsname),
                'Location': proj.country.countryC,
                'Industry': QStoList(industriesname),
                'financeAmount_USD': proj.financeAmount_USD,
                'financeAmount': proj.financeAmount,
                'TransactionType': QStoList(transactionTypeName),
                'B_introducteC' : proj.p_introducteC,
                'currency': proj.currency.currencyC,
            },
            'datasource': proj.datasource_id,
            'users': UserQSToList(user_qs),
        }
        saveSendEmailDataToMongo(datadic)


#从mongo获取邮件群发任务名单，执行发送任务
def sendEmailToUser():
    mongodatalist = readSendEmailDataFromMongo()
    for data in mongodatalist:
        try:
            userlist = data['users']
            projdata = data['proj']
            datasource = data['datasource']
            emailgroupsendlist_qs = emailgroupsendlist.objects.filter(proj=projdata['id'])
            for user in userlist:
                try:
                    if emailgroupsendlist_qs.filter(user=user['id']).exists():
                        pass
                    else:
                        sendProjEmailToUser(projdata, user, datasource)
                except Exception:
                    logexcption()
        except Exception:
            logexcption()



#发送邮件
def sendProjEmailToUser(proj,user,datasource):
    emailaddress = user['email']
    financeAmount = '$' + str(proj.get('financeAmount_USD','xxxxxxxx'))+'(美元)'
    if proj['Location'] == '中国':
        if proj['currency'] == '人民币':
            financeAmount = '￥' + str(proj.get('financeAmount','xxxxxxxx'))+'(人民币)'
    data = {
        'proj' : proj['id'],
        'projtitle': proj['Title'],
        'user' : user['id'],
        'username' : user['usernameC'],
        'userMobile': user['mobile'],
        'userEmail' : emailaddress,
        'isRead': False,
        'readtime' : None,
        'isSend' : False,
        'sendtime' : datetime.datetime.now(),
        'errmsg' : None,
        'datasource' : datasource,
    }
    if emailaddress and checkEmailTrue(emailaddress):
        varsdict = {
            'Title': proj['Title'],
            'Location':proj['Location'],
            'Industry': " ".join(proj['Industry']),
            'Tags': " ".join(proj['Tags']),
            'FA': financeAmount,
            'TransactionType': " ".join(proj['TransactionType']),
            'B_introducteC': proj['B_introducteC'],
        }
        response = xsendEmail(emailaddress, Email_project_sign, varsdict)
        if response.get('status') in ['success', True, 1]:
            if response.has_key('return'):
                if len(response['return']) > 0:
                    data['isSend'] = True
                    data['send_id'] = response['return'][0].get('send_id')
                    data['sendtime'] = datetime.datetime.now()
            data['errmsg'] = repr(response)
        else:
            data['errmsg'] = repr(response)
        emailsend = Emailgroupsendlistserializer(data=data)
        if emailsend.is_valid():
            emailsend.save()
        else:
            raise InvestError(8888,msg=emailsend.error_messages)

class EmailgroupsendlistView(viewsets.ModelViewSet):
    """
    list:获取邮件发送记录列表
    update:发送已读回执
    """
    filter_backends = (filters.SearchFilter,filters.DjangoFilterBackend)
    queryset = emailgroupsendlist.objects.all()
    filter_fields = ('proj','isRead','isSend','projtitle',)
    search_fields = ('username','userEmail','userMobile')
    serializer_class = Emailgroupsendlistserializer


    @loginTokenIsAvailable(['emailmanage.getemailmanage',])
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            queryset = self.filter_queryset(self.queryset).filter(datasource=request.user.datasource_id)
            sortfield = request.GET.get('sort', 'createdtime')
            desc = request.GET.get('desc', 1)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = Emailgroupsendlistserializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    def update(self, request, *args, **kwargs):
        try:
            data = request.data
            token = data.get('token')
            signature = data.get('signature')
            if not checkSubhookKey(token,signature):
                raise InvestError(8888, msg='subhook验证未通过')
            send_id = data.get('send_id')
            data['isSend'] = True
            try:
                emailgroupsend = self.queryset.get(send_id=send_id)
            except emailgroupsendlist.DoesNotExist:
                return JSONResponse(SuccessResponse(None))
            with transaction.atomic():
                emailserializer = Emailgroupsendlistserializer(emailgroupsend, data=data)
                if emailserializer.is_valid():
                    newemailgroupsend = emailserializer.save()
                    newemailgroupsend.isRead = True
                    newemailgroupsend.readtime = datetime.datetime.now()
                    newemailgroupsend.save()
                else:
                    raise InvestError(code=20071,msg='data有误_%s' % emailserializer.errors)
                return JSONResponse(SuccessResponse(None))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))