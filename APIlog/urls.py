#coding=utf-8
from django.conf.urls import url
from APIlog import views


apilog = views.APILogView.as_view({
        'get': 'list',
})

logininlog = views.LoginLogView.as_view({
        'get': 'list',
})

viewprojlog = views.ViewprojLogView.as_view({
        'get': 'list',
})

userinfoupdatelog = views.UserInfoUpdateLogView.as_view({
        'get': 'list',
})

urlpatterns = [
    url(r'^login$', logininlog,name='logininlog',),
    url(r'^api$', apilog,name='apilog'),
    url(r'^viewproj$', viewprojlog,name='viewprojlog'),
    url(r'^userupdate', userinfoupdatelog,name='userinfoupdatelog'),
]