#coding=utf-8
from django.conf.urls import url
from sourcetype import views

tag = views.TagView.as_view({
        'get': 'list',
        'post':'create',
})

tag_detail = views.TagView.as_view({
        'put': 'update',
        'delete':'destroy',
})

projstatus = views.ProjectStatusView.as_view({
        'get': 'list',

})
service = views.ServiceView.as_view({
        'get': 'list',
        # 'post':'create',
})


orgbdresponse = views.OrgBdResponseView.as_view({
        'get': 'list',
})

orgleveltype = views.OrgLevelTypeView.as_view({
        'get': 'list',
})

familiarlevel = views.FamiliarLevelView.as_view({
        'get': 'list',
})

country = views.CountryView.as_view({
        'get': 'list',
        'post':'create',
})

country_one = views.CountryView.as_view({
        'delete':'destroy',
})

didiType = views.DidiOrderTypeView.as_view({
        'get': 'list',
})


character = views.CharacterTypeView.as_view({
        'get': 'list',
        # 'post':'create',
})



title = views.TitleView.as_view({
        'get': 'list',
        # 'post':'create',
})


industry = views.IndustryView.as_view({
        'get': 'list',
        # 'post':'create',
})



datasource = views.DatasourceView.as_view({
        'get': 'list',
        # 'post':'create',
})



orgarea = views.OrgAreaView.as_view({
        'get': 'list',
        # 'post':'create',
})

bdStatus = views.BDStatusView.as_view({
        'get': 'list',
        # 'post':'create',
})

orgtype = views.OrgTypeView.as_view({
        'get': 'list',
        # 'post':'create',
})

orgAttribute = views.OrgAttributeView.as_view({
        'get': 'list',
        # 'post':'create',
})

transactionType = views.TransactionTypeView.as_view({
        'get': 'list',
        # 'post':'create',
})


transactionPhases = views.TransactionPhasesView.as_view({
        'get': 'list',
        # 'post':'create',
})

educationType = views.EducationView.as_view({
        'get': 'list',
        # 'post':'create',
})

performanceAppraisalLevelType = views.PerformanceAppraisalLevelView.as_view({
        'get': 'list',
        # 'post':'create',
})


currencyType = views.CurrencyTypeView.as_view({
        'get': 'list',
        # 'post':'create',
})


Orgtitletable = views.OrgtitletableView.as_view({
        'get': 'list',
        # 'post':'create',
})


IndustryGroup = views.IndustryGroupView.as_view({
        'get': 'list',
})


TrainingType = views.TrainingTypeView.as_view({
        'get': 'list',
})


TrainingStatus = views.TrainingStatusView.as_view({
        'get': 'list',
})


Webmenu = views.WebmenuView.as_view({
        'get': 'list',
})

ProjProgressContrast = views.ProjProgressContrastTableView.as_view({
        'get': 'list',
})

AndroidVersion = views.AndroidAppVersionView.as_view({
        'get': 'list',
        'post':'create',
})

AndroidVersion_detail = views.AndroidAppVersionView.as_view({
        'put': 'update',
        'delete':'destroy',
})

urlpatterns = [
    url(r'^tag$', tag,name='tagsource',),

    url(r'^tag/(?P<pk>\d+)/$', tag_detail,name='tag_detail',),

    url(r'^service', service,name='servicesource',),

    url(r'^orgAttribute', orgAttribute,name='orgAttributesource',),

    url(r'^orgbdres', orgbdresponse, name='orgbdresponsesource', ),

    url(r'^orglv', orgleveltype, name='orgleveltypesource', ),

    url(r'^famlv', familiarlevel, name='familiarlevelsource', ),

    url(r'^projstatus$', projstatus, name='projstatus', ),

    url(r'^country$', country,name='countrysource',),
    url(r'^country/(?P<pk>\d+)/$', country_one,name='countrysource',),

    url(r'^industry$', industry,name='industrysource',),

    url(r'^title$', title,name='titlesource',),

    url(r'^datasource$', datasource,name='datasourcesource',),

    url(r'^orgarea$', orgarea,name='orgareasource',),

    url(r'^orgtype$', orgtype,name='orgtypesource',),

    url(r'^bdStatus$', bdStatus,name='bdStatussource',),

    url(r'^didiType$', didiType, name='didiType',),

    url(r'^transactionType$', transactionType,name='transactionTypesource',),

    url(r'^transactionPhases$', transactionPhases,name='transactionPhasessource',),

    url(r'^currencyType$', currencyType,name='currencyTypesource',),

    url(r'^character$', character,name='charactersource',),

    url(r'^orgtitletable$', Orgtitletable,name='Orgtitletablesource',),

    url(r'^industryGroup$', IndustryGroup,name='IndustryGroupSource',),

    url(r'^trainingType$', TrainingType,name='TrainingTypeSource',),

    url(r'^trainingStatus$', TrainingStatus,name='TrainingStatusSource',),

    url(r'^education$', educationType,name='EducationSource',),

    url(r'^projProgressContrast$', ProjProgressContrast, name='projProgressContrast', ),

    url(r'^webmenu$', Webmenu, name='WebmenuSource', ),

    url(r'^palevel$', performanceAppraisalLevelType,name='PerformanceAppraisalLevelSource',),

    url(r'^android$', AndroidVersion,name='AndroidVersion',),

    url(r'^android/(?P<pk>\d+)/$', AndroidVersion_detail,name='AndroidVersion_detail',),

]