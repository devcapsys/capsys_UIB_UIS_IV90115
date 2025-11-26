import os, serial, atexit
from typing import Optional, Any
from modules.capsys_mysql_command.capsys_mysql_command import (GenericDatabaseManager, DatabaseConfig) # Custom
from modules.capsys_wrapper_tm_t20iii.capsys_wrapper_tm_t20III import PrinterDC  # Custom
# from modules.capsys_mac_manager.capsys_mac_manager import MACManager # Custom

# Initialize global variables
CURRENTH_PATH = os.path.dirname(__file__)
NAME_GUI = "UIB 3 en 1, 8E/8S, RS485, Ehernet, 24VDC"
CONFIG_JSON_NAME = "config_SOUU-001"
PRODUCT_LIST_ID_DEFAULT = "5"
VERSION = "V1.0.0"
HASH_GIT = "DEBUG" # Will be replaced by the Git hash when compiled with command .\build.bat
AUTHOR = "Thomas GERARDIN"
PRINTER_NAME = "EPSON TM-T20III Receipt"

def get_project_path(*paths):
    """Return the absolute path from the project root, regardless of current working directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), *paths))

def request_user_input(config, title: str, message: str, font_size: int = 14) -> Optional[str]:
    """
    Request text input from the user.
    
    If running from GUI (main.py), displays a dialog box.
    If running directly (debug mode), uses console input().
    
    Args:
        config: AppConfig instance
        title: Title of the dialog box (GUI mode only)
        message: Message to display to the user
        font_size: Font size for the message (default: 14)
    
    Returns:
        The text entered by the user, or None if cancelled
    """
    import time
    
    user_input_result = {"text": None, "received": False}
    
    def handle_user_input(text):
        user_input_result["text"] = text
        user_input_result["received"] = True
    
    if config.test_thread is not None:
        # GUI mode with dialog box
        config.test_thread.request_user_text_input(title, message, handle_user_input, font_size)
        
        # Wait for user input (without timeout)
        while not user_input_result["received"]:
            time.sleep(0.1)
        
        return user_input_result["text"]
    else:
        # Debug mode with console input
        user_text = input(message + " ")
        return user_text if user_text else None
    
class ConfigItems:
    """Container for all configuration items used in the test sequence."""
    key_map = {
        "STM32CubeProgrammer": "stm32_cube_programmer",
        "MAC_ADRESS_FILE": "mac_adress_file",
        "BTL": "btl",
        "µC": "microcontroller",
        "PORT_COM_DUT": "dut",
    }

    def init_config_items(self, configJson):
        """Initialize configItems attributes from the config JSON mapping pins and keys."""
        key_map = ConfigItems.key_map
        # For each element of config.json, create a corresponding ConfigItem
        for json_key, attr_name in key_map.items():
            item = configJson.get(json_key, {}) # Retrieves the JSON object or {} if absent
            # Create the ConfigItem with all the parameters from the JSON
            setattr(
                self,
                attr_name,
                ConfigItems.ConfigItem(                
                    key=json_key,
                    path=item.get("path", ""),
                    port=item.get("port", ""),
                    name=item.get("name", "")
                )
            )

    class ConfigItem:
        """Represents a single configuration item loaded from config.json or database."""
        def __init__(
            self,
            key = "",
            path = "",
            port = "",
            name = ""
        ):
            """Initialize a ConfigItem with optional parameters for test configuration."""
            self.key = key
            self.path = path
            self.port = port
            self.name = name
    
    def __init__(self):
        """Initialize all ConfigItem attributes for different test parameters."""
        self.stm32_cube_programmer = self.ConfigItem()
        self.mac_adress_file = self.ConfigItem()
        self.btl = self.ConfigItem()
        self.microcontroller = self.ConfigItem()
        self.dut = self.ConfigItem()

class Arg:
    name = NAME_GUI
    version = VERSION
    hash_git = HASH_GIT
    author = AUTHOR
    show_all_logs = False
    operator = AUTHOR
    commande = ""
    of = ""
    article = ""
    indice = ""
    product_list_id = PRODUCT_LIST_ID_DEFAULT
    user = "root"
    password = "root"
    host = "127.0.0.1"
    port = "3306"
    database = "capsys_db_bdt"
    product_list: Optional[dict] = None
    parameters_group: list[str] = []
    external_devices: Optional[list[str]] = None
    script: Optional[str] = None

class AppConfig:
    def __init__(self):
        self.arg = Arg()
        self.test_thread: Any = None  # Reference to TestThread for user input requests
        self.db_config: Optional[DatabaseConfig] = None
        self.db: Optional[GenericDatabaseManager] = None
        self.device_under_test_id: Optional[int] = None
        self.configItems = ConfigItems()
        self.printer: Optional[PrinterDC] = None
        self.ser: Optional[serial.Serial] = None
        atexit.register(self.cleanup) # Register cleanup function to be called on exit

    def cleanup(self):
        if self.db:
            self.db.disconnect()
            self.db = None
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None
        self.device_under_test_id = None
        
    def save_value(self, step_name_id: int, key: str, value, unit: str = "", min_value: Optional[float] = None, max_value: Optional[float] = None, valid: int = 0):
        """Save a key-value pair in the database."""
        if not self.db or not self.device_under_test_id:
            raise ValueError("Database or device under test ID is not initialized.")
        if isinstance(value, float) or isinstance(value, int):
            table = "skvp_float"
            col = "val_float"
            data = {"step_name_id": step_name_id, "key": key, col: value, "unit": unit, "min_configured": min_value, "max_configured": max_value, "valid": valid}
        elif isinstance(value, str):
            table = "skvp_char"
            col = "val_char"
            data = {"step_name_id": step_name_id, "key": key, col: value}
        elif isinstance(value, bytes):
            table = "skvp_file"
            col = "val_file"
            data = {"step_name_id": step_name_id, "key": key, col: value}
        elif isinstance(value, dict):
            table = "skvp_json"
            col = "val_json"
            data = {"step_name_id": step_name_id, "key": key, col: value}
        else:
            raise ValueError("Type de valeur non supporté.")
        id = self.db.create(table, data)
        return id