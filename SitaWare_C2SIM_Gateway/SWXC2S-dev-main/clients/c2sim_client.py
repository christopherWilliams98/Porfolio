import logging
import time
import threading
import queue
import requests
import stomp
import uuid
import xml.etree.ElementTree as ET
from typing import Dict, Any, Callable, Optional, List

class C2SIMListener(stomp.ConnectionListener):
    """
    Listener for STOMP messages from the C2SIM server.
    """
    def __init__(self, callback):
        self.callback = callback
        self.logger = logging.getLogger(__name__)
        
    def on_error(self, frame):
        self.logger.error(f"STOMP error: {frame.body}")
        
    def on_message(self, frame):
        self.callback(frame)
        
    def on_disconnected(self):
        self.logger.warning("STOMP connection disconnected")


class C2SIMClient(threading.Thread):
    """
    Client for interacting with the C2SIM server via REST and STOMP.
    Integrated with state management and messaging functionality.
    """
    def __init__(self, config, parser):
        threading.Thread.__init__(self)
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.parser = parser
        self.daemon = True
        
        # Extract configuration values
        self.host = config.get('host', 'localhost')
        self.rest_port = config.get('rest_port', 8080)
        self.stomp_port = config.get('stomp_port', 61613)
        self.topic = config.get('topic', '/topic/C2SIM')
        self.submitter_id = config.get('submitter_id', 'SWC2SGW')
        self.password = config.get('password', '')
        self.version = config.get('version', "4.8.4.9")
        
        # OIDP Authentication configuration
        self.use_oidp = config.get('use_oidp', False)
        self.oidp_client = 'CHE-SW'
        
        # Initialize OIDP client if authentication is enabled
        if self.use_oidp:
            self.logger.info("OIDP authentication enabled")
            oidp_config = config.get('oidp', {})
            
            if 'port' not in oidp_config:
                oidp_config['port'] = 30104  
            if 'client_id' not in oidp_config:
                oidp_config['client_id'] = 'CWIX' 
            
            self.oidp_client = OIDPClient(oidp_config)
            
            # Try to get token
            self.jwt_token = self.oidp_client.get_token()
            
            if not self.jwt_token:
                self.logger.warning("Failed to get OIDP token - will attempt requests without authentication")
                # We'll still try requests without the token
        
        # Base URLs for REST
        self.base_rest_url = f"http://{self.host}:{self.rest_port}/C2SIMServer"
        
        # STOMP connection
        self.stomp_conn = None
        self.conn_id = 1
        self._connected = False
        self.retry_wait = 2
        self.max_retry_wait = 60
        
        # Message queues
        self.incoming_queue = queue.Queue()  #NOTE THIS SHOULD ALWAYS BE EMPTY
        self.outgoing_queue = queue.Queue()  # Messages from C2SIM to SitaWare
        
        # State management
        self.name_to_symbol = {}  # Maps unit name to SitaWare symbol JSON
        self.name_to_uuid = {}    # Maps unit name to UUID
        self.uuid_to_name = {}    # Maps UUID to unit name
        
        # Control flag for thread
        self.running = True
        
        # Reference to SitaWare client (set later)
        self.sita_client = None

    def set_sita_client(self, sita_client):
        """Set reference to SitaWare client for message passing"""
        self.sita_client = sita_client
        
    def run(self):
        """Main thread method that processes messages and maintains connection"""
        self.logger.info("C2SIM client thread starting...")
        
        try:
            # Connect to STOMP server
            self.connect_and_subscribe(self.on_message_received)
            
            while self.running:
                # Check connection status and reconnect if needed
                if not self.is_connected():
                    self.logger.warning("STOMP connection lost. Attempting to reconnect...")
                    connected = self.connect_and_subscribe(self.on_message_received)
                    if connected:
                        self.logger.info("Reconnected to STOMP server")
                    else:
                        self.logger.error("Failed to reconnect to STOMP server")
                
                # Process any pending outgoing messages
                try:
                    # Non-blocking to allow connection checking
                    msg = self.incoming_queue.get(block=False)
                    self.process_outgoing_message(msg)
                    self.incoming_queue.task_done()
                except queue.Empty:
                    # No messages
                    pass
                
                # don't spam CPU
                time.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"Error in C2SIM client thread: {e}")
        finally:
            self.logger.info("C2SIM client thread stopping...")
            if self.is_connected():
                self.disconnect()
    
    def stop(self):
        """Signal the thread to stop"""
        self.running = False
    
    def is_connected(self) -> bool:
        """Check if the STOMP connection is active"""
        return self._connected and self.stomp_conn and self.stomp_conn.is_connected()
    
    def enqueue_message(self, message):
        """Add a message to the incoming queue (from SitaWare to C2SIM)"""
        self.incoming_queue.put(message)
        self.logger.debug("Message added to C2SIM incoming queue")
    
    def connect_and_subscribe(self, callback: Callable) -> bool:
        """Connect to the STOMP server and subscribe to the topic."""
        if self.is_connected():
            self.logger.info("Already connected to S" \
            "TOMP server")
            return True
            
        try:
            # Basic connection. 
            self.stomp_conn = stomp.Connection(
                [(self.host, self.stomp_port)],
                heartbeats=(10_000, 10_000),
                auto_decode=False
            )
            
            # Set up listeners
            listener = C2SIMListener(callback)
            self.stomp_conn.set_listener('', listener)
        
            # Connect without specifying host in headers
            self.logger.info(f"Connecting to STOMP server at {self.host}:{self.stomp_port}")
            self.stomp_conn.connect(wait=True)
            
            # Subscribe using message selector
            self.logger.info(f"Subscribing to {self.topic}")
            self.stomp_conn.subscribe(
                destination=self.topic,
                id=f"C2SIM_Sub_{self.conn_id}",
                ack='auto',
                headers={'selector': "protocol = 'SISO-STD-020-2020'"}
            )
            
            self._connected = True
            self.logger.info("Successfully connected to STOMP server")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to STOMP server: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from the STOMP server"""
        if self.stomp_conn and self._connected:
            try:
                self.stomp_conn.disconnect()
                self.logger.info("Disconnected from STOMP server")
            except Exception as e:
                self.logger.error(f"Error disconnecting from STOMP server: {e}")
            finally:
                self._connected = False

    def get_server_status(self) -> Optional[str]:
        """
        Get the status of the C2SIM server.
        
        Returns:
            str: XML response from the server or None if request failed
        """
        endpoint = f"{self.base_rest_url}/command"
        params = {
            'command': 'STATUS',
            'submitterID': "CHE-SW",
            'version': self.version
            
        }
        
        try:
            # Prepare request with authentication if OIDP is enabled
            headers = {}
            if self.use_oidp and self.jwt_token:
                headers["Authorization"] = f"Bearer {self.jwt_token}"
            
            resp = requests.post(endpoint, params=params, headers=headers, timeout=3000)
            resp.raise_for_status()
            
            # Parse the response to extract the sessionState
            root = ET.fromstring(resp.text)
            session_state = root.find("sessionState")
            if session_state is not None:
                self.logger.info(f"C2SIM server status: {session_state.text}")
                return session_state.text
            
            return resp.text
            
        except requests.RequestException as e:
            self.logger.error(f"Error getting server status: {e}")
            return None
        except ET.ParseError as e:
            self.logger.error(f"Error parsing status response: {e}")
            return None

    def query_init(self) -> Optional[str]:
        """
        Get the initialization data from the C2SIM server.
        
        Returns:
            str: XML with initialization data or None if request failed
        """
        endpoint = f"{self.base_rest_url}/command"
        params = {
            'command': 'QUERYINIT',
            'submitterID': 'CHE-SW',
            'version': self.version
        }
        
        try:
            # Prepare request with authentication if OIDP is enabled
            headers = {}
            if self.use_oidp and self.jwt_token:
                headers["Authorization"] = f"Bearer {self.jwt_token}"
            
            resp = requests.post(endpoint, params=params, headers=headers, timeout=3000)
            resp.raise_for_status()
            self.logger.info("Retrieved initialization data from C2SIM server")
            return resp.text
            
        except requests.RequestException as e:
            self.logger.error(f"Error querying initialization data: {e}")
            return None

    def send_command(self, command: str, parm1: str = "", parm2: str = "") -> Optional[str]:
        """
        Send a command to the C2SIM server.
        
        Args:
            command: Command to send (e.g., 'SHARE', 'START', 'STOP')
            parm1: First parameter (optional)
            parm2: Second parameter (optional)
            
        Returns:
            str: Response from the server or None if request failed
        """
        endpoint = f"{self.base_rest_url}/command"
        params = {
            'command': command,
            'parm1': parm1,
            'parm2': parm2,
            'submitter': self.submitter_id,
            'version': self.version
        }
        
        # If command needs password, add it
        if command in ['SHARE', 'START', 'STOP', 'RESET', 'PAUSE']:
            if not self.password:
                self.logger.warning(f"Command {command} requires password, but none provided in config")
            params['parm1'] = self.password
        
        try:
            # Prepare request with authentication if OIDP is enabled and token is available
            headers = {}
            if self.use_oidp and self.jwt_token:
                headers["Authorization"] = f"Bearer {self.jwt_token}"
            
            resp = requests.post(endpoint, params=params, headers=headers, timeout=300)
            resp.raise_for_status()
            self.logger.info(f"Command {command} sent successfully")
            return resp.text
            
        except requests.RequestException as e:
            self.logger.error(f"Error sending command {command}: {e}")
            return None
            
    def send_xml(self, xml_content: str, headers: Dict[str, Any] = None) -> Optional[str]:
        """
        Send XML content to the C2SIM server.
        
        Args:
            xml_content: XML to send
            headers: Additional headers for the request
            
        Returns:
            str: Response from the server or None if request failed
        """
        endpoint = f"{self.base_rest_url}/c2sim"
        
        params = {
            'protocol': 'SISO-STD-020-2020', #TODO grab from config
            'submitterID': self.submitter_id,
            'version': self.version
        }
        
        if headers:
            params.update(headers)
        
        try:
            # Prepare headers with content type and authorization
            request_headers = {'Content-Type': 'application/xml'}
            
            # Add authentication if OIDP is enabled
            if self.use_oidp and self.jwt_token:
                request_headers["Authorization"] = f"Bearer {self.jwt_token}"
            
            resp = requests.post(
                endpoint, 
                params=params, 
                data=xml_content, 
                headers=request_headers,
                timeout=3000
            )
            resp.raise_for_status()
            self.logger.info("XML sent successfully")
            return resp.text
            
        except requests.RequestException as e:
            self.logger.error(f"Error sending XML: {e}")
            return None
    
    def refresh_token(self) -> bool:
        """Refresh the JWT token if OIDP is enabled"""
        if not self.use_oidp or not self.oidp_client:
            return False
            
        try:
            new_token = self.oidp_client.get_token()
            if new_token:
                self.jwt_token = new_token
                self.logger.info("Successfully refreshed authentication token")
                return True
            else:
                self.logger.error("Failed to refresh authentication token")
                return False
        except Exception as e:
            self.logger.error(f"Error refreshing authentication token: {e}")
            return False
    
    def on_message_received(self, frame):
        print("Received C2SIM message.\n")
        """
        Handle incoming STOMP messages from C2SIM server.
        
        Args:
            frame: STOMP frame with message data
        """
        try:
            # Extract headers and body
            headers = frame.headers
            xml_msg = frame.body
            
            # Get message type from headers
            msg_selector = headers.get('message-selector', 'UNKNOWN')
            submitter = headers.get('submitter', 'UNKNOWN')
            
            self.logger.info(f"Received {msg_selector} message from {submitter}")
            
            # Handle message based on selector
            if msg_selector == 'C2SIM_Initialization':
                self.handle_initialization(xml_msg)
            elif msg_selector == 'C2SIM_Report':
                self.handle_report(xml_msg)
            else:
                self.logger.warning(f"Unhandled message selector: {msg_selector}")
                
        except Exception as e:
            self.logger.error(f"Error processing incoming STOMP message: {e}")
    
    def handle_initialization(self, xml_msg):
        """
        Handle C2SIM initialization message.
        
        Args:
            xml_msg: C2SIM initialization XML
        """
        self.logger.info("Processing C2SIM initialization message")
        
        try:
            # Parse the initialization data
            units = self.parser.parse_initialization_xml(xml_msg)
            
            # Clear existing state
            self.clear_state()
            
            # Convert to SitaWare symbols
            symbols = self.parser.c2sim_init_to_sitaware_symbols(units)
            
            # Add each symbol to outgoing queue for SitaWare and update state
            for unit, symbol in zip(units, symbols):
                # Add to state manager
                self.add_unit(unit['name'], unit['uuid'], symbol)
                
                # Add to outgoing queue for SitaWare
                self.outgoing_queue.put(symbol)
            
            # Process the outgoing queue if SitaWare client is set
            if self.sita_client:
                while not self.outgoing_queue.empty():
                    symbol = self.outgoing_queue.get()
                    self.sita_client.process_incoming_message(symbol)
                    self.outgoing_queue.task_done()
            
            self.logger.info(f"Processed {len(units)} units from initialization message")
            
        except Exception as e:
            self.logger.error(f"Error handling initialization message: {e}")
    
    def handle_report(self, xml_msg):
        """
        Handle C2SIM report message.
        
        Args:
            xml_msg: C2SIM report XML
        """
        try:
            # Parse the position report
            position_data = self.parser.parse_position_report(xml_msg)
            
            if not position_data:
                self.logger.warning("Failed to parse position report")
                return
            
            uuid = position_data.get('uuid')
            if not uuid:
                self.logger.warning("Missing UUID in position report")
                return
            
            # Get the unit name from state
            name = self.get_name_by_uuid(uuid)
            if not name:
                self.logger.warning(f"Received position report for unknown unit: UUID {uuid}")
                return
            
            # Get the current symbol
            symbol = self.get_symbol_by_name(name)
            if not symbol:
                self.logger.warning(f"No symbol found for unit: {name}")
                return
            
            # Update the symbol with new position data
            updated_symbol = self.parser.update_symbol_from_position(symbol, position_data)
            
            # Update state
            self.update_unit(uuid, updated_symbol)
            
            # Add to outgoing queue for SitaWare
            self.outgoing_queue.put(updated_symbol)
            
            # Process the outgoing queue if SitaWare client is set
            if self.sita_client:
                while not self.outgoing_queue.empty():
                    symbol = self.outgoing_queue.get()
                    self.sita_client.process_incoming_message(symbol)
                    self.outgoing_queue.task_done()
                
        except Exception as e:
            self.logger.error(f"Error handling report message: {e}")
    
    def process_outgoing_message(self, message):
        """
        Process a message from SitaWare to be sent to C2SIM.
        
        Args:
            message: Message to be processed
        """
        try:
            # Currently only handling XML messages
            if isinstance(message, str) and (message.startswith('<?xml') or message.startswith('<')):
                self.logger.info("Sending XML message to C2SIM server")
                response = self.send_xml(message)
                
                if response:
                    self.logger.info("Successfully sent message to C2SIM server")
                else:
                    self.logger.warning("Failed to send message to C2SIM server")
            else:
                self.logger.warning(f"Unsupported message type for C2SIM: {type(message)}")
                
        except Exception as e:
            self.logger.error(f"Error processing outgoing message: {e}")
    
    # State management methods
    def add_unit(self, name: str, uuid_str: str, symbol: Dict[str, Any]) -> None:
        """Add a new unit to the state"""
        self.name_to_symbol[name] = symbol
        self.name_to_uuid[name] = uuid_str
        self.uuid_to_name[uuid_str] = name
        self.logger.info(f"Added unit to state: {name} (UUID: {uuid_str})")
    
    def update_unit(self, uuid_str: str, updated_symbol: Dict[str, Any]) -> bool:
        """Update an existing unit's symbol"""
        name = self.uuid_to_name.get(uuid_str)
        if not name:
            self.logger.warning(f"Attempted to update unknown unit: UUID {uuid_str}")
            return False
            
        self.name_to_symbol[name] = updated_symbol
        self.logger.info(f"Updated unit in state: {name} (UUID: {uuid_str})")
        return True
    
    def get_symbol_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a unit's symbol by name"""
        return self.name_to_symbol.get(name)
    
    def get_symbol_by_uuid(self, uuid_str: str) -> Optional[Dict[str, Any]]:
        """Get a unit's symbol by UUID"""
        name = self.uuid_to_name.get(uuid_str)
        if name:
            return self.name_to_symbol.get(name)
        return None
    
    def get_name_by_uuid(self, uuid_str: str) -> Optional[str]:
        """Get a unit's name by UUID"""
        return self.uuid_to_name.get(uuid_str)
    
    def get_uuid_by_name(self, name: str) -> Optional[str]:
        """Get a unit's UUID by name"""
        return self.name_to_uuid.get(name)
    
    def clear_state(self) -> None:
        """Clear all state"""
        self.name_to_symbol.clear()
        self.name_to_uuid.clear()
        self.uuid_to_name.clear()
        self.logger.info("State cleared")
    
    def get_all_units(self) -> Dict[str, Dict[str, Any]]:
        """Return all units by name"""
        return self.name_to_symbol.copy()
    
    import requests
