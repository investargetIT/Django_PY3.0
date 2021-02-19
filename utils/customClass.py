#coding=utf-8
import datetime
import io

import operator
from django.db import models
from django.db.models import Q
from django.db.models.constants import LOOKUP_SEP
from django.http import HttpResponse
from django.utils import six
from qiniu.services.storage.upload_progress_recorder import UploadProgressRecorder
from rest_framework import throttling
from rest_framework.compat import is_authenticated, distinct
from rest_framework.filters import SearchFilter
from rest_framework.renderers import JSONRenderer
from django import forms
from invest.settings import APILOG_PATH
from utils.responsecode import responsecode
from django_filters import Filter, FilterSet, STRICTNESS
import json
import os
import base64

class JSONResponse(HttpResponse):
    def __init__(self,data, **kwargs):
        content = JSONRenderer().render(data=data)
        kwargs['content_type'] = 'application/json; charset=utf-8'
        super(JSONResponse, self).__init__(content , **kwargs)

class InvestError(Exception):
    def __init__(self, code,msg=None):
        self.code = code
        if msg:
            self.msg = msg
        else:
            self.msg = responsecode[str(code)]


class MyFilterSet(FilterSet):

    def __init__(self, data=None, queryset=None, prefix=None, strict=None, request=None):
        self.union_param = 'unionFields'
        self.union_fields = self.get_union_fields(request)
        super(MyFilterSet, self).__init__(data=data, queryset=queryset, prefix=prefix, strict=strict, request=request)

    def get_union_fields(self, request=None):
        params = ''
        if request:
            params = request.query_params.get(self.union_param, '')
        return params.replace(',', ' ').split()

    @property
    def qs(self):
        if not hasattr(self, '_qs'):
            if not self.is_bound:
                self._qs = self.queryset.all()
                return self._qs

            if not self.form.is_valid():
                if self.strict == STRICTNESS.RAISE_VALIDATION_ERROR:
                    raise forms.ValidationError(self.form.errors)
                elif self.strict == STRICTNESS.RETURN_NO_RESULTS:
                    self._qs = self.queryset.none()
                    return self._qs
            qs = self.queryset.all()
            for name, filter_ in six.iteritems(self.filters):
                value = self.form.cleaned_data.get(name)
                if value is not None and name not in self.union_fields:  # valid & clean data
                    qs = filter_.filter(qs, value)

            self._qs = self.unionFilterQuerySet(qs)
        return self._qs

    def unionFilterQuerySet(self, queryset):
        queries = []
        base = queryset
        for field in self.union_fields:
            isNull = False
            value = self.request.GET.get(field, '')
            if value in ([], (), {}, '', None):
                continue
            value = value.split(',')
            newvalue = []
            for i in range(0, len(value)):
                if value[i] in (u'true', 'true'):
                    newvalue.append(True)
                elif value[i] in (u'false', 'false'):
                    newvalue.append(False)
                elif value[i] in (u'none', 'none'):
                    isNull = True
                else:
                    newvalue.append(value[i])
            queries.append(models.Q(**{LOOKUP_SEP.join([field, 'in']): newvalue}))
            if isNull:
                queries.append(models.Q(**{LOOKUP_SEP.join([field, 'isnull']): isNull}))
        if len(queries) > 0:
            queryset = queryset.filter(reduce(operator.or_, queries))
            queryset = distinct(queryset, base)
        return queryset


