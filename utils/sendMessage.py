#coding=utf-8
import threading

from django.shortcuts import render_to_response

from dataroom.models import dataroom_User_file
from msg.models import schedule
from proj.models import project
from sourcetype.models import DataSource
from third.thirdconfig import sendSms, sendWebmsg, sendAppmsg, sendEmail
from usersys.models import MyUser, UserRelation
from msg.views import saveMessage
from third.views.jpush import pushnotification
from third.views.submail import xsendSms, xsendEmail
from utils.messagejson import MESSAGE_DICT
from utils.util import logexcption, checkEmailTrue



def getbase_domain(model):
    base_domain = None
    if isinstance(model, DataSource):
        base_domain = model.domain
    return base_domain

def getProjTitleWithSuperLink(proj,lang='cn'):
    if lang == 'cn':
        proj_superlink = '<a href=\'%s/app/projects/%s\'>%s</a>'%(getbase_domain(proj.datasource), proj.id, proj.projtitleC)
    else:
        proj_superlink = '<a href=\'%s/app/projects/%s\'>%s</a>'%(getbase_domain(proj.datasource), proj.id, proj.projtitleE)
    return proj_superlink


def getDataroomTitleWithSuperLink(dataroom,lang='cn'):
    if lang == 'cn':
        proj_superlink = '<a href=\'%s/app/dataroom/detail?id=%s&isClose=false&projectID=%s\'>%s</a>'%\
                         (getbase_domain(dataroom.datasource), dataroom.id, dataroom.proj.id, dataroom.proj.projtitleC)
    else:
        proj_superlink = '<a href=\'%s/app/dataroom/detail?id=%s&isClose=false&projectID=%s\'>%s</a>'%\
                         (getbase_domain(dataroom.datasource), dataroom.id, dataroom.proj.id, dataroom.proj.projtitleE)
    return proj_superlink


typelist = ['sms','app','email','webmsg']


def sendmessage_traderadd(model,receiver,types,sender=None):
    """
    :param model: UserRelation type
    :param receiver: myuser type
    :param types: list
    :param sender: myuser type
    :return: None
    """
    class sendmessage_traderchangeThread(threading.Thread):
        def __init__(self, model, receiver, types, sender=None):
            self.model = model
            self.receiver = receiver
            self.types = types
            self.sender = sender
            threading.Thread.__init__(self)

        def run(self):
            types = self.types
            receiver = self.receiver
            model = self.model
            sender = self.sender
            if isinstance(model, UserRelation):
                lang = 'cn'
                username = model.traderuser.usernameC
                if self.receiver.country:
                    if self.receiver.country.areaCode not in ['86', u'86', None, '', u'']:
                        lang = 'en'
                        username = model.traderuser.usernameE
                msgdic = MESSAGE_DICT['traderadd']
                title = msgdic['title_%s'%lang]
                content = msgdic['content_%s'%lang] % username
                messagetype = msgdic['messagetype']
                if 'app' in types and sendAppmsg:
                    try:
                        receiver_alias = receiver.id
                        bdage = 1
                        n_extras = {}
                        pushnotification(content, receiver_alias,  bdage, n_extras)
                    except Exception:
                        logexcption()
                if 'sms' in types and sendSms:
                    try:
                        destination = receiver.mobile
                        projectsign = 'pT0yA4'
                        vars = {'user': model.traderuser.usernameC}
                        xsendSms(destination, projectsign, vars)
                    except Exception:
                        logexcption()
                if 'webmsg' in types and sendWebmsg:
                    try:
                        saveMessage(content, messagetype, title, receiver, sender, modeltype='UserRelation',sourceid=model.id)
                    except Exception:
                        logexcption()

    if checkReceiverToSendMsg(receiver) and receiver.datasource_id not in [3, 4]:
        sendmessage_traderchangeThread(model,receiver,types,sender).start()

