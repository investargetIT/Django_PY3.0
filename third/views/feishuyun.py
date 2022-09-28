import datetime
import json
import os
import threading
import traceback
from urllib import parse
import requests
from rest_framework.decorators import api_view

from org.views import get_Org_By_Alias
from proj.models import project
from sourcetype.models import IndustryGroup
from third.thirdconfig import feishu_APPID, feishu_APP_SECRET
from usersys.models import MyUser, UserContrastThirdAccount
from BD.views import feishu_update_projbd_status, feishu_update_projbd_manager, feishu_update_projbd_comments, \
    feishu_update_orgbd, feishu_add_projbd
from proj.views import feishu_update_proj_response, feishu_update_proj_traders, feishu_update_proj_comments
from sourcetype.views import get_response_id_by_text, getmenulist
from usersys.views import get_traders_by_names, maketoken
from utils.customClass import InvestError, JSONResponse
from utils.somedef import excel_table_byindex
from utils.util import catchexcption, ExceptionResponse, InvestErrorResponse, SuccessResponse, checkRequestToken, \
    logexcption, logfeishuexcptiontofile, returnDictChangeToLanguage


# 获取app_access_token
def get_app_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
    post_data = {"app_id": feishu_APPID, "app_secret": feishu_APP_SECRET}
    r = requests.post(url, data=json.dumps(post_data))
    tat = r.json()["app_access_token"]
    return tat
# 获取tenant_access_token
def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    post_data = {"app_id": feishu_APPID, "app_secret": feishu_APP_SECRET}
    r = requests.post(url, data=post_data)
    tat = r.json()["tenant_access_token"]
    return tat

@api_view(['POST'])
def get_access_token(request):
    """
       获取 飞书access_token
    """
    try:
        data = request.data
        token_type = data.get('token_type', 'app_access_token')
        if token_type == 'app_access_token':
            url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
        elif token_type == 'tenant_access_token':
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        else:
            raise InvestError(20072, msg='token_type 无效', detail='token_type 无效')
        post_data = {"app_id": feishu_APPID, "app_secret": feishu_APP_SECRET}
        r = requests.post(url, data=json.dumps(post_data))
        return JSONResponse(SuccessResponse(r.json()))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

@api_view(['POST'])
def refresh_access_token(request):
    """
       刷新 飞书access_token
    """
    try:
        data = request.data
        Authorization = data.get('Authorization')
        refresh_token = data.get('refresh_token')
        if not Authorization or not refresh_token:
            raise InvestError(20072, msg='Authorization/refresh_token  是必传参数', detail='Authorization/refresh_token 不能为空')
        url = "https://open.feishu.cn/open-apis/authen/v1/refresh_access_token"
        post_data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        headers = {"Authorization": "Bearer {}".format(Authorization),
                   "Content-Type": "application/json; charset=utf-8"}
        r = requests.post(url, data=json.dumps(post_data), headers=headers)
        return JSONResponse(SuccessResponse(r.json()))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))



@api_view(['POST'])
def get_login_user_identity(request):
    """
        获取 飞书 登录用户身份
    """
    try:
        data = request.data
        Authorization = data.get('Authorization')
        code = data.get('code')
        if not Authorization  or not code:
            raise InvestError(20072, msg='Authorization/code  是必传参数', detail='Authorization/code 不能为空')
        url = "https://open.feishu.cn/open-apis/authen/v1/access_token"
        post_data = {"grant_type": "authorization_code", "code": code}
        headers = {"Authorization": "Bearer {}".format(Authorization),
                   "Content-Type":"application/json; charset=utf-8"}
        r = requests.post(url, data=json.dumps(post_data), headers=headers)
        union_id = r.json()['data']['union_id']
        try:
            thirdaccount = UserContrastThirdAccount.objects.get(thirdUnionID=union_id, is_deleted=False)
        except UserContrastThirdAccount.DoesNotExist:
            return JSONResponse(SuccessResponse({'feishu': r.json(), 'investarget': None}))
        else:
            user = thirdaccount.user
            clienttype = request.META.get('HTTP_CLIENTTYPE', 3)
            perimissions = user.get_all_permissions()
            menulist = getmenulist(user)
            response = maketoken(user, clienttype)
            response['permissions'] = perimissions
            response['menulist'] = menulist
            response['is_superuser'] = user.is_superuser
            return JSONResponse(SuccessResponse({'feishu': r.json(), 'investarget': returnDictChangeToLanguage(response, 'cn')}))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))


