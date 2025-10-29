import asyncio
import datetime
import os
import time
from pysnmp.hlapi import *
from pysnmp.hlapi.asyncio import *
from MainConnectFunc import oids, oidsSNMP, snmp_set, snmp_get, snmp_set_bulk, snmp_getBulk, equpimentV7
import paramiko

# from OSMK_Mv7.sshV7 import ssh_reload


def slot_to_block(slot):
    block = oidsSNMP()['slots_dict'][slot]
    return block


def check_loopback():
    for key in oidsSNMP()["slots_dict"]:
        if key == oidsSNMP()["loopback"][0]:
            return [key, oidsSNMP()["loopback"][1]]
        else:
            continue


def set_E1_loopback():
    for slot in [slot for slot in oidsSNMP()["slots_dict"] if
                 "E1" in oidsSNMP()["slots_dict"][slot]]:
        if len([[f"{oids()['loopbackOID'][oidsSNMP()['slots_dict'][slot]]}{slot}.{port}", 1] for port in
                range(1, oids()["quantPort"][oidsSNMP()["slots_dict"][slot]] + 1)]) > 7:
            for lenth in range(7, oids()["quantPort"][oidsSNMP()["slots_dict"][slot]] + 1, 7):
                asyncio.run(snmp_set_bulk([[f"{oids()['loopbackOID'][oidsSNMP()['slots_dict'][slot]]}{slot}.{port}", 1] for port in
                                           range(1, oids()["quantPort"][oidsSNMP()["slots_dict"][slot]] + 1)][lenth - 7:lenth]))


def klm_numbers(vc12):
    x = []
    for k in range(1, 4):
        for l in range(1, 8):
            for m in range(1, 4):
                x.append(f'{k}.{l}.{m}')
    return x[vc12 - 1]

def klm_numbersE1(vc12):
    x = []
    for m in range(1, 4):
        for l in range(1, 8):
            for k in range(1, 4):
                x.append(f'{k}.{l}.{m}')
    return x[vc12 - 1]


''' На всех слотах STM, E1, что есть в idReal, включается анализ на физических портах'''


async def alarmplusmask():
    for slot in oidsSNMP()["slots_dict"]:
        if 'STM' in oidsSNMP()["slots_dict"][slot] or 'E1' in oidsSNMP()["slots_dict"][slot]:
            await snmp_set_bulk([(oids()['alarmMODE'][oidsSNMP()['slots_dict'][slot]] + slot + f'.{port}', Integer(2))
                                 for port in range(1, oids()['quantPort'][oidsSNMP()['slots_dict'][slot]] + 1)])


# asyncio.run(alarmplusmask())
async def alarmplusmaslcnctSTM():
    for slot in oidsSNMP()["slots_dict"]:
        if 'KC-M12' not in oidsSNMP()["slots_dict"][slot] and 'KC' not in oidsSNMP()["slots_dict"][slot] and 'E1' not in oidsSNMP()["slots_dict"][
            slot] and 'Eth' not in oidsSNMP()["slots_dict"][slot]:
            allSets = ([(oids()["alarmMODEcnct"][oidsSNMP()['slots_dict'][slot]] + slot + f'.{port}.{vc}', Integer(2))
                        for port in range(1, oids()['quantPort'][oidsSNMP()['slots_dict'][slot]] + 1)
                        for vc in range(1, oids()['quantCnctPort'][oidsSNMP()['slots_dict'][slot]] + 1)])
            await snmp_set_bulk(allSets)
        elif 'E1' in oidsSNMP()["slots_dict"][slot]:
            allSets = ([(oids()["alarmMODEcnct"][oidsSNMP()['slots_dict'][slot]] + slot + '.1.1.' + f'{klm_numbersE1(vc)}', Integer(2))
                        for vc in range(1, oids()['quantCnctPort'][oidsSNMP()['slots_dict'][slot]] + 1)])
            await snmp_set_bulk(allSets)


