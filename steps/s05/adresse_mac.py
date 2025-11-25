# -*- coding: utf-8 -*-

import sys, os, re, time, serial
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

    if config.ser is None or not config.ser.is_open:
        return_msg["infos"].append("Le port série n'est pas ouvert.")
        return 1, return_msg
    
    mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$')
    
    while True:
        mac_address = configuration.request_user_input(
            config,
            "Mac Adresse",
            "À l'aide du fichier C:\\Users\\tgerardin\\CAPSYS\\R&D - Documents\\99 - Divers\\Adresses MAC\\adresses MAC.xlsx, saisir l'adresse MAC du DUT (format: XX:XX:XX:XX:XX:XX) :"
        )
        if mac_address is None:
            return_msg["infos"].append("L'utilisateur a annulé la saisie.")
            return 1, return_msg
        
        # Validation du format de l'adresse MAC
        if mac_pattern.match(mac_address):
            log(f"Adresse MAC saisie : {mac_address}", "blue")
            break
        else:
            log(f"Format d'adresse MAC invalide : {mac_address}. Veuillez utiliser le format XX:XX:XX:XX:XX:XX", "red")

    config.ser.write(f"TEST MAC={mac_address}\r".encode('utf-8'))
    time.sleep(0.5)  # Attendre une demi-seconde pour que le DUT traite la commande
    response = config.ser.readline().decode('utf-8').strip()
    if "OK" not in response:
        return_msg["infos"].append(f"Erreur lors de la configuration de l'adresse MAC sur le DUT.")
        return 1, return_msg

    config.ser.write(f"TEST MAC\r".encode('utf-8'))
    time.sleep(0.5)  # Attendre une demi-seconde pour que le DUT traite la commande
    response = config.ser.readline().decode('utf-8').strip()
    if mac_address not in response:
        return_msg["infos"].append(f"L'adresse MAC lue du DUT ({response}) ne correspond pas à l'adresse configurée ({mac_address}).")
        return 1, return_msg
    else:
        log(f"Adresse MAC {response} vérifiée avec succès sur le DUT.", "blue")

    config.save_value(step_name_id, "mac_address", mac_address, valid=1)

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
        print("Mode DEBUG détecté : utilisation du port COM11 pour le DUT.")
        port = "COM11"
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