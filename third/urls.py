#coding=utf-8
from django.conf.urls import url
from third.views import submail
from third.views import qiniufile
from third.views import others
from third.views import audioTransfer
from third.views import feishuyun

audioTrans = audioTransfer.AudioTranslateTaskRecordView.as_view({
        'get': 'list',
        'post': 'audioFileTranslateToWord',
})



audioTrans_detail = audioTransfer.AudioTranslateTaskRecordView.as_view({
        'get': 'getAudioFileTranslateToWordTaskResult',
        'put': 'update',
})

urlpatterns = [
    url(r'^sms$', submail.sendSmscode, name='sendsmscode', ),
    url(r'^currencyrate$', others.getcurrencyreat, name='getcurrencyrate', ),
    url(r'^phoneAddress$', others.getMobilePhoneAddress, name='getMobilePhoneAddress', ),
    url(r'^ccuploadbaidu$', others.ccupload_baidu, name='ccupload_baidu', ),
    url(r'^uploadToken$', qiniufile.qiniu_uploadtoken, name='getuploadtoken',),
    url(r'^downloadUrl$', qiniufile.qiniu_downloadurl, name='getdownloadurl',),
    url(r'^getQRCode$', others.getQRCode, name='getQRCode',),
    url(r'^recordUpload$', others.recordUpload, name='recordUpload',),
    url(r'^updateUpload$', others.updateUpload, name='updateUploadRecord',),
    url(r'^selectUpload$', others.selectUpload, name='selectFromUploadRecord',),
    url(r'^cancelUpload$', others.cancelUpload, name='cancelUploadRecord',),
    url(r'^deleteUpload$', others.deleteUpload, name='deleteUploadRecord',),
    url(r'^audioTranslate/$', audioTrans, name='audioTranslate',),
    url(r'^audioTranslate/(?P<pk>\d+)/$', audioTrans_detail, name='getAudioFileTranslateToWordTaskResult',),
    url(r'^uploaddata/$', qiniufile.fileChunkUpload, name='fileChunkUpload', ),
    url(r'^uploadres/$', qiniufile.getQiniuUploadRecordResponse, name='getQiniuUploadRecordResponse', ),
    url(r'^feishu/accesstoken/$', feishuyun.get_access_token, name='feishu_get_access_token', ),
    url(r'^feishu/useride/$', feishuyun.get_login_user_identity, name='feishu_get_access_token', ),
    url(r'^feishu/jsticket/$', feishuyun.get_jsapi_ticket, name='feishu_get_access_token', ),
]