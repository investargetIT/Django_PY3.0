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

urlpatterns = [
        url(r'^$', proj_list , name='proj_list'),
        url(r'^(?P<pk>\d+)/$', proj_detail, name='proj_detail'),
        url(r'^count$', proj_count, name='proj_count'),
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
        url(r'^pdf/(?P<pk>\d+)/$',getprojpdf,name='getprojpdf'),
        url(r'^test/$',views.testPdf),
]