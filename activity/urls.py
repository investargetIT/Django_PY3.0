#coding=utf-8
from django.conf.urls import url
from activity import views


activityView = views.ActivityView.as_view({
        'get': 'list',
})


urlpatterns = [
    url(r'^$', activityView,name='activity-list',),
]