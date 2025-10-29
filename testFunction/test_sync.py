import random

import pytest

from OSMKv6.MainTelnet import mainfunc
from TRAP_analyze.ParseTrapLog import clear_trap_log, parse_snmp_log
from OSMKv6.SnmpV6alarm import *
from OSMKv6.SnmpV6sync import *
from Vivavi.ViaviControl import VIAVI_set_command, VIAVI_get_command, value_parcer_OSMK

blocks = [block for block in oids()["slots_dict"] if "STM" in block or "E1" in block]
priornums = ['1', '2', '3', '4', '5', '6', '7', '8']


def test_preparing():
    asyncio.run(alarmplusmask(blocks))
    # asyncio.run(maskStmTIM())
    assert True


''' Проверка создания и удаление приоритетов синхронизаций для всех возможных блоков'''
''' Функция создает приоритет с указаным блоком, сверяет SNMP и регистры. Далее удаляет приоритет и проверяет, что регистры очистились'''
''' Добавлен анализ TRAP сообщений с изменением статуса приоритета синхронизации при создании/удалении источника синхр. '''
'''  TASK #14382'''


@pytest.mark.parametrize('block, priornum, portnum',
                         [(block, priornum, portnum)
                          for block in blocks
                          for priornum in priornums
                          for portnum in range(1, oids()["quantPort"][block] + 1)])
def test_STM_E1_create_del(block, priornum, portnum):
    asyncio.run(clearprior())
    # clear_trap_log()
    time.sleep(0.5)
    snmpSTM_set = asyncio.run(set_prior(block, priornum, portnum))
    time.sleep(2)
    # assert oids()["syncOID"]["priorSTATUS"] + f"{priornum}" == \
    #        parse_snmp_log(oids()["syncOID"]["priorSTATUS"] + f"{priornum}", 2)[0] and str(
    #     parse_snmp_log(oids()["syncOID"]["priorSTATUS"] + f"{priornum}", 2)[1][:-1]) in ["1", "2"]
    tlntSTM_set = mainfunc(oids()["priorityREG"][priornum], 'KC', oids()["ipaddr"])
    if 'KCp' in oids()["slots_dict"]:
        assert tlntSTM_set == mainfunc(oids()["priorityREG"][priornum], 'KCp', oids()["ipaddr"])
    assert snmpSTM_set == (
            oids()["statusOID"][block] + oids()["slots_dict"][block] + f'.{portnum}') and tlntSTM_set != '0000'
    snmpSTM_del = asyncio.run(del_prior(priornum))
    tlntSTM_del = mainfunc(oids()["priorityREG"][priornum], 'KC', oids()["ipaddr"])
    if 'KCp' in oids()["slots_dict"]:
        assert tlntSTM_del == mainfunc(oids()["priorityREG"][priornum], 'KCp', oids()["ipaddr"])
    assert snmpSTM_del == oids()["portNull"] and tlntSTM_del == '0000'
    time.sleep(2)
    # assert oids()["syncOID"]["priorSTATUS"] + f"{priornum}" == \
    #        parse_snmp_log(oids()["syncOID"]["priorSTATUS"] + f"{priornum}", 2)[0] and str(
    #     parse_snmp_log(oids()["syncOID"]["priorSTATUS"] + f"{priornum}", 2)[1][:-1]) == '3'


'''Проверка включения режмиов синхронизации (с/без анализаQL)'''


def test_QLmodeDOWN():
    snmpQL_set = asyncio.run(QL_up_down("down"))
    tlntQL_set = mainfunc('3E', 'KC', oids()["ipaddr"])
    assert snmpQL_set == 0 and tlntQL_set == '0000'
    if 'KCp' in oids()["slots_dict"]:
        assert tlntQL_set == mainfunc('3E', 'KCp', oids()["ipaddr"])


'''Проверка включения режмиов синхронизации (с/без анализаQL)'''


def test_QLmodeUP():
    snmpQL_set = asyncio.run(QL_up_down("up"))
    tlntQL_set = mainfunc('3E', 'KC', oids()["ipaddr"])
    assert snmpQL_set == 1 and tlntQL_set == '0001'
    if 'KCp' in oids()["slots_dict"]:
        assert tlntQL_set == mainfunc('3E', 'KCp', oids()["ipaddr"])


'''Проверка создания внешнего источника синхронизации'''


@pytest.mark.parametrize("priornum, portnum", [(priornum, portnum)
                                               for priornum in priornums
                                               for portnum in range(1, 3)
                                               ])
