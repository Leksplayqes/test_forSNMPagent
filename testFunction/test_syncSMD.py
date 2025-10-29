import time

import pytest

from OSMKv6.MainTelnet import mainfuncOSMKv4
from testFunction.SnmpSMDsync import *
from ViaviControl import VIAVI_set_command, VIAVI_get_command

pytestmark = [pytest.mark.webtest, pytest.mark.slowtest]

blocks = [block for block in oids()["slots_dict"] if "STM" in block or "E1" in block or "KAD" in block]
priornums = ['1', '2', '3', '4', '5', '6', '7']


def test_preparing():
    asyncio.run(alarmplusmask(blocks))
    assert True


''' Проверка создания и удаление приоритетов синхронизаций для всех возможных блоков'''
''' Функция создает приоритет с указаным блоком, сверяет SNMP и регистры.
Далее удаляет приоритет и проверяет, что регистры очистились'''


@pytest.mark.parametrize('block, priornum, portnum',
                         [(block, priornum, portnum)
                          for block in blocks
                          for priornum in priornums
                          for portnum in range(1, oids()["quantPort"][block] + 1)])
def test_STM_E1_create_del(block, priornum, portnum):
    asyncio.run(clearprior())
    snmpSTM_set = asyncio.run(set_prior(block, priornum, portnum))
    time.sleep(1)
    tlntSTM_set = mainfuncOSMKv4(oids()["priorityREG"][priornum], 'KS_SS')
    if "KS_SSp" in oids()["slots_dict"]:
        tlntSTM_set1 = mainfuncOSMKv4(oids()["priorityREG"][priornum], 'KS_SSp')
        assert tlntSTM_set == tlntSTM_set1
    time.sleep(0.5)
    assert snmpSTM_set == (oids()["statusOID"][block] + oids()["slots_dict"][block] + f'.{portnum}') and tlntSTM_set[
        -3] == checkpriorregID(block, portnum)
    snmpSTM_del = asyncio.run(del_prior(priornum))
    time.sleep(1)
    tlntSTM_del = mainfuncOSMKv4(oids()["priorityREG"][priornum], 'KS_SS')
    if "KS_SSp" in oids()["slots_dict"]:
        assert tlntSTM_del == mainfuncOSMKv4(oids()["priorityREG"][priornum], 'KS_SSp')
    assert snmpSTM_del == oids()["portNull"] and tlntSTM_del == "0"


'''Проверка включения режмиов синхронизации (с/без анализаQL)'''


def test_QLmodeDOWN():
    snmpQL_set = asyncio.run(QL_up_down("down"))
    time.sleep(1)
    tlntQL_set = mainfuncOSMKv4('3E', 'KS_SS')
    time.sleep(0.5)
    assert snmpQL_set == 0 and tlntQL_set == '0'
    if "KS_SSp" in oids()["slots_dict"]:
        assert tlntQL_set == mainfuncOSMKv4('3E', 'KS_SSp')


'''Проверка включения режмиов синхронизации (с/без анализаQL)'''


def test_QLmodeUP():
    snmpQL_set = asyncio.run(QL_up_down("up"))
    time.sleep(1)
    tlntQL_set = mainfuncOSMKv4('3E', 'KS_SS')
    time.sleep(0.5)
    assert snmpQL_set == 1 and tlntQL_set == '1'
    if "KS_SSp" in oids()["slots_dict"]:
        assert tlntQL_set == mainfuncOSMKv4('3E', 'KS_SSp')


'''Проверка создания внешнего источника синхронизации'''


@pytest.mark.parametrize("priornum, portnum", [(priornum, portnum)
                                               for portnum in range(1, 3)
                                               for priornum in priornums])
