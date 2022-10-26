#coding=utf-8


# 检测检测是否用户对接交易师
def is_userTrader(trader, investor_id):
    if investor_id and trader.trader_relations.all().filter(is_deleted=False, investoruser_id=investor_id).exists():
        return True
    return False


# 检测检测是否交易师名下投资人
def is_userInvestor(investor, trader_id):
    if trader_id and investor.investor_relations.all().filter(is_deleted=False, traderuser_id=trader_id).exists():
        return True
    return False


# 检测是否dataroom交易师  加上 PM
def is_dataroomTrader(user, dataroom):
    if dataroom.proj and dataroom.proj.proj_traders.all().filter(user=user, is_deleted=False).exists():
        return True
    elif dataroom.proj and dataroom.proj.PM == user:
        return True
    elif dataroom.isCompanyFile and user.has_perm('usersys.as_trader') and dataroom.proj:
        if dataroom.proj.indGroup and (dataroom.proj.indGroup == user.indGroup or user.user_indgroups.filter(indGroup=dataroom.proj.indGroup).exists()):
            return True
        elif not dataroom.proj.indGroup:
            return True
    return False


# 检测是否dataroom用户
def is_dataroomInvestor(user, dataroom_id):
    if dataroom_id and user.user_datarooms.all().filter(dataroom_id=dataroom_id, is_deleted=False).exists():
        return True
    return False

# 检测是否项目的dataroom用户
def is_projdataroomInvestor(user, proj_id):
    if proj_id and user.user_datarooms.all().filter(dataroom__proj_id=proj_id, is_deleted=False).exists():
        return True
    return False


# 检测是否项目交易师    加上 PM
def is_projTrader(user, proj_id):
    if proj_id and user.user_projects.all().filter(proj_id=proj_id, is_deleted=False).exists():
        return True
    elif proj_id and user.userPM_projs.all().filter(id=proj_id, is_deleted=False).exists():
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


# 检测是否机构BD交易师    加上 PM
def is_orgBDTrader(user, orgbd):
    if orgbd.proj and orgbd.proj.proj_traders.all().filter(user=user, is_deleted=False).exists():
        return True
    elif orgbd.proj and orgbd.proj.PM == user:
        return True
    return False


# 检测是否项目的机构看板负责人
def is_projOrgBDManager(user, proj_id):
    if proj_id and user.user_orgBDs.all().filter(proj_id=proj_id, is_deleted=False).exists():
        return True
    return False


# 检测是否机构投资人的交易师
def is_orgUserTrader(user, org):
    if user.trader_relations.all().filter(is_deleted=False, investoruser__in=org.org_users.all()).exists():
        return True
    return False


# 检测是否项目BD同行业组的交易师
def is_projBDIndGroupTrader(user, projbd):
    if projbd.indGroup == user.indGroup or user.user_indgroups.filter(indGroup=projbd.indGroup).exists():
        return True
    return False


# 检测是否交易师 直接上司
def is_traderDirectSupervisor(trader, supervisor):
    if trader.directSupervisor == supervisor:
        return True
    return False

# 检测是否交易师 导师
def is_traderMentor(trader, mentor):
    if trader.mentor == mentor:
        return True
    return False


# 检测是否公司dataroom的项目
def is_companyDataroomProj(proj):
    if proj.proj_datarooms.all().filter(is_deleted=False, isCompanyFile=True).exists():
        return True
    return False