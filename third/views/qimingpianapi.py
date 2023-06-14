import json

import requests

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
            res = json.loads(res)
            if res['status'] == 0:
                print('编辑投资人标签（投资人：%s, 机构：%s）成功' % (username, orgname))
            else:
                raise InvestError(20071, msg='编辑投资人标签（投资人：%s, 机构：%s）失败' % (username, orgname), detail=res['message'])
    except Exception:
        logexcption()
