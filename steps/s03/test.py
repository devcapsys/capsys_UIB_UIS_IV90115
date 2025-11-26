# -*- coding: utf-8 -*-

import sys, os, serial, time
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
    
    msg = configuration.request_user_input(
    config,
    "Teste du DUT",
    "Placer le switch de programmation vers le bas et rallumer le banc."
    )
    if msg is None:
        return_msg["infos"].append("L'utilisateur a annulé la saisie.")
        return 1, return_msg
    
    time.sleep(3)  # Attendre une seconde avant d'ouvrir le port série

    # Ouverture du port série
    if configuration.HASH_GIT == "DEBUG":
        log(f"DEBUG mode: Using COM11 for serial communication.", "yellow")
        port = "COM11"
    else:
        port = config.configItems.dut.port
    try:
        config.ser = serial.Serial(
            port=port,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        log(f"Port série 4 ouvert avec succès", "blue")

        # Envoi de la commande "test\n"
        command = "TEST\n"
        config.ser.write(command.encode('utf-8'))
        log(f"Commande envoyée: {command.strip()}", "blue")
        
        # Lecture de la réponse complète et attente du READY
        response_lines = []
        ready_received = False
        timeout_counter = 0
        max_timeout = 100  # 10 secondes maximum (100 * 0.1s)
        
        while not ready_received and timeout_counter < max_timeout:
            if config.ser.in_waiting > 0:
                line = config.ser.readline().decode('utf-8').strip()
                if line:
                    response_lines.append(line)
                    log(f"Réponse: {line}", "blue")
                    if line == "READY":
                        ready_received = True
            else:
                time.sleep(0.1)
                timeout_counter += 1
        
        # Vérification que READY a été reçu
        if not ready_received:
            return_msg["infos"].append("Erreur: READY non reçu")
            return 1, return_msg
        
        # Vérification que toutes les lignes de test se terminent par "OK"
        # On ignore "TEST EN COURS" qui est juste un message d'information
        test_failed = False
        for line in response_lines:
            # Ignorer les lignes qui ne sont pas des résultats de test
            if line in ["TEST EN COURS", "READY"]:
                continue
            # Vérifier que les lignes de test se terminent par "OK" et PAS par "NOK"
            if line.startswith("TEST"):
                if not line.endswith("OK") or line.endswith("NOK"):
                    return_msg["infos"].append(f"Test échoué: {line}")
                    test_failed = True
        
        if test_failed:
            return 1, return_msg
        
    except serial.SerialException as e:
        return_msg["infos"].append(f"Erreur port série: {e}")
        return 1, return_msg
    

    chaser = configuration.request_user_input(
        config,
        "Vérification du chenillard et des LEDs rouges",
        "Vérifier que :\n" \
        "- Le chenillard est bon (16 LEDs)\n" \
        "- La LED verte à gauche de la carte est allumée\n" \
        "- La LED qui clignote en 3 couleurs juste à côté est allumée\n" \
        "- Les LEDs rouges sont allumées\n" \
        "- La LED verte AT est allumée"
    )
    if chaser is None:
        return_msg["infos"].append("L'utilisateur a annulé la saisie.")
        return 1, return_msg
    
    # TODO Mesure la tension des 3 leds rouges et verte AT pour supprimer le imput
    # TODO Mettre des charges sur les sorties des leds rouges (voit VSE) et mesurer le courant
    
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