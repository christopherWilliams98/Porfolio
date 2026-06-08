import logging
import threading
import time
import queue
import requests
import json
import urllib3
import re
import urllib.parse
from typing import Dict, Any, Optional, List

class SitaClient(threading.Thread):
    """
    Client for interacting with the SitaWare REST API.
    Integrated with messaging functionality.
    """
    def __init__(self, config, parser):
        threading.Thread.__init__(self)
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.parser = parser
        self.daemon = True
        
        # Extract configuration
        self.host = config.get('host', 'localhost')
        self.api_port = config.get('api_port', 443)
        self.username = config.get('username', 'admin')
        self.password = config.get('password', 'admin')
        self.verify_ssl = config.get('verify_ssl', False)
        
        # If verify_ssl is False, disable warnings
        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.logger.warning("SSL verification is disabled. This is not recommended for production.")
        
        # Base URL for API requests
        self.base_url = f"https://{self.host}:{self.api_port}/sw/rest"
        
        # Default layer for units
        self.default_layer = config.get('default_layer', 'GMU_Main')
        
        # Session for connection reuse
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.verify = self.verify_ssl
        
        # Set default headers
        self.session.headers.update({
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Message queues
        self.incoming_queue = queue.Queue()  # Messages from C2SIM to SitaWare
        self.outgoing_queue = queue.Queue()  # Messages from SitaWare to C2SIM
        
        # Control flag for thread
        self.running = True
        
        # Reference to C2SIM client (set later)
        self.c2sim_client = None
        
        # Cache for layer info
        self.layer_cache = {}
        
        # Default API versions for different endpoints
        self.api_versions = {
            'symbols': 'v5',  # symbols endpoint uses v5
            'layerCatalogue': 'v1'  # layerCatalogue endpoint uses v1
        }

    def set_c2sim_client(self, c2sim_client):
        """Set reference to C2SIM client for message passing"""
        self.c2sim_client = c2sim_client

    def run(self):
        """Main thread method that processes messages"""
        self.logger.info("SitaWare client thread starting...")
        
        try:
            # Test connection to SitaWare
            if not self.test_connection():
                self.logger.error("Failed to connect to SitaWare, exiting thread")
                return
                
            while self.running:
                # Process any pending incoming messages (from C2SIM)
                try:
                    # Non-blocking to keep thread responsive
                    msg = self.incoming_queue.get(block=False)
                    self.process_incoming_message(msg)
                    self.incoming_queue.task_done()
                except queue.Empty:
                    # No messages to process
                    pass
                
                # Don't hog CPU
                time.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"Error in SitaWare client thread: {e}", exc_info=True)
        finally:
            self.logger.info("SitaWare client thread stopping...")

    def stop(self):
        """Signal the thread to stop"""
        self.running = False

    def enqueue_message(self, message):
        """Add a message to the incoming queue (from C2SIM to SitaWare)"""
        self.incoming_queue.put(message)
        self.logger.debug("Message added to SitaWare incoming queue")

    def test_connection(self) -> bool:
        """
        Test the connection to SitaWare.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.logger.info(f"Testing connection to SitaWare at {self.host}:{self.api_port}")
            
            # Use the layer catalog endpoint to test connection
            response = self.get_layer_catalog()
            if response:
                self.logger.info("Successfully connected to SitaWare")
                return True
            else:
                self.logger.error("Failed to connect to SitaWare")
                return False
        except Exception as e:
            self.logger.error(f"Error testing connection to SitaWare: {e}", exc_info=True)
            return False

    def get_layer_catalog(self) -> Optional[Dict[str, Any]]:
        """
        Get the layer catalog from SitaWare.
        
        Returns:
            Dictionary with layer catalog or None if request failed
        """
        # Use the known working API version for layerCatalogue
        path = f"{self.api_versions['layerCatalogue']}/layerCatalogue"
        
        try:
            url = f"{self.base_url}/{path}"
            self.logger.debug(f"GET: {url}")
            response = self.session.get(url, timeout=20)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.logger.debug(f"Successfully retrieved layers from {path}")
                    return data
                except ValueError:
                    self.logger.warning(f"Response from {path} is not valid JSON")

        except Exception as e:
            self.logger.error(f"Error getting layer catalog: {e}")
        
        self.logger.error("Failed to get layer catalog from any endpoint")
        return None

    def _encode_layer_id(self, layer_id: str) -> str:
        """
        URL encode the layer ID for use in API requests.
        
        Args:
            layer_id: Layer ID to encode
            
        Returns:
            URL encoded layer ID
        """
        return urllib.parse.quote(layer_id)

    def find_valid_layer(self) -> Optional[Dict[str, str]]:
        """
        Find a valid layer for adding symbols.
        First tries the configured default layer, then falls back to any available layer.
        
        Returns:
            Dictionary with 'id' and 'name' of a valid layer or None if no valid layer
        """
        # Check if we have a cached layer
        if self.layer_cache:
            return self.layer_cache
        
        self.logger.info("Trying to find a valid layer...")
        
        # First try to get the default layer
        default_layer = self.get_layer_by_name(self.default_layer)
        if default_layer:
            layer_id = default_layer.get('id')
            if layer_id:
                self.layer_cache = {'id': layer_id, 'name': self.default_layer}
                self.logger.info(f"Using configured layer '{self.default_layer}' with ID: {layer_id}")
                return self.layer_cache
        
        # If we still don't have a layer, look for any available layer
        catalog = self.get_layer_catalog()
        if catalog:
            # Try to find any suitable layer
            for section in ['ownOrganizationC2Layers', 'globallySignificantLayers']:
                if section in catalog and isinstance(catalog[section], dict) and 'items' in catalog[section]:
                    items = catalog[section]['items']
                    if items:
                        # Find the first item with an id
                        for item in items:
                            if 'id' in item and 'presentationName' in item:
                                layer_id = item['id']
                                layer_name = item['presentationName']
                                self.layer_cache = {'id': layer_id, 'name': layer_name}
                                self.logger.info(f"Using alternative layer '{layer_name}' with ID: {layer_id}")
                                return self.layer_cache
                elif section in catalog and isinstance(catalog[section], list):
                    for item in catalog[section]:
                        if 'id' in item and 'presentationName' in item:
                            layer_id = item['id']
                            layer_name = item['presentationName']
                            self.layer_cache = {'id': layer_id, 'name': layer_name}
                            self.logger.info(f"Using alternative layer '{layer_name}' with ID: {layer_id}")
                            return self.layer_cache
        
        self.logger.error("No valid layers found")
        return None

    def get_layer_by_name(self, layer_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific layer by name.
        
        Args:
            layer_name: Name of the layer to find
            
        Returns:
            Layer information or None if not found
        """
        catalog = self.get_layer_catalog()
        if not catalog:
            return None
        
        # Navigate through the catalog to find the layer
        for section_key, section in catalog.items():
            if isinstance(section, dict) and 'items' in section:
                # Check each item in this section
                for item in section['items']:
                    if item.get('presentationName') == layer_name:
                        return item
                    
                    # Check sublayers if this is a parent layer
                    if 'items' in item:
                        for subitem in item['items']:
                            if subitem.get('presentationName') == layer_name:
                                return subitem
        
        self.logger.warning(f"Layer '{layer_name}' not found")
        return None

    def add_unit(self, symbol_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Add a unit to SitaWare.
        
        Args:
            symbol_json: Symbol JSON to add
            
        Returns:
            Response JSON if successful, None otherwise
        """
        try:
            # Get unit name for logging
            unit_name = symbol_json.get('properties', {}).get('c2Attributes', {}).get('name', 'Unknown')
            self.logger.info(f"Adding unit to SitaWare: {unit_name}")
            
            # Get a valid layer
            layer_info = self.find_valid_layer()
            if not layer_info:
                self.logger.error("No valid layer found for adding unit")
                return None
            
            layer_id = layer_info['id']
            symbol_json['layerId'] = layer_id
            
            # URL encode the layer ID
            encoded_layer_id = self._encode_layer_id(layer_id)
            
            url = f"{self.base_url}/{self.api_versions['symbols']}/layers/{encoded_layer_id}/symbols"
            self.logger.debug(f"POST: {url}")
            
            # Send request
            response = self.session.post(
                url, 
                json=symbol_json,
                timeout=10
            )
            
            self.logger.debug(f"Response status: {response.status_code}")
            
            # Check if successful (201 Created or 200 OK)
            if response.status_code in [200, 201]:
                self.logger.info(f"Successfully added unit {unit_name}")
                try:
                    return response.json()
                except ValueError:
                    return {'success': True}
            else:
                self.logger.error(f"Failed to add unit {unit_name}: {response.status_code} - {response.text[:100]}...")
                return None
                
        except Exception as e:
            self.logger.error(f"Error adding unit: {e}", exc_info=True)
            return None

    def update_unit(self, symbol_id: str, updated_symbol: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update an existing unit in SitaWare.
        
        Args:
            symbol_id: ID of the symbol to update
            updated_symbol: Updated symbol JSON
            
        Returns:
            Response JSON or None if request failed
        """
        try:
            # Get unit name for logging
            unit_name = updated_symbol.get('properties', {}).get('c2Attributes', {}).get('name', 'Unknown')
            self.logger.info(f"Updating unit in SitaWare: {unit_name}")
            
            # Get layer ID
            layer_id = updated_symbol.get('layerId')
            if not layer_id:
                layer_info = self.find_valid_layer()
                if not layer_info:
                    self.logger.error("No valid layer found for updating unit")
                    return None
                layer_id = layer_info['id']
                updated_symbol['layerId'] = layer_id
            
            # URL encode the layer ID and symbol ID
            encoded_layer_id = self._encode_layer_id(layer_id)
            
            # Use the known working API version for symbols
            url = f"{self.base_url}/{self.api_versions['symbols']}/layers/{encoded_layer_id}/symbols/{symbol_id}"
            self.logger.debug(f"PUT: {url}")
            
            # Send request
            response = self.session.put(
                url, 
                json=updated_symbol,
                timeout=10
            )
            
            self.logger.debug(f"Response status: {response.status_code}")
            
            # Check if successful
            if response.status_code in [200, 201]:
                self.logger.info(f"Successfully updated unit {unit_name}")
                try:
                    return response.json()
                except ValueError:
                    return {'success': True}
            else:
                self.logger.error(f"Failed to update unit {unit_name}: {response.status_code} - {response.text[:100]}...")
                return None
                
        except Exception as e:
            self.logger.error(f"Error updating unit: {e}", exc_info=True)
            return None
        

    def delete_unit(self, symbol_id: str, layer_id: Optional[str] = None) -> bool:
        """
        Delete a unit from SitaWare.
        
        Args:
            symbol_id: ID of the symbol to delete
            layer_id: Layer ID (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Deleting unit from SitaWare: {symbol_id}")
            
            # Get layer ID if not provided
            if not layer_id:
                layer_info = self.find_valid_layer()
                if not layer_info:
                    self.logger.error("No valid layer found for deleting unit")
                    return False
                layer_id = layer_info['id']
            
            # URL encode the layer ID
            encoded_layer_id = self._encode_layer_id(layer_id)
            
            # Use v5 API endpoint WITH the symbol_id in the URL
            url = f"{self.base_url}/{self.api_versions['symbols']}/layers/{encoded_layer_id}/symbols/{symbol_id}"
            
            self.logger.debug(f"DELETE: {url}")
            
            # Send request
            response = self.session.delete(url, timeout=10)
            
            self.logger.debug(f"Response status: {response.status_code}")
            
            # Check if successful
            if response.status_code in [200, 204]:
                self.logger.info(f"Successfully deleted unit {symbol_id}")
                return True
            else:
                self.logger.error(f"Failed to delete unit {symbol_id}: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting unit: {e}", exc_info=True)
            return False

    def get_all_units(self, layer_id: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get all units in a layer.
        
        Args:
            layer_id: Layer ID (uses default if None)
            
        Returns:
            List of units or None if request failed
        """
        try:
            # Get layer ID if not provided
            if not layer_id:
                layer_info = self.find_valid_layer()
                if not layer_info:
                    self.logger.error("No valid layer found for getting units")
                    return None
                layer_id = layer_info['id']
            
            # URL encode the layer ID
            encoded_layer_id = self._encode_layer_id(layer_id)
            
            # Use the known working API version for symbols
            url = f"{self.base_url}/{self.api_versions['symbols']}/layers/{encoded_layer_id}/symbols"
            self.logger.debug(f"GET: {url}")
            
            # Send request
            response = self.session.get(url, timeout=10)
            
            self.logger.debug(f"Response status: {response.status_code}")
            
            # Check if successful
            if response.status_code == 200:
                try:
                    units = response.json()
                    self.logger.info(f"Successfully retrieved {len(units)} units")
                    return units
                except ValueError:
                    self.logger.warning("Response is not valid JSON")
                    return None
            else:
                self.logger.error(f"Failed to get units: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting units: {e}", exc_info=True)
            return None

    def clear_layer(self, layer_id: Optional[str] = None) -> bool:
        """
        Delete all units in a layer.
        
        Args:
            layer_id: Layer ID (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get layer ID if not provided
            if not layer_id:
                layer_info = self.find_valid_layer()
                if not layer_info:
                    self.logger.error("No valid layer found for clearing")
                    return False
                layer_id = layer_info['id']
                self.logger.info(f"Clearing layer {layer_info['name']} (ID: {layer_id})")
            else:
                self.logger.info(f"Clearing layer with ID: {layer_id}")
            
            # Get all units
            units = self.get_all_units(layer_id)
            if not units:
                self.logger.info("No units found in layer")
                return True
            
            # Delete each unit
            success_count = 0
            for unit in units:
                unit_id = unit.get('id')
                if unit_id:
                    if self.delete_unit(unit_id, layer_id):
                        success_count += 1
            
            self.logger.info(f"Successfully deleted {success_count}/{len(units)} units from layer")
            return success_count == len(units)
                
        except Exception as e:
            self.logger.error(f"Error clearing layer: {e}", exc_info=True)
            return False

    def process_incoming_message(self, message):
        """
        Process incoming message from C2SIM to update SitaWare.
        
        Args:
            message: The message to process (typically a SitaWare symbol)
        """
        try:
            if isinstance(message, dict):
                # This looks like a SitaWare symbol
                if 'id' in message and 'properties' in message:
                    symbol_id = message.get('id')
                    unit_name = message.get('properties', {}).get('c2Attributes', {}).get('name', 'Unknown')
                    
                    # Check if this is a new unit or update
                    existing_units = self.get_all_units()
                    
                    if existing_units:
                        existing_ids = [unit.get('id') for unit in existing_units]
                        
                        if symbol_id in existing_ids:
                            # Update existing unit
                            self.logger.info(f"Updating existing unit in SitaWare: {unit_name}")
                            self.update_unit(symbol_id, message)
                        else:
                            # Add new unit
                            self.logger.info(f"Adding new unit to SitaWare: {unit_name}")
                            self.add_unit(message)
                    else:
                        # No existing units, add new unit
                        self.logger.info(f"Adding new unit to SitaWare: {unit_name}")
                        self.add_unit(message)
                else:
                    self.logger.warning(f"Received invalid SitaWare symbol format")
            else:
                self.logger.warning(f"Unsupported message type for SitaWare: {type(message)}")
        
        except Exception as e:
            self.logger.error(f"Error processing incoming message: {e}", exc_info=True)