def sendmessage_userauditstatuchange(model,receiver,types,sender=None):
    """
    :param model: MyUser type
    :param receiver: myuser type
    :param types: list
    :param sender: myuser type
    :return: None
    """
    class sendmessage_auditstatuchangeThread(threading.Thread):
        def __init__(self, model, receiver, types, sender=None):
            self.model = model
            self.receiver = receiver
            self.types = types
            self.sender = sender
            threading.Thread.__init__(self)

        def run(self):
            receiver = self.receiver
            model = self.model
            sender = self.sender
            if model.datasource_id != 1:
                types = ['sms']
            else:
                types = self.types
            if isinstance(model, MyUser):
                lang = 'cn'
                datasourcename = model.datasource.nameC
                username = model.usernameC
                if self.receiver.country:
                    if self.receiver.country.areaCode not in ['86', u'86', None, '', u'']:
                        lang = 'en'
                        datasourcename = model.datasource.nameE
                        username = model.usernameE
                if model.userstatus.id == 2:
                    msgdic = MESSAGE_DICT['userauditpass']
                elif model.userstatus.id == 3:
                    msgdic = MESSAGE_DICT['userauditunpass']
                else:
                    return
                title = msgdic['title_%s' % lang]
                content = msgdic['content_%s' % lang]% (datasourcename, username)
                messagetype = msgdic['messagetype']

                if 'app' in types and sendAppmsg:
                    try:
                        receiver_alias = receiver.id
                        bdage = 1
                        n_extras = {}
                        pushnotification(content=content, receiver_alias=receiver_alias,  bdage=bdage, n_extras=n_extras)
                    except Exception:
                        logexcption()
                if 'email' in types and sendEmail and checkEmailTrue(receiver.email):
                    try:
                        if model.userstatus.id == 3:
                            destination = receiver.email
                            projectsign = 'ZNRYV3'
                            vars = {'nameC':model.usernameC,'nameE':model.usernameE}
                            xsendEmail(destination, projectsign, vars)
                    except Exception:
                        logexcption()
                if 'sms' in types and sendSms:
                    try:
                        if model.userstatus.id == 2:
                            destination = receiver.mobile
                            if model.datasource_id == 3:
                                projectsign = 'sDp8d3'
                            elif model.datasource_id == 4:
                                projectsign = 'vcb0k1'
                            elif model.datasource_id == 5:
                                projectsign = 'votun1'
                            elif model.datasource_id == 6:
                                projectsign = '3SenI3'
                            elif model.datasource_id == 7:
                                projectsign = 'Q5WL42'
                            elif model.datasource_id == 8:
                                projectsign = 's8Wfv1'
                            else:
                                projectsign = 'EXIDv1'
                            vars = {'user': model.usernameC}
                            xsendSms(destination, projectsign, vars)
                    except Exception:
                        logexcption()
                if 'webmsg' in types and sendWebmsg:
                    try:
                        saveMessage(content, messagetype, title, receiver, sender, modeltype='MyUser',sourceid=model.id)
                    except Exception:
                        logexcption()
    if checkReceiverToSendMsg(receiver):
        sendmessage_auditstatuchangeThread(model,receiver,types,sender).start()