def test_extPortID(priornum, portnum):
    asyncio.run(clearprior())
    exIDcr = asyncio.run(extPortCr(priornum, str(portnum)))
    assert exIDcr == oids()["syncOID"]["extTable"]["extID"] + str(portnum)
    assert mainfunc(oids()["priorityREG"][priornum], 'KC', oids()["ipaddr"]) == mainfunc(
        oids()["priorityREG"][priornum], 'KCp',
        oids()["ipaddr"])
    if str(portnum) == "1":
        assert mainfunc(oids()["priorityREG"][priornum], 'KC', oids()["ipaddr"]) == "0200"
    else:
        assert mainfunc(oids()["priorityREG"][priornum], 'KC', oids()["ipaddr"]) == "0300"
    exIDdel = asyncio.run(del_prior(priornum))
    assert exIDdel == oids()["portNull"]
    assert mainfunc(oids()["priorityREG"][priornum], 'KC', oids()["ipaddr"]) == mainfunc(
        oids()["priorityREG"][priornum], 'KCp',
        oids()["ipaddr"])
    assert mainfunc(oids()["priorityREG"][priornum], 'KC', oids()["ipaddr"]) == "0000"


'''Проверка занятия и очистки шины, при создании и удалении приоритета синхронизации'''
'''Нужна дороботка, выглядит как говно'''


@pytest.mark.parametrize("block, portnum, priornum", [(block, portnum, priornum)
                                                      for block in blocks
                                                      for priornum in priornums
                                                      for portnum in range(1, oids()["quantPort"][block] + 1)])
def test_busSYNC(block, priornum, portnum):
    dictPort = {"1": "1", "3": "2", "5": "3", "7": "4"}
    numprior = {"1": "2", "2": "3", "3": "4", "4": "5", "5": "7", "6": "8", "7": "9", "8": "10", "9": "1", "10": "6"}
    asyncio.run(clearprior())
    asyncio.run(set_prior(block, str(priornum), str(portnum)))
    if block != "63E1" and block != "21E1":
        busSTM = mainfunc(oids()["busSYNCsource"][block][numprior[priornum]], block, oids()["ipaddr"])
        busSTM = busSTM * 3
        assert int(dictPort[busSTM[-int(numprior[priornum])]]) == int(portnum)
        asyncio.run(del_prior(priornum))
        assert mainfunc(oids()["busSYNCsource"][block][numprior[priornum]], block, oids()["ipaddr"]) == "0000"
    elif block == '21E1':
        busSTM = mainfunc(oids()["busSYNCsource"][block][numprior[priornum]], block, oids()["ipaddr"])
        if int(numprior[priornum]) % 2 != 0:
            busSTM = busSTM[-2:]
        else:
            busSTM = busSTM[:-2]
        busSTM = int(busSTM, 16)
        assert int(busSTM) == int(portnum)
        asyncio.run(del_prior(priornum))
        assert mainfunc(oids()["busSYNCsource"][block][numprior[priornum]], block, oids()["ipaddr"]) == "0000"
    else:
        if int(portnum) < 22:
            TUG = 1
        elif 21 < int(portnum) < 43:
            TUG = 2
            portnum = int(portnum) - 21
        else:
            TUG = 3
            portnum = int(portnum) - 42
        busSTM = mainfunc(oids()["busSYNCsource"][block][f'{numprior[priornum]}.{TUG}'], block, oids()["ipaddr"])
        if int(numprior[priornum]) % 2 != 0:
            busSTM = busSTM[-2:]
        else:
            busSTM = busSTM[:-2]
        busSTM = int(busSTM, 16)
        assert int(busSTM) == int(portnum)
        asyncio.run(del_prior(priornum))
        assert mainfunc(oids()["busSYNCsource"][block][f'{priornum}.{TUG}'], block, oids()["ipaddr"]) == "0000"


''' Проверка установки качества на источнике внешней сонхронизации'''
''' Создается приоритет внешней синхронизации, устанавливается качество. Далее идет сверка качаества по регистрам и SNMP'''


@pytest.mark.parametrize("priornum, portnum, value", [(priornum, portnum, value)
                                                      for priornum in priornums
                                                      for portnum in range(1, 3)
                                                      for value in [2, 4, 8, 11, 15]])
def test_extPortQL(priornum, portnum, value):
    asyncio.run(clearprior())
    portnum = str(portnum)
    extCr = asyncio.run(extPortCr(priornum, portnum))
    extQl = asyncio.run(extPortQL(portnum, value))
    assert extCr == oids()["syncOID"]["extTable"]["extID"] + portnum
    assert extQl == value
    if portnum == "1":
        assert mainfunc(oids()["priorityREG"][priornum], 'KC',
                        oids()["ipaddr"]) == "020" + f'{oids()["qualDICT"][str(value)]}'
    else:
        assert mainfunc(oids()["priorityREG"][priornum], 'KC',
                        oids()["ipaddr"]) == "030" + f'{oids()["qualDICT"][str(value)]}'


'''Проверка установки режимов МГц и Мбит для портов вн. синхронизации'''


@pytest.mark.parametrize("portnum, value", [(portnum, value)
                                            for portnum in range(1, 3)
                                            for value in range(0, 2)])
def test_extPortConf(portnum, value):
    extConf = asyncio.run(extPortConf(str(portnum), value))
    assert extConf == value
    req = bin(int(mainfunc("22", 'KC', oids()["ipaddr"])))
    req = req.replace("b", "")
    assert req[-int(portnum)] == str(value)
    assert mainfunc("22", 'KC', oids()["ipaddr"]) == mainfunc("22", 'KCp', oids()["ipaddr"])


