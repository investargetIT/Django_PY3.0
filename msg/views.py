#coding=utf-8
import calendar
import os
import traceback

import datetime

import requests
from django.core.paginator import Paginator, EmptyPage
from django.db import transaction

# Create your views here.
from django.db.models import Q
from django.db.models.query import QuerySet
from rest_framework import filters
from rest_framework import viewsets
from rest_framework.decorators import api_view

from invest.settings import APILOG_PATH
from msg.models import message, schedule, webexUser, webexMeeting, InternOnlineTest
from msg.serializer import MsgSerializer, ScheduleSerializer, ScheduleCreateSerializer, WebEXUserSerializer, \
    WebEXMeetingSerializer, ScheduleMeetingSerializer, InternOnlineTestSerializer, InternOnlineTestCreateSerializer
from third.thirdconfig import webEX_siteName, webEX_webExID, webEX_password
from third.views.submail import sendEmailWithAttachmentFile
from utils.customClass import InvestError, JSONResponse, MyCalendar, add_CalendarEvent
import utils.sendMessage
from utils.util import logexcption, loginTokenIsAvailable, SuccessResponse, InvestErrorResponse, ExceptionResponse, \
    catchexcption, returnListChangeToLanguage, returnDictChangeToLanguage, mySortQuery, checkSessionToken, \
    checkRequestToken
import xml.etree.cElementTree as ET
requests.packages.urllib3.disable_warnings()

def saveMessage(content,type,title,receiver,sender=None,modeltype=None,sourceid=None):
    try:
        data = {}
        data['content'] = content
        data['messagetitle'] = title
        data['type'] = type
        data['receiver'] = receiver.id
        data['datasource'] = receiver.datasource_id
        if modeltype:
            data['sourcetype'] = modeltype
        if sourceid:
            data['sourceid'] = sourceid
        if sender:
            data['sender'] = sender.id
        msg = MsgSerializer(data=data)
        if msg.is_valid():
            msg.save()
        else:
            raise InvestError(code=20019)
        return msg.data
    except InvestError as err:
        logexcption()
        return err.msg
    except Exception as err:
        logexcption()
        return err.message

def deleteMessage(type, sourceid):
    message.objects.filter(is_deleted=False, type=type, sourceid=sourceid).update(is_deleted=True, deletedtime=datetime.datetime.now())