import logging

class OIDPClient:
    """
    OpenID Provider client for authentication with C2SIM server.
    """
    def __init__(self, config=None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Extract basic configuration
        self.host = self.config.get('host', 'localhost')
        self.port = self.config.get('port', 30104)  
        self.client_id = self.config.get('client_id', 'CWIX')  
        self.client_secret = self.config.get('client_secret', '')
        self.realm = self.config.get('realm', 'hla')
        
        # Log configuration (excluding secret)
        self.logger.info(f"OIDP configuration: host={self.host}, port={self.port}, client_id={self.client_id}")
        
        # Set up the well-known configuration URL
        self.config_url = f"http://{self.host}:{self.port}/realms/{self.realm}/.well-known/openid-configuration"
        self.logger.info(f"OpenID configuration URL: {self.config_url}")
        
        # For direct token endpoint use
        self.token_endpoint = f"http://{self.host}:{self.port}/realms/{self.realm}/protocol/openid-connect/token"
    
    def get_token(self):
        """Get token using multiple fallback approaches"""
        # First try the proper OpenID Connect flow
        token = self.get_token_with_discovery()
        if token:
            return token
            
        # else, try direct token endpoint
        self.logger.info("Discovery failed, trying direct token endpoint")
        return self.get_token_direct()
    
    def get_token_with_discovery(self):
        """Get token using OpenID Connect discovery flow"""
        try:
            # Setup session with retry capabilities
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                max_retries=3,
                pool_connections=1,
                pool_maxsize=1
            )
            session.mount('http://', adapter)
            
            # STEP 1: Get the OpenID configuration
            self.logger.info(f"Fetching OpenID configuration from {self.config_url}")
            
            config_response = session.get(
                self.config_url,
                timeout=1000
            )
            
            if config_response.status_code != 200:
                self.logger.error(f"Failed to get OpenID configuration: {config_response.status_code}")
                return None
            
            # Parse configuration
            config_data = config_response.json()
            self.logger.debug(f"config_data: {config_data}")
            token_endpoint = config_data.get("token_endpoint")
            
            if not token_endpoint:
                self.logger.error("No token_endpoint found in OpenID configuration")
                return None
            
            self.logger.info(f"Using token endpoint from discovery: {token_endpoint}")
            
            # STEP 2: Request token

            token = self.request_token(token_endpoint, session)
            self.logger.debug(token)
            return token
            
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error during discovery: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error during token discovery: {e}")
            return None
    
    def get_token_direct(self):
        """Get token using direct token endpoint"""
        try:
            # Use fresh session
            session = requests.Session()
            return self.request_token(self.token_endpoint, session)
        except Exception as e:
            self.logger.error(f"Error getting token directly: {e}")
            return None
    
    def request_token(self, token_endpoint, session):
        """Common token request logic"""
        try:
            payload = {
                "client_id": self.client_id,
                "scope": "hla",
                "client_secret": self.client_secret,
                "grant_type": "client_credentials"
            }
            
            self.logger.info(f"Requesting token from {token_endpoint}")
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            
            token_response = session.post(
                token_endpoint,
                data=payload,
                headers=headers,
                timeout=1000
            )
            
            if token_response.status_code != 200:
                self.logger.error(f"Token request failed: {token_response.status_code}")
                return None
            
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            
            if not access_token:
                self.logger.error("No access_token in response")
                return None
            
            self.logger.info(f"Successfully obtained token (length: {len(access_token)})")
            return access_token
            
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error during token request: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error requesting token: {e}")
            return None
        