@api_view(['POST'])
def get_jsapi_ticket(request):
    """
        获取 飞书 jsapi—ticket
    """
    try:
        data = request.data
        Authorization = data.get('Authorization')
        if not Authorization:
            raise InvestError(20072, msg='Authorization 是必传参数', detail='Authorization 不能为空')
        url = "https://open.feishu.cn/open-apis/jssdk/ticket/get"
        headers = {"Authorization": "Bearer {}".format(Authorization), "Content-Type":"application/json; charset=utf-8"}
        r = requests.post(url, headers=headers)
        return JSONResponse(SuccessResponse(r.json()))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

# 审批任务列表查询
def getApprovalTasks(user_id, user_id_type=None, page_size=None, page_token=None, approval_code=None, instance_code=None, task_status=None, task_start_time_from=None, task_start_time_to=None):
    '''
        查询时间跨度不得大于30天，开始和结束时间必须都设置，或者都不设置
    :return:
    '''
    url = 'https://open.feishu.cn/open-apis/approval/v4/tasks/search'
    params = {
        'user_id_type' : user_id_type,
        'page_size': page_size,
        'page_token': page_token
    }
    header = {"Authorization": "Bearer " + str(get_tenant_access_token())}
    r = requests.post(url, headers=header, params=params, data=json.dumps({
        'user_id': user_id,
        'approval_code': approval_code,
        'instance_code': instance_code,
        'task_status': task_status,
        'task_start_time_from': task_start_time_from,
        'task_start_time_to': task_start_time_to
    }))
    return r.json()

# 获取单个审批实例详情
def getApprovalInstance(instance_id):
    '''
    :param instance_id: instance_id  例如：3E18717B-B803-4518-8C9D-F0850CD9671A
    :return:
    '''
    url = 'https://open.feishu.cn/open-apis/approval/v4/instances/{}'.format(instance_id)
    header = {"Authorization": "Bearer " + str(get_tenant_access_token())}
    r = requests.get(url, headers=header)
    return r.json()


# 审批任务同意
def approvalstask_approve(user_id_type=None, approval_code=None, instance_code=None, user_id=None, task_id=None, comment=None, form=None):
    '''
   :param user_id_type: id类型 限定请求体中用户的id类型 例如：union_id, open_id, user_id
    :param approval_code: 审批定义id 例如：'BB51CE3E-C37D-4157-9411-46C6F2FC0526'
    :param instance_code: 审批实例id 例如：'0D74C973-48DB-421A-94F9-A38BF0A3092C',
    :param user_id: 操作用户id 例如： 'ou_307a66d205a6ff8ab6d88ae73520f454',
    :param task_id: 审批任务id 例如：'7148418136075665436',
    :param comment: 意见 例如：'第一条审批测试审核同意
    :param form: json 数组，控件值  示例值："[{"id":"111", "type": "input", "value":"test"}]"
    :return:
    '''
    url = 'https://open.feishu.cn/open-apis/approval/v4/tasks/approve?user_id_type={}'.format(user_id_type)
    header = {"Authorization": "Bearer " + str(get_tenant_access_token())}
    approved_data = {
        'approval_code': approval_code,
        'instance_code': instance_code,
        'user_id': user_id,
        'task_id': task_id,
        'comment': comment,
        'form': form
    }
    r = requests.post(url, headers=header, data=json.dumps(approved_data))
    return r.json()

