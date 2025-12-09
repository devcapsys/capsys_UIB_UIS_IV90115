# -*- coding: utf-8 -*-

import sys, os, re, time, datetime, json
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
import configuration  # Custom
from modules.capsys_mysql_command.capsys_mysql_command import (GenericDatabaseManager, DatabaseConfig) # Custom
from modules.capsys_mac_manager.capsys_mac_manager import MACManager # Custom
from modules.capsys_brady_manager.capsys_brady_manager import BradyBP12Printer  # Custom

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

    if config.serDut is None or not config.serDut.is_connected():
        return_msg["infos"].append("Le port série n'est pas ouvert.")
        return 1, return_msg

    mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$')
    
    config.serDut.send_command("TEST MAC\r", timeout=1.0) # Initial flush
    # Vérification si une adresse MAC existe déjà sur le DUT
    response = config.serDut.send_command("TEST MAC\r", timeout=1.0)
    
    # Si une adresse MAC valide existe déjà, on l'utilise
    existing_mac = None
    for part in response.split():
        if mac_pattern.match(part):
            existing_mac = part
            break
    
    if existing_mac:
        log(f"Adresse MAC existante détectée sur le DUT : {existing_mac}", "blue")
        config.save_value(step_name_id, "mac_address", existing_mac, valid=1)
        return_msg["infos"].append("Étape OK - Adresse MAC existante utilisée")
        return 0, return_msg
    
    log("Aucune adresse MAC détectée sur le DUT, assignation d'une nouvelle adresse.", "blue")
    
    path = config.configItems.mac_adress_file.path
    mac_address = ""
    manager = None
    product= ""
    date = ""
    bl = ""
    if configuration.HASH_GIT == "DEBUG":
        path = "C:\\Users\\tgerardin\\CAPSYS\\INDUSTRIE - Documents\\PROD\\Adresses MAC\\adresses MAC.xlsx"
        log(f"DEBUG MODE: Using MAC address file at {path} without assigning new MAC in the file", "yellow")
    else:
        product = config.arg.article
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        bl = config.arg.commande
    try:
        manager = MACManager(path, "attributions MAC address")
        manager.open_file()
        mac_address = manager.assign_mac(
            product=product,
            delivery_date=date,
            bl=bl
        )
        print(f"Assignment successful!")
    except Exception as e:
        print(f"Error: {e}")
        if manager:
            manager.close()
        return_msg["infos"].append(f"Erreur lors de l'assignation de l'adresse MAC: {e}")
        return 1, return_msg
    
    if mac_address != "":
        if not mac_pattern.match(mac_address['mac_address']):
            if manager:
                manager.close()
            return_msg["infos"].append(f"L'adresse MAC assignée ({mac_address['mac_address']}) ne correspond pas au format attendu.")
            return 1, return_msg
        else:
            log(f"MAC adresse : {mac_address['mac_address']} ligne {mac_address['row']}", "blue")
    else:
        if manager:
            manager.close()
        return_msg["infos"].append("Aucune adresse MAC n'a pu être assignée.")
        return 1, return_msg
    
    # Configuration de l'adresse MAC sur le DUT
    response = config.serDut.send_command_Cr(f"TEST MAC={mac_address['mac_address']}", timeout=1.0)
    if "OK" not in response:
        if manager:
            manager.close()
        return_msg["infos"].append(f"Erreur lors de la configuration de l'adresse MAC sur le DUT.")
        return 1, return_msg

    # Vérification de l'adresse MAC sur le DUT
    response = config.serDut.send_command("TEST MAC\r", timeout=1.0)
    if mac_address['mac_address'] not in response:
        if manager:
            manager.close()
        return_msg["infos"].append(f"L'adresse MAC lue du DUT ({response}) ne correspond pas à l'adresse configurée ({mac_address['mac_address']}).")
        return 1, return_msg
    else:
        log(f"Adresse MAC {response} vérifiée avec succès sur le DUT.", "blue")
    
    # Sauvegarder dans Excel seulement après vérification réussie
    try:
        manager.save()
        manager.close()
    except Exception as e:
        if manager:
            manager.close()
        return_msg["infos"].append(f"Erreur lors de la sauvegarde de l'adresse MAC dans Excel: {e}")
        return 1, return_msg

    config.save_value(step_name_id, "mac_address_line", mac_address['row'], valid=1)
    config.save_value(step_name_id, "mac_address", mac_address['mac_address'], valid=1)
    
    # Print label with Brady printer
    # printer_brady = BradyBP12Printer()
    # date = datetime.datetime.now().strftime("%Y-%m-%d")
    # messages = ["CAPSYS", date, f"ID: {config.device_under_test_id}", config.arg.article + config.arg.indice, configuration.HASH_GIT]
    # printer_brady.print_label(messages, qrcode=config.device_under_test_id, nb_copies=1)
    # jsonMessages = json.dumps(messages, ensure_ascii=False)
    # config.save_value(step_name_id, "label_printed", jsonMessages, valid=1)

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