''' Проверка на использование портов STM в качестве источника для выхода портов внешней синхронизации'''
''' Создается источник от СТМ, проверяется записан ли он в регистры и по SNMP'''


@pytest.mark.parametrize(' block, portnum, blockport', [(block, portnum, blockport)
                                                        for block in [block for block in oids()["slots_dict"] if "STM" in block]
                                                        for portnum in range(1, 3)
                                                        for blockport in range(1, oids()["quantPort"][block] + 1)
                                                        ])
def test_extSourceID(block, portnum, blockport):
    extSrcID = asyncio.run(extSourceID(str(portnum), block, str(blockport)))
    assert extSrcID == oids()["statusOID"][block] + oids()["slots_dict"][block] + f'.{blockport}'
    assert bin(int(mainfunc("24", "KC", oids()["ipaddr"])))[-int(portnum)] == "1"
    extPort = mainfunc(oids()["extSourceSTM"][block], block, oids()["ipaddr"])[-int(portnum)]
    assert oids()["prior_dict"][extPort] == str(blockport)


''' Проверка на статус приоритета синхронизации, созданного с участием безаварийного порта'''


@pytest.mark.parametrize('block, portnum, priornum',
                         [(block, portnum, priornum)
                          for block in blocks if "STM" or "E1" in block
                          for portnum in range(1, oids()["quantPort"][block] + 1) if asyncio.run(STM_alarm_status(block))[portnum - 1] != 2
                          for priornum in priornums])
def test_prior_status(block, portnum, priornum):
    numprior = {"1": -2, "2": -3, "3": -4, "4": -5, "5": -7, "6": -8, "7": -9, "8": -10}
    asyncio.run(clearprior())
    asyncio.run(set_prior(block, priornum, portnum))
    time.sleep(2)
    prstatustlnt = mainfunc('3A', 'KC', oids()["ipaddr"])
    assert asyncio.run(prior_status(priornum)) == 1
    assert bin(int(prstatustlnt, 16)).replace("b", "")[numprior[priornum]] == '0'


''' Создание двух одинаковых приоритетов синхронизации, при получении исключения - тест пройден'''


@pytest.mark.parametrize('block, priornum, portnum',
                         [(block, priornum, portnum)
                          for block in blocks if "STM" or "E1" in block
                          for priornum in priornums
                          for portnum in str(oids()['quantPort'][block])])
def test_double_prior(block, priornum, portnum):
    asyncio.run(clearprior())
    asyncio.run(set_prior(block, priornum, portnum))
    with pytest.raises(Exception):  # NotWritable
        newprior = str(random.randint(1, 8))
        if priornum != newprior:
            assert asyncio.run(set_prior(block, newprior, portnum))
        else:
            assert asyncio.run(set_prior(block, str(random.randint(1, 10)), portnum))


''' Проверка уровня качества на входе блоков СТМ'''
''' Для теста необходимо обязательное подключение VIAVI '''
''' На приборе изменяется качество на выходе и сверяется сразу же с качеством на входе блоков СТМ'''


@pytest.mark.parametrize('block', [block for block in oids()["slots_dict"] if "STM" in block])
def test_QLSTM_get(block):
    asyncio.run(clearprior())
    STM1alarm = asyncio.run(STM_alarm_status(block))
    for i in range(len(STM1alarm)):
        if STM1alarm[i] == 0:
            for QLvalue in oids()["qualDICT"]:
                VIAVI_set_command("OSMKv6", block, ":SOURCE:SDH:MS:Z1A:BYTE:VIEW", QLvalue)
                assert mainfunc(oids()["stmQLgetREG"][block][str(i + 1)], block, oids()["ipaddr"])[-1] == \
                       oids()["qualDICT"][QLvalue]
                assert oids()["qualDICT"][str(asyncio.run(STM1_QL_level(block, i + 1)))] == oids()["qualDICT"][QLvalue]


''' Проверка передачи качества ГСЭ по потокам STM'''
''' Функция создает ЗГ, определяет безаварийные порты блока СТМ-N. Изменяя качество ЗГ, отслеживает качество на выходе STM.'''
''' Для портов, к которым подключен VIAVI проверка идет по регистрам и на входе VIAVI'''


@pytest.mark.parametrize('block', [block for block in oids()["slots_dict"] if "STM" in block])
def test_QLSTM_set(block: str):
    asyncio.run(clearprior())
    for STMvalue in oids()["qualDICT"]:
        asyncio.run(SETS_create("1", int(STMvalue)))
        STM1alarm = asyncio.run(STM_alarm_status(block))
        for i in range(len(STM1alarm)):
            if STM1alarm[i] == 0 or STM1alarm[i] == 64:
                assert oids()["qualDICT"][str(STMvalue)] in mainfunc(oids()["stmQLset"][block][str(i + 1)], block,
                                                                     oids()["ipaddr"])
                time.sleep(1)
                resQLstm = VIAVI_get_command("OSMKv6", block, ":SENSE:DATA? INTEGER:SONET:LINE:S1:SYNC:STATUS")[2:-2]
                assert oids()["VIAVIcontrol"]["reqSTMql"][resQLstm] == mainfunc(oids()["stmQLset"][block][str(i + 1)],
                                                                                block,
                                                                                oids()["ipaddr"])


