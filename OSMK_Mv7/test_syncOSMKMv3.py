import random
from sshV7 import get_ssh_value
import pytest
from Vivavi.ViaviControl import VIAVI_set_command, VIAVI_get_command, value_parcer_OSMK
from SnmpV7alarm import *
from SnmpV7Sync import *
from sshV7 import bd_alarm_get
from TRAP_analyze.ParseTrapLog import parse_snmp_log,clear_trap_log
blocks = [block for block in oidsSNMP["slots_dict"] if "STM" in block or "E1" in block]
priornums = ['1', '2', '3', '4', '5', '6', '7', '8']


def test_preparing():
    asyncio.run(alarmplusmask())
    assert True


@pytest.fixture(scope="module")
def get_block_data_fixture():
    block_list = asyncio.run(equpimentV7())


''' Проверка создания и удаление приоритетов синхронизаций для всех возможных блоков'''
''' Функция создает приоритет с указаным блоком, сверяет SNMP и регистры. Далее удаляет приоритет и проверяет, что регистры очистились'''
''' Добавлен анализ TRAP сообщений с изменением статуса приоритета синхронизации при создании/удалении источника синхр. '''
'''  TASK #14382'''


@pytest.mark.parametrize('slot, priornum, portnum',
                         [(slot, priornum, portnum)
                          for slot in oidsSNMP["slots_dict"]
                          if 'STM' in oidsSNMP["slots_dict"][slot] or 'E1' in oidsSNMP["slots_dict"][slot]
                          for priornum in priornums
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]] + 1)])
def test_STM_E1_create_del(get_block_data_fixture, slot, priornum, portnum):
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


'''Проверка включения режмиов синхронизации (с/без анализаQL)'''


def test_QLmodeDOWN():
    snmpQL_set = asyncio.run(QL_up_down("down"))
    sshQL_set = get_ssh_value('9', '3E')
    assert int(snmpQL_set) == 0 and sshQL_set.strip() == '0000'
    if oidsSNMP["slots_dict"].get("10"):
        assert sshQL_set.strip() == get_ssh_value('10', '3E')


'''Проверка включения режмиов синхронизации (с/без анализаQL)'''


def test_QLmodeUP():
    snmpQL_set = asyncio.run(QL_up_down("up"))
    sshQL_set = get_ssh_value('9', '3E')
    assert int(snmpQL_set) == 1 and sshQL_set.strip() == '0001'
    if oidsSNMP["slots_dict"].get("10"):
        assert sshQL_set.strip() == get_ssh_value('10', '3E')


'''Проверка создания внешнего источника синхронизации'''


@pytest.mark.parametrize("priornum, portnum", [(priornum, portnum)
                                               for priornum in priornums
                                               for portnum in range(1, 3)
                                               ])
def test_extPortID(priornum, portnum):
    # Setup - clear prior
    asyncio.run(clearprior())

    # Test creation
    exIDcr = asyncio.run(extPortCr(priornum, str(portnum)))
    expected_oid = f"{oids['syncOID']['extTable']['extID']}{portnum}"
    assert exIDcr == expected_oid, "External port creation failed"

    # Get values once for verification
    reg_value_9 = get_ssh_value('9', oids["priorityREG"][priornum])

    # Verify sync between slots if slot 10 exists
    if "10" in oidsSNMP["slots_dict"]:
        reg_value_10 = get_ssh_value('10', oids["priorityREG"][priornum])
        assert reg_value_9.strip() == reg_value_10, "Slots 9 and 10 are not in sync after creation"

    # Verify port-specific expected value
    expected_value = "0200" if portnum == 1 else "0300"
    assert reg_value_9.strip() == expected_value, f"Unexpected register value for port {portnum}"

    # Test deletion
    exIDdel = asyncio.run(del_prior(priornum))
    assert exIDdel == oids["portNull"], "Port deletion failed"

    # Verify post-deletion state
    post_del_value_9 = get_ssh_value('9', oids["priorityREG"][priornum])
    assert post_del_value_9.strip() == "0000", "Register not cleared after deletion"

    # Final sync check if slot 10 exists
    if "10" in oidsSNMP["slots_dict"]:
        post_del_value_10 = get_ssh_value('10', oids["priorityREG"][priornum])
        assert post_del_value_9.strip() == post_del_value_10.strip(), "Slots 9 and 10 are not in sync after deletion"


'''Проверка занятия и очистки шины, при создании и удалении приоритета синхронизации'''
'''Нужна дороботка, выглядит как говно'''


