#coding=utf-8
import hashlib
import traceback

import datetime

import requests
from SUBMAIL_PYTHON_SDK_MAIL_AND_MESSAGE_WITH_ADDRESSBOOK.mail_send import MAILSend
from SUBMAIL_PYTHON_SDK_MAIL_AND_MESSAGE_WITH_ADDRESSBOOK.mail_xsend import MAILXsend
from SUBMAIL_PYTHON_SDK_MAIL_AND_MESSAGE_WITH_ADDRESSBOOK.message_xsend import MESSAGEXsend
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from third.models import MobileAuthCode
from third.thirdconfig import MAIL_CONFIGS, MESSAGE_CONFIGS, INTERNATIONALMESSAGE_CONFIGS, SUBHOOK_KEY
from utils.customClass import JSONResponse, InvestError
from utils.util import SuccessResponse, catchexcption, ExceptionResponse, InvestErrorResponse, checkIPAddressCanPass


'''
submail短信验证码模板
'''
SMSCODE_projectsign = {
    '1':{
        'in':'WzSYg',
        'out':'sk5Nu3'
        },
    '2':{
        'in':'tybmL4',
        'out':None
        },
    '3':{
        'in':'l58fI',
        'out':None
        },
    '4':{
        'in':'hIudP',
        'out':None
        },
    '5':{
        'in':'cWzJx',
        'out':None
        },
    }




def sendEmailWithAttachmentFile(destination, subject, html, attachmentpath):
    data = {'appid':MAIL_CONFIGS['appid'],
            'to': destination,
            'subject':subject,
            'html': html,
            'from': MAIL_CONFIGS['from'],
            'from_name': MAIL_CONFIGS['from_name'],
            'reply': MAIL_CONFIGS['reply'],
            'signature': MAIL_CONFIGS['appkey']}
    files = None
    if attachmentpath:
        files = {'attachments': open(attachmentpath)}
    res = requests.post('https://api.mysubmail.com/mail/send.json', data, files=files).content
    return res




def xsendEmail(destination,projectsign,vars=None):
    '''
    init MESSAGEXsend class
    '''
    submail = MAILXsend(MAIL_CONFIGS)
    '''
    Optional para
    The First para: recipient email address
    The second para: recipient name(optional)
    @Multi-para
    '''
    submail.add_to(destination,)

    '''
    Optional para
    set addressbook sign : Optional
    add addressbook contacts to Multi-Recipients
    @Multi-para
    '''
    # submail.add_address_book('subscribe')

    '''
    Optional para
    set sender address and name
    The First para: sender email address
    The second para: sender display name (optional)
    '''
    # submail.set_sender('no-reply@submail.cn','SUBMAIL')

    '''
    Optional para
    set reply address
    '''
    # submail.set_reply('service@submail.cn')

    '''
    Optional para
    set email subject
    '''
    # submail.set_subject('test SDK')
    '''
    Required para
    set project sign
    '''
    submail.set_project(projectsign)

    '''
    Optional para
    submail email text content filter
    @Multi-para
    '''
    if vars:
        submail.vars = vars

    '''
    Optional para
    email headers
    @Multi-para
    '''
    submail.add_header('X-Accept', 'zh-cn')
    submail.add_header('X-Mailer', 'leo App')
    response = submail.xsend()
    return response


@api_view(['POST'])
@throttle_classes([AnonRateThrottle])
def sendSmscode(request):
    try :
        source = request.META['HTTP_SOURCE']
        if request.META.has_key('HTTP_X_FORWARDED_FOR'):
            ip = request.META['HTTP_X_FORWARDED_FOR']
        else:
            ip = request.META['REMOTE_ADDR']
        if ip:
            if not checkIPAddressCanPass(ip):
                raise InvestError(code=3004,msg='单位时间内只能获取三次验证码')
        else:
            raise InvestError(code=3003)
        destination = request.data.get('mobile')
        areacode = request.data.get('areacode')
        now = datetime.datetime.now()
        start = now - datetime.timedelta(minutes=1)
        if MobileAuthCode.objects.filter(createTime__gt=start).filter(mobile=destination,is_deleted=False).exists():
            raise InvestError(code=3004)
        mobilecode = MobileAuthCode(mobile=destination)
        mobilecode.save()
        varsdict = {'code': mobilecode.code, 'time': '30'}
        if areacode in [u'86', '86', 86, None]:
            projectsign = SMSCODE_projectsign.get(str(source), {}).get('in')
            if projectsign:
                response = xsendSms(destination, projectsign, varsdict)
            else:
                raise InvestError(30011, msg='没有建立相应短信模板')
        else:
            projectsign = SMSCODE_projectsign.get(str(source), {}).get('out')
            if projectsign:
                response = xsendInternationalsms('+%s'%areacode + destination, projectsign, varsdict)
            else:
                raise InvestError(30012, msg='没有建立相应短信模板')
        success = response.get('status',None)
        if success:
            response['smstoken'] = mobilecode.token
        else:
            raise InvestError(code=30011,msg=response)
        return JSONResponse(SuccessResponse(response))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

@api_view(['POST'])
def checkSmsCode(request):
    try :
        data = request.data
        mobilecode = data.pop('mobilecode', None)
        mobilecodetoken = data.pop('mobilecodetoken', None)
        mobile = data.pop('mobile',None)
        if mobile and mobilecode and mobilecodetoken:
            try:
                mobileauthcode = MobileAuthCode.objects.get(mobile=mobile, code=mobilecode, token=mobilecodetoken)
            except MobileAuthCode.DoesNotExist:
                raise InvestError(code=2005)
            else:
                if mobileauthcode.isexpired():
                    raise InvestError(code=20051)
        else:
            raise InvestError(code=20072)
        return JSONResponse(SuccessResponse('验证通过'))
    except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))




def xsendSms(destination,projectsign,vars=None):
    if projectsign:
        submail = MESSAGEXsend(MESSAGE_CONFIGS)

        '''
        Optional para
        recipient cell phone number
        @Multi-para
        '''
        submail.add_to(destination)

        '''
        Optional para
        set addressbook sign : Optional
        add addressbook contacts to Multi-Recipients
        @Multi-para
        '''
        # submail.add_address_book('subscribe')

        '''
        Required para
        set message project sign
        '''
        submail.set_project(projectsign)

        '''
        Optional para
        submail email text content filter
        @Multi-para
        '''
        if vars:
            submail.vars = vars
        # submail.add_var('code', '198276')

        return submail.xsend()
    else:
        return None




def xsendInternationalsms(destination, projectsign, vars=None):
    submail = MESSAGEXsend(INTERNATIONALMESSAGE_CONFIGS)

    '''
    Optional para
    recipient cell phone number
    @Multi-para
    '''
    submail.add_to(destination)

    '''
    Optional para
    set addressbook sign : Optional
    add addressbook contacts to Multi-Recipients
    @Multi-para
    '''
    # submail.add_address_book('subscribe')

    '''
    Required para
    set message project sign
    '''
    submail.set_project(projectsign)

    '''
    Optional para
    submail email text content filter
    @Multi-para
    '''
    if vars:
        submail.vars = vars
    # submail.add_var('code', '198276')

    response = submail.xsend()
    return response



def checkSubhookKey(token, signature):
    if token and signature:
        keysign = token + SUBHOOK_KEY
        m = hashlib.md5()
        m.update(keysign)
        md5sign = m.hexdigest()
        if signature == md5sign:
            return True
    return False