''' Проверка установки уровней QL для интерфейсов E1'''
''' Создается приоритет синхронизации по блокам Е1, записываются все виды качества по очереди. Сверяются регистры блока КС'''


@pytest.mark.parametrize('priornum, block, portnum',
                         [(priornum, block, portnum)
                          for block in [block for block in oids()["slots_dict"] if "E1" in block]
                          for priornum in priornums
                          for portnum in [random.randint(1, oids()["quantPort"][block]) for _ in range(3)]])
def test_QLE1_set(priornum, block, portnum):
    asyncio.run(clearprior())
    asyncio.run(set_prior(block, priornum, portnum))
    assert mainfunc(oids()["priorityREG"][str(priornum)], "KC", oids()["ipaddr"]) != "0000"
    for value in oids()["qualDICT"]:
        asyncio.run(set_E1_QL(block, portnum, int(value)))
        tlntE1QL = mainfunc(oids()["priorityREG"][str(priornum)], "KC", oids()["ipaddr"])[-1]
        assert tlntE1QL == oids()["qualDICT"][value] == \
               mainfunc(oids()["priorityREG"][str(priornum)], "KCp", oids()["ipaddr"])[-1]


''' Проверка записи блоков СТМ как источников выходного сигнала'''
''' Записывается СТМ в ExtSourceID, по регистрам КС и самого блока СТМ проверяется коректность записи'''


@pytest.mark.parametrize('ExtPort, portnum, block',
                         [(ExtPort, portnum, block)
                          for block in [block for block in oids()["slots_dict"] if "STM" in block]
                          for ExtPort in range(1, 3)
                          for portnum in range(1, oids()["quantPort"][block] + 1)
                          ])
def test_STM_extport(ExtPort, portnum, block):
    extport = asyncio.run(STM1_ext_port(ExtPort, portnum, block))
    assert extport == oids()["statusOID"][block] + oids()["slots_dict"][block] + f'.{portnum}'
    assert bin(int(mainfunc('24', 'KC', oids()["ipaddr"])))[-int(ExtPort)] == "1"
    STMextPort = mainfunc(oids()["extSourceSTM"][block], block, oids()["ipaddr"])
    assert oids()["prior_dict"][STMextPort[-ExtPort]] == str(portnum)
    assert mainfunc('24', 'KC', oids()["ipaddr"]) == mainfunc('24', 'KCp', oids()["ipaddr"])


''' Проверка соответсвия текущего уровня качества источника синхронизации на входе блоков СТМ с качеством, записанным в КС'''


@pytest.mark.parametrize('ExtPort, portnum, block',
                         [(ExtPort, portnum, block)
                          for block in [block for block in oids()["slots_dict"] if "STM" in block]
                          for ExtPort in range(1, 3)
                          for portnum in range(1, oids()["quantPort"][block] + 1)
                          ])
def test_STM_QL_extport(ExtPort, portnum, block):
    asyncio.run(STM1_ext_port(ExtPort, portnum, block))
    extQLKS = mainfunc(oids()["KCqlGETreg"][str(ExtPort)], 'KC', oids()["ipaddr"])
    assert extQLKS == mainfunc(oids()["KCqlGETreg"][str(ExtPort)], 'KCp', oids()["ipaddr"])
    extQLstm = mainfunc(oids()["stmQLgetREG"][block][str(portnum)], block, oids()["ipaddr"])
    assert extQLKS == extQLstm
    time.sleep(1)


'Проверка аварий по порогам статистики для каждого интерфейсного блока и каждого качества на приеме'


@pytest.mark.parametrize('block, extPort, portnum, priornum', [(block, extPort, portnum, priornum)
                                                               for block in [block for block in oids()["slots_dict"] if "STM" in block]
                                                               for extPort in range(1, 3)
                                                               for portnum in range(1, oids()["quantPort"][block])
                                                               for priornum in priornums])
def test_ThresQL_AlarmBlock(block, extPort, portnum, priornum):
    asyncio.run(clearprior())
    STM1alarm = asyncio.run(STM_alarm_status(block))
    stmql1 = []
    for i in range(len(STM1alarm)):
        if STM1alarm[i] == 0:
            asyncio.run(set_prior(block, priornum, str(i + 1)))
            asyncio.run(extSourceID(str(extPort), block, str(i + 1)))
            stmql1.append(asyncio.run(STM1_QL_level(block, i + 1)))
            for QL in oids()["qualDICT"]:
                if QL != "0" and QL != "15" and stmql1:
                    ThreshQL = asyncio.run(extThreshQL(str(extPort), int(QL)))
                    if ThreshQL >= stmql1[0] != 0 and stmql1[0] != 15:
                        time.sleep(3)
                        QLalrmdatch = asyncio.run(extThreshAlarm(str(extPort)))
                        assert QLalrmdatch == 0
                        assert bin(int(mainfunc("4e", "KC", oids()["ipaddr"])))[-int(extPort)] == "0" or "b"
                    else:
                        time.sleep(3)
                        assert asyncio.run(extThreshAlarm(str(extPort))) == 2
                        assert bin(int(mainfunc("4e", "KC", oids()["ipaddr"])))[-int(extPort)] == "1"
                        assert mainfunc("4e", "KC", oids()["ipaddr"]) == mainfunc("4e", "KCp", oids()["ipaddr"])


