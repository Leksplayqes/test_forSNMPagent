import random
import pytest
from SnmpV7Sync import *
from SnmpV7alarm import check_alarmPH, alarmplusmask
from Vivavi.ViaviControl import VIAVI_set_command, VIAVI_get_command
from sshV7 import get_ssh_value, bd_alarm_get
from TRAP_analyze.ParseTrapLog import parse_snmp_log, clear_trap_log
import time


def test_preparing():
    asyncio.run(alarmplusmask())
    assert True


''' 
Проверка создания и удаления приоритетов синхронизации для всех возможных блоков
Функция создает приоритет с указанным блоком, сверяет SNMP и регистры. 
Далее удаляет приоритет и проверяет, что регистры очистились
Добавлен анализ TRAP сообщений с изменением статуса приоритета синхронизации при создании/удалении источника синхр.
Добавлен анализ аварий SYNCv1PriorStatus в таблице hw_alarm
TASK #14382 
'''


@pytest.mark.parametrize('slot, priornum, portnum',
                         [(slot, priornum, portnum)
                          for slot in oidsSNMP["slots_dict"]
                          if "E1" in oidsSNMP["slots_dict"][slot] or "STM" in oidsSNMP["slots_dict"][slot]
                          for priornum in ['1', '2', '3', '4', '5', '6', '7', '8']
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]] + 1)])
def test_STM_E1_create_del(slot, priornum, portnum):
    asyncio.run(clearprior())
    clear_trap_log()
    snmpSTM_set = str(asyncio.run(set_prior(slot, priornum, portnum)))
    time.sleep(2)

    regSTM_set = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10",
                               oids["priorityREG"][priornum])

    # Проверка регистров для двух плат при наличии
    if "9" in oidsSNMP["slots_dict"] and "10" in oidsSNMP["slots_dict"]:
        regSTM_set2 = get_ssh_value("10", oids["priorityREG"][priornum])
        assert regSTM_set == regSTM_set2

    expected_snmp = oids["statusOID"][oidsSNMP["slots_dict"][slot]] + slot + f'.{portnum}'
    assert snmpSTM_set == expected_snmp and regSTM_set[:2] != '0000'
    assert bd_alarm_get('LOS', oids["syncOID"]["priorSTATUS"] + f"{priornum}")

    # Проверка TRAP сообщения
    trap_log = parse_snmp_log(oids["syncOID"]["priorSTATUS"] + f"{priornum}", 2)
    assert oids["syncOID"]["priorSTATUS"] + f"{priornum}" == trap_log[0]
    assert str(trap_log[1]) in ["1", "2"]

    # Удаление приоритета
    snmpSTM_del = str(asyncio.run(del_prior(priornum)))
    tlntSTM_del = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10",
                                oids["priorityREG"][priornum])

    if "9" in oidsSNMP["slots_dict"] and "10" in oidsSNMP["slots_dict"]:
        tlntSTM_del2 = get_ssh_value("10", oids["priorityREG"][priornum])
        assert tlntSTM_del == tlntSTM_del2

    assert snmpSTM_del == oids["portNull"] and tlntSTM_del == '0000'
    time.sleep(2)

    assert not bd_alarm_get('LOS', oids["syncOID"]["priorSTATUS"] + f"{priornum}")

    # Проверка TRAP при удалении
    log = parse_snmp_log(oids["syncOID"]["priorSTATUS"] + f"{priornum}", 3)
    assert oids["syncOID"]["priorSTATUS"] + f"{priornum}" == str(log[0])
    assert str(log[1]) == '1'


'''Проверка включения режимов синхронизации (с/без анализа QL)'''


def test_QLmodeDOWN():
    snmpQL_set = asyncio.run(QL_up_down("down"))
    tlntQL_set = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10", '3E')
    assert snmpQL_set == 0 and tlntQL_set == '0000'


def test_QLmodeUP():
    snmpQL_set = asyncio.run(QL_up_down("up"))
    tlntQL_set = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10", '3E')
    assert snmpQL_set == 1 and tlntQL_set == '0001'


'''Проверка создания внешнего источника синхронизации'''


