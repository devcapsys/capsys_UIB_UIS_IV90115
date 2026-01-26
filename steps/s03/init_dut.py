# -*- coding: utf-8 -*-

import sys, os, time
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
import configuration  # Custom
from modules.capsys_mysql_command.capsys_mysql_command import (GenericDatabaseManager, DatabaseConfig) # Custom

def get_info():
    return "Cette étape teste les seuils de fonctionnement du radar."

def run_step(log, config: configuration.AppConfig, update_percentage=lambda x: None):
    step_name = os.path.splitext(os.path.basename(__file__))[0]
    return_msg = {"step_name": step_name, "infos": []}
    # Ensure db is initialized
    if not hasattr(config, "db") or config.db is None:
        return_msg["infos"].append(f"config.db n'est pas initialisé.")
        return 1, return_msg
    # We always save the name of the step in the db
    step_name_id = config.db.create("step_name", {"device_under_test_id": config.device_under_test_id, "step_name": step_name})
    ###################################################################
    if config.mcp_manager is None:
        return_msg["infos"].append("Le gestionnaire MCP n'est pas initialisé.")
        return 1, return_msg
    if config.daq_manager is None or config.daq_port is None:
        return_msg["infos"].append("Le gestionnaire DAQ n'est pas initialisé.")
        return 1, return_msg
    
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_BTL, False)
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_GND_IVE1_IVE2_IVF_2, False)
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_AUTOMATIC_24V, True)
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_AUTOMATIC_BTL, True)
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_24V, True)

    if configuration.HASH_GIT == "DEBUG":
        log(f"DEBUG mode: Using COM11 for serial communication.", "yellow")
        port = "COM11" # PC TGE
    else:
        port = config.configItems.dut.port
    
    config.serDut = configuration.SerialUsbDut(port=port)
    config.serDut.open_with_port(port)
    log(f"Port {port} ouvert avec succès", "blue")

    test_ok = 0
    # R1 = 12k ohm, R2 = 5.6k ohm, Vout = Vin * (R2 / (R1 + R2))
    mult = 5.6/(5.6+12)
    min = 23.5
    max = 25.5
    unit = "V"
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_GND_IVE1_IVE2_IVF_2, True)
    time.sleep(0.5)  # Wait for voltages to stabilize
    meas_ive1 = config.daq_manager.read_a_line(config.daq_port, configuration.DAQPin.M_V_IVE1.value) / mult
    log(f"Ive1 mesuré : {meas_ive1:.3f} V, min={min}{unit}, max={max}{unit}", "blue")
    id_skvp_ive1 = config.save_value(step_name_id, "IVE1_V", meas_ive1, unit, min, max)
    if (meas_ive1 < min) or (meas_ive1 > max):
        return_msg["infos"].append(f"IVE1 mesuré à {meas_ive1:.3f} V hors des limites ({min}-{max} {unit}).")
        test_ok = 1
    else:
        config.db.update_by_id("skvp_float", id_skvp_ive1, {"valid": 1})
    meas_ive2 = config.daq_manager.read_a_line(config.daq_port, configuration.DAQPin.M_V_IVE2.value) / mult
    log(f"Ive2 mesuré : {meas_ive2:.3f} V, min={min}{unit}, max={max}{unit}", "blue")
    id_skvp_ive2 = config.save_value(step_name_id, "IVE2_V", meas_ive2, unit, min, max)
    if (meas_ive2 < min) or (meas_ive2 > max):
        return_msg["infos"].append(f"IVE2 mesuré à {meas_ive2:.3f} V hors des limites ({min}-{max} {unit}).")
        test_ok = 1
    else:
        config.db.update_by_id("skvp_float", id_skvp_ive2, {"valid": 1})
    meas_ivf = config.daq_manager.read_a_line(config.daq_port, configuration.DAQPin.M_V_IVF.value) / mult
    log(f"Ivf mesuré : {meas_ivf:.3f} V, min={min}{unit}, max={max}{unit}", "blue")
    id_skvp_ivf = config.save_value(step_name_id, "IVF_V", meas_ivf, unit, min, max)
    if (meas_ivf < min) or (meas_ivf > max):
        return_msg["infos"].append(f"IVF mesuré à {meas_ivf:.3f} V hors des limites ({min}-{max} {unit}).")
        test_ok = 1
    else:
        config.db.update_by_id("skvp_float", id_skvp_ivf, {"valid": 1})
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_GND_IVE1_IVE2_IVF_2, False)
    
    if test_ok == 0:
        return_msg["infos"].append("Étape OK")
    return test_ok, return_msg


if __name__ == "__main__":
    """Allow to run this script directly for testing purposes."""

    def log_message(message, color):
        print(f"{color}: {message}")

    # Initialize config
    config = configuration.AppConfig()
    config.arg.show_all_logs = False
    config.arg.product_list_id = configuration.PRODUCT_LIST_ID_DEFAULT

    # Initialize Database
    config.db_config = DatabaseConfig(password="root")
    config.db = GenericDatabaseManager(config.db_config, debug=False)
    config.db.connect()
    
    # Launch the initialisation step
    from steps.s01.initialisation import run_step as run_step_init
    success_end, message_end = run_step_init(log_message, config)
    print(message_end)
    
    # Launch this step
    success, message = run_step(log_message, config)
    print(message)

    # Clear ressources
    from steps.zz.fin_du_test import run_step as run_step_fin_du_test
    success_end, message_end = run_step_fin_du_test(log_message, config)
    print(message_end)