''' Проверка аварии по порогам с выбранным ГСЭ, как источник вн синхронизации

    !!!! На новых блоках КСv4 из за WTR в минуту тест будет очень долгим > 70сек на каждую итерацию'''


@pytest.mark.parametrize('portnum, ThreshQuality, SETSquality', [(portnum, ThreshQuality, SETSquality)
                                                                 for portnum in range(2, 3)
                                                                 for ThreshQuality in [2, 4, 8, 11]
                                                                 for SETSquality in [0, 2, 4, 8, 11, 15]])
def test_ThreshQL_AlarmSETS(portnum, ThreshQuality, SETSquality):
    asyncio.run(clearprior())
    asyncio.run(QL_up_down("up"))
    asyncio.run(SETS_create(str(random.randint(1, 8)), SETSquality))
    asyncio.run(extSourceID(portnum, "SETS", ''))
    ThreshQLevel = asyncio.run(extThreshQL(portnum, ThreshQuality))
    tlnextTreshQL = mainfunc("4a", "KC", oids()["ipaddr"]) if portnum == 1 else mainfunc("4c", "KC", oids()["ipaddr"])
    time.sleep(61)
    assert int(tlnextTreshQL, 16) == ThreshQuality
    if ThreshQLevel >= SETSquality != 0 and SETSquality != 15:
        assert asyncio.run(extThreshAlarm(portnum)) == 0
        assert bin(int(mainfunc("4e", "KC", oids()["ipaddr"])))[-portnum] == "0" or "b"
    else:
        assert asyncio.run(extThreshAlarm(portnum)) == 2
        assert bin(int(mainfunc("4e", "KC", oids()["ipaddr"])))[-portnum] == "1"
        # assert mainfunc("4e", "KC", oids()["ipaddr"]) == mainfunc("4e", "KCp", oids()["ipaddr"])


''' Проверка переключений между приоритетами в режиме выключенного анализа QL'''


@pytest.mark.parametrize("block", [([block for block in oids()["slots_dict"] if "STM" in block])])
def test_noQual_PriorityChange(block):
    asyncio.run(clearprior())
    rangeList = iter(sample(range(1, 11), 5))
    for i in block:
        STMcreateWorkPrior(i, str(next(rangeList)))
    asyncio.run(SETS_create(str(next(rangeList))))
    asyncio.run(QL_up_down("down"))
    time.sleep(3)
    assert asyncio.run(prior_status(asyncio.run(curPrior()))) == 1 and len(asyncio.run(get_multi_slotID())) == 4
    for _ in asyncio.run(get_multi_slotID()):
        actualPrior = asyncio.run(curPrior())
        actualPriorIDs = asyncio.run(get_priorID(actualPrior))
        '''Проверка, что текущий активный приоритет является блоком СТМ, который синхронизируется от одного из портов VIAVI. Далее будет добавлено взаимодействие....'''
        for i in actualPriorIDs:
            for k in oids()["VIAVIcontrol"]["typeofport"]:
                if oids()["statusOID"][i] in asyncio.run(get_priorID(int(asyncio.run(curPrior())))) and i == \
                        oids()["VIAVIcontrol"]["typeofport"][k]:
                    time.sleep(5)
                    VIAVI_set_command("OSMKv6", i, ":OUTPUT:OPTIC ", "OFF")
                    time.sleep(5)
                    assert int(actualPrior) != int(asyncio.run(curPrior()))
                    time.sleep(5)
                    VIAVI_set_command("OSMKv6", i, ":OUTPUT:OPTIC ", "ON")
                    time.sleep(5)
                    assert int(actualPrior) == int(asyncio.run(curPrior()))
        asyncio.run(del_prior(str(asyncio.run(curPrior()))))
        time.sleep(5)
        assert int(actualPrior) != int(asyncio.run(curPrior()))
        time.sleep(5)
        asyncio.run(createPrbyID(str(actualPrior), str(actualPriorIDs)))
        time.sleep(5)
        assert int(actualPrior) == int(asyncio.run(curPrior()))
        time.sleep(5)
        asyncio.run(del_prior(str(asyncio.run(curPrior()))))


'''Проверка аварий физического порта блоков СТМ. Обязательно подключение VIAVI.
   С помощью VIAVI вводятся аварии, их наличие регестрируется по MIB и регистрам.
   В анализе участвуют только безаварийные порты'''


@pytest.mark.parametrize('block, portnum, alarmname', [(block, portnum, alarmname)
                                                       for block in [block for block in oids()["slots_dict"] if "STM" in block]
                                                       for portnum in range(1, oids()["quantPort"][block] + 1) if
                                                       [oids()["slots_dict"][block], str(portnum)] != oids()["loopback"] and
                                                       asyncio.run(check_alarmPH(block, portnum)) == 0 or
                                                       asyncio.run(check_alarmPH(block, portnum)) == 64
                                                       for alarmname in oids()["main_alarm"]["alarm_viavi"]])
