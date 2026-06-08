import logging
import time
import os
import sys
import signal
import threading
from PyQt6.QtWidgets import QApplication

from utils.config_loader import ConfigLoader
from clients.c2sim_client import C2SIMClient
from clients.sita_client import SitaClient
from Parser import Parser
from utils.logger import setup_logger
import gui

# Global flag for running state
running = True

def signal_handler(sig, frame):
    """Handle signals to gracefully shut down the application"""
    logging.info("Received shutdown signal, stopping application...")
    global running
    running = False

class GatewayController:
    """
    Controller class that connects the GUI with the C2SIM and SitaWare clients
    """
    def __init__(self, window, signals):
        self.window = window
        self.signals = signals #TODO migrate to just logger
        self.c2sim_client = None
        self.sita_client = None
        self.parser = None
        self.running = False
        self.thread = None
        self.units = []
        self.symbols = []
        
        # Set up a thread-safe queue for log messages
        self.log_queue = []
        self.log_lock = threading.Lock()
        
        # Connect signals from GUI
        self.window.start_gateway.connect(self.start_gateway)
    
    def start_gateway(self, config):
        """Start the gateway with the given configuration"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self.run_gateway, args=(config,))
        self.thread.daemon = True
        self.thread.start()
    
    def stop_gateway(self):
        """Stop the gateway"""
        if not self.running:
            return
            
        self.running = False
        
        # Stop clients if they exist
        if self.c2sim_client:
            self.c2sim_client.stop()
        
        if self.sita_client:
            self.sita_client.stop()
        
        # Wait for thread to end
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        
        self.signals.finished.emit()
    
    def run_gateway(self, config):
        """Main gateway operation - runs in a separate thread"""
        try:
            # Setup logging
            logging_config = config.get('logging', {})
            log_file = logging_config.get('log_file', 'sw_c2sim_gw.log')
            log_level = logging_config.get('log_level', 'INFO')
            
            setup_logger(log_file=log_file, log_level=log_level)
            logger = logging.getLogger(__name__)
            
            # Log startup
            logger.info("============= SitaWare-C2SIM Gateway =============")
            logger.info("Gateway starting with configuration")
            
            # Create the parser
            self.signals.update_processing_status.emit("Initializing parser...")
            translation_config = config.get('translation', {})
            self.parser = Parser(translation_config)
            
            # Create the SitaWare client
            sita_cfg = config.get('sitaware_server', {})
            self.signals.update_processing_status.emit(f"Connecting to SitaWare at {sita_cfg.get('host')}:{sita_cfg.get('api_port')}")
            logger.info(f"Connecting to SitaWare server at {sita_cfg.get('host')}:{sita_cfg.get('api_port')}")
            self.sita_client = SitaClient(sita_cfg, self.parser)
            
            # Create the C2SIM client
            c2sim_cfg = config.get('c2sim_server', {})
            self.signals.update_processing_status.emit(f"Connecting to C2SIM at {c2sim_cfg.get('host')}:{c2sim_cfg.get('rest_port')}")
            logger.info(f"Connecting to C2SIM server at {c2sim_cfg.get('host')}:{c2sim_cfg.get('rest_port')}")
            self.c2sim_client = C2SIMClient(c2sim_cfg, self.parser)
            
            # Connect the clients
            self.c2sim_client.set_sita_client(self.sita_client)
            self.sita_client.set_c2sim_client(self.c2sim_client)
            
            # Test C2SIM connection
            self.signals.update_processing_status.emit("Testing C2SIM server connection...")
            status = self.c2sim_client.get_server_status()
            if status:
                self.signals.c2sim_rest_connected.emit(True)
                self.signals.c2sim_server_status.emit(status)
                logger.info(f"C2SIM server status: {status}")
                
                if "RUNNING" in status:
                    logger.info("C2SIM server is RUNNING")
                else:
                    logger.warning(f"C2SIM server is not RUNNING (status: {status})")
                    
                    # Check if we should auto-start the server
                    if config.get("auto_start_c2sim", False):
                        logger.info("Attempting to start C2SIM server...")
                        self.signals.update_processing_status.emit("Auto-starting C2SIM server...")
                        
                        # If in INITIALIZED state, just START
                        if "INITIALIZED" in status:
                            self.c2sim_client.send_command("START")
                        # If in INITIALIZING state, SHARE then START
                        elif "INITIALIZING" in status:
                            self.c2sim_client.send_command("SHARE")
                            time.sleep(1)
                            self.c2sim_client.send_command("START")
            else:
                self.signals.c2sim_rest_connected.emit(False)
                logger.error("Failed to get C2SIM server status")
                self.signals.error.emit("Failed to connect to C2SIM server")
                return
            
            # Initialize the map by querying initialization data
            logger.info("Querying C2SIM initialization data")
            self.signals.update_processing_status.emit("Querying initialization data...")
            
            # Make multiple attempts to get initialization data
            init_attempts = 0
            max_attempts = 3
            init_xml = None
            
            while init_attempts < max_attempts and not init_xml and self.running:
                init_xml = self.c2sim_client.query_init()
                if not init_xml:
                    init_attempts += 1
                    logger.warning(f"Failed to get initialization data (attempt {init_attempts}/{max_attempts})")
                    self.signals.update_processing_status.emit(f"Initialization attempt {init_attempts}/{max_attempts}")
                    time.sleep(2)
            
            if init_xml:
                self.signals.initialization_received.emit(True)
                logger.info("Successfully retrieved initialization data from C2SIM server")
                self.signals.update_processing_status.emit("Initialization data received")
                
                # Test SitaWare connectivity
                logger.info("Testing SitaWare connectivity...")
                self.signals.update_processing_status.emit("Testing SitaWare connectivity...")
                connected = self.sita_client.test_connection()
                if connected:
                    self.signals.sitaware_connected.emit(True)
                    logger.info("Connected to SitaWare server")
                else:
                    self.signals.sitaware_connected.emit(False)
                    logger.error("Failed to connect to SitaWare, check host/credentials")
                    self.signals.error.emit("Failed to connect to SitaWare server")
                    return
            
                # Find a valid layer for adding units
                logger.info("Finding a valid SitaWare layer...")
                self.signals.update_processing_status.emit("Finding valid SitaWare layer...")
                valid_layer = self.sita_client.find_valid_layer()
                if not valid_layer:
                    logger.error("No valid SitaWare layer found, check layer configuration")
                    self.signals.error.emit("No valid SitaWare layer found")
                    return
                logger.info(f"Using SitaWare layer: {valid_layer['name']} (ID: {valid_layer['id']})")
                self.signals.update_processing_status.emit(f"Using SitaWare layer: {valid_layer['name']}")
            
                # Parse the initialization data
                self.signals.update_processing_status.emit("Parsing initialization data...")
                self.units = self.parser.parse_initialization_xml(init_xml)
                total_units = len(self.units)
                
                logger.info(f"Parsed {total_units} units from initialization data")
                
                # Convert to SitaWare symbols
                self.signals.update_processing_status.emit("Converting units to SitaWare symbols...")
                self.symbols = self.parser.c2sim_init_to_sitaware_symbols(self.units)
                logger.info(f"Created {len(self.symbols)} SitaWare symbols")
                
                # Initialize the state in the C2SIM client
                self.signals.update_processing_status.emit("Adding units to C2SIM state...")
                for i, (unit, symbol) in enumerate(zip(self.units, self.symbols)):
                    if not self.running:
                        return
                    self.c2sim_client.add_unit(unit['name'], unit['uuid'], symbol)
                    logger.info(f"Added unit to state: {unit['name']} ({i+1}/{len(self.units)})")
                    self.signals.update_processing_count.emit(i+1, len(self.units))
                
                # Clear the SitaWare layer first
                logger.info(f"Clearing SitaWare layer...")
                self.signals.update_processing_status.emit("Clearing SitaWare layer...")
                # Clear the processing count while clearing layer
                self.signals.clear_processing_count.emit()
                clear_result = self.sita_client.clear_layer()
                logger.info(f"Layer cleared: {clear_result}")
            
                # Try to add each unit to SitaWare
                self.signals.update_processing_status.emit("Adding units to SitaWare...")
                success_count = 0
                for i, symbol in enumerate(self.symbols):
                    if not self.running:
                        return
                    unit_name = symbol['properties']['c2Attributes']['name']
                    logger.info(f"Sending unit {i+1}/{len(self.symbols)}: {unit_name}")
                    
                    # Update status to show current unit
                    self.signals.update_processing_count.emit(i+1, len(self.symbols))
                    
                    # Update symbol to use the valid layer
                    symbol['layerId'] = valid_layer['id']
                    
                    result = self.sita_client.add_unit(symbol)
                    if result:
                        success_count += 1
                        logger.info(f"Successfully added unit to SitaWare: {unit_name}")
                    else:
                        logger.warning(f"Failed to add unit to SitaWare: {unit_name}")
                
                logger.info(f"Added {success_count}/{len(self.symbols)} units to SitaWare")
                self.signals.update_processing_status.emit(f"Added {success_count}/{len(self.symbols)} units to SitaWare")
            else:
                self.signals.initialization_received.emit(False)
                logger.error("Failed to get initialization data from C2SIM server")
                self.signals.error.emit("Failed to get initialization data from C2SIM server")
                return
            
            # Start the client threads
            logger.info("Starting client threads...")
            self.signals.update_processing_status.emit("Starting client threads...")
            
            self.c2sim_client.start()
            self.sita_client.start()
            self.signals.c2sim_stomp_connected.emit(True)
            
            # Main loop - keep running until stop is requested
            logger.info("Gateway running - monitoring for messages")
            self.signals.update_processing_status.emit("Gateway running - monitoring for messages")
            # Clear the processing count when we enter monitoring mode
            self.signals.clear_processing_count.emit()
            
            while self.running:
                # Check connection status
                if self.c2sim_client and not self.c2sim_client.is_connected():
                    self.signals.c2sim_stomp_connected.emit(False)
                    logger.warning("C2SIM STOMP connection lost")
                else:
                    self.signals.c2sim_stomp_connected.emit(True)
                
                # Sleep to prevent CPU hogging
                time.sleep(1)
            
            # Cleanup
            logger.info("Gateway stopping...")
            self.signals.update_processing_status.emit("Gateway stopping...")
            
            if self.c2sim_client:
                self.c2sim_client.stop()
            
            if self.sita_client:
                self.sita_client.stop()
            
            # Signal completion
            self.signals.finished.emit()
            logger.info("Gateway stopped")
            
        except Exception as e:
            logger.error(f"Error in gateway operation: {e}", exc_info=True)
            self.signals.error.emit(f"Error in gateway operation: {str(e)}")
        finally:
            self.running = False
    
    def setup_client_signals(self):
        """
        Connect client signals with GUI signals 
        """
        # This would be implemented to connect client events to GUI signals
        pass

def main():
    global running
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Find configuration file path
    config_path = ConfigLoader.find_config_file() or 'config.yaml'
    
    setup_logger(log_file="sw_c2sim_gw_startup.log", log_level="INFO")
    logger = logging.getLogger(__name__)
    logger.info("============= Starting SitaWare-C2SIM Gateway =============")
    
    # Create application instance
    app = QApplication(sys.argv)
    
    # Start the GUI (the gui module handles configuration loading)
    window, runner = gui.start_gateway_gui(config_path)
    
    # Create the controller that connects the GUI with the gateway
    controller = GatewayController(window, window.signals)
    
    # Set up a method to handle the 'Stop Gateway' button
    def handle_stop_gateway():
        controller.stop_gateway()
    
    # Connect the stop gateway button to our controller's stop method
    try:
        window.stop_btn.clicked.disconnect()  # Disconnect any previous connections
    except:
        pass  # Ignore if there was nothing to disconnect
    window.stop_btn.clicked.connect(handle_stop_gateway)
    
    # Set up a callback for window closing to stop the gateway
    def on_close_event(event):
        if controller.running:
            controller.stop_gateway()
        event.accept()
        
    # Override the window's closeEvent method
    window.closeEvent = on_close_event
    
    # Start the event loop
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())