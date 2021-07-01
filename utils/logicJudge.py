#coding=utf-8


# 检测检测是否用户对接交易师
def is_userTrader(trader, investor_id):
    if trader.trader_relations.all().filter(is_deleted=False, investoruser_id=investor_id).exists():
        return True
    return False


# 检测检测是否交易师名下投资人
def is_userInvestor(investor, trader_id):
    if investor.investor_relations.all().filter(is_deleted=False, traderuser_id=trader_id).exists():
        return True
    return False


# 检测是否dataroom交易师
def is_dataroomTrader(user, dataroom):
    if dataroom.proj.proj_traders.all().filter(user=user, is_deleted=False).exists():
        return True
    return False


# 检测是否dataroom用户
def is_dataroomInvestor(user, dataroom_id):
    if user.user_datarooms.all().filter(dataroom_id=dataroom_id, is_deleted=False).exists():
        return True
    return False


# 检测是否项目交易师
def is_projTrader(user, proj_id):
    if user.user_projects.all().filter(proj_id=proj_id, is_deleted=False).exists():
        return True
    return False


# 检测是否项目BD负责人
def is_projBDManager(user_id, projbd):
    if user_id == projbd.manager_id: #主负责人
        return True
    elif user_id == projbd.contractors_id: #签约负责人
        return True
    elif projbd.ProjectBD_managers.filter(is_deleted=False, manager_id=user_id).exists():
        return True
    return False


# 检测是否机构BD交易师
def is_orgBDTrader(user, orgbd):
    if orgbd.proj.proj_traders.all().filter(user=user, is_deleted=False).exists():
        return True
    return False