# asyncio.run(alarmplusmaslcnctSTM())
async def check_alarmPH(slot, portnum):
    alarm = await snmp_get(
        f'{oids()["main_alarm"]["alarm_status"]["physical"][oidsSNMP()["slots_dict"][slot]] + str(slot) + f".{portnum}"}')
    return alarm


async def check_alarm_cnct(slot, portnum, vc):
    alarm = await snmp_get(
        f'{oids()["main_alarm"]["alarm_status"]["connective"][oidsSNMP()["slots_dict"][slot]] + f"{slot}" + f".{portnum}" + f".{vc}"}')
    return alarm


async def check_alarm_cnctE1(slot, vc):
    alarm = await snmp_get(
        f'{oids()["main_alarm"]["alarm_status"]["connective"][oidsSNMP()["slots_dict"][slot]] + str(slot) + f".1.1" + f".{klm_numbersE1(vc)}"}')
    return alarm


'''Value must be 15 symbols'''


async def change_traceTD(slot, portnum, value):
    traceTD = await snmp_set(
        f"{oids()['main_alarm']['alarm_setup_oid']['TIM']['TD'][oidsSNMP()['slots_dict'][slot]] + str(slot) + f'.{portnum}'}",
        OctetString(f"{value}"))
    return traceTD


async def change_traceTDE1(slot, portnum, value):
    traceTD = await snmp_set(
        f"{oids()['main_alarm']['alarm_setup_oid']['TIM']['TD'][oidsSNMP()['slots_dict'][slot]] + str(slot) + f'.1.1.{klm_numbersE1(portnum)}'}",
        OctetString(f"{value}"))
    return traceTD


# async def change_traceTDGE(block, vc, value):
#     traceTD = await snmp_set(
#         f"{oids()['main_alarm']['alarm_setup_oid']['TIM']['TD'][block] + str(oidsSNMP()['slots_dict'][block]) + f'.1.{vc}'}",
#         OctetString(f"{value}"))
#     return traceTD


# async def change_traceExpectedGE(block, vc, value):
#     traceTD = await snmp_set(
#         f"{oids()['main_alarm']['alarm_setup_oid']['TIM']['EXPECTED'][block] + str(oidsSNMP()['slots_dict'][block]) + f'.1.{vc}'}",
#         OctetString(f"{value}"))
#     return traceTD


async def change_traceExpected(slot, portnum, value):
    traceTD = await snmp_set(
        f"{oids()['main_alarm']['alarm_setup_oid']['TIM']['EXPECTED'][oidsSNMP()['slots_dict'][slot]] + str(slot) + f'.{portnum}'}",
        OctetString(f"{value}"))
    return traceTD


async def create_commutationVC4(slot, port, vc):
    await snmp_set(
        f"{oids()['switch_portVC4'][oidsSNMP()['slots_dict'][check_loopback()[0]]] + str(check_loopback()[0]) + '.' + str(oidsSNMP()['loopback'][1]) + '.1'}",
        ObjectIdentifier(f"{oids()['data_directionVC4'][oidsSNMP()['slots_dict'][slot]] + str(slot) + f'.{port}' + f'.{vc}'}"))
    await snmp_set(f"{oids()['switch_portVC4'][oidsSNMP()['slots_dict'][slot]] + str(slot) + f'.{port}' + f'.{vc}'}", ObjectIdentifier(
        f"{oids()['data_directionVC4'][oidsSNMP()['slots_dict'][check_loopback()[0]]] + str(check_loopback()[0]) + '.' + str(oidsSNMP()['loopback'][1]) + '.1'}"))


async def create_commutationVC12(slot, port, vc4, vc12):
    await snmp_set(
        f"{oids()['switch_portVC12'][oidsSNMP()['slots_dict'][str(check_loopback()[0])]] + str(check_loopback()[0]) + '.' + str(oidsSNMP()['loopback'][1]) + '.1.1.1.1'}",
        ObjectIdentifier(
            f"{oids()['data_directionVC12'][oidsSNMP()['slots_dict'][slot]] + str(slot) + f'.{port}' + f'.{vc4}' + f'.{klm_numbers(vc12)}'}"))
    await snmp_set(
        f"{oids()['switch_portVC12'][oidsSNMP()['slots_dict'][slot]] + str(slot) + f'.{port}' + f'.{vc4}' + f'.{klm_numbers(vc12)}'}",
        ObjectIdentifier(
            f"{oids()['data_directionVC12'][oidsSNMP()['slots_dict'][str(check_loopback()[0])]] + str(check_loopback()[0]) + '.' + str(oidsSNMP()['loopback'][1]) + '.1.1.1.1'}"))