def test_extPortID(priornum, portnum):
    asyncio.run(clearprior())
    asyncio.run(extPortCr(priornum, str(portnum)))
    time.sleep(1)
    newExtPriortlnt = mainfuncOSMKv4(oids()["priorityREG"][priornum], "KS_SS")
    assert int(newExtPriortlnt[-3]) == int(portnum) + 1
    if "KS_SSp" in oids()["slots_dict"]:
        assert newExtPriortlnt == mainfuncOSMKv4(oids()["priorityREG"][priornum], "KS_SSp")
    exIDdel = asyncio.run(del_prior(priornum))
    time.sleep(1)
    assert exIDdel == oids()["portNull"]
    assert mainfuncOSMKv4(oids()["priorityREG"][priornum], "KS_SS") == "0"


'''Проверка занятия и очистки шины, при создании и удалении приоритета синхронизации'''
'''Нужна дороботка, выглядит как говно'''


@pytest.mark.parametrize("block, priornum, portnum ", [(block, priornum, portnum)
                                                       for block in
                                                       [block for block in oids()["slots_dict"] if "E1" in block or "KAD" in block]
                                                       for priornum in priornums
                                                       for portnum in range(1, oids()["quantPort"][block] + 1)])
def test_busSYNC(block, priornum, portnum):
    asyncio.run(clearprior())
    asyncio.run(set_prior(block, str(priornum), str(portnum)))
    time.sleep(1)
    if block == "TE1":
        busSYNC = mainfuncOSMKv4(oids()["busSYNCsource"][block][priornum + ".1"], block) if int(
            portnum) < 5 else mainfuncOSMKv4(
            oids()["busSYNCsource"][block][priornum + ".2"], block)
        if int(priornum) % 2 == 0:
            busSYNC = busSYNC[:-2]
        assert portnum == int(busSYNC) if (int(portnum) < 5) else int(portnum) - 4 == int(busSYNC[-1])
        asyncio.run(del_prior(priornum))
        time.sleep(1)
        assert mainfuncOSMKv4(oids()["busSYNCsource"][block][priornum + ".1"], block) == "0" if int(
            portnum) < 5 else mainfuncOSMKv4(
            oids()["busSYNCsource"][block][priornum + ".2"], block) == "0"
    elif block == "T16E1":
        busSYNC = mainfuncOSMKv4(oids()["busSYNCsource"][block][str(priornum) + ".1"], block) if int(
            portnum) < 5 or int(
            portnum) in range(9, 13) else mainfuncOSMKv4(
            oids()["busSYNCsource"][block][str(priornum) + ".2"], block)
        if int(priornum) % 2 == 0:
            busSYNC = busSYNC[:-2]
        if int(portnum) < 5:
            assert str(portnum) == busSYNC
        elif 4 < int(portnum) < 13:
            assert int(portnum) - 4 == int(busSYNC)
        else:
            assert int(portnum) - 8 == int(busSYNC)
        asyncio.run(del_prior(str(priornum)))
        time.sleep(1)
        assert mainfuncOSMKv4(oids()["busSYNCsource"][block][str(priornum) + ".1"], block) == "0" if int(
            portnum) < 5 or 8 < int(portnum) < 13 else mainfuncOSMKv4(oids()["busSYNCsource"][block][str(priornum) + ".2"], block) == "0"
    elif block == "21E1":
        busSYNC = mainfuncOSMKv4(oids()["busSYNCsource"][block][str(priornum)], "21E1")
        if int(priornum) % 2 == 0:
            busSYNC = busSYNC[:-2]
        if portnum < 16:
            assert str(hex(portnum))[-1] == busSYNC
        else:
            assert str(int(portnum) - 6) == busSYNC
        asyncio.run(del_prior(str(priornum)))
        time.sleep(1)
        assert mainfuncOSMKv4(oids()["busSYNCsource"][block][str(priornum)], "21E1") == "0"
    elif block == "KAD":
        busSYNC = mainfuncOSMKv4(oids()["busSYNCsource"][block][str(priornum)], "KAD")
        assert busSYNC == mainfuncOSMKv4(oids()["priorityREG"][priornum], 'KS_SS')
        asyncio.run(del_prior(str(priornum)))
        time.sleep(1)
        assert mainfuncOSMKv4(oids()["busSYNCsource"][block][str(priornum)], block) == "0"
    


