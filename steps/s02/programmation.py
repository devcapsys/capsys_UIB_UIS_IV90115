# -*- coding: utf-8 -*-

import sys, os, subprocess, binascii
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
import configuration  # Custom
from modules.capsys_mysql_command.capsys_mysql_command import (GenericDatabaseManager, DatabaseConfig) # Custom

def get_info():
    return "Cette étape vient programmer le DUT."

# def compute_file_crc32(path):
#     """Compute CRC32 of a binary file."""
#     with open(path, "rb") as f:
#         data = f.read()
#     return binascii.crc32(data) & 0xFFFFFFFF


# def read_mcu_crc32(programmer_cli, port, address, size):
#     """Read CRC32 from MCU memory using STM32_Programmer_CLI."""
#     cmd = [
#         programmer_cli,
#         "-c", f"port={port}",
#         "-crc32", hex(address), hex(size)
#     ]
#     print(f"Executing command: {' '.join(cmd)}")
#     result = subprocess.run(cmd, capture_output=True, text=True)

#     if result.returncode != 0:
#         return None

#     for line in result.stdout.splitlines():
#         if "CRC32" in line.upper():
#             try:
#                 return int(line.split(":")[1].strip(), 16)
#             except:
#                 return None

#     return None

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

    # If debug, skip programming
    if (configuration.HASH_GIT == "DEBUGG"):
        log("Mode DEBUG détecté, la programmation est désactivée.", "yellow")
        return 0, return_msg
    else:
        if configuration.HASH_GIT == "DEBUG":
            log(f"DEBUG mode: Using COM11.", "yellow")
            port = "COM11"
        else:
            port = config.configItems.dut.port
        path_btl = config.configItems.btl.path
        path_soft = config.configItems.microcontroller.path
            
        binaries = [
            {"path": path_btl, "log_key": "Bootloader"},
            {"path": path_soft, "log_key": "Application"},
        ]
        # Paths STM32CubeProgrammer
        path_stm32 = config.configItems.stm32_cube_programmer.path
        programmer_dir = getattr(config, 'stm32_programmer_dir', path_stm32)
        programmer_cli = os.path.join(programmer_dir, "STM32_Programmer_CLI.exe")
        if not os.path.exists(programmer_cli):
            return 1, f"STM32CubeProgrammer not found at {programmer_cli}."
        
        msg = configuration.request_user_input(
            config,
            "Programmation",
            "Est-ce que la programmation a déjà été effectuée ?\n" \
            "- Si OUI, écrivez oui puis appuyer sur entrée\n" \
            "- Si NON, appuyer sur OK"
        )
        if msg is None:
            return_msg["infos"].append("L'utilisateur a annulé la saisie.")
            return 1, return_msg
        if msg.lower() == "oui":
            log("Programmation déjà effectuée, étape sautée.", "yellow")
            return_msg["infos"].append("Programmation déjà effectuée, étape sautée.")
            return 0, return_msg

        # # -----------------------------------------------------------------------
        # #     CRC CHECK BEFORE PROGRAMMING APPLICATION
        # # -----------------------------------------------------------------------

        # # Application Flash address (to adapt if needed)
        # APP_ADDRESS = 0x08004000     
        # app_size = os.path.getsize(path_soft)

        # log("Calcul du CRC local de l'application…", "blue")
        # local_crc = compute_file_crc32(path_soft)
        # log(f"CRC local = 0x{local_crc:08X}", "blue")

        # log("Lecture du CRC dans le MCU…", "blue")
        # mcu_crc = read_mcu_crc32(programmer_cli, port, APP_ADDRESS, app_size)

        # if mcu_crc is None:
        #     log("Impossible de lire le CRC dans le MCU → Programmation nécessaire.", "yellow")
        # else:
        #     log(f"CRC MCU = 0x{mcu_crc:08X}", "blue")

        #     if mcu_crc == local_crc:
        #         log("CRC identique → pas de programmation de l'application.", "green")
        #         return_msg["infos"].append("CRC identique → application non programmée")
        #         # We still ask user to switch off programming mode
        #         prog_end = configuration.request_user_input(
        #             config,
        #             "Fin de programmation du DUT",
        #             "Placer le switch de programmation vers le bas et rallumer le banc."
        #         )
        #         return 0, return_msg

        #     else:
        #         log("CRC différent → programmation nécessaire.", "yellow")

        # # -----------------------------------------------------------------------
        # #     PROGRAMMATION (Bootloader + Application)
        # # -----------------------------------------------------------------------

        total_binaries = len(binaries)
        for idx, binary in enumerate(binaries):
            percentage = int((idx / total_binaries) * 100)
            update_percentage(percentage)
            if not os.path.exists(binary["path"]):
                return 1, f"File not found: {binary['path']}"
            
            cmd = [
                programmer_cli,
                "-c", f"port={port}",
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
                return 1, f"Error programming file: {binary['path']}"
        
        prog_end = configuration.request_user_input(
        config,
        "Fin de programmation du DUT",
        "Placer le switch de programmation vers le bas et rallumer le banc."
        )
        if prog_end is None:
            return_msg["infos"].append("L'utilisateur a annulé la saisie.")
            return 1, return_msg

        return_msg["infos"].append("Étape OK")
        return 0, return_msg


if __name__ == "__main__":
    """Allow to run this script directly for testing purposes."""

    def log_message(message, color):
        print(f"{color}: {message}")

    # Initialize config
    config = configuration.AppConfig()
    config.arg.show_all_logs = False

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