async def create_commutationGE(block, vc4):
    slot, port = await portViavi()  # loopbackslot, loopbackport = oidsSNMP()['loopback']
    await snmp_set(
        f"{oids()['switch_portVC4'][block] + str(oidsSNMP()['slots_dict'][block]) + '.1.' + f'{vc4}'}",
        ObjectIdentifier(
            f"{oids()['data_directionVC4'][slot] + str(oidsSNMP()['slots_dict'][slot]) + f'.{port}' + '.1'}"))
    await snmp_set(
        f"{oids()['switch_portVC4'][slot] + str(oidsSNMP()['slots_dict'][slot]) + f'.{port}' + '.1'}",
        ObjectIdentifier(
            f"{oids()['data_directionVC4'][block] + str(oidsSNMP()['slots_dict'][block]) + '.1.' + f'{vc4}'}"))


async def create_commutationE1(slot, vc12):
    loopbackslot, loopbackport = oidsSNMP()['loopback']
    await snmp_set(
        f"{oids()['switch_portVC12'][oidsSNMP()['slots_dict'][slot]] + slot + '.1.1.' + f'{klm_numbersE1(vc12)}'}",
        ObjectIdentifier(
            f"{oids()['data_directionVC12'][oidsSNMP()['slots_dict'][loopbackslot]] + loopbackslot + f'.{loopbackport}' + '.1.1.1.1'}"))
    await snmp_set(
        f"{oids()['switch_portVC12'][oidsSNMP()['slots_dict'][loopbackslot]] + loopbackslot + f'.{loopbackport}' + '.1.1.1.1'}",
        ObjectIdentifier(
            f"{oids()['data_directionVC12'][oidsSNMP()['slots_dict'][slot]] + slot + '.1.1.' + f'{klm_numbersE1(vc12)}'}"))


async def delete_commutation(oid):
    await snmp_set(oid, Integer(1))


async def STM_alarm_status(slot):
    block = oidsSNMP()["slots_dict"][slot]
    check_alarm = []
    for i in range(1, oids()['quantPort'][block] + 1):
        res = await snmp_get(oids()["alarmOID"][block] + f'.{slot}' + f'.{i}')
        check_alarm.append(str(res))

    return check_alarm


async def maskStmTIM():
    for block in oids()["maskSTMoid"]:
        for port in range(1, oids()["quantPort"][block] + 1):
            await snmp_set(oids()['maskSTMoid'][block] + str(oidsSNMP()["slots_dict"][block]) + f'.{port}',
                           Integer(190))


async def check_alarmPH(slot, portnum):
    alarm = await snmp_get(
        f'{oids()["main_alarm"]["alarm_status"]["physical"][oidsSNMP()["slots_dict"][slot]] + str(slot) + f".{portnum}"}')
    return alarm


def fpga_reload():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('192.168.72.72', port=22, username='admin', password='')
    ssh.get_transport()
    stdin, stdout, stderr = ssh.exec_command(f'state slot 9')
    time.sleep(5)
    result = stdout.read().decode()
    for i in range(1, 1000):
        ssh.exec_command(f'fpga-reload 9')
        time.sleep(35)
        stdin, stdout, stderr = ssh.exec_command(f'state slot 9')
        result = stdout.read().decode()
        print(result)
        if 'KS 9 & 10 is equal' not in result:
            print(f"{datetime.datetime.now()} - {i} - False ")
            break
        print(f"{datetime.datetime.now()} - {i} - True ")
    ssh.close()


# fpga_reload()