''' Проверка установки качества на источнике внешней сонхронизации'''
''' Создается приоритет внешней синхронизации, устанавливается качество. Далее идет сверка качаества по регистрам и SNMP'''


@pytest.mark.parametrize("priornum, portnum, value", [(priornum, portnum, value)
                                                      for priornum in priornums
                                                      for portnum in range(1, 3)
                                                      for value in [2, 4, 8, 11, 15]])
def test_extPortQL(priornum, portnum, value):
    asyncio.run(clearprior())
    assert asyncio.run(extPortCr(priornum, str(portnum))) == oids()["syncOID"]["extTable"]["extID"] + str(portnum)
    assert asyncio.run(extPortQL(str(portnum), value)) == value
    time.sleep(2)
    assert mainfuncOSMKv4(oids()["priorityREG"][priornum],
                          'KS_SS') == "20" + f'{oids()["qualDICT"][str(value)]}' if str(
        portnum) == "1" else "30" + f'{oids()["qualDICT"][str(value)]}'
    asyncio.run(del_prior(priornum))


'''Проверка установки режимов МГц и Мбит для портов вн. синхронизации'''
'''Создается приоритет от вн. синхр, проверяется его статус. Изменяем режим порта, опять смотрим статус.
В одном случае ожидаем норму, в другом аварию'''


@pytest.mark.parametrize("priornum, portnum, value", [(priornum, portnum, value)
                                                      for priornum in priornums
                                                      for portnum in range(1, 3)
                                                      for value in range(0, 2)])
def test_extPortConf(priornum, portnum, value):
    asyncio.run(clearprior())
    extConf = asyncio.run(extPortConf(str(portnum), value))
    assert extConf == value
    req = bin(int(mainfuncOSMKv4("22", 'KS_SS')))
    req = req.replace("b", "")
    assert req[-int(portnum)] == str(value)
    if "KS_SSp" in oids()["slots_dict"]:
        assert mainfuncOSMKv4("22", 'KS_SS') == mainfuncOSMKv4("22", 'KS_SSp')
    asyncio.run(extPortCr(str(priornum), str(portnum)))
    asyncio.run(extPortConf(str(portnum), (value + 1) % 2))
    time.sleep(2)
    assert asyncio.run(prior_status(str(priornum))) == 1 if value == 0 else asyncio.run(prior_status(str(priornum))) == 2
    assert asyncio.run(curPrior()) == int(priornum) if value == 0 else asyncio.run(curPrior()) == 9


''' Проверка на использование портов STM в качестве источника для выхода портов внешней синхронизации'''
''' Создается источник от СТМ, проверяется записан ли он в регистры и по SNMP'''


@pytest.mark.parametrize(' block, portnum, blockport', [(block, portnum, blockport)
                                                        for block in [block for block in oids()["slots_dict"] if "STM" in block]
                                                        for portnum in range(1, 3)
                                                        for blockport in range(1, oids()["quantPort"][block] + 1)
                                                        ])
def test_extSourceID(block, portnum, blockport):
    extSrcID = asyncio.run(extSourceID(str(portnum), block, str(blockport)))
    time.sleep(1)
    assert extSrcID == oids()["statusOID"][block] + oids()["slots_dict"][block] + f'.{blockport}'
    assert mainfuncOSMKv4("24", "KS_SS").replace("b", "")[-int(portnum)] == oids()["stmportID"][
        oids()["slots_dict"][block] + str(blockport)]
    if "KS_SSp" in oids()["slots_dict"]:
        assert mainfuncOSMKv4("24", "KS_SS").replace("b", "")[-int(portnum)] == \
               mainfuncOSMKv4("24", "KS_SSp").replace("b", "")[-int(portnum)]


''' Проверка на статус приоритета синхронизации, созданного с участием безаварийного порта'''


@pytest.mark.parametrize('block, priornum',
                         [(block, priornum)
                          for block in blocks
                          for priornum in priornums])