class RelationFilter(Filter):
    def __init__(self, filterstr,lookup_method='exact',relationName=None, **kwargs):
        self.filterstr = filterstr
        self.lookup_method = lookup_method
        self.relationName = relationName
        super(RelationFilter,self).__init__(**kwargs)
    def filter(self, qs, value):
        isNull = False
        value = self.parent.request.GET[self.name]
        if value in ([], (), {}, '', None):
            return qs
        if self.lookup_method == 'in':
            value = value.split(',')
            newvalue = []
            for i in range(0, len(value)):
                if value[i] in (u'true', 'true'):
                    newvalue.append(True)
                elif value[i] in (u'false', 'false'):
                    newvalue.append(False)
                elif value[i] in (u'none', 'none'):
                    isNull = True
                else:
                    newvalue.append(value[i])
            value = newvalue
        else:
            if value in (u'true', 'true'):
                value = True
            if value in (u'false', 'false'):
                value = False
            if value in (u'none', 'none'):
                value = None
                isNull = True
        if self.relationName is not None:
            if isNull:
                return qs.filter(Q(**{'%s__%s' % (self.filterstr, self.lookup_method): value, self.relationName: False}) | Q(**{'%s__isnull' % self.filterstr: isNull})).distinct()
            else:
                return qs.filter(**{'%s__%s' % (self.filterstr, self.lookup_method): value, self.relationName:False}).distinct()
        else:
            if isNull:
                return qs.filter(Q(**{'%s__%s' % (self.filterstr, self.lookup_method): value}) | Q(**{'%s__isnull' % self.filterstr: isNull})).distinct()
            else:
                return qs.filter(**{'%s__%s' % (self.filterstr, self.lookup_method): value}).distinct()

class MySearchFilter(SearchFilter):
    def get_search_terms(self, request):
        """
        Search terms are set by a ?search=... query parameter,
        and may be comma and/or whitespace delimited.
        """
        params = request.query_params.get(self.search_param, '')
        return params.replace('，', ',').replace(',', ' ').split()

    def filter_queryset(self, request, queryset, view):
        search_fields = getattr(view, 'search_fields', None)
        search_terms = map(lambda x: x.strip(), self.get_search_terms(request))

        if not search_fields or not search_terms:
            return queryset

        orm_lookups = [
            self.construct_search(six.text_type(search_field))
            for search_field in search_fields
            ]

        qslist = []
        for search_term in search_terms:
            queries = [
                models.Q(**{orm_lookup: search_term})
                for orm_lookup in orm_lookups
                ]
            qs = queryset.filter(reduce(operator.or_, queries))
            qslist.append(qs)
        queryset = reduce(lambda x,y:x|y,qslist).distinct()
        return queryset


class AppEventRateThrottle(throttling.SimpleRateThrottle):
    scope = 'rw_mongodata'

    def get_cache_key(self, request, view):
        if is_authenticated(request.user):
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

class MyModel(models.Model):
    lastmodifytime = models.DateTimeField(blank=True, null=True)
    createdtime = models.DateTimeField(blank=True, null=True)
    deletedtime = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(blank=True, default=False)

    class Meta:
        abstract = True

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None, automodifytime=True):
        if self.createdtime is None:
            self.createdtime = datetime.datetime.now()
        if automodifytime or not self.lastmodifytime:
            self.lastmodifytime = datetime.datetime.now()
        super(MyModel,self).save(force_insert, force_update, using, update_fields)

class MyForeignKey(models.ForeignKey):
    def __init__(self, to, on_delete=None, related_name=None, related_query_name=None,
                 limit_choices_to=None, parent_link=False, to_field=None,
                 db_constraint=True, **kwargs):
        if kwargs.get('null'):
            if on_delete:
                pass
            else:
                on_delete = models.SET_NULL
        super(MyForeignKey, self).__init__(to,on_delete=on_delete,related_name=related_name,related_query_name=related_query_name,
                                           limit_choices_to=limit_choices_to,parent_link=parent_link,to_field=to_field,db_constraint=db_constraint,**kwargs)

    def get_extra_descriptor_filter(self,instance):
        # if hasattr(instance,'is_deleted'):
        #     return {'is_deleted':False}
        return {}


class MyUploadProgressRecorder(UploadProgressRecorder):
    def __init__(self):
        self.record_folder = APILOG_PATH['qiniuuploadprogresspath']
    #
    def get_upload_record(self, file_name, key):
        key = '{0}.{1}.doc'.format(key,'p')
        key = base64.urlsafe_b64encode(key.encode('utf-8'))
        upload_record_file_path = os.path.join(self.record_folder,
                                               key)
        if not os.path.isfile(upload_record_file_path):
            return None
        with open(upload_record_file_path, 'r') as f:
            json_data = json.load(f)
        return json_data

    def set_upload_record(self, file_name, key, data):
        key = '{0}.{1}.doc'.format(key, 'p')
        key = base64.urlsafe_b64encode(key.encode('utf-8'))
        upload_record_file_path = os.path.join(self.record_folder, key)
        with open(upload_record_file_path, 'w') as f:
            json.dump(data, f)

    def delete_upload_record(self, file_name, key):
        key = '{0}.{1}.doc'.format(key, 'p')
        key = base64.urlsafe_b64encode(key.encode('utf-8'))
        record_file_path = os.path.join(self.record_folder,
                                        key)
        os.remove(record_file_path)