@pytest.mark.parametrize("priornum, portnum",
                         [(priornum, portnum)
                          for priornum in range(1, 9)
                          for portnum in range(1, 3)])
def test_extPortID(priornum, portnum):
    asyncio.run(clearprior())
    exIDcr = asyncio.run(extPortCr(str(priornum), str(portnum)))

    assert exIDcr == oids["syncOID"]["extTable"]["extID"] + str(portnum)
    reg_value = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10",
                              oids["priorityREG"][str(priornum)])
    expected_value = "0200" if str(portnum) == "1" else "0300"
    assert reg_value == expected_value

    exIDdel = asyncio.run(del_prior(str(priornum)))
    assert exIDdel == oids["portNull"]

    reg_after_del = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10",
                                  oids["priorityREG"][str(priornum)])
    assert reg_after_del == "0000"


'''Проверка занятия и очистки шины, при создании и удалении приоритета синхронизации'''


@pytest.mark.parametrize("slot, portnum, priornum",
                         [(slot, portnum, priornum)
                          for slot in oidsSNMP["slots_dict"]
                          if "E1" in oidsSNMP["slots_dict"][slot] or "STM" in oidsSNMP["slots_dict"][slot]
                          for priornum in ['1', '2', '3', '4', '5', '6', '7', '8']
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]] + 1)])
def test_busSYNC(slot, priornum, portnum):
    dictPort = {"1": "1", "3": "2", "5": "3", "7": "4", "9": "5", "B": "6", "D": "7", "F": "8", }
    asyncio.run(clearprior())
    asyncio.run(set_prior(slot, str(priornum), str(portnum)))
    if oidsSNMP["slots_dict"][slot] != "63E1M":
        busSTM = get_ssh_value(slot, oids["busSYNCsource"][oidsSNMP["slots_dict"][slot]][priornum])
        busSTM = busSTM * 3
        assert int(dictPort[busSTM[-int(priornum)]]) == int(portnum)
        asyncio.run(del_prior(priornum))
        assert get_ssh_value(slot, oids["busSYNCsource"][oidsSNMP["slots_dict"][slot]][priornum]) == "0000"
    else:
        if int(portnum) < 22:
            TUG = 1
        elif 21 < int(portnum) < 43:
            TUG = 2
            portnum = int(portnum) - 21
        else:
            TUG = 3
            portnum = int(portnum) - 42
        busSTM = get_ssh_value(slot, oids["busSYNCsource"][oidsSNMP["slots_dict"][slot]][f'{priornum}.{TUG}'])
        if int(priornum) % 2 != 0:
            busSTM = busSTM[-2:]
        else:
            busSTM = busSTM[:-2]
        busSTM = int(busSTM, 16)
        assert int(busSTM) == int(portnum)
        asyncio.run(del_prior(priornum))
        assert get_ssh_value(slot, oids["busSYNCsource"][oidsSNMP["slots_dict"][slot]][f'{priornum}.{TUG}']) == "0000"


'''Проверка установки качества на источнике внешней синхронизации'''


@pytest.mark.parametrize("priornum, portnum, value",
                         [(priornum, portnum, value)
                          for priornum in [str(x) for x in range(1, 9)]
                          for portnum in range(1, 3)
                          for value in [2, 4, 8, 11, 15]])
def test_extPortQL(priornum, portnum, value):
    asyncio.run(clearprior())
    extCr = asyncio.run(extPortCr(priornum, str(portnum)))
    extQl = asyncio.run(extPortQL(str(portnum), value))

    assert extCr == oids["syncOID"]["extTable"]["extID"] + str(portnum)
    assert extQl == value

    reg_value = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10",
                              oids["priorityREG"][priornum])
    expected_prefix = "020" if str(portnum) == "1" else "030"
    expected_value = expected_prefix + f'{oids["qualDICT"][str(value)]}'
    assert reg_value == expected_value


'''Проверка установки режимов МГц и Мбит для портов вн. синхронизации'''


@pytest.mark.parametrize("portnum, value",
                         [(portnum, value)
                          for portnum in range(1, 3)
                          for value in range(0, 2)])