def sendmessage_userregister(model,receiver,types,sender=None):
    """
    :param model: MyUser type
    :param receiver: myuser type
    :param types: list
    :param sender: myuser type
    :return: None
    """
    class sendmessage_userregisterThread(threading.Thread):
        def __init__(self, model, receiver, types, sender=None):
            self.model = model
            self.receiver = receiver
            self.types = types
            self.sender = sender
            threading.Thread.__init__(self)

        def run(self):
            types = self.types
            receiver = self.receiver
            model = self.model
            sender = self.sender
            if isinstance(model, MyUser):
                lang = 'cn'
                datasourcename = model.datasource.nameC
                username = model.usernameC
                if self.receiver.country:
                    if self.receiver.country.areaCode not in ['86', u'86', None, '', u'']:
                        lang = 'en'
                        datasourcename = model.datasource.nameE
                        username = model.usernameE
                msgdic = MESSAGE_DICT['userregister']
                title = msgdic['title_%s' % lang]
                content = msgdic['content_%s' % lang] % (datasourcename, username)
                messagetype = msgdic['messagetype']
                if 'app' in types and sendAppmsg:
                    try:
                        receiver_alias = receiver.id
                        bdage = 1
                        n_extras = {}
                        pushnotification(content=content, receiver_alias=receiver_alias, bdage=bdage, n_extras=n_extras)
                    except Exception:
                        logexcption()
                if 'email' in types and sendEmail and checkEmailTrue(receiver.email):
                    try:
                        destination = receiver.email
                        projectsign = 'J6VK41'
                        vars = {}
                        xsendEmail(destination, projectsign, vars)
                    except Exception:
                        logexcption()
                if 'webmsg' in types and sendWebmsg:
                    try:
                        saveMessage(content, messagetype, title, receiver, sender,modeltype='MyUser',sourceid=model.id)
                    except Exception:
                        logexcption()

    if checkReceiverToSendMsg(receiver) and receiver.datasource_id not in [3, 4]:
        sendmessage_userregisterThread(model,receiver,types,sender).start()


def sendmessage_dataroomuseradd(model,receiver,types,sender=None):
    """
    :param model: dataroom_User_file type
    :param receiver: myuser type
    :param types: list
    :param sender: myuser type
    :return: None
    """
    class sendmessage_dataroomuseraddThread(threading.Thread):
        def __init__(self, model, receiver, types, sender=None):
            self.model = model
            self.receiver = receiver
            self.types = types
            self.sender = sender
            threading.Thread.__init__(self)

        def run(self):
            types = self.types
            receiver = self.receiver
            model = self.model

            if isinstance(model, dataroom_User_file):
                if 'email' in types and sendEmail and checkEmailTrue(receiver.email):
                    try:
                        destination = receiver.email
                        if receiver.datasource_id == 3:
                            projectsign = 'yMgMP'
                        elif receiver.datasource_id == 4:
                            projectsign = 'ewq604'
                        elif receiver.datasource_id == 5:
                            projectsign = 'aJbDc1'
                        elif receiver.datasource_id == 6:
                            projectsign = 'yMgMP'
                        elif receiver.datasource_id == 7:
                            projectsign = 'KrhUa3'
                        elif receiver.datasource_id == 8:
                            projectsign = 'QJ9NB3'
                        else:
                            projectsign = '3a6W92'
                        vars = {'name': receiver.usernameC, 'projectC': getDataroomTitleWithSuperLink(model.dataroom, 'cn'), 'projectE': getDataroomTitleWithSuperLink(model.dataroom, 'en')}
                        xsendEmail(destination, projectsign, vars)
                    except Exception:
                        logexcption()
                if 'webmsg' in types and sendWebmsg:  # 发送通知以后，将站内信发送给该DataRoom项目的承揽承做PM
                    try:
                        msg_content = '已向用户【%s】发送了项目【%s】的dataroom邮件通知' % (receiver.usernameC, model.dataroom.proj.projtitleC)
                        msg_title = '发送dataroom邮件通知记录'
                        user_ids = []
                        for proj_trader in model.dataroom.proj.proj_traders.filter(is_deleted=False):
                            user_ids.append(proj_trader.user.id)
                        if model.dataroom.proj.PM:
                            user_ids.append(model.dataroom.proj.PM.id)
                        msg_receiverusers = MyUser.objects.filter(id__in=user_ids).distinct()
                        for msg_receiver in msg_receiverusers:
                            saveMessage(msg_content, 12, msg_title, msg_receiver, sender, modeltype='dataroomEmailMsg', sourceid=model.id)
                    except Exception:
                        logexcption()

    sendmessage_dataroomuseraddThread(model,receiver,types,sender).start()


