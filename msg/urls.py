from django.conf.urls import url, include
import views



msg_list = views.WebMessageView.as_view({
        'get': 'list',
})
msg_detail = views.WebMessageView.as_view({
        'get': 'retrieve',
        'post': 'update',
        'delete': 'destroy',
})

schedule_list = views.ScheduleView.as_view({
        'get': 'list',
        'post': 'create',
})

schedule_detail = views.ScheduleView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy',
})


webexMeeting_list = views.WebEXMeetingView.as_view({
        'get': 'list',
        'post': 'create',
})

webexMeeting_check = views.WebEXMeetingView.as_view({
        'get': 'checkMeeingDateAvailable',
})

webexMeeting_detail = views.WebEXMeetingView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy',
})


webexuser_list = views.WebEXUserView.as_view({
        'get': 'list',
        'post': 'create',
})

webexuser_detail = views.WebEXUserView.as_view({
        'get': 'retrieve',
        # 'put': 'update',
        'delete': 'destroy',
})

InternOnlineTest_list = views.InternOnlineTestView.as_view({
        'get': 'list',
        'post': 'create',
})

InternOnlineTest_detail = views.InternOnlineTestView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy',
})


webexAPI_list = views.WebEXMeetingView.as_view({
        'post': 'getWebExMeetingListAPI',
})



urlpatterns = [
        url(r'^$', msg_list,name='msg-list'),
        url(r'^(?P<pk>\d+)/$', msg_detail,name='msg-detail'),
        url(r'^schedule/$', schedule_list, name='schedule-list'),
        url(r'^schedule/(?P<pk>\d+)/$', schedule_detail, name='schedule-detail'),
        url(r'^webexAPI/meeting/$', webexAPI_list, name='webexAPI_-list'),
        url(r'^webex/meeting/$', webexMeeting_list, name='webexMeeting-list'),
        url(r'^webex/meeting/(?P<pk>\d+)/$', webexMeeting_detail, name='webexMeeting-detail'),
        url(r'^webex/meeting/check/$', webexMeeting_check, name='webexMeeting_check'),
        url(r'^webex/user/$', webexuser_list, name='webexuser-list'),
        url(r'^webex/user/(?P<pk>\d+)/$', webexuser_detail, name='webexuser-detail'),
        url(r'^icsmail$', views.sendIcsFileEmail, name='sendIcsFileEmail'),
        url(r'^internTest/$', InternOnlineTest_list, name='InternOnlineTest-list'),
        url(r'^internTest/(?P<pk>\d+)/$', InternOnlineTest_detail, name='InternOnlineTest-detail'),
]