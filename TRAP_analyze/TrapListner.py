import datetime
import json
import logging
import os

import ifaddr
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntfrcv


def configure_snmp_engine(snmpEngine, TrapAgentAddress, Port):
    config.add_transport(
        snmpEngine,
        udp.DOMAIN_NAME + (1,),
        udp.UdpTransport().open_server_mode((TrapAgentAddress, Port))
    )
    config.add_v1_system(snmpEngine, 'public', 'public')


def get_trap_agent_address():
    iplist = []
    adapt = ifaddr.get_adapters()
    for ad in adapt:
        if hasattr(ad, 'ips'):
            for ip in ad.ips:
                ip = str(ip)
                if "192.168.72" in ip and ":" not in ip:
                    TrapAgentAddress1 = ip.split()[0][7:-2]
                    iplist.append(TrapAgentAddress1)

    return iplist[0] if iplist else None


def trap_callback(snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
    recive = "Received new Trap message"
    print("\033[31m{}".format(str(datetime.datetime.now().time()) + " " + recive))
    logging.info("Received new Trap message", )
    for name, val in varBinds:
        logging.info('%s = %s' % (name.prettyPrint(), val.prettyPrint()))
        trys = 0
        with open("TrapDescript.json", "r") as data:
            OIDdescr = json.load(data)
            for device in OIDdescr:
                for serive in OIDdescr[device]:
                    for value in OIDdescr[device][serive]:
                        for descr in OIDdescr[device][serive][value]:
                            if descr in name.prettyPrint():
                                parcrecive = '%s = %s' % (
                                    value + OIDdescr[device][serive][value][descr] + "." + name.prettyPrint().replace(
                                        descr, ""),
                                    val.prettyPrint()) if "5756" in str(name) else None
                                print("\033[34m{}".format(parcrecive)) if parcrecive is not None else None
                                trys = 1
        if trys == 0:
            unparcericive = '%s = %s' % (name.prettyPrint(), val.prettyPrint()) if "5756" in str(name) else None
            print("\033[34m{}".format(unparcericive)) if unparcericive is not None else None


def run_snmp_trap_listener():
    TrapAgentAddress = get_trap_agent_address()
    if not TrapAgentAddress:
        print("Unable to determine Trap Agent Address.")
        return
    snmpEngine = engine.SnmpEngine()
    Port = 1164
    logging.basicConfig(filename='received_traps.log', filemode='w', format='%(asctime)s - %(message)s',
                        level=logging.INFO)
    logging.info("Agent is listening SNMP Trap on " + TrapAgentAddress + " , Port : " + str(Port))
    logging.info('--------------------------------------------------------------------------')
    print("Agent is listening SNMP Trap on " + TrapAgentAddress + " , Port : " + str(Port))
    configure_snmp_engine(snmpEngine, TrapAgentAddress, Port)
    ntfrcv.NotificationReceiver(snmpEngine, trap_callback)
    snmpEngine.transport_dispatcher.job_started(1)
    try:
        snmpEngine.transport_dispatcher.run_dispatcher()
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        snmpEngine.transport_dispatcher.close_dispatcher()


def dtest():
    os.remove("received_traps.log")


run_snmp_trap_listener()