def sendmessage_dataroomuserfileupdate(model,receiver,types,sender=None):
    """
    :param model: dataroom_User_file type
    :param receiver: myuser type
    :param types: list
    :param sender: myuser type
    :return: None
    """
    class sendmessage_dataroomuserfileupdateThread(threading.Thread):
        def __init__(self, model, receiver, types, sender=None):
            self.model = model
            self.receiver = receiver
            self.types = types
            self.sender = sender
            threading.Thread.__init__(self)

        def run(self):
            types = self.types
            receiver = self.receiver
            model = self.model

            if isinstance(model, dataroom_User_file):
                if model.lastgettime:
                    seefiles_queryset = model.dataroomuser_seeFiles.all().filter(is_deleted=False,
                                                                                 createdtime__gte=model.lastgettime)
                else:
                    seefiles_queryset = model.dataroomuser_seeFiles.all().filter(is_deleted=False)
                if 'email' in types and sendEmail and checkEmailTrue(receiver.email):
                    try:
                        destination = receiver.email
                        projectsign = 'oQGaH3'
                        filestr = ''
                        projectUrl = getDataroomTitleWithSuperLink(model.dataroom, 'cn')
                        dataroomUrl = '%s/app/dataroom/detail?id=%s&isClose=false&projectID=%s'% (getbase_domain(model.datasource), model.dataroom.id, model.dataroom.proj.id)
                        if seefiles_queryset.exists():
                            for seefile in seefiles_queryset:
                                filestr = filestr + '<a href=\'%s\'>%s</a>' % (dataroomUrl, seefile.file.filename) + '<br>'
                        vars = {'name': receiver.usernameC, 'projectC': projectUrl, 'file': filestr}
                        xsendEmail(destination, projectsign, vars)
                    except Exception:
                        logexcption()
                if 'webmsg' in types and sendWebmsg:  # 发送通知以后，将站内信发送给该DataRoom项目的承揽承做PM
                    try:
                        filestr = '新增文件如下：' + '<br>'
                        if seefiles_queryset.exists():
                            for seefile in seefiles_queryset:
                                filestr = filestr + seefile.file.filename + '<br>'
                        msg_content = '已向用户【%s】发送了项目【%s】的dataroom文件更新邮件通知' % (receiver.usernameC, model.dataroom.proj.projtitleC) + '<br><br>' + filestr
                        msg_title = '发送dataroom文件更新邮件通知记录'
                        user_ids = []
                        for proj_trader in model.dataroom.proj.proj_traders.filter(is_deleted=False):
                            user_ids.append(proj_trader.user.id)
                        if model.dataroom.proj.PM:
                            user_ids.append(model.dataroom.proj.PM.id)
                        msg_receiverusers = MyUser.objects.filter(id__in=user_ids).distinct()
                        for msg_receiver in msg_receiverusers:
                            saveMessage(msg_content, 13, msg_title, msg_receiver, sender, modeltype='dataroomFileUpdateEmailMsg', sourceid=model.id)
                            # 13 区分dataroom邮件通知的12类型，站内信用到了12类型的消息
                    except Exception:
                        logexcption()

    # if checkReceiverToSendMsg(receiver):
    sendmessage_dataroomuserfileupdateThread(model,receiver,types,sender).start()



def sendmessage_projectpublish(model, receiver, types, sender=None):
    """
        :param model: project type
        :param receiver: myuser type
        :param types: list
        :param sender: myuser type
        :return: None
        """

    class sendmessage_projectpublishThread(threading.Thread):
        def __init__(self, model, receiver, types, sender=None):
            self.model = model
            self.receiver = receiver
            self.types = types
            self.sender = sender
            threading.Thread.__init__(self)

        def run(self):
            types = self.types
            receiver = self.receiver
            model = self.model
            sender = self.sender
            if isinstance(model, project):
                lang = 'cn'
                projtitle = model.projtitleC
                if self.receiver.country:
                    if self.receiver.country.areaCode not in ['86', u'86', None, '', u'']:
                        lang = 'en'
                        projtitle = model.projtitleE
                msgdic = MESSAGE_DICT['projectpublish']
                title = msgdic['title_%s' % lang]
                content = msgdic['content_%s' % lang] % projtitle
                messagetype = msgdic['messagetype']
                if 'email' in types and sendEmail and checkEmailTrue(receiver.email):
                    try:
                        destination = receiver.email
                        projectsign = 'IszFR1'
                        vars = {'projectC': getProjTitleWithSuperLink(model), 'projectE': getProjTitleWithSuperLink(model, 'en')}
                        xsendEmail(destination, projectsign, vars)
                    except Exception:
                        logexcption()
                if 'webmsg' in types and sendWebmsg:
                    try:
                        saveMessage(content, messagetype, title, receiver, sender,modeltype='project',sourceid=model.id)
                    except Exception:
                        logexcption()

    if checkReceiverToSendMsg(receiver) and receiver.datasource_id not in [3, 4]:
        sendmessage_projectpublishThread(model,receiver,types,sender).start()