# 审批任务拒绝
def approvalstask_reject(user_id_type=None, approval_code=None, instance_code=None, user_id=None, task_id=None, comment=None):
    '''
    :param user_id_type: id类型 限定请求体中用户的id类型 例如：union_id, open_id, user_id
    :param approval_code: 审批定义id 例如：'BB51CE3E-C37D-4157-9411-46C6F2FC0526'
    :param instance_code: 审批实例id 例如：'0D74C973-48DB-421A-94F9-A38BF0A3092C',
    :param user_id: 操作用户id 例如： 'ou_307a66d205a6ff8ab6d88ae73520f454',
    :param task_id: 审批任务id 例如：'7148418136075665436',
    :param comment: 意见 例如：'第一条审批测试审核拒绝'
    :return:
    '''
    url = 'https://open.feishu.cn/open-apis/approval/v4/tasks/reject?user_id_type={}'.format(user_id_type)
    header = {"Authorization": "Bearer " + str(get_tenant_access_token())}
    approved_data = {
        'approval_code': approval_code,
        'instance_code': instance_code,
        'user_id': user_id,
        'task_id': task_id,
        'comment': comment
    }
    r = requests.post(url, headers=header, data=json.dumps(approved_data))
    return r.json()

# 审批任务转交
def approvalstask_transfer(user_id_type=None, approval_code=None, instance_code=None, user_id=None, task_id=None, comment=None, transfer_user_id=None):
    '''
    :param user_id_type: id类型 限定请求体中用户的id类型 例如：union_id, open_id, user_id
    :param approval_code: 审批定义id 例如：'BB51CE3E-C37D-4157-9411-46C6F2FC0526'
    :param instance_code: 审批实例id 例如：'0D74C973-48DB-421A-94F9-A38BF0A3092C',
    :param user_id: 操作用户id 例如： 'ou_307a66d205a6ff8ab6d88ae73520f454',
    :param transfer_user_id: 被转交人唯一id 例如： 'ou_307a66d205a6ff8ab6d88ae73520f454',
    :param task_id: 审批任务id 例如：'7148418136075665436',
    :param comment: 意见 例如：'第一条审批测试审核拒绝'

    :return:
    '''
    url = 'https://open.feishu.cn/open-apis/approval/v4/tasks/transfer?user_id_type={}'.format(user_id_type)
    header = {"Authorization": "Bearer " + str(get_tenant_access_token())}
    approved_data = {
        'approval_code': approval_code,
        'instance_code': instance_code,
        'user_id': user_id,
        'task_id': task_id,
        'comment': comment,
        'transfer_user_id': transfer_user_id
    }
    r = requests.post(url, headers=header, data=json.dumps(approved_data))
    return r.json()

# 审批任务退回
def approvalstask_specified_rollback(user_id_type=None, user_id=None, task_id=None, reason=None, task_def_key_list=None):
    '''
    :param user_id_type: id类型 限定请求体中用户的id类型 例如：union_id, open_id, user_id
    :param user_id: 操作用户id 例如： 'ou_307a66d205a6ff8ab6d88ae73520f454',
    :param task_id: 审批任务id 例如：'7148418136075665436',
    :param reason: 退回原因 例如：'申请事项填写不具体，请重新填写'
    :param task_def_key_list: 退回到节点列表 例如： ["START","APPROVAL_27997_285502","APPROVAL_462205_2734554"] 在审批实例详情中有timeline ：node_key
    :return:
    '''
    url = 'https://open.feishu.cn/open-apis/approval/v4/instances/specified_rollback?user_id_type={}'.format(user_id_type)
    header = {"Authorization": "Bearer " + str(get_tenant_access_token())}
    approved_data = {
        'user_id': user_id,
        'task_id': task_id,
        'reason': reason,
        'task_def_key_list': task_def_key_list
    }
    r = requests.post(url, headers=header, data=json.dumps(approved_data))
    return r.json()

