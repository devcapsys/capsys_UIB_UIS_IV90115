# -*- coding: utf-8 -*-

import sys, os, subprocess, socket
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
    log("Il faut bien penser à configuer la carte réseau sur l'ip 192.168.1.11", "blue")
    
    # Ping de l'adresse IP du DUT
    dut_ip = "192.168.1.10"
    log(f"Vérification de la connectivité avec {dut_ip}...", "blue")
    
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            log(f"Tentative {attempt}/{max_retries}...", "blue")
            # Tenter une connexion socket pour vérifier la connectivité
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = os.system(f"ping -n 2 {dut_ip} > nul")
            
            sock.close()
            
            if result == 0:
                log(f"Connectivité avec {dut_ip} réussie", "green")
                break
            else:
                if attempt < max_retries:
                    log(f"Tentative {attempt} échouée, nouvelle tentative...", "yellow")
                else:
                    return_msg["infos"].append(f"Échec de la connectivité avec {dut_ip} après {max_retries} tentatives")
                    return 1, return_msg
                
        except Exception as e:
            if attempt < max_retries:
                log(f"Erreur lors de la tentative {attempt}: {str(e)}, nouvelle tentative...", "yellow")
            else:
                return_msg["infos"].append(f"Erreur lors du test de connectivité après {max_retries} tentatives: {str(e)}")
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
    config.arg.product_list_id = configuration.PRODUCT_LIST_ID_DEFAULT

    # Initialize Database
    config.db_config = DatabaseConfig(password="root")
    config.db = GenericDatabaseManager(config.db_config, debug=False)
    config.db.connect()
    
    # Launch the initialisation step
    from steps.s01.initialisation import run_step as run_step_init
    success_end, message_end = run_step_init(log_message, config)
    print(message_end)
    
    # Launch the init_dut step
    from steps.s03.init_dut import run_step as run_step_init_dut
    success_end, message_end = run_step_init_dut(log_message, config)
    print(message_end)
    
    # Launch this step
    success, message = run_step(log_message, config)
    print(message)

    # Clear ressources
    from steps.zz.fin_du_test import run_step as run_step_fin_du_test
    success_end, message_end = run_step_fin_du_test(log_message, config)
    print(message_end)