def sendmessage_schedulemsg(model,receiver,types,sender=None):
    """
    :param model: schedule type
    :param receiver: myuser type
    :param types: list
    :param sender: myuser type
    :return: None
    """
    if checkReceiverToSendMsg(receiver) and receiver.datasource_id not in [3, 4]:
        if isinstance(model, schedule):
            lang = 'cn'
            if receiver.country:
                if receiver.country.areaCode not in ['86', u'86', None, '', u'']:
                    lang = 'en'
            msgdic = MESSAGE_DICT['schedulemsg']
            title = msgdic['title_%s' % lang]
            content = msgdic['content_%s' % lang]
            messagetype = msgdic['messagetype']
            if 'app' in types and sendAppmsg:
                try:
                    receiver_alias = receiver.id
                    bdage = 1
                    n_extras = {}
                    pushnotification(content, receiver_alias, bdage, n_extras)
                except Exception:
                    logexcption()
            if 'webmsg' in types and sendWebmsg:
                try:
                    saveMessage(content, messagetype, title, receiver, sender, modeltype='schedule', sourceid=model.id)
                except Exception:
                    logexcption()


def sendmessage_orgBDMessage(model,receiver,types,sender=None):
    """
    :param model: orgBD type
    :param receiver: myuser type
    :param types: list
    :param sender: myuser type
    :return: None
    """
    class sendmessage_orgBDMessageThread(threading.Thread):
        def __init__(self, model, receiver, types, sender = None):
            self.model = model
            self.receiver = receiver
            self.types = types
            self.sender = sender
            threading.Thread.__init__(self)

        def run(self):
            types = self.types
            receiver = self.receiver
            model = self.model
            sender = self.sender
            lang = 'cn'
            projtitle = '空'
            if model.proj:
                projtitle = model.proj.projtitleC
            if self.receiver.country:
                if self.receiver.country.areaCode not in ['86', u'86', None, '', u'']:
                    lang = 'en'
                    if model.proj:
                        projtitle = model.proj.projtitleE
            msgdic = MESSAGE_DICT['orgBDMessage']
            title = msgdic['title_%s' % lang]
            content = msgdic['content_%s' % lang] % projtitle
            messagetype = msgdic['messagetype']
            if 'app' in types and sendAppmsg:
                try:
                    receiver_alias = receiver.id
                    bdage = 1
                    n_extras = {'info': {
                                        'proj': model.proj_id if model.proj else None,
                                        'projtitle': projtitle,
                                        'org': model.org_id if model.org else None,
                                        'orgname': model.org.orgnameC if model.org else None
                                        },
                                'type': 'OrgBD'}
                    pushnotification(content, receiver_alias, bdage, n_extras)
                except Exception:
                    logexcption()
            if 'webmsg' in types and sendWebmsg:
                try:
                    saveMessage(content, messagetype, title, receiver, sender, modeltype='OrgBD', sourceid=model.id)
                except Exception:
                    logexcption()
            if 'sms' in types and sendSms:
                try:
                    destination = receiver.mobile
                    projectsign = msgdic['sms_sign']
                    vars = {'proj': model.proj.projtitleC}
                    xsendSms(destination, projectsign, vars)
                except Exception:
                    logexcption()

    if checkReceiverToSendMsg(receiver) and receiver.datasource_id not in [3, 4]:
        sendmessage_orgBDMessageThread(model,receiver,types,sender).start()