# 审批任务加签
def approvalstask_add_sign(user_id_type=None, approval_code=None, instance_code=None, user_id=None, task_id=None, comment=None, add_sign_user_ids=None, add_sign_type=None, approval_method=None):
    '''
    :param approval_code: 审批定义id 例如：'BB51CE3E-C37D-4157-9411-46C6F2FC0526'
    :param instance_code: 审批实例id 例如：'0D74C973-48DB-421A-94F9-A38BF0A3092C',
    :param user_id: 操作用户id 例如： 'b16g66e3',
    :param task_id: 审批任务id 例如：'7148418136075665436',
    :param comment: 意见 例如：'第一条审批测试审核拒绝'
    :param add_sign_user_ids: 被加签人id 例如：  ["d19b913b","3313g62b"],
    :param add_sign_type: 1/2/3 分别代表前加签/后加签/并加签 例如：1
    :param approval_method: 仅在前加签、后加签时需要填写，1/2 分别代表或签/会签 例如：1
    :return:
    '''
    url = 'https://open.feishu.cn/open-apis/approval/v4/instances/add_sign'
    header = {"Authorization": "Bearer " + str(get_tenant_access_token())}
    approved_data = {
        'approval_code': approval_code,
        'instance_code': instance_code,
        'user_id': user_id,
        'task_id': task_id,
        'comment': comment,
        'add_sign_user_ids': add_sign_user_ids,
        'add_sign_type': add_sign_type,
        'approval_method': approval_method,
    }
    r = requests.post(url, headers=header, data=json.dumps(approved_data))
    return r.json()


# 审批任务重新提交
def approvalstask_resubmit(user_id_type=None, approval_code=None, instance_code=None, user_id=None, task_id=None, comment=None, form=None):
    '''
    :param user_id_type: id类型 限定请求体中用户的id类型 例如：union_id, open_id, user_id
    :param approval_code: 审批定义id 例如：'BB51CE3E-C37D-4157-9411-46C6F2FC0526'
    :param instance_code: 审批实例id 例如：'0D74C973-48DB-421A-94F9-A38BF0A3092C',
    :param user_id: 操作用户id 例如： 'ou_307a66d205a6ff8ab6d88ae73520f454',
    :param form: json 数组，控件值，同创建审批实例接口中form字段 例如： "[{"id":"user_name", "type": "input", "value":"test"}]"
    # form 控件值说明 https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/approval-v4/instance/create#4fd9fac6
    :param task_id: 审批任务id 例如：'7148418136075665436',
    :param comment: 意见 例如：'第一条审批测试审核拒绝'

    :return:
    '''
    url = 'https://open.feishu.cn/open-apis/approval/v4/tasks/resubmit?user_id_type={}'.format(user_id_type)
    header = {"Authorization": "Bearer " + str(get_tenant_access_token())}
    approved_data = {
        'approval_code': approval_code,
        'instance_code': instance_code,
        'user_id': user_id,
        'task_id': task_id,
        'comment': comment,
        'form': form
    }
    r = requests.post(url, headers=header, data=json.dumps(approved_data))
    return r.json()


@api_view(['POST'])
def request_GetApprovals(request):
    """
        获取 飞书 审批任务
    """
    try:
        data = request.data
        data['user_id_type'] = data['user_id_type'] if data.get('user_id_type') in ['union_id', 'open_id', 'user_id'] else 'union_id'
        res = getApprovalTasks(**data)
        return JSONResponse(SuccessResponse(res))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

@api_view(['POST'])
def request_GetApprovalInstance(request):
    """
        获取 查询审批实例详情
    """
    try:
        data = request.data
        res = getApprovalInstance(data['instance_id'])
        return JSONResponse(SuccessResponse(res))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))

@api_view(['POST'])
def request_handleApprovalsTask(request):
    """
        处理 飞书 审批任务
    """
    try:
        data = request.data
        data['user_id_type'] = data['user_id_type'] if data.get('user_id_type') in ['union_id', 'open_id', 'user_id'] else 'union_id'
        handle_type = request.GET.get('type')
        if handle_type == 'approve':
            res = approvalstask_approve(**data)
        elif handle_type == 'reject':
            res = approvalstask_reject(**data)
        elif handle_type == 'transfer':
            res = approvalstask_transfer(**data)
        elif handle_type == 'specified_rollback':
            res = approvalstask_specified_rollback(**data)
        elif handle_type == 'add_sign':
            res = approvalstask_add_sign(**data)
        elif handle_type == 'resubmit':
            res = approvalstask_resubmit(**data)
        else:
            raise InvestError(20071, msg='无效的类型', detail='handle_type 无效')
        return JSONResponse(SuccessResponse(res))
    except InvestError as err:
        return JSONResponse(InvestErrorResponse(err))
    except Exception:
        catchexcption(request)
        return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))




