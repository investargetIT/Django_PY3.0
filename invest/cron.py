#coding=utf-8
import threading

import datetime

from BD.views import sendExpiredOrgBDEmail, sendWorkReportMessage, downloadProjectBDCommentAttachments
from dataroom.views import downloadDataroomFiles
from emailmanage.views import getAllProjectsNeedToSendMail, sendEmailToUser
from msg.models import schedule
from org.views import downloadOrgAttachments
from proj.views import importDidiRecordCsvFile
from third.views.feishuyun import update_feishu_excel
from utils.sendMessage import sendmessage_schedulemsg


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


def task4_sendAllExpiredMsg():
    class task4_Thread(threading.Thread):
        def run(self):
            sendExpiredScheduleMsg()
            sendExpiredOrgBDEmail()
    task4_Thread().start()


def task5_downloadOrgAttachments():
    class task5_Thread(threading.Thread):
        def run(self):
            start = datetime.datetime.now() - datetime.timedelta(hours=1)
            downloadDataroomFiles(start)
            downloadOrgAttachments(start)
            downloadProjectBDCommentAttachments(start)
    task5_Thread().start()



def task7_sendWorkReportMsg():
    class task7_Thread(threading.Thread):
        def run(self):
            sendWorkReportMessage()
    task7_Thread().start()



def task8_importDidiRecordCsv():
    class task8_Thread(threading.Thread):
        def run(self):
            importDidiRecordCsvFile()
    task8_Thread().start()


def task9_updateFeiShuExcel():
    class task8_Thread(threading.Thread):
        def run(self):
            update_feishu_excel()
    task8_Thread().start()

















def sendExpiredScheduleMsg():
    schedule_qs = schedule.objects.all().filter(is_deleted=False,
                                                scheduledtime__year=datetime.datetime.now().year,
                                                scheduledtime__month=datetime.datetime.now().month,
                                                scheduledtime__day=datetime.datetime.now().day)
    if schedule_qs.exists():
        for instance in schedule_qs:
            sendmessage_schedulemsg(instance, receiver=instance.createuser,
                                    types=['app', 'webmsg'])
