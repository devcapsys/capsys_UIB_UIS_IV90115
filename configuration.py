import os, atexit
from enum import Enum
from typing import Optional, Any
from modules.capsys_mysql_command.capsys_mysql_command import (GenericDatabaseManager, DatabaseConfig) # Custom
from modules.capsys_wrapper_tm_t20iii.capsys_wrapper_tm_t20III import PrinterDC  # Custom
from modules.capsys_daq_manager.capsys_daq_manager import DAQManager  # Custom
from modules.capsys_mcp23017.capsys_mcp23017 import MCP23017, MCP23017Manager  # Custom
from modules.capsys_serial_instrument_manager.capsys_serial_instrument_manager import SerialInstrumentManager  # Custom
from modules.capsys_brady_manager.capsys_brady_manager import BradyBP12Printer  # Custom

# Initialize global variables
CURRENT_PATH = os.path.dirname(__file__)
NAME_GUI = "UIB 3 en 1 8E8S RS485 Ehernet 24VDC"
CONFIG_JSON_NAME = "config_IV90115"
PRODUCT_LIST_ID_DEFAULT = "6"
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

class SerialUsbDut(SerialInstrumentManager):
    def __init__(self, port=None, baudrate=115200, timeout=1, debug=False):
        SerialInstrumentManager.__init__(self, port, baudrate, timeout, debug)
        self._debug_log("DUT initialized")

    def get_valid(self, sn=None) -> bool:
        # TODO
        return True
    
    def send_command_Cr(self, command: str, expected_response: str = "", exact_match: bool = False, timeout: float = 0, read_until: str = "") -> str:
        return super().send_command(command + "\n", expected_response, exact_match, timeout, read_until)
    
class DAQPin(Enum):
    """
    Enumerates DAQ USB 6000 pin assignments for various signals and measurements.
    https://www.ni.com/fr-fr/shop/model/usb-6000.html
    """
    I2C_SCL = "port0/line0"  # SCL (clock) – yellow wire
    I2C_SDA_OUT = "port0/line1"  # SDA output – blue wire
    I2C_SDA_IN = "port0/line2"  # SDA input – blue wire - read for ACK
    P03 = "port0/line3"  # Not used
    AI0 = "ai0"  # Not used
    AI1 = "ai1"  # Not used
    AI2 = "ai2"  # Not used
    AI3 = "ai3"  # Not used
    M_V_AT = "ai4"
    M_V_IVE2 = "ai5"
    M_V_IVF = "ai6"
    M_V_IVE1 = "ai7"

class MCP23017Pin(Enum):
    """
    Enumerates MCP23017 I2C GPIO expander pin assignments for power and control signals.
    https://www.adafruit.com/product/5346
    Used with RL40004-24 Numato Lab.
    https://numato.com/product/8-channel-relay-controller-board/
    """
    EN_AUTOMATIC_24V = (0x20, MCP23017.Pin.B0, 'out')  # Pin A0 Relay 0
    EN_24V = (0x20, MCP23017.Pin.B1, 'out')  # Pin A1 Relay 1
    EN_AUTOMATIC_BTL = (0x20, MCP23017.Pin.B2, 'out')  # Pin A2 Relay 2
    EN_BTL = (0x20, MCP23017.Pin.B3, 'out')  # Pin A3 Relay 3
    B4 = (0x20, MCP23017.Pin.B4, 'out')  # Pin B4 Relay 4 not used
    EN_VCC_USB = (0x20, MCP23017.Pin.B5, 'out')  # Pin B5 Relay 5 Vcc USB
    EN_GND_IVE1_IVE2_IVF_2 = (0x20, MCP23017.Pin.B6, 'out')  # Pin B6 Relay 6
    EN_AUTOMATIC_GND_IVE1_IVE2_IVF = (0x20, MCP23017.Pin.B7, 'out')  # Pin B7 Relay 7

    def __init__(self, mcp_addr, pin, mode):
        self.mcp_addr = mcp_addr
        self.pin = pin
        self.mode = mode

class ConfigItems:
    """Container for all configuration items used in the test sequence."""
    key_map = {
        "STM32CubeProgrammer": "stm32_cube_programmer",
        "MAC_ADRESS_FILE": "mac_adress_file",
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
    product_list_id = ""
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
        self.first_test = True
        self.µc_path: Optional[str] = None
        self.daq_port: Optional[str] = None
        self.daq_manager: Optional[DAQManager] = None
        self.mcp_manager: Optional[MCP23017Manager] = None
        self.serDut: Optional[SerialUsbDut] = None
        self.printer: Optional[PrinterDC] = None
        self.brady_printer: Optional[BradyBP12Printer] = None
        atexit.register(self.cleanup) # Register cleanup function to be called on exit

    def cleanup(self):
        if self.db:
            self.db.disconnect()
            self.db = None
        if self.mcp_manager:
            for pin in MCP23017Pin:
                self.mcp_manager.digital_write(pin, False)
            self.mcp_manager = None
        if self.daq_manager:
            self.daq_manager.close_all()
            self.daq_manager = None
        if self.serDut and self.serDut.is_connected():
            self.serDut.close()
            self.serDut = None
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