# 多维表格—-列出记录
def getTableRecords(app_token, table_id, view_id=None, page_token=None):
    '''
    :param app_token: 表格token  例如：bascnnEqEJKzsOaNNJLUyQmachc
    :param table_id: 表格table id 例如：tblJCs6ZrP9AQEPK
    :param view_id: 表格view_id 例如：vewWlgSLiS
    :return:
    '''
    url = 'https://open.feishu.cn/open-apis/bitable/v1/apps/{}/tables/{}/records'.format(app_token, table_id)
    params = {'view': view_id, 'page_token': page_token}
    header = {"content-type": "application/json; charset=utf-8",
              "Authorization": "Bearer " + str(get_app_access_token())}
    r = requests.get(url, headers=header, params=params)
    res = json.loads(r.content.decode())
    return res

# 多维表格—-列出表格全部记录
def getTableAllRecords(app_token, table_id, view_id=None):
    try:
        if table_id:
            res = getTableRecords(app_token, table_id, view_id)
            records = res['data']['items']
            while res['data']['has_more']:
                res = getTableRecords(app_token, table_id, view_id, res['data']['page_token'])
                records.extend(res['data']['items'])
            return records
        else:
            return []
    except Exception:
        logfeishuexcptiontofile()
        return []



# 多维表格—-列出表格全部数据表
def getAppAllTables(app_token):
    try:
        url = 'https://open.feishu.cn/open-apis/bitable/v1/apps/{}/tables'.format(app_token)
        params = {'page_size': 100}
        header = {"content-type": "application/json; charset=utf-8",
                  "Authorization": "Bearer " + str(get_tenant_access_token())}
        r = requests.get(url, headers=header, params=params)
        res = json.loads(r.content.decode())
        print(res)
        if res['code'] != 0:
            raise InvestError(20071, msg='获取数据表失败, %s' % str(res))
        else:
            alltables = res['data']['items']
        return alltables
    except InvestError as err:
        logfeishuexcptiontofile(msg=err.msg)
        return []
    except Exception:
        logfeishuexcptiontofile()
        return []




def update_feishu_excel():
    """
        更新飞书多维表格数据
    """
    try:
        indgroup_qs = IndustryGroup.objects.filter(is_deleted=False, ongongingurl__isnull=False)
        for indgroup_ins in indgroup_qs:
            try:
                app_token, table_id, view_id = parseFeiShuExcelUrl("https://investarget.feishu.cn/base/bascnnEqEJKzsOaNNJLUyQmachc?table=tblJCs6ZrP9AQEPK&view=vewWlgSLiS")
                records = getTableAllRecords(app_token, table_id, view_id)
                print(indgroup_ins.ongongingurl)
                print(app_token, table_id, view_id)
                print(len(records))
                update_feishu_indgroup_task(records, 1, indgroup_ins)
            except Exception:
                logfeishuexcptiontofile(msg=str(indgroup_ins.nameC))
        project_qs = project.objects.filter(is_deleted=False, feishuurl__isnull=False)
        for proj_ins in project_qs:
            try:
                app_token, table_id, view_id = parseFeiShuExcelUrl(proj_ins.feishuurl)
                records = getTableAllRecords(app_token, table_id, view_id)
                update_feishu_project_task(records, 1, proj_ins)
            except Exception:
                logfeishuexcptiontofile(msg=str(proj_ins.projtitleC))
        print('jieshu')
    except Exception:
        logfeishuexcptiontofile()

def parseFeiShuExcelUrl(excelurl):
    url = parse.urlparse(excelurl)
    app_token = url.path.replace('/base/', '')
    if parse.parse_qs(url.query).get('table'):
        table_id = parse.parse_qs(url.query)['table'][0]
    else:
        table_id = None
    if parse.parse_qs(url.query).get('view'):
        view_id = parse.parse_qs(url.query)['view'][0]
    else:
        view_id = None
    if not table_id:
        alltables = getAppAllTables(app_token)
        if len(alltables) > 0:
            table_id = alltables[0]['table_id']
    return app_token, table_id, view_id