def test_extPortConf(portnum, value):
    extConf = asyncio.run(extPortConf(str(portnum), value))
    assert extConf == value

    reg_value = bin(int(get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10", '22'))).replace("b", "")
    assert reg_value[-int(portnum)] == str(value)


'''Проверка на использование портов STM в качестве источника для выхода портов внешней синхронизации'''


@pytest.mark.parametrize('slot, portnum, blockport',
                         [(slot, portnum, blockport)
                          for slot in oidsSNMP["slots_dict"] if "STM" in oidsSNMP["slots_dict"][slot]
                          for portnum in range(1, 3)
                          for blockport in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]] + 1)])
def test_extSourceID(slot, portnum, blockport):
    block = oidsSNMP["slots_dict"][slot]
    extSrcID = asyncio.run(extSourceID(str(portnum), slot, str(blockport)))

    assert str(extSrcID) == oids["statusOID"][block] + slot + f'.{blockport}'
    assert bin(int(get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10", '24')))[-int(portnum)] == "1"

    extPort = get_ssh_value(slot, oids["extSourceSTM"][block])[-int(portnum)]
    assert oids["prior_dict"][extPort] == str(blockport)


'''Проверка на статус приоритета синхронизации, созданного с участием безаварийного порта'''


@pytest.mark.parametrize('slot, portnum, priornum',
                         [(slot, portnum, priornum)
                          for slot in oidsSNMP["slots_dict"] if "STM" in oidsSNMP["slots_dict"][slot]
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]] + 1)
                          if str(asyncio.run(check_alarmPH(slot, portnum))) not in ["1", "2"]
                          for priornum in range(1, 9)])
def test_prior_statusSTM(slot, portnum, priornum):
    numprior = {"1": -2, "2": -3, "3": -4, "4": -5, "5": -7, "6": -8, "7": -9, "8": -10}

    asyncio.run(clearprior())
    clear_trap_log()

    snmpSTM_set = asyncio.run(set_prior(slot, str(priornum), portnum))
    time.sleep(65)

    prstatustlnt = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10", '3A')
    assert asyncio.run(prior_status(priornum)) == 1
    assert bin(int(prstatustlnt, 16)).replace('b', '')[numprior[str(priornum)]] == '0'

    KCpriorAlarm = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10", '3A')
    assert bin(int(KCpriorAlarm, 16)).replace('b', '')[numprior[str(priornum)]] == "0"
    assert str(asyncio.run(snmp_get(oids["syncOID"]["priorACTIVE"]))) == str(int(priornum) - 1)

    trap_log = parse_snmp_log(oids["syncOID"]["priorSTATUS"] + f"{priornum}", 2)
    assert oids["syncOID"]["priorSTATUS"] + f"{priornum}" == trap_log[0]
    assert str(trap_log[1]) in ["1", "2"]

    tlntSTM_set = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10",
                                oids["priorityREG"][str(priornum)])
    expected_snmp = oids["statusOID"][oidsSNMP["slots_dict"][slot]] + slot + f'.{portnum}'
    assert str(snmpSTM_set) == expected_snmp and tlntSTM_set != '0000'

    snmpSTM_del = asyncio.run(del_prior(str(priornum)))
    tlntSTM_del = get_ssh_value("9" if "9" in oidsSNMP["slots_dict"] else "10",
                                oids["priorityREG"][str(priornum)])
    assert snmpSTM_del == oids["portNull"] and tlntSTM_del == '0000'


'''Проверка уровня качества на входе блоков СТМ'''


@pytest.mark.parametrize('slot, ql',
                         [(slot, ql)
                          for slot in oidsSNMP["slots_dict"] if 'STM' in oidsSNMP["slots_dict"][slot]
                          for ql in oids["qualDICT"]])
def test_QLSTM_get(slot, ql):
    asyncio.run(clearprior())
    STM1alarm = list(asyncio.run(STM_alarm_status(slot)).values())

    for i in range(len(STM1alarm)):
        if int(STM1alarm[i]) == 0 or STM1alarm[i] == 64:
            VIAVI_set_command(oidsSNMP["slots_dict"][slot], ":SOURCE:SDH:MS:Z1A:BYTE:VIEW", ql)

            reg_value = get_ssh_value(slot, oids["stmQLgetREG"][oidsSNMP["slots_dict"][slot]][str(i + 1)])[-1]
            assert reg_value == oids["qualDICT"][ql]

            snmp_ql = asyncio.run(STM1_QL_level(slot, i + 1))
            assert oids["qualDICT"][str(snmp_ql)] == oids["qualDICT"][ql]