@pytest.mark.parametrize('slot, priornum, portnum',
                         [(slot, priornum, portnum)
                          for slot in oidsSNMP["slots_dict"]
                          if 'STM' in oidsSNMP["slots_dict"][slot] or 'E1' in oidsSNMP["slots_dict"][slot]
                          for priornum in priornums
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
    assert extCr == oids["syncOID"]["extTable"]["extID"] + portnum
    assert extQl == value
    if portnum == "1":
        assert get_ssh_value('9', oids["priorityREG"][priornum]) == "020" + f'{oids["qualDICT"][str(value)]}'
    else:
        assert get_ssh_value('9', oids["priorityREG"][priornum]) == "030" + f'{oids["qualDICT"][str(value)]}'


'''Проверка установки режимов МГц и Мбит для портов вн. синхронизации'''


@pytest.mark.parametrize("portnum, value", [(portnum, value)
                                            for portnum in range(1, 3)
                                            for value in range(0, 2)])
def test_extPortConf(portnum, value):
    extConf = asyncio.run(extPortConf(str(portnum), value))
    assert extConf == value
    req = bin(int(get_ssh_value('9', "22")))
    req = req.replace("b", "")
    assert req[-int(portnum)] == str(value)


''' Проверка на использование портов STM в качестве источника для выхода портов внешней синхронизации'''
''' Создается источник от СТМ, проверяется записан ли он в регистры и по SNMP'''


@pytest.mark.parametrize('slot, portnum, blockport', [(slot, portnum, blockport)
                                                      for slot in oidsSNMP["slots_dict"] if 'STM' in oidsSNMP["slots_dict"][slot]
                                                      for portnum in range(1, 3)
                                                      for blockport in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]] + 1)
                                                      ])
def test_extSourceID(slot, portnum, blockport):
    block = oidsSNMP["slots_dict"][slot]
    extSrcID = asyncio.run(extSourceID(str(portnum), slot, str(blockport)))
    assert str(extSrcID) == oids["statusOID"][block] + slot + f'.{blockport}'
    assert bin(int(get_ssh_value('9', "24")))[-int(portnum)] == "1"
    extPort = get_ssh_value(slot, oids["extSourceSTM"][block])[-int(portnum)]
    assert oids["prior_dict"][extPort] == str(blockport)


# ''' Проверка на статус приоритета синхронизации, созданного с участием безаварийного порта'''
#
#
# @pytest.mark.parametrize('slot, portnum, priornum', [(slot, portnum, priornum)
#                                                      for slot in oidsSNMP["slots_dict"] if
#                                                      'STM' in oidsSNMP["slots_dict"][slot] or 'E1' in oidsSNMP["slots_dict"][slot]
#                                                      for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]] + 1) if
#                                                      asyncio.run(STM_alarm_status(slot))[portnum - 1] != 2
#                                                      for priornum in priornums])
# def test_prior_status(block, portnum, priornum):
#     numprior = {"1": -2, "2": -3, "3": -4, "4": -5, "5": -7, "6": -8, "7": -9, "8": -10}
#     asyncio.run(clearprior())
#     asyncio.run(set_prior(block, priornum, portnum))
#     time.sleep(2)
#     prstatustlnt = get_ssh_value('9', '3A')
#     assert asyncio.run(prior_status(priornum)) == 1
#     assert bin(int(prstatustlnt, 16)).replace("b", "")[numprior[priornum]] == '0'


''' Проверка уровня качества на входе блоков СТМ'''
''' Для теста необходимо обязательное подключение VIAVI '''
''' На приборе изменяется качество на выходе и сверяется сразу же с качеством на входе блоков СТМ'''


@pytest.mark.parametrize('slot, ql', [(slot, ql)
                                      for slot in oidsSNMP["slots_dict"] if 'STM' in oidsSNMP["slots_dict"][slot]
                                      for ql in oids["qualDICT"]])
def test_QLSTM_get(slot, ql):
    asyncio.run(clearprior())
    STM1alarm = list(asyncio.run(STM_alarm_status(slot)).values())
    for i in range(len(STM1alarm)):
        if int(STM1alarm[i]) == 0 or STM1alarm[i] == 64:
            VIAVI_set_command(oidsSNMP["slots_dict"][slot], ":SOURCE:SDH:MS:Z1A:BYTE:VIEW", ql)
            assert get_ssh_value(slot, oids["stmQLgetREG"][oidsSNMP["slots_dict"][slot]][str(i + 1)])[-1] == \
                   oids["qualDICT"][ql]
            assert oids["qualDICT"][str(asyncio.run(STM1_QL_level(slot, i + 1)))] == oids["qualDICT"][ql]