def test_prior_statusSTM_E1(block, priornum):
    asyncio.run(clearprior())
    blockAlarm = asyncio.run(STM_alarm_status(block))
    if 0 in blockAlarm:
        for norm in range(len(blockAlarm)):
            if blockAlarm[norm] == 0:
                asyncio.run(set_prior(block, priornum, norm + 1))
                time.sleep(2)
                if "KS_SSp" in oids()["slots_dict"]:
                    assert bin(int(mainfuncOSMKv4('3A', 'KS_SS'), 16)).replace("b", "")[-int(priornum)] == '0'
                assert asyncio.run(prior_status(priornum)) == 1
    else:
        assert False


''' Создание двух одинаковых приоритетов синхронизации, при получении исключения - тест пройден'''

# @pytest.mark.parametrize('block, priornum, portnum',
#                          [(block, priornum, portnum)
#                           for block in blocks
#                           for priornum in priornums
#                           for portnum in str(random.randint(1, oids()['quantPort'][block]))])
# def test_double_prior(block, priornum, portnum):
#     asyncio.run(clearprior())
#     asyncio.run(set_prior(block, priornum, portnum))
#     with pytest.raises(Exception):
#         newprior = str(random.randint(1, 10))
#         if priornum != newprior:
#             assert asyncio.run(set_prior(block, newprior, portnum))
#         else:
#             assert asyncio.run(set_prior(block, str(random.randint(1, 10)), portnum))


''' Проверка уровня качества на входе блоков СТМ'''
''' Для теста необходимо обязательное подключение VIAVI '''
''' На приборе изменяется качество на выходе и сверяется сразу же с качеством на входе блоков СТМ'''


@pytest.mark.parametrize('block', [block for block in oids()["slots_dict"] if "STM" in block])
def test_QLSTM_get(block):
    asyncio.run(clearprior())
    STMalarm = asyncio.run(STM_alarm_status(block))
    if 0 in STMalarm:
        for QLvalue in oids()["qualDICT"]:
            VIAVI_set_command("SMD", block, ":SOURCE:SDH:MS:Z1A:BYTE:VIEW", QLvalue)
            time.sleep(1)
            assert mainfuncOSMKv4(oids()["stmQLgetREG"][block][str(STMalarm.index(0) + 1)], block) == oids()["qualDICT"][QLvalue]
            assert oids()["qualDICT"][str(asyncio.run(STM1_QL_level(block, STMalarm.index(0) + 1)))] == oids()["qualDICT"][QLvalue]
    else:
        assert False


''' Проверка передачи качества ГСЭ по потокам STM'''
''' Функция создает ЗГ, определяет безаварийные порты блока СТМ-N. Изменяя качество ЗГ, отслеживает качество на выходе STM.'''
''' Для портов, к которым подключен VIAVI проверка идет по регистрам и на входе VIAVI'''


@pytest.mark.parametrize('block', [block for block in oids()["slots_dict"] if "STM" in block])
def test_QLSTM_set(block: str):
    asyncio.run(clearprior())
    for STMvalue in oids()["qualDICT"]:
        asyncio.run(SETSs_create("1", int(STMvalue)))
        time.sleep(3)
        resQLstm = VIAVI_get_command("SMD", block, ":SENSE:DATA? INTEGER:SONET:LINE:S1:SYNC:STATUS")[2:-2]
        time.sleep(3)
        assert oids()["VIAVIcontrol"]["reqSTMql"][resQLstm][-1] == oids()["qualDICT"][STMvalue].upper()


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
    time.sleep(1)
    assert mainfuncOSMKv4(oids()["priorityREG"][str(priornum)], "KS_SS")[-3] == "c"
    for value in oids()["qualDICT"]:
        asyncio.run(set_E1_QL(block, portnum, int(value)))
        time.sleep(1)
        tlntE1QL = mainfuncOSMKv4(oids()["priorityREG"][str(priornum)], "KS_SS")[-1]
        if "KS_SSp" in oids()["slots_dict"]:
            assert tlntE1QL == oids()["qualDICT"][value] == mainfuncOSMKv4(oids()["priorityREG"][str(priornum)], "KS_SSp")[
                -1]


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
    time.sleep(1)
    assert extport == oids()["statusOID"][block] + oids()["slots_dict"][block] + f'.{portnum}'
    assert mainfuncOSMKv4('24', 'KS_SS')[-int(ExtPort)] == oids()["stmportID"][
        (oids()["slots_dict"][block] + str(portnum))]
    if "KS_SSp" in oids()["slots_dict"]:
        assert mainfuncOSMKv4('24', 'KS_SS')[-int(ExtPort)] == mainfuncOSMKv4('24', 'KS_SSp')[-int(ExtPort)]