class WebMessageView(viewsets.ModelViewSet):
    """
    list:获取站内信列表
    update:已读回执
    """
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = message.objects.all().filter(is_deleted=False)
    filter_fields = ('datasource','type','isRead','receiver')
    serializer_class = MsgSerializer


    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.get_queryset()).filter(receiver=request.user.id).order_by('-createdtime',)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = MsgSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':serializer.data}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            msg = self.get_object()
            if msg.receiver.id != request.user.id:
                raise InvestError(2009)
            with transaction.atomic():
                data = {
                    'isRead':True,
                    'readtime':datetime.datetime.now(),
                }
                msgserializer = MsgSerializer(msg, data=data)
                if msgserializer.is_valid():
                    msgserializer.save()
                else:
                    raise InvestError(code=20071,msg='data有误_%s' % msgserializer.errors)
                return JSONResponse(SuccessResponse(msgserializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.receiver.id == request.user.id or request.user.is_superuser:
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                msgserializer = MsgSerializer(instance)
                return JSONResponse(SuccessResponse(msgserializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.receiver.id == request.user.id or request.user.is_superuser:
                pass
            else:
                raise InvestError(2009, msg='没有删除权限')
            instance.is_deleted = True
            instance.deletedtime = datetime.datetime.now()
            instance.save()
            return JSONResponse(SuccessResponse({'is_deleted': True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

class WebEXMeetingView(viewsets.ModelViewSet):
    """
        list: 视频会议列表
        create: 新增视频会议
        retrieve: 查看某一视频会议
        update: 修改某一视频会议信息
        destroy: 删除某一视频会议
        """
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    queryset = webexMeeting.objects.all().filter(is_deleted=False)
    filter_fields = ('title', 'meetingKey', 'createuser')
    search_fields = ('startDate', 'createuser__usernameC', 'createuser__usernameE')
    serializer_class = WebEXMeetingSerializer
    webex_url = 'https://investarget.webex.com.cn/WBXService/XMLService'

    @loginTokenIsAvailable(['msg.getMeeting'])
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.queryset.filter(datasource_id=request.user.datasource_id))
            status = request.GET.get('status')
            if status:
                now = datetime.datetime.now()
                if status == '0':
                    queryset = queryset.filter(endDate__lte=now)
                elif status == '1':
                    queryset = queryset.filter(startDate__lte=now, endDate__gte=now)
                elif status == '2':
                    queryset = queryset.filter(startDate__lte=now + datetime.timedelta(hours=24), startDate__gt=now)
                else:
                    queryset = queryset.filter(startDate__gt=now + datetime.timedelta(hours=24))
            sortfield = request.GET.get('sort', 'startDate')
            desc = request.GET.get('desc', 0)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def checkMeeingDateAvailable(self, request, *args, **kwargs):
        try:
            startDate = datetime.datetime.strptime(request.GET.get('startDate'), "%Y-%m-%dT%H:%M:%S")
            duration = int(request.GET.get('duration'))
            endDate = startDate + datetime.timedelta(minutes=duration)
            qs = self.get_queryset().filter(Q(startDate__lte=startDate, endDate__gt=startDate) | Q(startDate__lt=endDate, startDate__gte=startDate))
            if qs.exists():
                return JSONResponse(SuccessResponse(False))
            return JSONResponse(SuccessResponse(True))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



    @loginTokenIsAvailable(['msg.manageMeeting', 'msg.createMeeting'])
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            data['createuser'] = request.user.id
            with transaction.atomic():
                instanceSerializer = self.serializer_class(data=data)
                if instanceSerializer.is_valid():
                    instance = instanceSerializer.save()
                else:
                    raise InvestError(code=20071, msg='参数错误：%s' % instanceSerializer.errors)
                data['startDate'] = instance.startDate.strftime('%m/%d/%Y %H:%M:%S')
                XML_body = getCreateXMLBody(data)
                s = requests.post(url=self.webex_url, data=XML_body.encode("utf-8"))
                if s.status_code == 200:
                    res = ET.fromstring(s.text)
                    result = next(res.iter('{http://www.webex.com/schemas/2002/06/service}result')).text
                    if result == 'FAILURE':
                        reason = next(res.iter('{http://www.webex.com/schemas/2002/06/service}reason')).text
                        raise InvestError(8006, msg=reason)
                    else:
                        meetingkey = next(res.iter('{http://www.webex.com/schemas/2002/06/service/meeting}meetingkey')).text
                        serv_host = next(res.iter('{http://www.webex.com/schemas/2002/06/service}host')).text
                        serv_attendee = next(res.iter('{http://www.webex.com/schemas/2002/06/service}attendee')).text
                        meetGuestToken = next(res.iter('{http://www.webex.com/schemas/2002/06/service/meeting}guestToken')).text
                        meetingData = {'meetingKey': meetingkey, 'url_host': serv_host, 'url_attendee': serv_attendee,
                                  'guestToken': meetGuestToken}
                        newInstanceSerializer = self.serializer_class(instance, data=meetingData)
                        if newInstanceSerializer.is_valid():
                            newInstanceSerializer.save()
                else:
                    raise InvestError(8006, msg=s.text)
            return JSONResponse(SuccessResponse(instanceSerializer.data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable(['msg.getMeeting', 'msg.manageMeeting'])
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            serializer = self.serializer_class(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('msg.manageMeeting'):
                pass
            elif request.user == instance.createuser or webexUser.objects.filter(meeting=instance.id, user=request.user, meetingRole=True).exists():
                pass
            else:
                raise InvestError(2009, msg='没有修改权限')
            data = request.data
            startDate, duration, title = instance.startDate, instance.duration, instance.title
            with transaction.atomic():
                instanceSerializer = self.serializer_class(instance, data=data)
                if instanceSerializer.is_valid():
                    instanceSerializer.save()
                else:
                    raise InvestError(code=20071, msg='参数错误：%s' % instanceSerializer.errors)
            data['startDate'] = instance.startDate.strftime('%m/%d/%Y %H:%M:%S')
            XML_body = getUpdateXMLBody(instance.meetingKey, data)
            s = requests.post(url=self.webex_url, data=XML_body.encode("utf-8"))
            if s.status_code != 200:
                raise InvestError(8006, msg=s.text)
            else:
                res = ET.fromstring(s.text)
                result = next(res.iter('{http://www.webex.com/schemas/2002/06/service}result')).text
                if result == 'FAILURE':
                    reason = next(res.iter('{http://www.webex.com/schemas/2002/06/service}reason')).text
                    raise InvestError(8006, msg=reason)
                else:
                    serv_host = next(res.iter('{http://www.webex.com/schemas/2002/06/service}host')).text
                    serv_attendee = next(res.iter('{http://www.webex.com/schemas/2002/06/service}attendee')).text
                    meetingData = {'url_host': serv_host, 'url_attendee': serv_attendee,}
                    with transaction.atomic():
                        instanceSerializer = self.serializer_class(instance, data=meetingData)
                        if instanceSerializer.is_valid():
                            newInstance = instanceSerializer.save()
                        else:
                            raise InvestError(code=20071, msg='参数错误：%s' % instanceSerializer.errors)
                        if startDate != newInstance.startDate or duration != newInstance.duration or title != newInstance.title:
                            webexSch_qs = instance.meeting_schedule.all().filter(is_deleted=False)
                            webexSch_qs.update(scheduledtime=newInstance.startDate, comments=newInstance.title)
                            webexUser_qs = instance.meeting_webexUser.all().filter(is_deleted=False)
                            utils.sendMessage.sendmessage_WebEXMeetingMessage(webexUser_qs)
                    return JSONResponse(SuccessResponse(returnDictChangeToLanguage(instanceSerializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('msg.manageMeeting'):
                pass
            elif request.user == instance.createuser or webexUser.objects.filter(meeting=instance.id, user=request.user, meetingRole=True).exists():
                pass
            else:
                raise InvestError(2009, msg='没有删除权限')
            XML_body = getDeleteXMLBody(instance.meetingKey)
            s = requests.post(url=self.webex_url, data=XML_body.encode("utf-8"))
            if s.status_code != 200:
                raise InvestError(8006, msg=s.text)
            else:
                res = ET.fromstring(s.text)
                result = next(res.iter('{http://www.webex.com/schemas/2002/06/service}result')).text
                if result == 'FAILURE':
                    reason = next(res.iter('{http://www.webex.com/schemas/2002/06/service}reason')).text
                    raise InvestError(8006, msg=reason)
                else:
                    with transaction.atomic():
                        instance.is_deleted = True
                        instance.deleteduser = request.user
                        instance.deletedtime = datetime.datetime.now()
                        instance.save()
                        webexUser_qs = instance.meeting_webexUser.all().filter(is_deleted=False)
                        msg_list = list(webexUser_qs)
                        webexUser_qs.update(is_deleted=True, deletedtime=datetime.datetime.now(), deleteduser=request.user)
                        webexSch_qs = instance.meeting_schedule.all().filter(is_deleted=False)
                        webexSch_qs.update(is_deleted=True, deletedtime=datetime.datetime.now(), deleteduser=request.user)
                    utils.sendMessage.sendmessage_WebEXMeetingCancelMessage(msg_list)
                    return JSONResponse(SuccessResponse({'is_deleted': True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def getWebExMeetingListAPI(self, request, *args, **kwargs):
        try:
            data = request.data
            XML_body = getListXMLBody(data)
            s = requests.post(url=self.webex_url, data=XML_body.encode("utf-8"), verify=False)
            if s.status_code != 200:
                raise InvestError(8006, msg=s.text)
            else:
                res = ET.fromstring(s.text)
                xmlns_serv = "{http://www.webex.com/schemas/2002/06/service}"
                xmlns_meeting = '{http://www.webex.com/schemas/2002/06/service/meeting}'
                result = next(res.iter('{}{}'.format(xmlns_serv, 'result'))).text
                if result == 'FAILURE':
                    reason = next(res.iter('{}{}'.format(xmlns_serv, 'reason'))).text
                    exceptionID = next(res.iter('{}{}'.format(xmlns_serv, 'exceptionID'))).text
                    if exceptionID == "000015":
                        return JSONResponse(SuccessResponse({'meetings': [], 'returned': 0, 'total': 0, 'startFrom': data.get('startFrom', 1)}))
                    raise InvestError(8006, msg=reason)
                else:
                    meetings = []
                    for elem in res.iter('{}{}'.format(xmlns_meeting, 'meeting')):
                        meeting_info = {
                            'meetingKey': (elem.find('{}{}'.format(xmlns_meeting, 'meetingKey'))).text,
                            'meetingUUID': (elem.find('{}{}'.format(xmlns_meeting, 'meetingUUID'))).text,
                            'confName': (elem.find('{}{}'.format(xmlns_meeting, 'confName'))).text,
                            'meetingType': (elem.find('{}{}'.format(xmlns_meeting, 'meetingType'))).text,
                            'hostWebExID': (elem.find('{}{}'.format(xmlns_meeting, 'hostWebExID'))).text,
                            'otherHostWebExID': (elem.find('{}{}'.format(xmlns_meeting, 'otherHostWebExID'))).text,
                            'timeZoneID': (elem.find('{}{}'.format(xmlns_meeting, 'timeZoneID'))).text,
                            'timeZone': (elem.find('{}{}'.format(xmlns_meeting, 'timeZone'))).text,
                            'status': (elem.find('{}{}'.format(xmlns_meeting, 'status'))).text,
                            'startDate': (elem.find('{}{}'.format(xmlns_meeting, 'startDate'))).text,
                            'duration': (elem.find('{}{}'.format(xmlns_meeting, 'duration'))).text,
                            'listStatus': (elem.find('{}{}'.format(xmlns_meeting, 'listStatus'))).text,
                            'hostJoined': (elem.find('{}{}'.format(xmlns_meeting, 'hostJoined'))).text,
                            'participantsJoined': (elem.find('{}{}'.format(xmlns_meeting, 'participantsJoined'))).text,
                            'telePresence': (elem.find('{}{}'.format(xmlns_meeting, 'telePresence'))).text,
                        }
                        meetings.append(meeting_info)
                    total = next(res.iter('{}{}'.format(xmlns_serv, 'total'))).text
                    returned = next(res.iter('{}{}'.format(xmlns_serv, 'returned'))).text
                    startFrom = next(res.iter('{}{}'.format(xmlns_serv, 'startFrom'))).text
            return JSONResponse(SuccessResponse({'meetings': meetings, 'returned': returned, 'total': total, 'startFrom': startFrom}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

def getXMLHeaders():
    headers = """
                         <header>
                             <securityContext>
                                 <siteName>{siteName}</siteName>
                                 <webExID>{webExID}</webExID>
                                 <password>{password}</password>
                             </securityContext>
                         </header>
             """.format(siteName=webEX_siteName, webExID=webEX_webExID, password=webEX_password)
    return headers

def getCreateXMLBody(data):
    headers = getXMLHeaders()
    meetingPassword = data.get('password', 'Aa123456')  # 会议密码
    title = data.get('title', '')  # 会议名称
    agenda = data.get('agenda', '议程暂无')  # 会议议程
    startDate = data.get('startDate', '')  # 会议开始时间（格式：11/30/2015 10:00:00）
    duration = data.get('duration', '60')  # 会议持续时间（单位：分钟）
    XML_body = """
                               <?xml version="1.0" encoding="UTF-8"?>
                               <serv:message xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                                   {headers}
                                   <body>
                                       <bodyContent xsi:type="java:com.webex.service.binding.meeting.CreateMeeting">
                                           <accessControl>
                                               <meetingPassword>{meetingPassword}</meetingPassword>
                                           </accessControl>
                                           <telephony>
                                               <telephonySupport>CALLIN</telephonySupport>
                                           </telephony>
                                           <metaData>
                                               <confName>{title}</confName>
                                               <agenda>{agenda}</agenda>
                                           </metaData>
                                           <schedule>
                                               <startDate>{startDate}</startDate>
                                               <duration>{duration}</duration>
                                           </schedule>
                                       </bodyContent>
                                   </body>
                               </serv:message>
                           """.format(headers=headers, meetingPassword=meetingPassword, title=title, agenda=agenda,
                                      startDate=startDate, duration=duration)
    return XML_body


def getGetXMLBody(meetingKey):
    headers = getXMLHeaders()
    XML_body = """
                            <?xml version="1.0" encoding="UTF-8"?>
                            <serv:message xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                                {headers}
                                <body>
                                    <bodyContent xsi:type="java:com.webex.service.binding.meeting.GetMeeting">
                                        <meetingKey>{meetingKey}</meetingKey>
                                    </bodyContent>
                                </body>
                            </serv:message>
                        """.format(headers=headers, meetingKey=meetingKey)
    return XML_body


def getListXMLBody(data):
    headers = getXMLHeaders()
    startFrom = data.get('startFrom', 1)
    maximumNum = data.get('maximumNum', 10)
    listMethod = data.get('listMethod', 'AND')
    orderBy = data.get('orderBy', 'STARTTIME')
    orderAD = data.get('orderAD', 'ASC')
    now = datetime.date.today()
    this_month_start = datetime.datetime(now.year, now.month, 1)
    this_month_end = datetime.datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1], 23, 59, 59)
    startDateStart = data.get('startDateStart', this_month_start.strftime('%m/%d/%Y %H:%M:%S'))
    timeZoneID = data.get('timeZoneID', 45)
    endDateEnd = data.get('endDateEnd', this_month_end.strftime('%m/%d/%Y %H:%M:%S'))
    XML_body = """
                            <?xml version="1.0" encoding="UTF-8"?>
                            <serv:message xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                                {headers}
                                <body>
                                    <bodyContent xsi:type="java:com.webex.service.binding.meeting.LstsummaryMeeting">
                                        <listControl>
                                         <startFrom>{startFrom}</startFrom>
                                         <maximumNum>{maximumNum}</maximumNum>
                                         <listMethod>{listMethod}</listMethod>
                                        </listControl>
                                        <order>
                                         <orderBy>{orderBy}</orderBy>
                                         <orderAD>{orderAD}</orderAD>
                                        </order>
                                        <dateScope>
                                         <startDateStart>{startDateStart}</startDateStart>
                                         <timeZoneID>{timeZoneID}</timeZoneID>
                                         <endDateEnd>{endDateEnd}</endDateEnd>
                                        </dateScope>
                                    </bodyContent>
                                </body>
                            </serv:message>
                        """.format(headers=headers, startFrom=startFrom, maximumNum=maximumNum, listMethod=listMethod,
                                   orderBy=orderBy, orderAD=orderAD, startDateStart=startDateStart,
                                   timeZoneID=timeZoneID, endDateEnd=endDateEnd)
    return XML_body

def get_hostKey(meetingKey):
    XML_body = getGetXMLBody(meetingKey)
    webex_url = 'https://investarget.webex.com.cn/WBXService/XMLService'
    s = requests.post(url=webex_url, data=XML_body.encode("utf-8"))
    if s.status_code != 200:
        raise InvestError(8006, msg=s.text)
    else:
        res = ET.fromstring(s.text)
        hostKey = next(res.iter('{http://www.webex.com/schemas/2002/06/service/meeting}hostKey')).text
        return hostKey

def getUpdateXMLBody(meetingKey, data):
    headers = getXMLHeaders()
    confName = '<confName>{}</confName>'.format(data['title']) if data.get('title') else ''  # 会议名称
    startDate = '<startDate>{}</startDate>'.format(data['startDate']) if data.get('startDate') else ''  # 会议开始时间
    duration = '<duration>{}</duration>'.format(data['duration']) if data.get('duration') else ''  # 会议持续时间
    XML_body = """
                                <?xml version="1.0" encoding="UTF-8"?>
                                <serv:message xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                                    {headers}
                                    <body>
                                        <bodyContent xsi:type="java:com.webex.service.binding.meeting.SetMeeting">
                                            <meetingkey>{meetingKey}</meetingkey>
                                            <metaData>
                                                {confName}
                                            </metaData>
                                            <schedule>
                                                {startDate}
                                                {duration}
                                            </schedule>
                                        </bodyContent>
                                    </body>
                                </serv:message>
                            """.format(headers=headers, meetingKey=meetingKey,
                                       confName=confName, startDate=startDate, duration=duration)
    return XML_body

def getDeleteXMLBody(meetingKey):
    headers = getXMLHeaders()
    XML_body = """
                            <?xml version="1.0" encoding="UTF-8"?>
                            <serv:message xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                                {headers}
                                <body>
                                    <bodyContent xsi:type="java:com.webex.service.binding.meeting.DelMeeting">
                                        <meetingKey>{meetingKey}</meetingKey>
                                    </bodyContent>
                                </body>
                            </serv:message>
                        """.format(headers=headers, meetingKey=meetingKey)
    return XML_body


def createWebEXMeeting(data):
    webex_url = 'https://investarget.webex.com.cn/WBXService/XMLService'
    with transaction.atomic():
        instanceSerializer = WebEXMeetingSerializer(data=data)
        if instanceSerializer.is_valid():
            instance = instanceSerializer.save()
        else:
            raise InvestError(code=20071, msg='创建会议参数错误：%s' % instanceSerializer.errors)
        data['startDate'] = instance.startDate.strftime('%m/%d/%Y %H:%M:%S')
        XML_body = getCreateXMLBody(data)
        s = requests.post(url=webex_url, data=XML_body.encode("utf-8"))
        if s.status_code == 200:
            res = ET.fromstring(s.text)
            result = next(res.iter('{http://www.webex.com/schemas/2002/06/service}result')).text
            if result == 'FAILURE':
                reason = next(res.iter('{http://www.webex.com/schemas/2002/06/service}reason')).text
                raise InvestError(8006, msg=reason)
            else:
                meetingkey = next(res.iter('{http://www.webex.com/schemas/2002/06/service/meeting}meetingkey')).text
                serv_host = next(res.iter('{http://www.webex.com/schemas/2002/06/service}host')).text
                serv_attendee = next(res.iter('{http://www.webex.com/schemas/2002/06/service}attendee')).text
                meetGuestToken = next(res.iter('{http://www.webex.com/schemas/2002/06/service/meeting}guestToken')).text
                hostKey = get_hostKey(meetingkey)
                meetingData = {'meetingKey': meetingkey, 'url_host': serv_host, 'url_attendee': serv_attendee,
                               'guestToken': meetGuestToken, 'hostKey': hostKey}
                newInstanceSerializer = WebEXMeetingSerializer(instance, data=meetingData)
                if newInstanceSerializer.is_valid():
                    newInstance = newInstanceSerializer.save()
                else:
                    raise InvestError(code=20071, msg='会议信息错误：%s' % instanceSerializer.errors)
        else:
            raise InvestError(8006, msg=s.text)
        return newInstance



class ScheduleView(viewsets.ModelViewSet):
    """
        list:日程安排列表
        create:新建日程
        retrieve:查看某一日程安排信息
        update:修改日程安排信息
        destroy:删除日程安排
        """
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    queryset = schedule.objects.all().filter(is_deleted=False)
    filter_fields = ('proj', 'createuser', 'user', 'projtitle', 'country', 'manager')
    search_fields = ('createuser__usernameC', 'user__usernameC', 'user__mobile', 'proj__projtitleC', 'proj__projtitleE')
    serializer_class = ScheduleSerializer


    @loginTokenIsAvailable()
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            date = request.GET.get('date')
            time = request.GET.get('time')
            queryset = self.filter_queryset(self.queryset.filter(datasource_id=request.user.datasource_id))
            if date:
                date = datetime.datetime.strptime(date.encode('utf-8'), "%Y-%m-%d")
                queryset = queryset.filter(scheduledtime__year=date.year,scheduledtime__month=date.month)
            if time:
                time = datetime.datetime.strptime(time.encode('utf-8'), "%Y-%m-%dT%H:%M:%S")
                queryset = queryset.filter(scheduledtime__gt=time)
            if request.user.has_perm('msg.admin_manageSchedule'):
                queryset = queryset
            else:
                queryset = queryset.filter(Q(manager_id=request.user.id) | Q(createuser_id=request.user.id))
            sortfield = request.GET.get('sort', 'scheduledtime')
            desc = request.GET.get('desc', 0)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = ScheduleSerializer(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable()
    def create(self, request, *args, **kwargs):
        try:
            checkSessionToken(request)
            data = request.data
            map(lambda x: x.update({'createuser': request.user.id if not x.get('createuser') else x['createuser'],
                                    'manager': request.user.id if not x.get('manager') else x['manager']
                                    }), data)
            with transaction.atomic():
                for i in range(0, len(data)):
                    if data[i]['type'] == 4 and not data[i].get('meeting'):
                        if request.user.has_perm('msg.createMeeting') or request.user.has_perm('msg.manageMeeting'):
                            pass
                        else:
                            raise InvestError(2009, msg='没有新建视频会议权限')
                        data[i]['startDate'] = data[i]['scheduledtime']
                        meetingInstance = createWebEXMeeting(data[i])
                        data[i]['meeting'] = meetingInstance.id
                scheduleserializer = ScheduleCreateSerializer(data=data, many=True)
                if scheduleserializer.is_valid():
                    instances = scheduleserializer.save()
                else:
                    raise InvestError(code=20071, msg='参数错误：%s' % scheduleserializer.errors)
                return JSONResponse(SuccessResponse(ScheduleMeetingSerializer(instances, many=True).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if request.user.has_perm('msg.admin_manageSchedule'):
                pass
            elif request.user in [instance.createuser, instance.manager]:
                pass
            else:
                raise InvestError(code=2009)
            serializer = ScheduleSerializer(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('msg.admin_manageSchedule'):
                pass
            elif request.user in [instance.createuser, instance.manager]:
                pass
            else:
                raise InvestError(code=2009)
            data = request.data
            data['lastmodifyuser'] = request.user.id
            with transaction.atomic():
                scheduleserializer = ScheduleCreateSerializer(instance, data=data)
                if scheduleserializer.is_valid():
                    newinstance = scheduleserializer.save()
                else:
                    raise InvestError(code=20071, msg='参数错误：%s' % scheduleserializer.errors)
                return JSONResponse(SuccessResponse(ScheduleSerializer(newinstance).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.has_perm('msg.admin_manageSchedule'):
                pass
            elif request.user in [instance.createuser, instance.manager]:
                pass
            else:
                raise InvestError(code=2009)
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                if instance.meeting and instance.manager:
                    webexUser_qs = webexUser.objects.filter(is_deleted=False, meeting=instance.meeting, user=instance.manager)
                    webexUser_qs.update(is_deleted=True, deletedtime=datetime.datetime.now(), deleteduser=request.user)
                return JSONResponse(SuccessResponse(ScheduleCreateSerializer(instance).data))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


class WebEXUserView(viewsets.ModelViewSet):
    """
        list: 视频会议参会人员列表
        create: 新增视频会议参会人员
        retrieve: 查看某一视频会议参会人员
        update: 修改某一视频会议参会人员信息
        destroy: 删除某一视频会议参会人员
        """
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend,)
    queryset = webexUser.objects.all().filter(is_deleted=False)
    filter_fields = ('user', 'name', 'email', 'meeting', 'meetingRole')
    search_fields = ('meeting__startDate', 'user__usernameC', 'user__usernameE', 'name', 'email')
    serializer_class = WebEXUserSerializer


    @loginTokenIsAvailable(['msg.manageMeeting', 'msg.getMeeting'])
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.filter_queryset(self.queryset.filter(datasource_id=request.user.datasource_id))
            sortfield = request.GET.get('sort', 'lastmodifytime')
            desc = request.GET.get('desc', 0)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable(['msg.manageMeeting', 'msg.createMeeting'])
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            map(lambda x: x.update({'createuser': request.user.id if not x.get('createuser') else x['createuser']}), data)
            with transaction.atomic():
                instanceSerializer = self.serializer_class(data=data, many=True)
                if instanceSerializer.is_valid():
                    instances = instanceSerializer.save()
                else:
                    raise InvestError(code=20071, msg=instanceSerializer.errors)
                utils.sendMessage.sendmessage_WebEXMeetingMessage(instances)
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(instanceSerializer.data)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['msg.manageMeeting', 'msg.getMeeting'])
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            serializer = self.serializer_class(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['msg.manageMeeting'])
    def destroy(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
                return JSONResponse(SuccessResponse(returnDictChangeToLanguage(self.serializer_class(instance).data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


@api_view(['POST'])
@checkRequestToken()
def sendIcsFileEmail(request):
    try:
        data = request.data
        destination = data.get('destination')
        html = data.get('html')
        subject = data.get('subject')
        icsFilePath = getICSFile(data)
        response = sendEmailWithAttachmentFile(destination, subject, html, icsFilePath)
        os.remove(icsFilePath)
        return JSONResponse(SuccessResponse(response))
    except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


def getICSFile(data):
    path = APILOG_PATH['icsFilePath']
    calendar_name = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    startDate = datetime.datetime.strptime(data.get('startDate'), "%Y-%m-%dT%H:%M:%S")
    endDate = datetime.datetime.strptime(data.get('endDate'), "%Y-%m-%dT%H:%M:%S")
    if startDate >= endDate:
        raise InvestError(2007, msg='开始时间不能早于结束时间')
    summary = data.get('summary', '事件标题')
    description = data.get('description', '事件描述')
    location = data.get('location', '未知')
    calendar = MyCalendar(calendar_name)
    add_CalendarEvent(calendar, summary, startDate, endDate, description, location)
    calendar.save_as_ics_file(path)
    return os.path.join(path, '{}.ics'.format(calendar_name)).decode('utf-8')


class InternOnlineTestView(viewsets.ModelViewSet):
    """
        list: 获取在线测试结果列表
        create: 开始在线测试
        retrieve: 查看某在线测试结果
        update: 提交在线测试结果
        destroy: 删除某在线测试结果
        """
    queryset = InternOnlineTest.objects.filter(is_deleted=False)
    serializer_class = InternOnlineTestSerializer

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            if self.request.user.is_authenticated:
                queryset = queryset.filter(datasource=self.request.user.datasource)
            else:
                raise InvestError(code=2009, msg='未知来源')
        else:
            raise InvestError(code=8890)
        return queryset

    @loginTokenIsAvailable(['msg.user_onlineTest'])
    def list(self, request, *args, **kwargs):
        try:
            page_size = request.GET.get('page_size', 10)
            page_index = request.GET.get('page_index', 1)
            lang = request.GET.get('lang', 'cn')
            queryset = self.get_queryset().filter(user_id=request.user.id)
            sortfield = request.GET.get('sort', 'lastmodifytime')
            desc = request.GET.get('desc', 0)
            queryset = mySortQuery(queryset, sortfield, desc)
            try:
                count = queryset.count()
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count':count,'data':returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


    @loginTokenIsAvailable(['msg.user_onlineTest'])
    def create(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            with transaction.atomic():
                instanceSerializer = InternOnlineTestCreateSerializer(data={'startTime': datetime.datetime.now(), 'user': request.user.id})
                if instanceSerializer.is_valid():
                    instanceSerializer.save()
                else:
                    raise InvestError(code=20071, msg=instanceSerializer.errors)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(instanceSerializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['msg.user_onlineTest'])
    def retrieve(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            if instance.user != request.user.id:
                raise InvestError(2007, msg='非本人不能查看')
            serializer = self.serializer_class(instance)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(serializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable(['msg.user_onlineTest'])
    def update(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            instance = self.get_object()
            data = request.data
            if instance.user.id != request.user.id:
                raise InvestError(2007, msg='非本人不能提交')
            if data.get('user') and data.get('user') != instance.user.id:
                raise InvestError(2007, msg='答题人不能被修改')
            if not data.get('key'):
                raise InvestError(2007, msg='答题结束附件不能为空')
            if instance.key:
                raise InvestError(2007, msg='只能提交一次')
            data['endTime'] = datetime.datetime.now()
            with transaction.atomic():
                instanceSerializer = InternOnlineTestCreateSerializer(instance, data=data)
                if instanceSerializer.is_valid():
                    instanceSerializer.save()
                else:
                    raise InvestError(5004, msg='提交测试结果失败--%s' % instanceSerializer.error_messages)
            return JSONResponse(SuccessResponse(returnDictChangeToLanguage(instanceSerializer.data, lang)))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

    @loginTokenIsAvailable()
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.is_superuser:
                pass
            else:
                raise InvestError(2009)
            with transaction.atomic():
                instance.is_deleted = True
                instance.deleteduser = request.user
                instance.deletedtime = datetime.datetime.now()
                instance.save()
            return JSONResponse(SuccessResponse({'is_deleted': True}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            catchexcption(request)
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))