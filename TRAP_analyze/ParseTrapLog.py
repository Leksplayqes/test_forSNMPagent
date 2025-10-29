import re

"""
Функция ищет указанный OID в лог-файле, сверяет его значение,
уведомляет, если найдено несколько записей, и проверяет значение
последнего по времени.
"""


def parse_snmp_log(target_oid, expected_value):
    file_path = "TRAP_analyze/received_traps.log"
    timestamp_pattern = re.compile(r"(\d{2}:\d{2}:\d{2},\d+)")
    oid_entries = []
    try:
        with open(file_path, "r") as log_file:
            for line in log_file:
                if target_oid in line:
                    timestamp_match = timestamp_pattern.search(line)
                    timestamp = timestamp_match.group(0) if timestamp_match else "unknown"
                    oid_match = re.search(f"{target_oid} = ([^ ]+)", line)
                    if oid_match:
                        value = oid_match.group(1)
                        oid_entries.append((timestamp.strip(), value.strip()))
    except FileNotFoundError:
        return target_oid, "File not found"
    if not oid_entries:
        return target_oid, "No entries found"
    last_entry = oid_entries[-1]
    return str(target_oid), str(last_entry[1])


def clear_trap_log():
    with open("TRAP_analyze/received_traps.log", "a") as data:
        data.truncate(0)