def sendmessage_orgBDExpireMessage(receiver, types, content):
    """
    :param receiver: myuser type
    :param types: list
    :param content: html
    :return: None
    """
    class sendmessage_orgBDExpireMessageThread(threading.Thread):

        def run(self):
            msgdic = MESSAGE_DICT['orgBdExpire']
            if 'email' in types and sendEmail and checkEmailTrue(receiver.email):

                try:
                    destination = receiver.email
                    projectsign = msgdic['email_sign']
                    vars = {'html': content}
                    xsendEmail(destination, projectsign, vars)
                except Exception:
                    logexcption()

    if checkReceiverToSendMsg(receiver) and receiver.datasource_id not in [3, 4]:
        sendmessage_orgBDExpireMessageThread().start()


def sendmessage_WebEXMeetingMessage(webEXUsers):
    """
    :param webEXUsers: Iterable object. like list、 queryset
    """
    class sendmessage_WebEXMeetingMessageThread(threading.Thread):

        def run(self):
            for webexuser in webEXUsers:
                name, email, role, meeting = webexuser.name, webexuser.email, webexuser.meetingRole, webexuser.meeting
                if sendEmail and checkEmailTrue(email):
                    try:
                        if role == True:
                            projectsign = 'N7ygf2'
                            vars = {'name': name, 'title': meeting.title, 'data': meeting.agenda,
                                    'time': meeting.startDate.strftime('%Y-%m-%d %H:%M'), 'duration': meeting.duration,
                                    'meetingkey': meeting.meetingKey, 'hostkey': meeting.hostKey,
                                    'password': meeting.password,}
                        else:
                            projectsign = 'Bk4EY4'
                            vars = {'name': name, 'title': meeting.title, 'data': meeting.agenda,
                                    'time': meeting.startDate.strftime('%Y-%m-%d %H:%M'), 'duration': meeting.duration,
                                    'meetingkey': meeting.meetingKey, 'password': meeting.password, }
                        xsendEmail(email, projectsign, vars)
                    except Exception:
                        logexcption()

    sendmessage_WebEXMeetingMessageThread().start()

def sendmessage_WebEXMeetingCancelMessage(webEXUsers):
    """
    :param webEXUsers: Iterable object. like list、 queryset
    """
    class sendmessage_WebEXMeetingCancelMessageThread(threading.Thread):

        def run(self):
            for webexuser in webEXUsers:
                name, email, role, meeting = webexuser.name, webexuser.email, webexuser.meetingRole, webexuser.meeting
                if sendEmail and checkEmailTrue(email):
                    try:
                        if not role:
                            projectsign = '0PXbw'
                            vars = {'name': name, 'title': meeting.title, 'data': meeting.agenda,
                                        'time': meeting.startDate.strftime('%Y-%m-%d %H:%M'), 'duration': meeting.duration}
                            xsendEmail(email, projectsign, vars)
                    except Exception:
                        logexcption()

    sendmessage_WebEXMeetingCancelMessageThread().start()


def sendmessage_workReportDonotWrite(receiver):
    """
    :param webEXUsers: Iterable object. like list、 queryset
    """
    class sendmessage_workReportDonotWriteThread(threading.Thread):
        def run(self):
            if sendSms:
                try:
                    destination = receiver.mobile
                    projectsign = 'v9pNC4'
                    vars = {'user': receiver.usernameC}
                    res = xsendSms(destination, projectsign, vars)
                    print(res)
                except Exception:
                    logexcption()
    sendmessage_workReportDonotWriteThread().start()




# 判断是否发送消息
def checkReceiverToSendMsg(receiver):
    if receiver is not None:
        if isinstance(receiver, MyUser):
            if getattr(receiver, 'datasource_id') in [1, 3, 4, 5] and receiver.is_active:
                return True
    return False