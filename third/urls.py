#coding=utf-8
from django.conf.urls import url
from third.views import submail
from third.views import qiniufile
from third.views import others
from third.views import zoom
urlpatterns = [
    url(r'^sms$', submail.sendSmscode, name='sendsmscode', ),
    url(r'^qiniubigupload$', qiniufile.bigfileupload, name='qiniubig', ),
    url(r'^qiniucoverupload$', qiniufile.qiniu_coverupload, name='qiniucover', ),
    url(r'^currencyrate$', others.getcurrencyreat, name='getcurrencyrate', ),
    url(r'^phoneAddress', others.getMobilePhoneAddress, name='getMobilePhoneAddress', ),
    url(r'^ccupload', others.ccupload, name='ccupload', ),
    url(r'^uploadToken$', qiniufile.qiniu_uploadtoken, name='getuploadtoken',),
    url(r'^downloadUrl$', qiniufile.qiniu_downloadurl, name='getdownloadurl',),
    url(r'^getQRCode$', others.getQRCode, name='getQRCode',),
    url(r'^upload/record', others.recordUpload, name='recordUpload',),
    url(r'^upload/update', others.updateUpload, name='updateUploadRecord',),
    url(r'^upload/select', others.selectUpload, name='selectFromUploadRecord',),
    url(r'^upload/cancel', others.cancelUpload, name='cancelUploadRecord',),
    url(r'^upload/delete', others.deleteUpload, name='deleteUploadRecord',),
    url(r'^zoom/redirect/', zoom.requestOAuthCodeRedirectURI, name='zoom_requestOAuthCodeRedirectURI'),
    url(r'^zoom/access/', zoom.accessTokenExists, name='zoom_accessTokenExists'),
    url(r'^zoom/meetings/', zoom.getUsersMeetings, name='zoom_getUsersMeetings'),
]