def update_feishu_indgroup_task(records, user_id, indgroup):
    try:
        for record in records:
            try:
                data = record['fields']
                if data.get('项目类型') == 'On going':
                    if data.get('系统ID'):
                        proj_id = int(data['系统ID'])
                        proj_respone_text = data.get('项目进度')
                        proj_respone_id = get_response_id_by_text(proj_respone_text, 1)
                        traders_2_text = data.get('承做-PM')
                        traders_2 = get_traders_by_names(traders_2_text)
                        traders_3_text = data.get('承做-参与人员')
                        traders_3 = get_traders_by_names(traders_3_text)
                        traders_4_text = data.get('承销-主要人员')
                        traders_4 = get_traders_by_names(traders_4_text)
                        traders_5_text = data.get('承销-参与人员')
                        traders_5 = get_traders_by_names(traders_5_text)
                        comments = data.get('项目最新进展')
                        if comments and len(comments) > 0:
                            comment_list = comments.split('；')
                        else:
                            comment_list = []
                        feishu_update_proj_response(proj_id, proj_respone_id, user_id)
                        feishu_update_proj_traders(proj_id, traders_2, 2, user_id)
                        feishu_update_proj_traders(proj_id, traders_3, 3, user_id)
                        feishu_update_proj_traders(proj_id, traders_4, 4, user_id)
                        feishu_update_proj_traders(proj_id, traders_5, 5, user_id)
                        feishu_update_proj_comments(proj_id, comment_list, user_id)
                elif data.get('项目类型') in ['BD中', '签约中']:
                    projbd_status_text = data.get('项目进度')
                    projbd_status_id = get_response_id_by_text(projbd_status_text, 0)
                    managers_2_text = data.get('BD-线索提供')
                    managers_2 = get_traders_by_names(managers_2_text)
                    managers_3_text = data.get('BD-主要人员')
                    managers_3 = get_traders_by_names(managers_3_text)
                    managers_4_text = data.get('BD-参与或材料提供人员')
                    managers_4 = get_traders_by_names(managers_4_text)
                    managers_3.extend(managers_4)
                    comments = data.get('项目最新进展')
                    if comments and len(comments) > 0:
                        comment_list = comments.split('；')
                    else:
                        comment_list = []
                    if data.get('系统ID'):
                        projbd_id = int(data['系统ID'])
                    else:
                        com_name = data['项目名称']
                        projbd_id = feishu_add_projbd(com_name, projbd_status_id, user_id, indgroup.id, managers_3)
                    if projbd_id:
                        feishu_update_projbd_status(projbd_id, projbd_status_id, user_id)
                        feishu_update_projbd_manager(projbd_id, managers_2, 2, user_id)
                        feishu_update_projbd_manager(projbd_id, managers_3, 3, user_id)
                        feishu_update_projbd_comments(projbd_id, comment_list, user_id)
                else:
                    print(data.get('项目类型'))
            except Exception:
                logfeishuexcptiontofile(msg=str(record))
    except Exception:
        logfeishuexcptiontofile(msg=str(indgroup.nameC))

def update_feishu_project_task(records, user_id, proj):
    try:
        for record in records:
            try:
                data = record['fields']
                orgnames = data.get('机构名称', '')
                org = get_Org_By_Alias(orgnames)
                if not org:
                    raise InvestError(20071, msg='未匹配到机构')
                status_text = data.get('跟进情况')
                status_id = get_response_id_by_text(status_text, 1)
                if not status_id:
                    raise InvestError(20071, msg='未匹配到任务状态')
                manager_names = data.get('负责IR同事')
                managers = get_traders_by_names(manager_names)
                if len(managers) == 0:
                    raise InvestError(20071, msg='未匹配到IR')
                important = data.get('优先级', 0)
                comment_keys = ['备注', '机构备注', '该机构备注']
                comment = ''
                for comment_key in comment_keys:
                    if comment_key in data:
                        comment = data.get(comment_key, '')
                        break
                for manager in managers:
                    feishu_update_orgbd(org, proj, status_id, user_id, manager, comment, important)
            except Exception:
                logfeishuexcptiontofile(msg=str(record))
    except Exception:
        logfeishuexcptiontofile(msg=str(proj.projtitleC))