class CalendarEvent:
    """
    事件对象
    """

    def __init__(self, kwargs):
        self.event_data = kwargs

    def __turn_to_string__(self):
        self.event_text = "BEGIN:VEVENT\n"
        for item, data in self.event_data.items():
            item = str(item).replace("_", "-")
            if item not in ["ORGANIZER", "DTSTART", "DTEND", "ATTENDEE"]:
                self.event_text += "%s:%s\n" % (item, data)
            else:
                self.event_text += "%s;%s\n" % (item, data)
        self.event_text += "END:VEVENT\n"
        return self.event_text


class MyCalendar:
    """
    日历对象
    """

    def __init__(self, calendar_name="My Calendar"):
        self.__events__ = {}
        self.__event_id__ = 0
        self.calendar_name = calendar_name

    def add_event(self, **kwargs):
        event = CalendarEvent(kwargs)
        event_id = self.__event_id__
        self.__events__[self.__event_id__] = event
        self.__event_id__ += 1
        return event_id

    def modify_event(self, event_id, **kwargs):
        for item, data in kwargs.items():
            self.__events__[event_id].event_data[item] = data

    def remove_event(self, event_id):
        self.__events__.pop(event_id)

    def get_ics_text(self):
        self.__calendar_text__ = """BEGIN:VCALENDAR\nPRODID:-//Microsoft Corporation//Outlook 10.0 MIMEDIR//EN\nVERSION:2.0\nMETHOD:REQUEST\nBEGIN:VTIMEZONE\nTZID:China Time\nBEGIN:STANDARD\nTZOFFSETFROM:+0800\nTZOFFSETTO:+0800\nTZNAME:Standard Time\nEND:STANDARD\nEND:VTIMEZONE\n"""
        for key, value in self.__events__.items():
            self.__calendar_text__ += value.__turn_to_string__()
        self.__calendar_text__ += "END:VCALENDAR"
        return self.__calendar_text__

    def save_as_ics_file(self, path=None):
        if path:
            savePath = os.path.join(path, "%s.ics" % self.calendar_name)
        else:
            savePath = "%s.ics" % self.calendar_name
        ics_text = self.get_ics_text().decode('utf-8')
        io.open(savePath, "w", encoding="utf-8").write(ics_text)  # 使用utf8编码生成ics文件，否则日历软件打开是乱码

    def open_ics_file(self):
        os.system("%s.ics" % self.calendar_name)


def add_CalendarEvent(cal, SUMMARY, DTSTART, DTEND, DESCRIPTION, LOCATION):
    """
    向Calendar日历对象添加事件的方法
    :param cal: calender日历实例
    :param SUMMARY: 事件名
    :param DTSTART: 事件开始时间
    :param DTEND: 时间结束时间
    :param DESCRIPTION: 备注
    :param LOCATION: 时间地点
    :return:
    """
    time_format = "TZID=\"China Time\":{date.year}{date.month:0>2d}{date.day:0>2d}T{date.hour:0>2d}{date.minute:0>2d}00"
    dt_start = time_format.format(date=DTSTART)
    dt_end = time_format.format(date=DTEND)
    create_time = datetime.datetime.today().strftime("%Y%m%dT%H%M%SZ")
    attend = ";ROLE=REQ-PARTICIPANT;RSVP=FALSE:MAILTO:summer.xia@investarget.com"
    organizer="CN=\"\":MAILTO:"
    cal.add_event(
        SUMMARY=SUMMARY,
        DTSTART=dt_start,
        ATTENDEE=attend,
        ORGANIZER=organizer,
        DTEND=dt_end,
        DTSTAMP=create_time,
        UID="{}-1397@investarget.com".format(create_time),
        SEQUENCE="0",
        CREATED=create_time,
        DESCRIPTION=DESCRIPTION,
        LAST_MODIFIED=create_time,
        LOCATION=LOCATION,
        TRANSP="OPAQUE"
    )

