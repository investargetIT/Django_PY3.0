#coding=utf-8
import threading

import datetime

from django.db.models import Count

from BD.models import OrgBD
from BD.views import sendExpiredOrgBDEmail, sendWorkReportMessage
from dataroom.views import downloadDataroomPDFs
from emailmanage.views import getAllProjectsNeedToSendMail, sendEmailToUser
from msg.models import schedule
from org.views import downloadOrgAttachments
from third.views.huanxin import downloadChatMessages
from third.views.zoom import refreshAccessToken
from timeline.models import timelineTransationStatu
from utils.sendMessage import sendmessage_schedulemsg, sendmessage_timelinealertcycleexpire, \
    sendmessage_orgBDExpireMessage


def task1_loadsendmailproj():
    class task1_Thread(threading.Thread):
        def run(self):
            getAllProjectsNeedToSendMail()
    task1_Thread().start()

def task2_sendmailprojtouser():
    class task2_Thread(threading.Thread):
        def run(self):
            sendEmailToUser()
    task2_Thread().start()

def task3_downloadDataroomPDFs():
    class task3_Thread(threading.Thread):
        def run(self):
            downloadDataroomPDFs()
    task3_Thread().start()


def task4_sendAllExpiredMsg():
    class task4_Thread(threading.Thread):
        def run(self):
            sendExpiredScheduleMsg()
            sendExpiredTimelineMsg()
            sendExpiredOrgBDEmail()
    task4_Thread().start()


def task5_downloadOrgAttachments():
    class task5_Thread(threading.Thread):
        def run(self):
            downloadOrgAttachments()
    task5_Thread().start()

def task6_refreshZoomToken():
    class task6_Thread(threading.Thread):
        def run(self):
            refreshAccessToken()
    task6_Thread().start()


def task7_sendWorkReportMsg():
    class task7_Thread(threading.Thread):
        def run(self):
            sendWorkReportMessage()
    task7_Thread().start()






















def sendExpiredScheduleMsg():
    schedule_qs = schedule.objects.all().filter(is_deleted=False,
                                                scheduledtime__year=datetime.datetime.now().year,
                                                scheduledtime__month=datetime.datetime.now().month,
                                                scheduledtime__day=datetime.datetime.now().day)
    if schedule_qs.exists():
        for instance in schedule_qs:
            sendmessage_schedulemsg(instance, receiver=instance.createuser,
                                    types=['app', 'webmsg'])
def sendExpiredTimelineMsg():
    timelineTransationStatu_qs = timelineTransationStatu.objects.all().filter(is_deleted=False,isActive=True,
                                                               inDate__year=datetime.datetime.now().year,
                                                               inDate__month=datetime.datetime.now().month,
                                                               inDate__day=datetime.datetime.now().day)
    if timelineTransationStatu_qs.exists():
        for instance in timelineTransationStatu_qs:
            sendmessage_timelinealertcycleexpire(instance, receiver=instance.createuser,
                                    types=['app', 'webmsg'])