def test_physical_alarmSTM(block, portnum, alarmname):
    if alarmname != "SD" and alarmname != "EXC" and alarmname != "TIM":
        time.sleep(0.5)
        try:
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi"][alarmname], "OFF" if alarmname == "LOS" else "ON")
            time.sleep(1)
            assert value_parcer_OSMK(mainfunc(oids()["main_alarm"]["ph_reg_alarmSTM"][block][str(portnum)], block, oids()["ipaddr"]))[
                       oids()["main_alarm"]["alarm_bit"][alarmname]] == "1"
            assert asyncio.run(check_alarmPH(block, portnum)) == oids()["main_alarm"]["alarm_mib_value"][alarmname]
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi"][alarmname], "ON" if alarmname == "LOS" else "OFF")
        except:
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi"][alarmname], "ON" if alarmname == "LOS" else "OFF")
            raise Exception("Порт проверить невозможно")
    elif alarmname == "TIM":
        asyncio.run(UNmaskStmTIM())
        clear_trap_log()
        try:
            TD = ''
            for _ in range(15):
                TD = TD + random.choice(list('123456789qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM'))
            asyncio.run(change_traceTD(block, portnum, TD[::-1]))
            for i in range(0, 15):
                VIAVI_set_command("OSMKv6", block, f":SOURCE:SDH:RS:TRACE (@{i})", value=ord(TD[i]))
            time.sleep(1)
            
            assert oids()["main_alarm"]["alarm_status"]["physical"][block] + str(oids()["slots_dict"][block]) + f".{portnum}" == \
                   parse_snmp_log(oids()["main_alarm"]["alarm_status"]["physical"][block] + oids()["slots_dict"][
                       block] + f".{portnum}",
                                  oids()["main_alarm"]["alarm_mib_value"][alarmname])[0]
            
            assert (str(oids()["main_alarm"]["alarm_mib_value"][alarmname]) ==
                    str(parse_snmp_log(oids()["main_alarm"]["alarm_status"]["physical"][block]
                                       + str(oids()["slots_dict"][block]) + f".{portnum}",
                                       oids()["main_alarm"]["alarm_mib_value"][alarmname])[1][:-1]))
            assert asyncio.run(check_alarmPH(block, portnum)) == oids()["main_alarm"]["alarm_mib_value"][alarmname]
            asyncio.run(change_traceTD(block, portnum, TD))
            time.sleep(1)
            assert asyncio.run(check_alarmPH(block, portnum)) == 0
        except:
            TD = "J0             "
            asyncio.run(change_traceTD(block, portnum, "J0             "))
            for i in range(0, 15):
                VIAVI_set_command("OSMKv6", block, f":SOURCE:SDH:RS:TRACE (@{i})", value=ord(TD[i]))
            assert False
    elif alarmname == "SD" or alarmname == "EXC":
        time.sleep(1)
        try:
            VIAVI_set_command("OSMKv6", block, ":SOURCE:SDH:MS:BIP:TYPE", "RATE")
            VIAVI_set_command("OSMKv6", block, ":SOURCE:SDH:MS:BIP:RATE", "1E5" if alarmname == "SD" else "1E3")
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi"][alarmname], "ON")
            time.sleep(3)
            assert asyncio.run(check_alarmPH(block, portnum)) == oids()["main_alarm"]["alarm_mib_value"][alarmname]
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi"][alarmname], "OFF")
            time.sleep(2)
        except:
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi"][alarmname], "OFF")
            assert False


''' Проверка аварий соеденительного порта блоков STM-N.
    Для начала тестирования необходимо указать, где установлен физический шлейф, на этот шлейф будет делаться вся коммутация.
    Перед работой для каждого теста проходит анализ на наличие активных аварий, если такие есть, то тест будет скипнут.
    Далее с Viavi запускается авария, регистрируется по SNMP и **регистрам**.'''


@pytest.mark.parametrize('block, portnum, alarmname, vc', [(block, portnum, alarmname, vc)
                                                           for block in [block for block in oids()["slots_dict"] if "STM" in block]
                                                           for portnum in range(1, oids()["quantPort"][block] + 1) if
                                                           [oids()["slots_dict"][block], str(portnum)] != oids()["loopback"] and
                                                           asyncio.run(check_alarmPH(block, portnum)) == 0 or
                                                           asyncio.run(check_alarmPH(block, portnum)) == 64
                                                           for alarmname in oids()["main_alarm"]["alarm_viavi_cnct"]
                                                           for vc in range(1, int(block[4:]) + 1)])
