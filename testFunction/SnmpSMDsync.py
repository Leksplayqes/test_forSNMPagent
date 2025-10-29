import asyncio
import json
import random

from puresnmp import Client, V2C, PyWrapper, ObjectIdentifier
from puresnmp.types import Integer


def oids():
    with open("../OIDstatusNEW.json", "r") as jsonslot:
        oid = json.load(jsonslot)
        return oid["SMD"]


async def typeOfEq():
    equipment = await client().get("1.3.6.1.2.1.1.1.0")
    return equipment





def client():
    return PyWrapper(Client(oids()["ipaddr"], V2C("private")))


def clientget():
    return PyWrapper(Client(oids()["ipaddr"], V2C("public")))


def checkpriorregID(block, portnum):
    if oids()["slots_dict"][block] == "17":
        nums = {1: "4", 2: "5", 3: "6", 4: "7"}
        portindexreg = nums[portnum]
    elif oids()["slots_dict"][block] == "18":
        nums = {1: "8", 2: "9", 3: "a", 4: "b"}
        portindexreg = nums[portnum]
    elif block == "KAD":
        nums = {1: "d", 2: "e", 3: "f", 4: "0", 5: "1", 6: "2", 7: "3", 8: "4"}
        portindexreg = nums[portnum]
    else:
        portindexreg = "c"
    return portindexreg


async def alarmplusmask(blocks: list):
    for block in blocks:
        for i in range(1, oids()["quantPort"][block] + 1):
            await client().set(oids()['alarmMODE'][block] + str(oids()["slots_dict"][block]) + f'.{i}', Integer(2))
        if "STM" in block:
            for portnum in range(1, oids()["quantPort"][block] + 1):
                await client().set(oids()["SFPmode"][block] + str(oids()["slots_dict"][block]) + f'.{portnum}', Integer(1))


async def clearprior():
    for i in range(1, 8):
        await client().set(f'{oids()["syncOID"]["priorID"]}{i}', ObjectIdentifier(oids()["portNull"]))


async def set_prior(block, priornum, portnum):
    syncSTMset = await client().set(f'{oids()["syncOID"]["priorID"] + priornum}',
                                    ObjectIdentifier(
                                        '.' + oids()['statusOID'][block] + oids()["slots_dict"][block] + f'.{portnum}'))
    return syncSTMset


async def get_prior(priornum):
    STMget = await clientget().get(f'{oids()["syncOID"]["priorID"] + priornum}')
    return STMget


async def del_prior(priornum):
    syncSTMdel = await client().set(f'{oids()["syncOID"]["priorID"] + priornum}', ObjectIdentifier(oids()['portNull']))
    return syncSTMdel


async def QL_up_down(mode):
    if mode == "up":
        upQL = await  client().set(oids()["syncOID"]["modeQL"], Integer(1))
    else:
        upQL = await  client().set(oids()["syncOID"]["modeQL"], Integer(0))
    return upQL


async def STM_alarm_status(blck):
    check_alarm = []
    for i in range(1, oids()['quantPort'][blck] + 1):
        res = await clientget().get(oids()["alarmOID"][blck] + oids()["slots_dict"][blck] + f'.{i}')
        check_alarm.append(res)
    return check_alarm


async def prior_status(priornum):
    check_prior_status = await clientget().get(oids()["syncOID"]["priorSTATUS"] + str(priornum))
    return check_prior_status


async def STM1_QL_level(block, portnum):
    QL_check = await clientget().get(oids()["stmQLget"][block] + oids()["slots_dict"][block] + f'.{portnum}')
    return QL_check


async def SETS_create(portnum):
    SETS_value = await client().set(oids()['syncOID']["priorID"] + str(portnum),
                                    ObjectIdentifier(oids()["syncOID"]["setsID"]))
    keybef = list(oids()["qualDICT"].items())
    keyaft, valueaft = keybef[random.randint(0, len(keybef) - 1)]
    await client().set(oids()["syncOID"]["setsQL"], Integer(int(keyaft)))
    return SETS_value


async def SETSs_create(portnum, value):
    SETS_value = await client().set(oids()['syncOID']["priorID"] + str(portnum),
                                    ObjectIdentifier(oids()["syncOID"]["setsID"]))
    await client().set(oids()["syncOID"]["setsQL"], Integer(value))
    return SETS_value


async def SETS_QL():
    SETSQL = await clientget().get(oids()["syncOID"]["setsQL"])
    return SETSQL


async def STM1_ext_port(lgc, portnum, block):
    ext_port_set = await client().set(oids()["syncOID"]["extTable"]["extSourceID"] + str(lgc),
                                      ObjectIdentifier(
                                          oids()["statusOID"][block] + oids()["slots_dict"][block] + f'.{portnum}'))
    return ext_port_set


