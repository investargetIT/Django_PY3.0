#coding=utf-8
from django.conf.urls import url
from third.views import submail
from third.views import qiniufile
from third.views import others


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
    url(r'^uploaddata/$', qiniufile.fileChunkUpload, name='fileChunkUpload', ),
]