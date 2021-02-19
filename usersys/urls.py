#coding=utf-8
from django.conf.urls import url
from usersys import views


user_list = views.UserView.as_view({
        'get': 'list',
        'post': 'adduser',   #（系统内新增用户）
        'put': 'update',     #修改（批量）
        'delete': 'destroy', #删除（批量）
})

regist_user = views.UserView.as_view({
        'post':'create',   #注册
})

user_detail = views.UserView.as_view({
        'get': 'retrieve',   #查看详情
})

getFalseMobile = views.UserView.as_view({
        'get': 'getAvaibleFalseMobileNumber',   #查看详情
})

getRegistSource = views.UserView.as_view({
        'get': 'getUserRegisterSource',   # 获取注册来源
})

find_password = views.UserView.as_view({
        'post': 'findpassword',
})

change_password = views.UserView.as_view({
        'get': 'resetpassword',
        'put': 'changepassword'
})

getuserinfo_simple = views.UserView.as_view({
        'get': 'getUserSimpleInfo',
})


getUserInvestor = views.UserView.as_view({
        'get': 'getIndGroupInvestor',
})


user_relationshiplist = views.UserRelationView.as_view({
        'get': 'list',
        'post': 'create',
        'put': 'update',         #（批量）
        'delete': 'destroy',     #（批量）
})
checkrealtion = views.UserRelationView.as_view({
        'post': 'checkUserRelation',
})

checkFriendship = views.UserFriendshipView.as_view({
        'post': 'checkUserFriendShip',
})


detail_relationone = views.UserRelationView.as_view({
        'get': 'retrieve',
})

getUserCount = views.UserView.as_view({
        'get': 'getCount',
})

user_attachments = views.UserAttachmentView.as_view({
        'get': 'list',
        'post': 'create',
})

user_attachments_detail = views.UserAttachmentView.as_view({
        'put': 'update',
        'delete': 'destroy',
})


user_events = views.UserEventView.as_view({
        'get': 'list',
        'post': 'create',
})

user_events_detail = views.UserEventView.as_view({
        'put': 'update',
        'delete': 'destroy',
})


user_friendship = views.UserFriendshipView.as_view({
        'get': 'list',
        'post': 'create',
})

user_friendship_detail = views.UserFriendshipView.as_view({
        'put': 'update',
        'delete': 'destroy',
})

userremark_list = views.UserRemarkView.as_view({
        'get':'list',
        'post':'create',
})

userremark_detail = views.UserRemarkView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy',
})

group_list = views.GroupPermissionView.as_view({
        'get':'list',
        'post':'create',
})

group_permission = views.GroupPermissionView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy',
})

permission = views.PermissionView.as_view({
        'get':'list',
})

unreachuser_list = views.UnReachUserView.as_view({
        'get': 'list',
        'post': 'create',
})

unreachuser_deteil = views.UnReachUserView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy',
})

checkUserAccountExist = views.UserView.as_view({
        'get':'checkUserAccountExist',
})

urlpatterns = [
    url(r'^$', user_list,name='user-list',),
    url(r'^simple$', getuserinfo_simple,name='getuserinfo_simple',),
    url(r'^investor$', getUserInvestor,name='getUserInvestor_indGroup',),
    url(r'^regsource$', getRegistSource, name='getRegistSource', ),
    url(r'^mobile$', getFalseMobile, name='getAvaibleFalseMobileNumber', ),
    url(r'^count$', getUserCount, name='getUserCount', ),
    url(r'^checkexists/$', checkUserAccountExist,name='user-checkUserAccountExist',),
    url(r'^(?P<pk>\d+)/$', user_detail,name='user-one'),
    url(r'^password/$', find_password ,name='find-password'),
    url(r'^password/(?P<pk>\d+)/$', change_password ,name='change-password'),
    url(r'^atta/$',user_attachments, name='user_attachments-list'),
    url(r'^atta/(?P<pk>\d+)/$', user_attachments_detail, name='user_attachments-detail'),
    url(r'^event/$',user_events, name='user_events-list'),
    url(r'^event/(?P<pk>\d+)/$', user_events_detail, name='user_events-detail'),
    url(r'^relationship/$', user_relationshiplist, name='user-relationshiplist'),
    url(r'^checkrelation/$', checkrealtion, name='user-checkrealtion'),
    url(r'^checkfriendship/$', checkFriendship, name='user-checkfriendship'),
    url(r'^relationship/(?P<pk>\d+)/$', detail_relationone, name='user-relationshipone'),
    url(r'^register/$', regist_user),
    url(r'^login/$', views.login),
    url(r'^friend/$', user_friendship, name='user-friendship'),
    url(r'^friend/(?P<pk>\d+)/$', user_friendship_detail, name='user-friendship-detail'),
    url(r'^group/$', group_list, name='group-list'),
    url(r'^group/(?P<pk>\d+)/$', group_permission, name='group_permission-detail'),
    url(r'^perm/$', permission, name='permission-list'),
    url(r'^unuser/$',unreachuser_list, name='unreachuser-list'),
    url(r'^unuser/(?P<pk>\d+)/$', unreachuser_deteil, name='unreachuser_-detail'),
    url(r'^remark/$',userremark_list, name='userremark-list'),
    url(r'^remark/(?P<pk>\d+)/$', userremark_detail, name='userremark-detail'),
    url(r'^session/$', views.getSessionToken),
    url(r'^checksession/$', views.checkRequestSessionToken),
    # url(r'^test/$',views.test)
]
