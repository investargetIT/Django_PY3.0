import datetime
import json
import os
import traceback

from requests_toolbelt import MultipartEncoder
import requests

from invest.settings import APILOG_PATH
from third.thirdconfig import qimingpian_open_id
from utils.customClass import InvestError
from utils.util import logexcption


def updatePersonTag(username, orgname, tags):
    try:
        if username and orgname and len(tags) > 0:
            tag_list = [tag.nameC for tag in tags]
            data = {
                'open_id': qimingpian_open_id,
                'name': username,
                'agency': orgname,
                'content': '|'.join(tag_list),
            }
            url = 'https://qimingpianapi.investarget.com/Person/updatePersonTag'
            res = requests.post(url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'}).content
            try:
                res = json.loads(res.decode())
            except json.decoder.JSONDecodeError:
                res = json.loads(res)
            if res['status'] == 0:
                print('编辑投资人标签（投资人：%s, 机构：%s）成功' % (username, orgname))
            else:
                raise InvestError(20071, msg='编辑投资人标签（投资人：%s, 机构：%s）失败' % (username, orgname),
                                  detail=res['message'])
    except Exception:
        logexcption()

# 企名片上传文件
def uploadfile(file_path, key):
    data = {
        'open_id': qimingpian_open_id,
        'file': (key, open(file_path, 'rb'), 'application/octet-stream')
    }
    form_data = MultipartEncoder(data)
    url = 'https://qimingpianapi.investarget.com/Upload/file'
    try:
        res = requests.post(url, data=form_data,  headers={'Content-Type': form_data.content_type}).content
        res = json.loads(res.decode())
        if res['status'] == 0:
            print('上传企名片文件（文件id：%s, 文件url：%s）成功' % (key, res['data']['list']['url']))
            return res['data']['list']['url']
        else:
            logexcption('****上传文件企名片（%s）失败' % str(res))
            return None
    except Exception:
        logexcption('----上传企名片文件err（文件id：%s）' % key)
        return None


def addProductSummary(username, projectname, file_key, filename):
    try:
        file_path = os.path.join(APILOG_PATH['uploadFilePath'], file_key)
        file_url = uploadfile(file_path, file_key)
        if username and projectname and file_url and filename:
            data = {
                'open_id': qimingpian_open_id,
                'name': projectname,    # 企名片项目名称
                'summary': 'dataroom文件',
                'file': json.dumps([{"file_name": filename, "url": file_url}]),
                'user_name': username,   # 创建人
            }
            url = 'https://qimingpianapi.investarget.com/Summary/addProductSummary'
            res = requests.post(url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'}).content
            res = json.loads(res.decode())
            if res['status'] == 0:
                print('导入dataroom文件（项目：%s, 文件：%s）成功' % (projectname, filename))
            elif res['status'] == 60004:
                print('导入dataroom文件（%s)失败，用户(%s)不存在' % (projectname, filename))
                data['user_name'] = 'Investarget'
                res = requests.post(url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'}).content
                res = json.loads(res.decode())
                if res['status'] == 0:
                    print('导入dataroom文件（项目：%s, 文件：%s）成功' % (projectname, filename))
                else:
                    print('导入dataroom文件（%s)失败，(%s)' % (projectname, res['message']))
                    raise InvestError(20071, msg='添加项目开发纪要（项目：%s, 文件：%s）失败' % (projectname, filename),
                                      detail=res['message'])
            else:
                print('导入dataroom文件（%s)失败，(%s)' % (projectname, res['message']))
                raise InvestError(20071, msg='添加项目开发纪要（项目：%s, 文件：%s）失败' % (projectname, filename),
                                  detail=res['message'])
        else:
            print('上传企名片文件err（username：%s, projectname：%s, file_key：%s, filename：%s）' %
                        (username, projectname, file_key, filename))
            logexcption('上传企名片文件err（username：%s, projectname：%s, file_key：%s, filename：%s）' %
                        (username, projectname, file_key, filename))
    except Exception:
        logexcption()