async def extPortCr(priornum, portnum):
    extID = await client().set(oids()["syncOID"]["priorID"] + priornum,
                               ObjectIdentifier(oids()["syncOID"]["extTable"]["extID"] + portnum))
    return extID


async def extPortQL(portnum, value):
    extQL = await client().set(oids()["syncOID"]["extTable"]["extSetQL"] + portnum, Integer(value))
    return extQL


async def extSourceID(portnum, block, blockport):
    if block == "SETS":
        sourceID = await client().set(oids()["syncOID"]["extTable"]["extSourceID"] + portnum,
                                      ObjectIdentifier(oids()["syncOID"]["setsID"]))
    else:
        sourceID = await client().set(oids()["syncOID"]["extTable"]["extSourceID"] + portnum, ObjectIdentifier(
            oids()["statusOID"][block] + oids()["slots_dict"][block] + f'.{blockport}'))

    return sourceID


async def extPortConf(portnum, value):
    extConf = await client().set(oids()["syncOID"]["extTable"]["extConf"] + portnum, Integer(value))
    return extConf


async def extThreshQL(portnum, value):
    extThresh = await client().set(oids()["syncOID"]["extTable"]["extThreshQL"] + portnum, Integer(value))
    return extThresh


async def extThreshAlarm(portnum):
    extThreshAl = await clientget().get(oids()["syncOID"]["extTable"]["extThreshAlarm"] + portnum)
    return extThreshAl


def STMcreateWorkPrior(block, priornum):
    STMalarm = asyncio.run(STM_alarm_status(block))
    for i in range(len(STMalarm)):
        if STMalarm[i] == 0:
            asyncio.run(set_prior(block, priornum, str(i + 1)))


async def curPrior():
    activePrior = await clientget().get(oids()["syncOID"]["priorACTIVE"])
    return activePrior


async def get_multi_prior():
    STMget = await clientget().multiget(
        [(f'{oids()["syncOID"]["priorID"] + "1"}'), (f'{oids()["syncOID"]["priorID"] + "2"}'),
         (f'{oids()["syncOID"]["priorID"] + "3"}'),
         (f'{oids()["syncOID"]["priorID"] + "4"}'), (f'{oids()["syncOID"]["priorID"] + "5"}'),
         (f'{oids()["syncOID"]["priorID"] + "6"}'),
         (f'{oids()["syncOID"]["priorID"] + "7"}')])
    return STMget


async def get_multi_slotID():
    listofprior = []
    fullTable = await clientget().multiget(
        [(f'{oids()["syncOID"]["priorID"] + "1"}'), (f'{oids()["syncOID"]["priorID"] + "2"}'),
         (f'{oids()["syncOID"]["priorID"] + "3"}'),
         (f'{oids()["syncOID"]["priorID"] + "4"}'), (f'{oids()["syncOID"]["priorID"] + "5"}'),
         (f'{oids()["syncOID"]["priorID"] + "6"}'),
         (f'{oids()["syncOID"]["priorID"] + "7"}')])
    for i in fullTable:
        if i != '1.3.6.1.4.1.5756.1.205.0':
            for block in oids()["statusOID"]:
                if oids()["statusOID"][block] in i:
                    listofprior.append(block)
    return listofprior


async def set_E1_QL(block, portnum, value):
    E1_set = await client().set(oids()["E1QLset"][block] + oids()["slots_dict"][block] + f'.{portnum}', Integer(value))
    return E1_set


async def get_priorID(nums):
    prID = await clientget().get(f'{oids()["syncOID"]["priorID"]}{nums}')
    for block in oids()["statusOID"]:
        if oids()["statusOID"][block] in prID:
            return block


async def createPrbyID(prior, oid):
    prSet = await client().set(oids()["syncOID"]["priorID"] + prior, ObjectIdentifier(oid))
    return prSet


async def maskStmTIM():
    for block in oids()["maskSTMoid"]:
        for port in range(1, oids()["quantPort"][block] + 1):
            await client().set(oids()['maskSTMoid'][block] + str(oids()["slots_dict"][block]) + f'.{port}',
                               Integer(190))


''' Анализ TRAP сообщений на соответсвие с ожидаемым значением'''


def analize_trap(dev, trap, value):
    with open("../OIDstatusNEW.json", "r") as jsonoid:
        oid = json.load(jsonoid)
    for list in reversed(oid["TRAP_list"]):
        if trap in list[0] and value in list[1]:
            print("WP")
            assert True
            break
