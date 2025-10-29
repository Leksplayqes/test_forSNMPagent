import asyncio
from typing import Dict, List, Tuple, Optional
from pysnmp.hlapi import *
from pysnmp.hlapi.asyncio import *
from MainConnectFunc import oids, json_input, oidsSNMP, close_connections_by_dst, snmp_set, snmp_get, snmp_set_bulk


def slot_to_block(slot: str) -> str:
    """Конвертирует номер слота в название блока"""
    return oidsSNMP['slots_dict'][slot]


async def snmp_getBulk(oid: str, repetition: int) -> Dict[str, str]:
    """Выполняет SNMP GETBULK запрос"""
    bulkDict = {}

    try:
        error_indication, error_status, error_index, var_binds = await bulkCmd(
            SnmpEngine(),
            UsmUserData("admin"),
            UdpTransportTarget(("localhost", 1161)),
            ContextData(),
            0,
            repetition,
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False
        )

        if error_indication:
            print(f"SNMP GETBULK error: {error_indication}")
            return bulkDict

        if error_status:
            print(f"SNMP GETBULK error: {error_status.prettyPrint()}")
            return bulkDict

        for varBindRow in var_binds:
            for varBind in varBindRow:
                oid_str = str(varBind[0])
                key = oid_str[oid_str.rfind('.') + 1:]
                bulkDict[key] = str(varBind[1])

    except Exception as e:
        print(f"Exception in SNMP GETBULK: {e}")

    finally:
        close_connections_by_dst(oidsSNMP['ipaddr'])

    return bulkDict


async def equpimentV7() -> Dict[str, str]:
    """Получает информацию о оборудовании V7"""
    idReal = await snmp_getBulk("1.3.6.1.4.1.5756.1.220.1.1.2", 12)

    # Фильтруем пустые значения и преобразуем идентификаторы
    noNullIdReal = {}
    for slot, block in idReal.items():
        if block != '1.3.6.1.4.1.5756.1.202.0':
            for j in oids['statusOID']:
                if block in oids['statusOID'][j]:
                    noNullIdReal[slot] = j
                    break

    json_input(["CurrentEQ", "slots_dict"], noNullIdReal)
    return noNullIdReal


def check_loopback() -> Optional[List[str]]:
    """Проверяет наличие loopback конфигурации"""
    if "loopback" in oidsSNMP and len(oidsSNMP["loopback"]) >= 2:
        return oidsSNMP["loopback"]
    return None


async def set_E1_loopback() -> None:
    """Устанавливает loopback для E1 портов"""
    e1_slots = [slot for slot in oidsSNMP["slots_dict"] if "E1" in oidsSNMP["slots_dict"][slot]]

    for slot in e1_slots:
        block = oidsSNMP["slots_dict"][slot]
        port_count = oids["quantPort"][block]
        if port_count <= 0:
            continue

        # Создаем список OID для настройки loopback
        oid_list = []
        for port in range(1, port_count + 1):
            oid = f"{oids['loopbackOID'][block]}{slot}.{port}"
            oid_list.append([oid, 1])

        # Отправляем команды пачками по 7
        batch_size = 7
        for i in range(0, len(oid_list), batch_size):
            batch = oid_list[i:i + batch_size]
            await snmp_set_bulk(batch)


def klm_numbers(vc12: int) -> str:
    """Генерирует K.L.M номер для VC12"""
    if vc12 < 1 or vc12 > 84:
        raise ValueError("VC12 должен быть в диапазоне 1-84")

    x = []
    for k in range(1, 4):
        for l in range(1, 8):
            for m in range(1, 4):
                x.append(f'{k}.{l}.{m}')

    return x[vc12 - 1]


def klm_numbersE1(vc12: int) -> str:
    """Генерирует K.L.M номер для E1 VC12"""
    if vc12 < 1 or vc12 > 84:
        raise ValueError("VC12 должен быть в диапазоне 1-84")

    x = []
    for m in range(1, 4):
        for l in range(1, 8):
            for k in range(1, 4):
                x.append(f'{k}.{l}.{m}')

    return x[vc12 - 1]


async def alarmplusmask() -> None:
    """Включает анализ аварий на физических портах"""
    tasks = []

    for slot, block in oidsSNMP["slots_dict"].items():
        if 'STM' in block or 'E1' in block:
            port_count = oids['quantPort'][block]
            if port_count <= 0:
                continue

            oid_list = []
            for port in range(1, port_count + 1):
                oid = f"{oids['alarmMODE'][block]}{slot}.{port}"
                oid_list.append((oid, Integer(2)))

            if oid_list:
                tasks.append(snmp_set_bulk(oid_list))

    # Запускаем все задачи параллельно
    if tasks:
        await asyncio.gather(*tasks)


async def alarmplusmaslcnctSTM() -> None:
    """Включает анализ аварий на логических портах STM"""
    tasks = []

    for slot, block in oidsSNMP["slots_dict"].items():
        if any(exclude in block for exclude in ['KC-M12', 'KC', 'E1', 'Eth']):
            continue

        port_count = oids['quantPort'][block]
        vc_count = oids['quantCnctPort'][block]

        if port_count <= 0 or vc_count <= 0:
            continue

        oid_list = []
        for port in range(1, port_count + 1):
            for vc in range(1, vc_count + 1):
                oid = f"{oids['alarmMODEcnct'][block]}{slot}.{port}.{vc}"
                oid_list.append((oid, Integer(2)))

        if oid_list:
            tasks.append(snmp_set_bulk(oid_list))

    # Обработка E1 отдельно
    for slot, block in oidsSNMP["slots_dict"].items():
        if 'E1' not in block:
            continue

        vc_count = oids['quantCnctPort'][block]

        if vc_count <= 0:
            continue

        oid_list = []
        for vc in range(1, vc_count + 1):
            klm = klm_numbersE1(vc)
            oid = f"{oids['alarmMODEcnct'][block]}{slot}.1.1.{klm}"
            oid_list.append((oid, Integer(2)))

        if oid_list:
            tasks.append(snmp_set_bulk(oid_list))

    # Запускаем все задачи параллельно
    if tasks:
        await asyncio.gather(*tasks)