'''Проверка передачи качества ГСЭ по потокам STM'''

@pytest.mark.parametrize('slot, ql',
                         [(slot, ql)
                          for slot in oidsSNMP["slots_dict"] if 'STM' in oidsSNMP["slots_dict"][slot]
                          for ql in oids["qualDICT"]])
def test_QLSTM_set(slot, ql):
    asyncio.run(clearprior())
    asyncio.run(SETS_create("1", int(ql)))
    STM1alarm = list(asyncio.run(STM_alarm_status(slot)).values())

    for i in range(len(STM1alarm)):
        if int(STM1alarm[i]) == 0 or int(STM1alarm[i]) == 64:
            time.sleep(30)

            reg_value = get_ssh_value(slot, oids["stmQLset"][oidsSNMP["slots_dict"][slot]][str(i + 1)])
            assert oids["qualDICT"][str(ql)] in reg_value

            time.sleep(1)
            resQLstm = VIAVI_get_command(oidsSNMP["slots_dict"][slot],
                                         ":SENSE:DATA? INTEGER:SONET:LINE:S1:SYNC:STATUS")[2:-2]
            expected_ql = oidsVIAVI["reqSTMql"][resQLstm]
            assert expected_ql == get_ssh_value(slot, oids["stmQLset"][oidsSNMP["slots_dict"][slot]][str(i + 1)])

'''Проверка установки уровней QL для интерфейсов E1'''

@pytest.mark.parametrize('slot, priornum, portnum',
                         [(slot, priornum, portnum)
                          for slot in oidsSNMP["slots_dict"] if 'E1' in oidsSNMP["slots_dict"][slot]
                          for priornum in [str(x) for x in range(1, 9)]
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]])])
def test_QLE1_set(slot, priornum, portnum):
    asyncio.run(clearprior())
    asyncio.run(set_prior(slot, priornum, portnum))
    assert get_ssh_value('9', oids["priorityREG"][str(priornum)]) != "0000"

    for value in oids["qualDICT"]:
        asyncio.run(set_E1_QL(slot, portnum, int(value)))
        tlntE1QL = get_ssh_value('9', oids["priorityREG"][str(priornum)])[-1]
        assert tlntE1QL == oids["qualDICT"][value]

'''Проверка записи блоков СТМ как источников выходного сигнала'''

@pytest.mark.parametrize('extport, portnum, slot',
                         [(extport, portnum, slot)
                          for slot in oidsSNMP["slots_dict"] if "STM" in oidsSNMP["slots_dict"][slot]
                          for extport in range(1, 3)
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]] + 1)])
def test_STM_extport(extport, portnum, slot):
    extportvalue = asyncio.run(STM1_ext_port(extport, portnum, slot))

    assert extportvalue == oids["statusOID"][oidsSNMP["slots_dict"][slot]] + slot + f'.{portnum}'
    assert bin(int(get_ssh_value('9', '24')))[-int(extport)] == "1"

    STMextport = get_ssh_value(slot, oids["extSourceSTM"][oidsSNMP["slots_dict"][slot]])
    assert oids["prior_dict"][STMextport[-extport]] == str(portnum)

'''Проверка соответствия текущего уровня качества источника синхронизации на входе блоков СТМ с качеством, записанным в КС'''

@pytest.mark.parametrize('slot, extport, portnum',
                         [(slot, extport, portnum)
                          for slot in oidsSNMP["slots_dict"] if 'STM' in oidsSNMP["slots_dict"][slot]
                          for extport in range(1, 3)
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]] + 1)])
def test_STM_QL_extport(slot, extport, portnum):
    asyncio.run(STM1_ext_port(extport, portnum, slot))
    time.sleep(1)

    extQLKS = get_ssh_value('9', oids["KCqlGETreg"][str(extport)])
    extQLstm = get_ssh_value(slot, oids["stmQLgetREG"][oidsSNMP["slots_dict"][slot]][str(portnum)])
    assert extQLKS == extQLstm

