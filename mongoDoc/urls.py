#coding=utf-8
from django.conf.urls import url
from mongoDoc import views

CompanyCatDataList = views.CompanyCatDataView.as_view({
        'get': 'list',
        'post':'create',
})


MergeFinanceDataList = views.MergeFinanceDataView.as_view({
        'get': 'list',
        'post':'create',
        'put':'update',
})

ProjectDataList = views.ProjectDataView.as_view({
        'get': 'list',
        'post':'create',
        'delete':'destroy',
})

ProjectSimpleList = views.ProjectDataView.as_view({
        'get': 'namelist',
})

ProjectExcelDataList = views.ProjectDataView.as_view({
        'post': 'excellist',
})


ProjectIndustryInfoList = views.ProjectIndustryInfoView.as_view({
        'get': 'retrieve',
        'post':'create',
})


ProjectNewsList = views.ProjectNewsView.as_view({
        'get': 'list',
        'post':'create',
})

ProjectRemarkList = views.ProjectRemarkView.as_view({
        'get': 'list',
        'post':'create',
        'put': 'update',
        'delete':'destroy',
})
EmailGroupList = views.GroupEmailDataView.as_view({
        'get': 'list',

})

WXChatDataList = views.WXChatDataView.as_view({
        'get': 'list',
        'put': 'update',
})

getCount = views.MergeFinanceDataView.as_view({
        'get':'getCount',
})


com_search = views.ProjectSearchNameView.as_view({
        'get':'list',
})



OpenAiChatTopicDataList = views.OpenAiChatTopicDataView.as_view({
        'get': 'list',
        'post': 'create',
        'put': 'update',
        'delete': 'destroy',
})


OpenAiChatDataList = views.OpenAiChatDataView.as_view({
        'get': 'list',
        'delete': 'destroy',
})

OpenAiZillizChatDataList = views.OpenAiZillizChatDataView.as_view({
        'get': 'list',
        'delete': 'destroy',
})

DiscordImageDataList = views.DiscordImageDataView.as_view({
        'get': 'list',
        'post': 'create',
        'put': 'update',
        'delete': 'destroy',
})


urlpatterns = [
    url(r'^proj/search', com_search, name='com_search-list', ),
    url(r'^cat', CompanyCatDataList, name='CompanyCatData-list', ),
    url(r'^event$', MergeFinanceDataList, name='MergeFinanceData-list', ),
    url(r'^proj$', ProjectDataList, name='ProjectData-list',),
    url(r'^proj/simple$', ProjectSimpleList, name='ProjectSimple-list',),
    url(r'^projexc$', ProjectExcelDataList, name='ProjectData-list',),
    url(r'^projinfo$', ProjectIndustryInfoList, name='ProjectIndustryInfo-list',),
    url(r'^projnews$', ProjectNewsList, name='ProjectNews-list',),
    url(r'^projremark$', ProjectRemarkList, name='ProjectRemark-list',),
    url(r'^email$', EmailGroupList,name='WXContent-list',),
    url(r'^wxmsg$', WXChatDataList, name='WXChatData-list', ),
    url(r'^count', getCount, name='count', ),
    url(r'^aichattopic', OpenAiChatTopicDataList, name='openaichattopicdata', ),
    url(r'^aichat', OpenAiChatDataList, name='openaichatdata', ),
    url(r'^aizillizchat', OpenAiZillizChatDataList, name='OpenAiZillizChatData', ),
    url(r'^discordimage', DiscordImageDataList, name='DiscordImageDataList', ),
]