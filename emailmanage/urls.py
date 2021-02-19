#coding=utf-8
from django.conf.urls import url
from emailmanage import views

sendemaillist = views.EmailgroupsendlistView.as_view({
        'get': 'list',
        'post': 'update',
})

urlpatterns = [
    url(r'^$', sendemaillist,name='sendemail-list',),

]