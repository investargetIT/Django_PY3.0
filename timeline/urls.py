#coding=utf-8
from django.conf.urls import url
from timeline import views

timelines = views.TimelineView.as_view({
        'get': 'list',
        'post': 'create',
        'delete': 'destroy',
})
timeline_detail = views.TimelineView.as_view({
        'get':'retrieve',
        'put': 'update',
})
timelinesbasic = views.TimelineView.as_view({
        'get': 'basiclist',
})

timelineremark = views.TimeLineRemarkView.as_view({
        'get': 'list',
        'post': 'create',
})


timelineremark_detail = views.TimeLineRemarkView.as_view({
        'get':'retrieve',
        'put': 'update',
        'delete': 'destroy',
})




urlpatterns = [
    url(r'^$', timelines,name='timeline-list',),
    url(r'^basic/$', timelinesbasic, name='timeline-basiclist', ),
    url(r'^(?P<pk>\d+)/$', timeline_detail,name='timeline-detail'),
    url(r'^remark/$', timelineremark, name='timelineremark-list'),
    url(r'^remark/(?P<pk>\d+)/$', timelineremark_detail, name='timelineremark-detail'),

]