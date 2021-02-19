#coding=utf-8
import base64
import datetime
import threading
import traceback

import pytz
import requests
from rest_framework.decorators import api_view
from third.thirdconfig import zoom_clientSecrect, zoom_clientId, zoom_redirect_uri, zoom_users
from utils.customClass import JSONResponse, InvestError
from utils.util import catchexcption, ExceptionResponse, SuccessResponse, InvestErrorResponse, read_from_cache, \
    write_to_cache, checkRequestToken, logexcption


# 获取请求码
def requestOAuthCode():
    authorize_url = 'https://zoom.us/oauth/authorize'
    params = {'response_type': 'code', 'redirect_uri': zoom_redirect_uri, 'client_id': zoom_clientId}
    requests.get(authorize_url, params=params)


# zoom请求码重定向uri
@api_view(['GET'])
def requestOAuthCodeRedirectURI(request):
    """
    zoom请求码重定向uri
    """
    try:
        code = request.GET.get('code', None)
        token_url = 'https://zoom.us/oauth/token'
        data = {'grant_type': 'authorization_code', 'redirect_uri': zoom_redirect_uri, 'code': code}
        basic = '{0}:{1}'.format(zoom_clientId, zoom_clientSecrect)
        headers = {'Authorization': 'Basic {}'.format(base64.b64encode(basic))}
        response = requests.post(token_url, data=data, headers=headers)
        if response.status_code == 200:
            access_token = response.json()['access_token']
            refresh_token = response.json()['refresh_token']
            write_to_cache('zoom_access_token', access_token, 3599)
            write_to_cache('zoom_refresh_token', refresh_token, 3599)
        return JSONResponse(SuccessResponse(response.json()))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


# zoom刷新token
def refreshAccessToken():
    try:
        token_url = 'https://zoom.us/oauth/token'
        refresh_token = read_from_cache('zoom_refresh_token')
        if not refresh_token:
            raise InvestError(9100, msg='refresh_token不存在')
        data = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
        basic = '{0}:{1}'.format(zoom_clientId, zoom_clientSecrect)
        headers = {'Authorization': 'Basic {}'.format(base64.b64encode(basic))}
        response = requests.post(token_url, params=data, headers=headers)
        if response.status_code == 200:
            access_token = response.json()['access_token']
            refresh_token = response.json()['refresh_token']
            write_to_cache('zoom_access_token', access_token, 3599)
            write_to_cache('zoom_refresh_token', refresh_token, 3599)
        else:
            raise InvestError(9100, msg=response.content)
    except Exception:
        logexcption()


# 确认是否存在zoom鉴权令牌
@api_view(['GET'])
def accessTokenExists(request):
    """
    确认是否存在zoom鉴权令牌
    """
    try:
        access_token = read_from_cache('zoom_access_token')
        if access_token:
            return JSONResponse(SuccessResponse(True))
        return JSONResponse(SuccessResponse(False))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

# 获取用户会议
def getUserMeetings(access_token, meetings_type):
    meetings = {}
    def request_task(userId):
        print('task____{}'.format(userId))
        userMeetings = []
        def getUserMeetings_pageone(userId, page_index):
            print('{}___{}'.format(userId, page_index))
            meetings_url = 'https://api.zoom.us/v2/users/{}/meetings'.format(userId)
            params = {'type': meetings_type, 'page_size': 30, 'page_number': page_index}
            response = requests.get(meetings_url, params=params,
                                    headers={'Authorization': 'Bearer  {}'.format(access_token)})
            if response.status_code != 200:
                userMeetings.append(response.json())
                return True
            else:
                res = response.json()
                isEndPage = int(res['total_records']) < page_index * int(res['page_size'])
                for meeting in res['meetings']:
                    local_tz = pytz.timezone(meeting['timezone'])
                    created_at_UTC = datetime.datetime.strptime(meeting['created_at'], '%Y-%m-%dT%H:%M:%SZ').replace(
                        tzinfo=pytz.timezone("UTC"))
                    created_at_local = created_at_UTC.astimezone(local_tz)
                    meeting['created_at'] = datetime.datetime.strftime(created_at_local, '%Y-%m-%dT%H:%M:%SZ')
                    start_time_UTC = datetime.datetime.strptime(meeting['start_time'], '%Y-%m-%dT%H:%M:%SZ').replace(
                        tzinfo=pytz.timezone("UTC"))
                    start_time_local = start_time_UTC.astimezone(local_tz)
                    meeting['start_time'] = datetime.datetime.strftime(start_time_local, '%Y-%m-%dT%H:%M:%SZ')
                    meeting.pop('timezone', '')
                    userMeetings.append(meeting)
                return isEndPage

        page_index = 1
        isEndPage = getUserMeetings_pageone(userId, page_index)
        while not isEndPage:
            page_index += 1
            isEndPage = getUserMeetings_pageone(userId, page_index)
        meetings[userId] = userMeetings

    threads = []
    for userId in zoom_users:
        t = threading.Thread(target=request_task, args=(userId,))
        threads.append(t)
    for t in threads:
        t.setDaemon(True)
        t.start()
    for t in threads:
        t.join()
    return meetings


# zoom获取user会议列表接口
@api_view(['GET'])
@checkRequestToken()
def getUsersMeetings(request):
    """
    zoom获取user会议列表
    """
    try:
        if not request.user.has_perm('usersys.as_trader'):
            raise InvestError(2009)
        access_token = read_from_cache('zoom_access_token')
        if not access_token:
            raise InvestError(9100, msg='zoom Access_token无效或不存在, 请重新获取')
        else:
            meetings_type = request.GET.get('type', 'upcoming')
            meetings = getUserMeetings(access_token, meetings_type)
            return JSONResponse(SuccessResponse(meetings))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))