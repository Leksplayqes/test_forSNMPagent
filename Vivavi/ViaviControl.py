import socket
import time
import contextlib
from typing import Optional, Dict, Any
from MainConnectFunc import oidsVIAVI


def create_socket_connection(ipaddr: str, port: int) -> Optional[socket.socket]:
    """Создает и возвращает подключение к устройству VIAVI"""
    if not ipaddr:
        return None

    try:
        client = socket.socket()
        client.settimeout(3)  # Добавляем таймаут для безопасности
        client.connect((ipaddr, port))
        client.send(b'*REM VISIBLE FULL\n')
        return client
    except (socket.error, ConnectionError, TimeoutError) as e:
        print(f"Connection error to {ipaddr}:{port}: {e}")
        return None


def close_socket_connection(client: socket.socket) -> None:
    """Корректно закрывает соединение с устройством VIAVI"""
    try:
        client.send(b':SESS:END\n')
    except (socket.error, OSError):
        pass  # Игнорируем ошибки при отправке команды закрытия

    try:
        client.close()
    except (socket.error, OSError):
        pass  # Игнорируем ошибки при закрытии сокета


@contextlib.contextmanager
def viavi_connection(ipaddr: str, port: int):
    """Контекстный менеджер для работы с подключением к VIAVI"""
    client = None
    try:
        client = create_socket_connection(ipaddr, port)
        yield client
    finally:
        if client:
            close_socket_connection(client)


def VIAVI_clearTest() -> None:
    """Очистка тестовых настроек на всех устройствах VIAVI"""
    for device_name, device_config in oidsVIAVI["settings"].items():
        if not device_config.get("ipaddr"):
            continue

        with viavi_connection(
                device_config["ipaddr"],
                int(device_config["port"])
        ) as client:
            if not client:
                continue

            client.send(b':SYST:APPL:CAPP?\n')
            req = client.recv(80).decode().split(",")

            if req == ['\n']:
                continue

            for app_name in req:
                if app_name.strip():  # Проверяем, что имя приложения не пустое
                    result = bytes(f':SYST:APPL:SEL {app_name}', "utf-8")
                    client.send(result + b'\n')
                    client.send(b':Exit\n')
                    time.sleep(2)  # Уменьшаем задержку для оптимизации


def VIAVI_secndStage(vc: str) -> None:
    """Второй этап настройки VIAVI для конкретного виртуального контейнера"""
    VIAVI_clearTest()

    for device_name, device_config in oidsVIAVI["settings"].items():
        if not device_config.get("ipaddr"):
            continue

        for port_name, port_type in device_config["typeofport"].items():
            if not port_type:  # Пропускаем пустые порты
                continue

            with viavi_connection(
                    device_config["ipaddr"],
                    int(device_config["port"])
            ) as client:
                if not client:
                    continue

                # Получаем соответствующее приложение для типа порта и VC
                app_name = oidsVIAVI["testappl"][port_type].get(vc)
                if not app_name:
                    print(f"No application found for {port_type} and {vc}")
                    continue

                testsetup = bytes(f':SYST:APPL:LAUN {app_name}', "utf-8")
                client.send(testsetup + b'\n')
                time.sleep(60)  # Уменьшаем время ожидания

                client.send(b':SYST:APPL:CAPP?\n')
                req = client.recv(80).decode().split(",")

                for app_name in req:
                    if app_name.strip():
                        result = bytes(f':SYST:APPL:SEL {app_name}', "utf-8")
                        client.send(result + b'\n')
                        client.send(b':OUTPUT:OPTIC ON\n')


def connect_to_device(block: str) -> Optional[socket.socket]:
    for device_name, device_config in oidsVIAVI["settings"].items():
        for port_name, port_type in device_config["typeofport"].items():
            if port_type == block:  # Ищем устройство с нужным типом порта
                client = create_socket_connection(
                    device_config["ipaddr"],
                    int(device_config["port"]))
                return client
    return None


def select_application(client: socket.socket, block: str, vc: str = "vc-4") -> None:
    """Выбирает приложение на устройстве VIAVI для конкретного типа порта и VC"""
    try:
        client.send(b':SYST:APPL:CAPP?\n')
        req = client.recv(80).decode().split(",")

        # Получаем имя приложения для данного типа порта и VC
        app_name = oidsVIAVI["testappl"][block].get(vc)
        if not app_name:
            print(f"No application found for {block} and {vc}")
            return

        # Ищем приложение в списке доступных
        for app in req:
            if app_name in app:
                client.send(bytes(f':SYST:APPL:SEL {app}\n', "utf-8"))
                client.send(b':SESS:CREATE\n')
                client.send(b':SESS:START\n')
                return

        print(f"Application {app_name} not found on device")
    except socket.error as exc:
        print(f"Socket error occurred: {exc}")


def VIAVI_type_test(block: str, vc: str) -> None:
    """Проверяет тип теста на устройстве VIAVI"""
    client = None
    try:
        client = connect_to_device(block)
        if not client:
            return

        client.send(b':SYST:APPL:CAPP?\n')
        req = client.recv(80).decode().split(",")

        # Получаем имя приложения для проверки
        app_name = oidsVIAVI["testappl"][block].get(vc)
        if not app_name:
            print(f"No application found for {block} and {vc}")
            return

        # Проверяем, доступно ли приложение на устройстве
        for test in req:
            if app_name in test:
                return  # Приложение уже доступно

        # Если приложение не найдено, запускаем второй этап настройки
        VIAVI_secndStage(vc)
    except Exception as e:
        print(f"Error in VIAVI_type_test: {e}")
    finally:
        if client:
            close_socket_connection(client)


def VIAVI_set_command(block: str, command: str, value: str = "") -> None:
    """Отправляет команду на устройство VIAVI с указанным типом порта"""
    client = None
    try:
        client = connect_to_device(block)
        if not client:
            print(f"Could not connect to device for block {block}")
            return

        select_application(client, block)
        bytecommand = bytes(f'{command} {value}', "utf-8")
        client.send(bytecommand + b'\n')
    except Exception as e:
        print(f"Error in VIAVI_set_command: {e}")
    finally:
        if client:
            close_socket_connection(client)


def VIAVI_get_command(block: str, command: str, vc: str = "vc-4") -> str:
    """Получает данные от VIAVI"""
    client = None
    try:
        client = connect_to_device(block)
        if not client:
            print(f"Could not connect to device for block {block}")
            return "-"

        select_application(client, block, vc)
        client.send(b':SESS:CREATE\n')
        client.send(b':SESS:START\n')

        bytecommand = bytes(f'{command}', "utf-8")
        client.send(bytecommand + b'\n')
        response = client.recv(35).decode()
        return response
    except Exception as e:
        print(f"Error in VIAVI_get_command: {e}")
        return "-"
    finally:
        if client:
            close_socket_connection(client)


def value_parcer_OSMK(value: str) -> str:
    """Парсит HEX значение в бинарную строку"""
    try:
        return bin(int(value, 16))[2:].zfill(16)
    except ValueError:
        return "0" * 16
