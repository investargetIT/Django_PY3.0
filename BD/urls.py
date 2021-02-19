from django.conf.urls import url, include
from BD import views

projbd_list = views.ProjectBDView.as_view({
        'get': 'list',
        'post': 'create'
})

projbd_count = views.ProjectBDView.as_view({
        'get': 'countBd',
})
projbd_detail = views.ProjectBDView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
})

projbdmanagers_create = views.ProjectBDManagersView.as_view({
        'post': 'create'
})
projbdmanagers_delete = views.ProjectBDManagersView.as_view({
        'delete': 'destroy'
})


projdbcomment_list = views.ProjectBDCommentsView.as_view({
        'get': 'list',
        'post': 'create'
})
projbdcomment_detail = views.ProjectBDCommentsView.as_view({
        'put': 'update',
        'delete': 'destroy'
})
orgbd_baselist = views.OrgBDView.as_view({
        'get': 'countBDProjectOrg',
})

orgbd_list = views.OrgBDView.as_view({
        'get': 'list',
        'post': 'create'
})

orgbd_managercount = views.OrgBDView.as_view({
        'get': 'countBDManager',

})

orgbd_responsecount = views.OrgBDView.as_view({
        'get': 'countBDResponse',

})

orgbd_read = views.OrgBDView.as_view({
        'post': 'readBd',
})

orgbd_projectcount = views.OrgBDView.as_view({
        'get': 'countBDProject',
})

orgbd_detail = views.OrgBDView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
})
orgbdcomment_list = views.OrgBDCommentsView.as_view({
        'get': 'list',
        'post': 'create'
})
orgbdcomment_detail = views.OrgBDCommentsView.as_view({
        'put': 'update',
        'delete': 'destroy'
})

orgbdblack_list = views.OrgBDBlackView.as_view({
        'get': 'list',
        'post': 'create'
})
orgbdblack_detail = views.OrgBDBlackView.as_view({
        'put': 'update',
        'delete': 'destroy'
})


meetbd_list = views.MeetingBDView.as_view({
        'get': 'list',
        'post': 'create'
})

meetbd_share = views.MeetingBDView.as_view({
        'get': 'getShareMeetingBDdetail',
        'post': 'getShareMeetingBDtoken'
})

meetbd_detail = views.MeetingBDView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
})

deleteAttachment = views.MeetingBDView.as_view({
        'post': 'deleteAttachment',

})


workreport_list = views.WorkReportView.as_view({
        'get': 'list',
        'post': 'create'
})
workreport_detail = views.WorkReportView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
})

workreportmarketmsg_list = views.WorkReportMarketMsgView.as_view({
        'get': 'list',
        'post': 'create'
})
workreportmarketmsg_detail = views.WorkReportMarketMsgView.as_view({
        'put': 'update',
        'delete': 'destroy'
})

workreportproj_list = views.WorkReportProjInfoView.as_view({
        'get': 'list',
        'post': 'create'
})
workreportproj_detail = views.WorkReportProjInfoView.as_view({
        'put': 'update',
        'delete': 'destroy'
})


okr_list = views.OKRView.as_view({
        'get': 'list',
        'post': 'create'
})

okr_detail = views.OKRView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
})

okrResult_list = views.OKRResultView.as_view({
        'get': 'list',
        'post': 'create'
})

okrResult_detail = views.OKRResultView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
})


urlpatterns = [
        url(r'^projbd/$', projbd_list, name='projbd_list'),
        url(r'^projbd/count/$', projbd_count, name='projbd_count'),
        url(r'^projbd/(?P<pk>\d+)/$', projbd_detail, name='projbd_detail'),
        url(r'^projbd/relatemanager/$', projbdmanagers_create, name='projbdmanagers_create'),
        url(r'^projbd/relatemanager/(?P<pk>\d+)/$', projbdmanagers_delete, name='projbdmanagers_delete'),
        url(r'^projbd/$', projbd_list, name='projbd_list'),
        url(r'^projbd/comment/$', projdbcomment_list, name='projdbcomment_list'),
        url(r'^projbd/comment/(?P<pk>\d+)/$', projbdcomment_detail, name='projbdcomment_detail'),
        url(r'^orgbd/$', orgbd_list, name='orgbd_list'),
        url(r'^orgbd/read/$', orgbd_read, name='orgbd_read'),
        url(r'^orgbdbase/$', orgbd_baselist, name='orgbdbase_list'),
        url(r'^orgbd/count/$', orgbd_managercount, name='orgbd_managercount'),
        url(r'^orgbd/response/$', orgbd_responsecount, name='orgbd_responsecount'),
        url(r'^orgbd/proj/$', orgbd_projectcount, name='orgbd_projectcount'),
        url(r'^orgbd/(?P<pk>\d+)/$', orgbd_detail, name='orgbd_detail'),
        url(r'^orgbd/black/$', orgbdblack_list, name='orgbdblack_list'),
        url(r'^orgbd/black/(?P<pk>\d+)/$', orgbdblack_detail, name='orgbdblack_detail'),
        url(r'^orgbd/comment/$', orgbdcomment_list, name='orgbdcomment_list'),
        url(r'^orgbd/comment/(?P<pk>\d+)/$', orgbdcomment_detail, name='orgbdcomment_detail'),
        url(r'^meetbd/$', meetbd_list, name='meetbd_list'),
        url(r'^meetbd/share/$', meetbd_share, name='meetbd_share'),
        url(r'^meetbd/(?P<pk>\d+)/$', meetbd_detail, name='meetbd_detail'),
        url(r'^meetbd/delatt/(?P<pk>\d+)/$', deleteAttachment, name='deleteAttachment'),

        url(r'^workreport/$', workreport_list, name='workreport_list'),
        url(r'^workreport/(?P<pk>\d+)/$', workreport_detail, name='workreport_detail'),
        url(r'^workreport/market/$', workreportmarketmsg_list, name='workreportmarketmsg_list'),
        url(r'^workreport/market/(?P<pk>\d+)/$', workreportmarketmsg_detail, name='workreportmarketmsg_detail'),
        url(r'^workreport/proj/$', workreportproj_list, name='workreportproj_list'),
        url(r'^workreport/proj/(?P<pk>\d+)/$', workreportproj_detail, name='workreportproj_detail'),

        url(r'^okr/$', okr_list, name='okr_list'),
        url(r'^okr/(?P<pk>\d+)/$', okr_detail, name='okr_detail'),
        url(r'^okr/krs/$', okrResult_list, name='okrResult_list'),
        url(r'^okr/krs/(?P<pk>\d+)/$', okrResult_detail, name='okrResult_detail'),
]