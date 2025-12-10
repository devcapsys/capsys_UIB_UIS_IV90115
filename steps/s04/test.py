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

    if config.serDut is None:
        return_msg["infos"].append("Le port série du DUT n'est pas initialisé.")
        return 1, return_msg
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

    # Retry mechanism for serial communication and testing
    max_retries = 3
    retry_count = 0
    test_success = False

    time.sleep(1)  # Small delay before starting the test loop
    
    while not test_success and retry_count < max_retries:        
        if retry_count > 0:
            log(f"Tentative {retry_count + 1}/{max_retries}", "yellow")

        try:
            # Envoi de la commande "TEST"
            command = "TEST"
            answer = config.serDut.send_command_Cr(command, read_until="READY")
            log(f"{command.strip()} envoyé, {answer} reçu", "blue")

            response_lines = answer.strip().splitlines()

            # Vérification que toutes les lignes de test se terminent par "OK"
            # On ignore "TEST EN COURS" qui est juste un message d'information
            test_failed = False
            failed_tests = []
            for line in response_lines:
                # Ignorer les lignes qui ne sont pas des résultats de test
                if line in ["TEST EN COURS", "READY"]:
                    continue
                # Vérifier que les lignes de test se terminent par "OK" et PAS par "NOK"
                if line.startswith("TEST"):
                    if not line.endswith("OK"):
                        failed_tests.append(line)
                        test_failed = True
            
            if test_failed:
                log(f"Tests échoués: {', '.join(failed_tests)}", "red")
                retry_count += 1
                
                if retry_count < max_retries:
                    retry_msg = configuration.request_user_input(
                        config,
                        "Tests échoués",
                        f"Tests échoués: {', '.join(failed_tests)}\nTentative {retry_count}/{max_retries}.\nVoulez-vous réessayer ? (Appuyez sur Entrée pour continuer ou Annuler)"
                    )
                    if retry_msg is None:
                        for test in failed_tests:
                            return_msg["infos"].append(f"Test échoué: {test}")
                        return 1, return_msg
                else:
                    for test in failed_tests:
                        return_msg["infos"].append(f"Test échoué: {test}")
                    return 1, return_msg
            else:
                # Si on arrive ici, le test est réussi
                test_success = True
                
        except serial.SerialException as e:
            log(f"Erreur de communication: {e}", "red")
            retry_count += 1
            
            if retry_count < max_retries:
                retry_msg = configuration.request_user_input(
                    config,
                    "Erreur de communication",
                    f"READY non reçu ou erreur de communication.\nTentative {retry_count}/{max_retries}.\nVoulez-vous réessayer ? (Appuyez sur Entrée pour continuer ou Annuler)"
                )
                if retry_msg is None:
                    return_msg["infos"].append(f"Erreur de communication: {e}")
                    return 1, return_msg
            else:
                return_msg["infos"].append(f"Erreur de communication: {e}")
                return 1, return_msg

    # R1 = 12k ohm, R2 = 5.6k ohm, Vout = Vin * (R2 / (R1 + R2))
    mult = 5.6/(5.6+12)
    min = 23
    max = 25.5
    unit = "V"
    
    # Retry mechanism for AT voltage measurement
    max_retries_at = 3
    retry_count_at = 0
    at_measurement_success = False
    
    while not at_measurement_success and retry_count_at < max_retries_at:
        if retry_count_at > 0:
            log(f"Tentative de mesure AT {retry_count_at + 1}/{max_retries_at}", "yellow")
        
        config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_GND_IVE1_IVE2_IVF_2, True)
        time.sleep(0.2)  # Wait for voltages to stabilize
        meas_at = config.daq_manager.read_a_line(config.daq_port, configuration.DAQPin.M_V_AT.value) / mult
        log(f"AT mesuré : {meas_at:.3f} V, min={min}{unit}, max={max}{unit}", "blue")
        id_skvp_at = config.save_value(step_name_id, "AT_V", meas_at, unit, min, max)
        
        if (meas_at < min) or (meas_at > max):
            config.db.update_by_id("skvp_float", id_skvp_at, {"valid": 0})
            retry_count_at += 1
            
            if retry_count_at < max_retries_at:
                retry_msg = configuration.request_user_input(
                    config,
                    "Mesure AT hors limites",
                    f"AT mesuré à {meas_at:.3f} V hors des limites ({min}-{max} {unit}).\nTentative {retry_count_at}/{max_retries_at}.\nVoulez-vous réessayer ? (Appuyez sur Entrée pour continuer ou Annuler)"
                )
                if retry_msg is None:
                    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_GND_IVE1_IVE2_IVF_2, False)
                    return_msg["infos"].append(f"AT mesuré à {meas_at:.3f} V hors des limites ({min}-{max} {unit}).")
                    return 1, return_msg
            else:
                config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_GND_IVE1_IVE2_IVF_2, False)
                return_msg["infos"].append(f"AT mesuré à {meas_at:.3f} V hors des limites ({min}-{max} {unit}).")
                return 1, return_msg
        else:
            config.db.update_by_id("skvp_float", id_skvp_at, {"valid": 1})
            at_measurement_success = True
    
    config.mcp_manager.digital_write(configuration.MCP23017Pin.EN_GND_IVE1_IVE2_IVF_2, False)   

    chaser = configuration.request_user_input(
        config,
        "Vérification du chenillard et des LEDs rouges",
        "Vérifier que :\n" \
        "- Le chenillard est bon (16 LEDs)\n" \
        "- La LED verte à gauche de la carte est allumée\n" \
        "- La LED qui clignote en 3 couleurs juste à côté est allumée"
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