def test_connective_alarmSTM(block, portnum, alarmname, vc):
    asyncio.run(delete_commutation())
    asyncio.run(create_commutationVC4(block, portnum, vc))
    VIAVI_set_command("OSMKv6", block, ":SOURCE:SDH:STMN:CHANNEL ", vc)
    time.sleep(10)
    assert asyncio.run(check_alarm_cnct(block, portnum, vc)) == 0
    if alarmname in ["AUAIS", "AULOP", "VCUNEQ", "VCRDI"]:
        VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnct"][alarmname], "ON")
        time.sleep(3)
        try:
            assert asyncio.run(check_alarm_cnct(block, portnum, vc)) == oids()["main_alarm"]["alarm_mib_valueCnct"][alarmname]
            assert value_parcer_OSMK(mainfunc(oids()["main_alarm"]["cnct_reg_alarm"][block][str(portnum)][str(vc)], block,
                                              oids()["ipaddr"]))[oids()["main_alarm"]["alarm_bit_cnct"][alarmname]] == "1"
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnct"][alarmname], "OFF")
        except:
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnct"][alarmname], "OFF")
            assert False
    elif alarmname == "VCAIS":
        VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnct"][alarmname], "255")
        time.sleep(3)
        try:
            assert asyncio.run(check_alarm_cnct(block, portnum, vc)) == oids()["main_alarm"]["alarm_mib_valueCnct"][alarmname]
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnct"][alarmname], "254")
        except:
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnct"][alarmname], "254")
            assert False
    elif alarmname == "AUPJE":
        VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnct"][alarmname], "INTERNAL")
        time.sleep(3)
        try:
            assert asyncio.run(check_alarm_cnct(block, portnum, vc)) == oids()["main_alarm"]["alarm_mib_valueCnct"][alarmname]
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnct"][alarmname], "RECOVERED")
        except:
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnct"][alarmname], "RECOVERED")
            assert False
    elif alarmname == "VCPLM":
        asyncio.run(delete_commutation())
        asyncio.run(create_commutationVC12(block, portnum, vc, 1))
        time.sleep(10)
        assert asyncio.run(check_alarm_cnct(block, portnum, vc)) == oids()["main_alarm"]["alarm_mib_valueCnct"][alarmname]


'''Как всегда работает как говно.
Нужен VIAVI, блок СТМ любой и естественно Е1.
Иcследуемые порты обязательно должны быть физически зашлейфены сами на себя. МОЖНО РЕАЛИЗОВАТЬ ПО ПРОГРАММНОМУ ШЛЕЙФУ!!!!
Тестируются блоки 21Е1 и 63Е1, если на момент начала теста по физическому порту была авария E1-AIS (используется как идентификатор наличия шлейфа)
Далее по очереди для каждого порта сеттятся аварии и проверяется их наличие как в регистрах блока так и по SNMP.
Тест долгий, каждая авария анализруется около 7-8 секунд, т.е примерно 45 секунд на порт.
ВНИМАНИЕ!!!
В тесте используется только ПЕРВЫЙ ПОРТ VIAVI!!!!
'''

''' Необходимо сделать создание теста на VIAVI при запуске группы Е1 тестов.'''


@pytest.mark.parametrize('block, alarmname, vc', [(block, alarmname, vc)
                                                  for block in [block for block in oids()["slots_dict"] if "E1" in block]
                                                  for alarmname in oids()["main_alarm"]["alarm_viavi_cnctE1"]
                                                  for vc in range(1, int(block[:2]) + 1) if asyncio.run(check_alarmPH(block, vc)) == 4])