''' Проверка соответсвия текущего уровня качества источника синхронизации на входе блоков СТМ с качеством, записанным в КС'''
''' НЕОБХОДИМО ПЕРЕДЕЛАТЬ, НЕПОНЯТНАЯ ХЕРНЯ'''


@pytest.mark.parametrize('ExtPort, portnum, block',
                         [(ExtPort, portnum, block)
                          for block in ["STM-1", "STM-4"]
                          for ExtPort in range(1, 3)
                          for portnum in range(1, oids()["quantPort"][block] + 1)
                          ])
def test_STM_QL_extport(ExtPort, portnum, block):
    asyncio.run(STM1_ext_port(ExtPort, portnum, block))
    extQLKS = mainfuncOSMKv4(oids()["KS_SSqlGETreg"][str(ExtPort)], 'KS_SS')
    if "KS_SSp" in oids()["slots_dict"]:
        assert extQLKS == mainfuncOSMKv4(oids()["KS_SSqlGETreg"][str(ExtPort)], 'KS_SSp')
    extQLstm = mainfuncOSMKv4(oids()["stmQLgetREG"][block][str(portnum)], block)
    assert extQLKS == extQLstm


''' Проверка переключений между приоритетами в режиме выключенного анализа QL'''


# @pytest.mark.parametrize("block", [([block for block in oids()["slots_dict"] if "STM" in block])])
# def test_noQual_PriorityChange(block):
#     asyncio.run(clearprior())
#     rangeList = iter(sample(range(1, 11), 5))
#     for i in block:
#         STMcreateWorkPrior(i, str(next(rangeList)))
#     asyncio.run(SETS_create(str(next(rangeList))))
#     asyncio.run(QL_up_down("down"))
#     time.sleep(3)
#     assert asyncio.run(prior_status(asyncio.run(curPrior()))) == 1 and len(asyncio.run(get_multi_slotID())) == 2
#     for _ in asyncio.run(get_multi_slotID()):
#         actualPrior = asyncio.run(curPrior())
#         actualPriorIDs = asyncio.run(get_priorID(actualPrior))
#         '''Проверка, что текущий активный приоритет является блоком СТМ, который синхронизируется от одного из портов VIAVI. Далее будет добавлено взаимодействие....'''
#         for i in actualPriorIDs:
#             for k in oids()["VIAVIcontrol"]["typeofport"]:
#                 if oids()["statusOID"][i] in asyncio.run(get_priorID(int(asyncio.run(curPrior())))) and i == \
#                         oids()["VIAVIcontrol"]["typeofport"][k]:
#                     time.sleep(5)
#                     VIAVI_set_command("SMD", i, ":OUTPUT:OPTIC ", "OFF")
#                     time.sleep(5)
#                     assert int(actualPrior) != int(asyncio.run(curPrior()))
#                     time.sleep(5)
#                     VIAVI_set_command("SMD", i, ":OUTPUT:OPTIC ", "ON")
#                     time.sleep(5)
#                     assert int(actualPrior) == int(asyncio.run(curPrior()))
#         asyncio.run(del_prior(str(asyncio.run(curPrior()))))
#         time.sleep(5)
#         assert int(actualPrior) != int(asyncio.run(curPrior()))
#         time.sleep(5)
#         asyncio.run(createPrbyID(str(actualPrior), str(actualPriorIDs)))
#         time.sleep(5)
#         assert int(actualPrior) == int(asyncio.run(curPrior()))
#         time.sleep(5)
#         asyncio.run(del_prior(str(asyncio.run(curPrior()))))