''' Проверка передачи качества ГСЭ по потокам STM'''
''' Функция создает ЗГ, определяет безаварийные порты блока СТМ-N. Изменяя качество ЗГ, отслеживает качество на выходе STM.'''
''' Для портов, к которым подключен VIAVI проверка идет по регистрам и на входе VIAVI'''


@pytest.mark.parametrize('slot, ql', [(slot, ql)
                                      for slot in oidsSNMP["slots_dict"] if 'STM' in oidsSNMP["slots_dict"][slot]
                                      for ql in oids["qualDICT"]])
def test_QLSTM_set(slot, ql):
    asyncio.run(clearprior())
    asyncio.run(SETS_create("1", int(ql)))
    STM1alarm = list(asyncio.run(STM_alarm_status(slot)).values())
    for i in range(len(STM1alarm)):
        if int(STM1alarm[i]) == 0 or int(STM1alarm[i]) == 64:
            time.sleep(30)
            assert oids["qualDICT"][str(ql)] in get_ssh_value(slot, oids["stmQLset"][oidsSNMP["slots_dict"][slot]][str(i + 1)])
            time.sleep(1)
            resQLstm = VIAVI_get_command(oidsSNMP["slots_dict"][slot], ":SENSE:DATA? INTEGER:SONET:LINE:S1:SYNC:STATUS")[2:-2]
            assert oidsVIAVI["reqSTMql"][resQLstm] == get_ssh_value(slot, oids["stmQLset"][oidsSNMP["slots_dict"][slot]][str(i + 1)])


''' Проверка установки уровней QL для интерфейсов E1'''
''' Создается приоритет синхронизации по блокам Е1, записываются все виды качества по очереди. Сверяются регистры блока КС'''


@pytest.mark.parametrize('slot, priornum, portnum',
                         [(slot, priornum, portnum)
                          for slot in oidsSNMP["slots_dict"] if 'E1' in oidsSNMP["slots_dict"][slot]
                          for priornum in priornums
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]])])
def test_QLE1_set(slot, priornum, portnum):
    asyncio.run(clearprior())
    asyncio.run(set_prior(slot, priornum, portnum))
    assert get_ssh_value('9', oids["priorityREG"][str(priornum)]) != "0000"
    for value in oids["qualDICT"]:
        asyncio.run(set_E1_QL(slot, portnum, int(value)))
        tlntE1QL = get_ssh_value('9', oids["priorityREG"][str(priornum)])[-1]
        assert tlntE1QL == oids["qualDICT"][value] == \
               get_ssh_value('9', oids["priorityREG"][str(priornum)])[-1]


''' Проверка записи блоков СТМ как источников выходного сигнала'''
''' Записывается СТМ в ExtSourceID, по регистрам КС и самого блока СТМ проверяется коректность записи'''


@pytest.mark.parametrize('slot, extport, portnum',
                         [(slot, extport, portnum)
                          for slot in oidsSNMP["slots_dict"] if 'STM' in oidsSNMP["slots_dict"][slot]
                          for extport in range(1, 3)
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]])])
def test_STM_extport(slot, extport, portnum):
    newextport = str(asyncio.run(STM1_ext_port(extport, portnum, slot)))
    assert oids["statusOID"][oidsSNMP["slots_dict"][slot]] + slot + f'.{portnum}' == newextport
    assert bin(int(get_ssh_value('9', '24')))[-int(extport)] == "1"
    STMextPort = get_ssh_value(slot, oids["extSourceSTM"][oidsSNMP["slots_dict"][slot]])
    assert oids["prior_dict"][STMextPort[-extport]] == str(portnum)


''' Проверка соответсвия текущего уровня качества источника синхронизации на входе блоков СТМ с качеством, записанным в КС'''


@pytest.mark.parametrize('slot, extport, portnum',
                         [(slot, extport, portnum)
                          for slot in oidsSNMP["slots_dict"] if 'STM' in oidsSNMP["slots_dict"][slot]
                          for extport in range(1, 3)
                          for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]] + 1)])
def test_STM_QL_extport(slot, extport, portnum, ):
    asyncio.run(STM1_ext_port(extport, portnum, slot))
    time.sleep(1)
    extQLKS = get_ssh_value('9', oids["KCqlGETreg"][str(extport)])
    extQLstm = get_ssh_value(slot, oids["stmQLgetREG"][oidsSNMP["slots_dict"][slot]][str(portnum)])
    assert extQLKS == extQLstm