def test_connective_alarmE1(block, alarmname, vc):
    asyncio.run(delete_commutation())
    asyncio.run(create_commutationE1(block, vc))
    time.sleep(3)
    if alarmname in ["TUAIS", "VCUNEQ", "VCRDI"]:
        VIAVI_set_command("OSMKv6", oids()["VIAVIcontrol"]["settings"]["NumOne"]["typeofport"]["Port1"],
                          oids()["main_alarm"]["alarm_viavi_cnctE1"][alarmname], "ON")
        time.sleep(2)
        try:
            assert value_parcer_OSMK(mainfunc(oids()["main_alarm"]["cnct_reg_alarmE1"][block][str(vc)], block, oids()["ipaddr"]))[
                       oids()["main_alarm"]["alarm_bit_cnctE1"][alarmname]] == "1"
            assert asyncio.run(check_alarm_cnctE1(block, vc)) == oids()["main_alarm"]["alarm_mib_valueE1"][alarmname]
            VIAVI_set_command("OSMKv6", oids()["VIAVIcontrol"]["settings"]["NumOne"]["typeofport"]["Port1"],
                              oids()["main_alarm"]["alarm_viavi_cnctE1"][alarmname], "OFF")
        except:
            VIAVI_set_command("OSMKv6", oids()["VIAVIcontrol"]["settings"]["NumOne"]["typeofport"]["Port1"],
                              oids()["main_alarm"]["alarm_viavi_cnctE1"][alarmname], "OFF")
            raise Exception("Порт проверить невозможно")
    elif alarmname in ["VCAIS", "VCPLM"]:
        VIAVI_set_command("OSMKv6", oids()["VIAVIcontrol"]["settings"]["NumOne"]["typeofport"]["Port1"],
                          oids()["main_alarm"]["alarm_viavi_cnctE1"][alarmname], "14" if alarmname == "VCAIS" else "10")
        time.sleep(2)
        try:
            assert value_parcer_OSMK(mainfunc(oids()["main_alarm"]["cnct_reg_alarmE1"][block][str(vc)], block, oids()["ipaddr"]))[
                       oids()["main_alarm"]["alarm_bit_cnctE1"][alarmname]] == "1"
            assert asyncio.run(check_alarm_cnctE1(block, vc)) == oids()["main_alarm"]["alarm_mib_valueE1"][alarmname]
            VIAVI_set_command("OSMKv6", oids()["VIAVIcontrol"]["settings"]["NumOne"]["typeofport"]["Port1"],
                              oids()["main_alarm"]["alarm_viavi_cnctE1"][alarmname], "4")
        except:
            VIAVI_set_command("OSMKv6", oids()["VIAVIcontrol"]["settings"]["NumOne"]["typeofport"]["Port1"],
                              oids()["main_alarm"]["alarm_viavi_cnctE1"][alarmname], "4")
            raise Exception("Порт проверить невозможно")
    
    elif alarmname == "TUPJE":
        VIAVI_set_command("OSMKv6", oids()["VIAVIcontrol"]["settings"]["NumOne"]["typeofport"]["Port1"],
                          oids()["main_alarm"]["alarm_viavi_cnctE1"][alarmname], "INTERNAL")
        time.sleep(2)
        try:
            assert value_parcer_OSMK(mainfunc(oids()["main_alarm"]["cnct_reg_alarmE1"][block][str(vc)], block, oids()["ipaddr"]))[
                       oids()["main_alarm"]["alarm_bit_cnctE1"][alarmname]] == "1"
            assert asyncio.run(check_alarm_cnctE1(block, vc)) == oids()["main_alarm"]["alarm_mib_valueE1"][alarmname]
            VIAVI_set_command("OSMKv6", oids()["VIAVIcontrol"]["settings"]["NumOne"]["typeofport"]["Port1"],
                              oids()["main_alarm"]["alarm_viavi_cnctE1"][alarmname], "RECOVERED")
        except:
            VIAVI_set_command("OSMKv6", oids()["VIAVIcontrol"]["settings"]["NumOne"]["typeofport"]["Port1"],
                              oids()["main_alarm"]["alarm_viavi_cnctE1"][alarmname], "RECOVERED")
            assert False


''' Тесть исключительно только для первого VC-4 в блоке Eth1000
VIAVI подключается к блоку СТМ(любом) на Eth1000 ставим физ шлейф.
коммутация создается автоматически, далее сеттятся по очереди аварии.
TRAP не прикручены, как и проверка устранения аварий!'''


@pytest.mark.parametrize('block, portnum, alarmname, vc', [(block, portnum, alarmname, vc)
                                                           for block in [block for block in oids()["slots_dict"] if "Eth1000" in block]
                                                           for portnum in range(1, oids()["quantPort"][block] + 1) if
                                                           [oids()["slots_dict"][block], str(portnum)] != oids()["loopback"]
                                                           for alarmname in oids()["main_alarm"]["alarm_viavi_cnctGE"]
                                                           for vc in range(1, 2)])
def test_connective_alarmGE(block, portnum, alarmname, vc):
    asyncio.run(delete_commutation())
    asyncio.run(create_commutationVC4(block, portnum, vc))
    VIAVI_set_command("OSMKv6", block, ":SOURCE:SDH:HP:C2:BYTE", 27)
    VIAVI_set_command("OSMKv6", block, ":SOURCE:SDH:STMN:CHANNEL ", vc)
    VIAVI_set_command("OSMKv6", block, ":OUTPUT:CLOCK:SOURCE", "RECOVERED")
    time.sleep(3)
    assert asyncio.run(check_alarm_cnct(block, portnum, vc)) == 0
    if alarmname in ["AUAIS", "VCUNEQ", "VCRDI"]:
        VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnctGE"][alarmname], "ON")
        time.sleep(1)
    elif alarmname in ["VCAIS", "VCPLM"]:
        VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnctGE"][alarmname], "255" if alarmname == "VCAIS" else "207")
        time.sleep(1)
    elif alarmname in ["AUPJE"]:
        VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnctGE"][alarmname], "INTERNAL")
        time.sleep(2)
    try:
        assert asyncio.run(check_alarm_cnct(block, portnum, vc)) == oids()["main_alarm"]["alarm_mib_valueCnctGE"][alarmname]
        assert value_parcer_OSMK(mainfunc(oids()["main_alarm"]["cnct_reg_alarm"][block][str(portnum)][str(vc)], block,
                                          oids()["ipaddr"]))[oids()["main_alarm"]["alarm_bit_cnctGE"][alarmname]] == "1"
        if alarmname in ["AUAIS", "VCUNEQ", "VCRDI"]:
            VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnctGE"][alarmname], "OFF")
            time.sleep(2)
    except:
        VIAVI_set_command("OSMKv6", block, oids()["main_alarm"]["alarm_viavi_cnctGE"][alarmname], "OFF")
        assert False