'''Проверка аварий по порогам статистики для каждого интерфейсного блока и каждого качества на приеме'''

@pytest.mark.parametrize('slot, extPort, portnum, priornum',
                         [(slot, extPort, portnum, priornum)
                          for slot in oidsSNMP["slots_dict"] if 'STM' in oidsSNMP["slots_dict"][slot]
                          for extPort in range(1, 3)
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]])
                          for priornum in [str(x) for x in range(1, 9)]])
def test_ThresQL_AlarmBlock(slot, extPort, portnum, priornum):
    asyncio.run(clearprior())
    STM1alarm = list(asyncio.run(STM_alarm_status(slot)).values())
    stmql_values = []
    for i in range(len(STM1alarm)):
        if STM1alarm[i] == "0":
            asyncio.run(set_prior(slot, priornum, str(i + 1)))
            asyncio.run(extSourceID(str(extPort), slot, str(i + 1)))
            stmql_values.append(asyncio.run(STM1_QL_level(slot, i + 1)))

            for QL in oids["qualDICT"]:
                if QL != "0" and QL != "15" and stmql_values:
                    ThreshQL = asyncio.run(extThreshQL(str(extPort), int(QL)))

                    if ThreshQL >= stmql_values[0] != 0 and stmql_values[0] != 15:
                        time.sleep(1)
                        QLalarmdatch = asyncio.run(extThreshAlarm(str(extPort)))
                        assert QLalarmdatch == 0
                        assert bin(int(get_ssh_value('9', "4e")))[-int(extPort)] in ["0", "b"]
                    else:
                        time.sleep(1)
                        assert asyncio.run(extThreshAlarm(str(extPort))) == 2
                        assert bin(int(get_ssh_value('9', "4e")))[-int(extPort)] == "1"

'''Проверка аварии по порогам с выбранным ГСЭ, как источник вн синхронизации'''

@pytest.mark.parametrize('portnum, thresh_quality, sets_quality',
                         [(portnum, thresh_quality, sets_quality)
                          for portnum in range(1, 3)
                          for thresh_quality in [2, 4, 8, 11]
                          for sets_quality in [0, 2, 4, 8, 11, 15]])
def test_ThreshQL_AlarmSETS(portnum, thresh_quality, sets_quality):
    asyncio.run(QL_up_down("up"))
    asyncio.run(clearprior())

    asyncio.run(SETS_create(str(random.randint(1, 8)), sets_quality))
    asyncio.run(extSourceID(str(portnum), "SETS", ''))
    asyncio.run(extThreshQL(str(portnum), 11))
    time.sleep(65)

    clear_trap_log()
    asyncio.run(extThreshQL(str(portnum), thresh_quality))

    tlnextThreshQL = get_ssh_value("9", "4a") if portnum == 1 else get_ssh_value("9", "4c")
    assert int(tlnextThreshQL, 16) == thresh_quality

    if thresh_quality >= sets_quality and sets_quality not in [0, 15]:
        assert asyncio.run(extThreshAlarm(str(portnum))) == 0
        assert bin(int(get_ssh_value("9", "4e")))[-portnum] in ["0", "b"]
    elif sets_quality in [0, 15]:
        assert asyncio.run(extThreshAlarm(str(portnum))) == 2
        assert bd_alarm_get('LOW_QL', oids["syncOID"]["extTable"]["extThreshAlarm"] + str(portnum))
        assert bin(int(get_ssh_value("9", "4e")))[-portnum] == "1"
    else:
        assert asyncio.run(extThreshAlarm(str(portnum))) == 2
        assert bd_alarm_get('LOW_QL', oids["syncOID"]["extTable"]["extThreshAlarm"] + str(portnum))

        trap_log = parse_snmp_log(oids["syncOID"]["extTable"]["extThreshAlarm"] + str(portnum), 2)
        assert oids["syncOID"]["extTable"]["extThreshAlarm"] + str(portnum) == trap_log[0]
        assert str(trap_log[1]) in ["1", "2"]

        assert bin(int(get_ssh_value("9", "4e")))[-portnum] == "1"
