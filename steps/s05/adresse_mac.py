# -*- coding: utf-8 -*-

import sys, os, re, time, serial, datetime
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
import configuration  # Custom
from modules.capsys_mysql_command.capsys_mysql_command import (GenericDatabaseManager, DatabaseConfig) # Custom
from modules.capsys_mac_manager.capsys_mac_manager import MACManager # Custom

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

    if config.ser is None or not config.ser.is_open:
        return_msg["infos"].append("Le port série n'est pas ouvert.")
        return 1, return_msg
    
    if config.printer_brady is None:
        return_msg["infos"].append("L'imprimante Brady n'est pas initialisée.")
        return 1, return_msg

    mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$')
    
    # Vérification si une adresse MAC existe déjà sur le DUT
    config.ser.write(f"TEST MAC\r".encode('utf-8'))
    time.sleep(1)
    response = config.ser.readline().decode('utf-8').strip()
    
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
    
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    mac_address = ""
    manager = None
    try:
        manager = MACManager(config.configItems.mac_adress_file.path, "attributions MAC address")
        manager.open_file()
        mac_address = manager.assign_mac(
            product=config.arg.article,
            delivery_date=date,
            bl=config.arg.commande
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
    config.ser.write(f"TEST MAC={mac_address['mac_address']}\r".encode('utf-8'))
    time.sleep(1)
    response = config.ser.readline().decode('utf-8').strip()
    if "OK" not in response:
        if manager:
            manager.close()
        return_msg["infos"].append(f"Erreur lors de la configuration de l'adresse MAC sur le DUT.")
        return 1, return_msg

    # Vérification de l'adresse MAC sur le DUT
    config.ser.write(f"TEST MAC\r".encode('utf-8'))
    time.sleep(1)
    response = config.ser.readline().decode('utf-8').strip()
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
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    messages = ["CAPSYS", date, f"ID: {config.device_under_test_id}", config.arg.article + config.arg.indice, configuration.HASH_GIT]
    config.printer_brady.print_label(messages, qrcode=config.device_under_test_id, nb_copies=1)

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

    if configuration.HASH_GIT == "DEBUG":
        print("Mode DEBUG détecté : utilisation du port COM14 pour le DUT.")
        port = "COM14"
    else:
        port = config.configItems.dut.port
    
    config.ser = serial.Serial(
        port=port,
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1
    )

    # Launch this step
    success, message = run_step(log_message, config)
    print(message)

    # Clear ressources
    from steps.zz.fin_du_test import run_step as run_step_fin_du_test
    success_end, message_end = run_step_fin_du_test(log_message, config)
    print(message_end)