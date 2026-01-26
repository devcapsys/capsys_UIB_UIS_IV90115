# -*- coding: utf-8 -*-

import sys, os, subprocess, time
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
import configuration  # Custom
from modules.capsys_mysql_command.capsys_mysql_command import (GenericDatabaseManager, DatabaseConfig) # Custom

def get_info():
    return "Cette étape vient programmer le DUT."

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
    if not hasattr(config, "mcp_manager") or config.mcp_manager is None:
        return_msg["infos"].append("Le gestionnaire MCP n'est pas initialisé.")
        return 1, return_msg
    
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_24V, False)
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_BTL, True)
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_AUTOMATIC_BTL, True)
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_AUTOMATIC_24V, True)
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_24V, True)
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_VCC_USB, True)
    time.sleep(1)

    # If debug, skip programming
    # TODO
    if (configuration.HASH_GIT == "DEBUGG"):
        log("Mode DEBUG détecté, la programmation est désactivée.", "yellow")
        return 0, return_msg
    else:
        path_soft = config.µc_path
        binaries = [
            {"path": path_soft, "log_key": "Application"},
        ]
        # Paths STM32CubeProgrammer
        path_stm32 = config.configItems.stm32_cube_programmer.path
        programmer_dir = getattr(config, 'stm32_programmer_dir', path_stm32)
        programmer_cli = os.path.join(programmer_dir, "STM32_Programmer_CLI.exe")
        if not os.path.exists(programmer_cli):
            return 1, f"STM32CubeProgrammer not found at {programmer_cli}."
        
        total_binaries = len(binaries)
        for idx, binary in enumerate(binaries):
            percentage = int((idx / total_binaries) * 100)
            update_percentage(percentage)
            if not os.path.exists(binary["path"]):
                return 1, f"File not found: {binary['path']}"
            
            cmd = [
                programmer_cli,
                "-c", f"port=usb1",
                "-w", binary["path"]
            ]
            log(f"Commande subprocess: {' '.join(cmd)}", "blue")
            
            result = subprocess.run(
                cmd,
                check=False,
                # stdout=subprocess.DEVNULL,
                # stderr=subprocess.DEVNULL,
            )
            msg = f"Programmation de {binary['path']} - returncode={result.returncode}"
            log(msg, "blue")
            config.db.create(
                "skvp_char", {
                    "step_name_id": step_name_id,
                    "val_char": msg
                }
            )
            if result.returncode != 0:
                return_msg["infos"].append(f"Code de retour : {result.returncode}")
                return_msg["infos"].append(f"Pensez à vérifier l'état du port COM et le câblage.")
                return 1, return_msg
        
        time.sleep(1)
        config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_VCC_USB, False)
        config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_24V, False)
        config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_BTL, False)
        config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_AUTOMATIC_BTL, True)
        config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_AUTOMATIC_24V, True)
        time.sleep(1)

        return_msg["infos"].append("Étape OK")
        return 0, return_msg


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