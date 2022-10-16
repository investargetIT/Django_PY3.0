from django.conf.urls import url, include
# from rest_framework import routers

from proj import views
proj_list = views.ProjectView.as_view({
        'get': 'list',
        'post': 'create'
})

proj_count = views.ProjectView.as_view({
        'get': 'countProject'
})

proj_detail = views.ProjectView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
})

sendWXGroupPdfURI = views.ProjectView.as_view({
        'post':'sendWXGroupPdf'
})


projTraders_list = views.ProjTradersView.as_view({
        'get': 'list',
        'post': 'create'
})

projTraders_detail = views.ProjTradersView.as_view({
        'put': 'update',
        'delete': 'destroy'
})


proj_finance = views.ProjFinanceView.as_view({
        'get': 'list',
        'post':'create',
        'put': 'update',
        'delete': 'destroy'
})

proj_attachment = views.ProjAttachmentView.as_view({
        'get': 'list',
        'post':'create',
        'put': 'update',
        'delete': 'destroy'
})


proj_didiRecord = views.ProjDiDiRecordView.as_view({
        'get': 'list',
        'post':'create',
})

getshareprojtoken = views.ProjectView.as_view({
        'get':'getshareprojtoken'
})

getshareproj = views.ProjectView.as_view({
        'get':'getshareprojdetail'
})

getprojpdf = views.ProjectView.as_view({
        'get':'sendPDF'
})

projcomments_list = views.ProjCommentsView.as_view({
        'get': 'list',
        'post': 'create'
})

projcomments_detail = views.ProjCommentsView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
})


governmentproj_list = views.GovernmentProjectView.as_view({
        'get': 'list',
        'post': 'create'
})

governmentproj_detail = views.GovernmentProjectView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
})

governmentprojinfo_list = views.GovernmentProjectInfoView.as_view({
        'get': 'list',
        'post': 'create'
})

governmentprojinfo_detail = views.GovernmentProjectInfoView.as_view({
        'put': 'update',
})
governmentprojinfoatta_list = views.GovernmentProjectInfoAttachmentView.as_view({
        'get': 'list',
        'post': 'create'
})

governmentprojinfoatta_detail = views.GovernmentProjectInfoAttachmentView.as_view({
        'delete': 'destroy'
})
governmentprojhistycase_list = views.GovernmentProjectHistoryCaseView.as_view({
        'get': 'list',
        'post': 'create'
})

governmentprojhistycase_detail = views.GovernmentProjectHistoryCaseView.as_view({
        'delete': 'destroy'
})
governmentprojtrader_list = views.GovernmentProjectTraderView.as_view({
        'get': 'list',
        'post': 'create'
})

governmentprojtrader_detail = views.GovernmentProjectTraderView.as_view({
        'delete': 'destroy'
})

urlpatterns = [
        url(r'^$', proj_list , name='proj_list'),
        url(r'^(?P<pk>\d+)/$', proj_detail, name='proj_detail'),
        url(r'^traders$', projTraders_list , name='projTraders_list'),
        url(r'^count$', proj_count, name='proj_count'),
        url(r'^traders/(?P<pk>\d+)/$', projTraders_detail, name='projTraders_detail'),
        url(r'^sendpdf/(?P<pk>\d+)/$', sendWXGroupPdfURI, name='sendWXGroupPdf'),
        url(r'^finance/$', proj_finance, name='proj_finance'),
        url(r'^attachment/$', proj_attachment, name='proj_attachment'),
        url(r'^didi/$', proj_didiRecord, name='proj_didiRecord'),
        url(r'^share/(?P<pk>\d+)/$',getshareprojtoken,name='getshareprojtoken'),
        url(r'^shareproj/$',getshareproj,name='getshareprojdetail'),
        url(r'^comment/$', projcomments_list, name='projcomments-list'),
        url(r'^comment/(?P<pk>\d+)/$', projcomments_detail, name='projcomments-detail'),
        url(r'^govproj/$', governmentproj_list, name='governmentproj-list'),
        url(r'^govproj/(?P<pk>\d+)/$', governmentproj_detail, name='governmentproj-detail'),
        url(r'^govproj/info/$', governmentprojinfo_list, name='governmentprojinfo-list'),
        url(r'^govproj/info/(?P<pk>\d+)/$', governmentprojinfo_detail, name='governmentprojinfo-detail'),
        url(r'^govproj/info/atta/$', governmentprojinfoatta_list, name='governmentprojinfoatta-list'),
        url(r'^govproj/info/atta/(?P<pk>\d+)/$', governmentprojinfoatta_detail, name='governmentprojinfoatta-detail'),
        url(r'^govproj/historycase/$', governmentprojhistycase_list, name='governmentprojhistycase-list'),
        url(r'^govproj/historycase/(?P<pk>\d+)/$', governmentprojhistycase_detail, name='governmentprojhistycase-detail'),
        url(r'^govproj/trader/$', governmentprojtrader_list, name='governmentprojtrader-list'),
        url(r'^govproj/trader/(?P<pk>\d+)/$', governmentprojtrader_detail, name='governmentprojtrader-detail'),

        url(r'^pdf/(?P<pk>\d+)/$',getprojpdf,name='getprojpdf'),
        url(r'^test/$',views.testPdf),
]