'Проверка аварий по порогам статистики для каждого интерфейсного блока и каждого качества на приеме'


@pytest.mark.parametrize('slot, extPort, portnum, priornum', [(slot, extPort, portnum, priornum)
                                                              for slot in oidsSNMP["slots_dict"] if 'STM' in oidsSNMP["slots_dict"][slot]
                                                              for extPort in range(1, 3)
                                                              for portnum in range(1, oids["quantPort"][oidsSNMP["slots_dict"][slot]])
                                                              for priornum in priornums])
def test_ThresQL_AlarmBlock(slot, extPort, portnum, priornum):
    asyncio.run(clearprior())
    STM1alarm = list(asyncio.run(STM_alarm_status(slot)).values())
    stmql1 = []
    for i in range(0, len(STM1alarm)):
        if STM1alarm[i] == "0":
            asyncio.run(set_prior(slot, priornum, str(i + 1)))
            asyncio.run(extSourceID(str(extPort), slot, str(i + 1)))
            stmql1.append(asyncio.run(STM1_QL_level(slot, i + 1)))
            for QL in oids["qualDICT"]:
                if QL != "0" and QL != "15" and stmql1:
                    ThreshQL = asyncio.run(extThreshQL(str(extPort), int(QL)))
                    if ThreshQL >= stmql1[0] != 0 and stmql1[0] != 15:
                        time.sleep(1)
                        QLalrmdatch = asyncio.run(extThreshAlarm(str(extPort)))
                        assert QLalrmdatch == 0
                        assert bin(int(get_ssh_value('9', "4e")))[-int(extPort)] == "0" or "b"
                    else:
                        time.sleep(1)
                        assert asyncio.run(extThreshAlarm(str(extPort))) == 2
                        assert bin(int(get_ssh_value('9', "4e")))[-int(extPort)] == "1"


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
    tlnextTreshQL = get_ssh_value("9", "4a") if portnum == 1 else get_ssh_value("9", "4c")
    time.sleep(61)
    assert int(tlnextTreshQL, 16) == ThreshQuality
    if ThreshQLevel >= SETSquality != 0 and SETSquality != 15:
        assert asyncio.run(extThreshAlarm(portnum)) == 0
        assert bin(int(get_ssh_value("9", "4e")))[-portnum] == "0" or "b"
    else:
        assert asyncio.run(extThreshAlarm(portnum)) == 2
        assert bin(int(get_ssh_value("9", "4e")))[-portnum] == "1"


# ''' Проверка переключений между приоритетами в режиме выключенного анализа QL'''
#
#
# @pytest.mark.parametrize("block", [([block for block in oidsSNMP["slots_dict"] if "STM" in block])])
# def test_noQual_PriorityChange(block):
#     asyncio.run(clearprior())
#     rangeList = iter(sample(range(1, 11), 5))
#     for i in block:
#         STMcreateWorkPrior(i, str(next(rangeList)))
#     asyncio.run(SETS_create(str(next(rangeList))))
#     asyncio.run(QL_up_down("down"))
#     time.sleep(3)
#     assert asyncio.run(prior_status(asyncio.run(curPrior()))) == 1 and len(asyncio.run(get_multi_slotID())) == 4
#     for _ in asyncio.run(get_multi_slotID()):
#         actualPrior = asyncio.run(curPrior())
#         actualPriorIDs = asyncio.run(get_priorID(actualPrior))
#         '''Проверка, что текущий активный приоритет является блоком СТМ, который синхронизируется от одного из портов VIAVI. Далее будет добавлено взаимодействие....'''
#         for i in actualPriorIDs:
#             for k in oids["VIAVIcontrol"]["typeofport"]:
#                 if oids["statusOID"][i] in asyncio.run(get_priorID(int(asyncio.run(curPrior())))) and i == \
#                         oids["VIAVIcontrol"]["typeofport"][k]:
#                     time.sleep(5)
#                     VIAVI_set_command("OSMKv6", i, ":OUTPUT:OPTIC ", "OFF")
#                     time.sleep(5)
#                     assert int(actualPrior) != int(asyncio.run(curPrior()))
#                     time.sleep(5)
#                     VIAVI_set_command("OSMKv6", i, ":OUTPUT:OPTIC ", "ON")
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
#