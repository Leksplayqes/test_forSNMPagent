import json
import subprocess
from pysnmp.hlapi.asyncio import (bulk_cmd, SnmpEngine, UsmUserData, UdpTransportTarget, ContextData, ObjectType,
                                  get_cmd, set_cmd,
                                  ObjectIdentity)


def oids():
    with open("OIDstatusNEW.json", "r") as jsonblock:
        oid = json.load(jsonblock)
        oids = oid[oid["CurrentEQ"]["name"]]
        return oids


def oidsSNMP():
    with open("OIDstatusNEW.json", "r") as jsonblock:
        oid = json.load(jsonblock)
        oidsSNMP = oid["CurrentEQ"]
        return oidsSNMP


def oidsVIAVI():
    with open("OIDstatusNEW.json", "r") as jsonblock:
        oid = json.load(jsonblock)
        oidsVIAVI = oid["VIAVIcontrol"]
        return oidsVIAVI


def json_input(key_path, new_value):
    with open('OIDstatusNEW.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    current = data
    for i, key in enumerate(key_path):
        if i < len(key_path) - 1:
            if key in current and isinstance(current[key], dict):
                current = current[key]
            else:
                print(f"Ошибка: Путь '{key_path[:i + 1]}' не найден в JSON.")
                return False
        else:
            current[key] = new_value
    with open('OIDstatusNEW.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def run_tunnel(ip, password):
    command = f"ncat -uk -l -c \"exec sshpass -p '{password}' ssh admin@{ip} -p 22 -s snmp\" 127.0.0.1 1161"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process


def close_tunnel():
    command = f"kill `lsof -t -i :1161`"
    subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


async def multi_snmp_get(oids: list):
    object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids()]
    error_indication, error_status, error_index, var_binds = await get_cmd(
        SnmpEngine(), UsmUserData("admin"),
        await UdpTransportTarget.create(("localhost", 1161), timeout=0.5, retries=1),
        ContextData(),
        *object_types)
    return [str(var_bind[1]) if var_bind[1] else None
            for var_bind in var_binds]


async def snmp_set_bulk(oid_value_pairs, host="localhost", port=1161, community="admin"):
    object_types = [ObjectType(ObjectIdentity(oid), value) for oid, value in oid_value_pairs]
    error_indication, error_status, error_index, var_binds = await set_cmd(
        SnmpEngine(),
        UsmUserData(community),
        await UdpTransportTarget.create(("localhost", 1161), timeout=0.5, retries=1),
        ContextData(),
        *object_types)
    return [str(var_bind[1]) if var_bind[1] else None
            for var_bind in var_binds]


async def snmp_set(oid, value):
    error_indication, error_status, error_index, var_binds = \
        await set_cmd(SnmpEngine(), UsmUserData("admin"), await UdpTransportTarget.create(("localhost", 1161)),
                      ContextData(), ObjectType(ObjectIdentity(oid), value))
    for value in var_binds:
        return value[1]


async def snmp_get(oid):
    error_indication, error_status, error_index, var_binds = \
        await get_cmd(SnmpEngine(), UsmUserData("admin"),
                      await UdpTransportTarget.create(("localhost", 1161), timeout=1, retries=5),
                      ContextData(), ObjectType(ObjectIdentity(oid)))
    for value in var_binds:
        return value[1]


async def snmp_getBulk(oid: str, max_repetitions: int):
    base = oid.rstrip('.')
    result = {}

    error_indication, error_status, error_index, var_binds = await bulk_cmd(
        SnmpEngine(),
        UsmUserData("admin"),
        await UdpTransportTarget.create(("localhost", 1161)),
        ContextData(),
        0, max_repetitions,
        ObjectType(ObjectIdentity(base)),
        lexicographicMode=False
    )
    for row in var_binds:
        row = (str(row).split())
        result[f'1.3.6.1.4.1.{row[0][24:]}'] = row[2]
    return result


''' Обращение к таблице hw_alarm с поиском аварии по определенному блоку (oid)
    На выходе список с активными авариями по этому порту, елси аварий нет, то список пустой'''


async def get_device_info():
    try:
        device_info = await snmp_get("1.3.6.1.2.1.1.1.0")
        name = str(device_info).split()[0]
        version = '7' if name in ['OSM-K', 'P-317S'] else '3'
        json_input(["CurrentEQ", "name"], f"{name}v{version}")
        return f"{name}v{version}"
    except Exception as e:
        print(f"Ошибка получения информации об устройстве: {e}")
        return "Unknown"


async def equpimentV7():
    idReal = await snmp_getBulk("1.3.6.1.4.1.5756.1.220.1.1.2", 12)
    noNullIdReal = {slot.split('.')[-1]: block for slot, block in idReal.items() if
                    block != '1.3.6.1.4.1.5756.1.202.0' and block != '1.3.6.1.4.1.5756.1.207.0'}
    for k in noNullIdReal:
        for j in oids()['statusOID']:
            if noNullIdReal[k] in oids()['statusOID'][j]:
                noNullIdReal[k] = j
    json_input(["CurrentEQ", "slots_dict"], noNullIdReal)
    return noNullIdReal

# asyncio.run(equpimentV7())
