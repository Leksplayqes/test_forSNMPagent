"""Catalogs of available pytest nodeids grouped by feature."""
from __future__ import annotations

SYNC_TESTS_CATALOG = {
    "Создание/удаление приоритетов (STM/E1)": "OSMK_Mv7/test_syncV7.py::test_STM_E1_create_del",
    "Режим QL: выключить": "OSMK_Mv7/test_syncV7.py::test_QLmodeDOWN",
    "Режим QL: включить": "OSMK_Mv7/test_syncV7.py::test_QLmodeUP",
    "Создание внешнего источника синхронизации": "OSMK_Mv7/test_syncV7.py::test_extPortID",
    "Занятие/очистка шины SYNC": "OSMK_Mv7/test_syncV7.py::test_busSYNC",
    "Установка качества для extPort": "OSMK_Mv7/test_syncV7.py::test_extPortQL",
    "Конфигурация частоты extPort": "OSMK_Mv7/test_syncV7.py::test_extPortConf",
    "STM как источник для extPort": "OSMK_Mv7/test_syncV7.py::test_extSourceID",
    "Статус приоритета (STM)": "OSMK_Mv7/test_syncV7.py::test_prior_statusSTM",
    "Получение уровня QL на STM-входе": "OSMK_Mv7/test_syncV7.py::test_QLSTM_get",
    "Передача QL через STM": "OSMK_Mv7/test_syncV7.py::test_QLSTM_set",
    "Запись STM как источника выхода": "OSMK_Mv7/test_syncV7.py::test_STM_extport",
    "Соответствие QL extPort ↔ STM": "OSMK_Mv7/test_syncV7.py::test_STM_QL_extport",
    "Аварии по порогам QL (блоки)": "OSMK_Mv7/test_syncV7.py::test_ThresQL_AlarmBlock",
    "Аварии по порогам QL (SETS)": "OSMK_Mv7/test_syncV7.py::test_ThreshQL_AlarmSETS",
}

ALARM_TESTS_CATALOG = {
    "Физические аварии STM": "OSMK_Mv7/test_alarmV7.py::test_physical_alarmSTM",
    "Аварии связности STM": "OSMK_Mv7/test_alarmV7.py::test_connective_alarmSTM",
    "Аварии связности E1": "OSMK_Mv7/test_alarmV7.py::test_connective_alarmE1",
    "Аварии связности GE": "OSMK_Mv7/test_alarmV7.py::test_connective_alarmGE",
}

__all__ = ["SYNC_TESTS_CATALOG", "ALARM_TESTS_CATALOG"]
