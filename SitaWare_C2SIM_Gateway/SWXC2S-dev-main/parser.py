import logging
import time
import copy
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET

from utils.xml_utils import parse_xml, find_element, find_elements, get_text, NAMESPACES

class Parser:
    """
    Handles translation between C2SIM XML and SitaWare JSON formats.
    """
    def __init__(self, config=None):
        self.logger = logging.getLogger(__name__)    
        self.config = config or {}
        self.default_sidc = self.config.get('default_sidc', 'SFGPUCI----E***')
        
        # Load symbol template
        self.symbol_template = self.load_symbol_template()
        self.logger.info("Loaded SitaWare symbol template")
    
    def load_symbol_template(self) -> Dict[str, Any]:
        """
        Load the SitaWare symbol template.
        
        Returns:
            Symbol template as a dictionary
        """
        return {
                "type": 9,
                "properties": {
                    "symbolCode": "SFGPUCI----E***",
                    "reportTime": "0",
                    "c2Attributes": {
                        "type": 3,
                        "name": "",
                        "operationalStatus": "1",
                        "reportingOrganisationName": None
                    },
                    "geometry": {
                        "type": "point",
                        "coordinates": ["0.0", "0.0"]
                    }
                }
            }
    
    def translate_operational_status(self, c2sim_status: str) -> str:
        """
        Translate C2SIM operational status codes to SitaWare values.
        
        Args:
            c2sim_status: C2SIM operational status code
            
        Returns:
            SitaWare operational status code
        """
        status_map = {
            "NKN": "0",           # Not known
            "FullyOperational": "1",  # Fully operational 
            "MOPS": "2",          # Marginally operational
            "NOP": "3",           # Not operational
            "SOPS": "4",          # Substantially operational
            "TOPS": "5"           # Temporarily operational
        }
        
        return status_map.get(c2sim_status, "0")  # Default to "Not known"
    
    def parse_initialization_xml(self, init_xml: str) -> List[Dict[str, Any]]:
        """
        Parse C2SIM initialization XML into a list of unit dictionaries.
        """
        units = []

        try:
            root = parse_xml(init_xml)
            if not len(root):
                self.logger.error("Failed to parse initialization XML")
                return units
            
            # Debug the actual structure
            self.logger.debug(f"Root tag: {root.tag}")
            for child in root:
                self.logger.debug(f"Child of root: {child.tag}")
                
            # First find MessageBody element
            message_body = find_element(root, "MessageBody", 'c2sim')
            if not message_body:
                self.logger.error("MessageBody element not found")
                return units
                
            # Then find C2SIMInitializationBody within MessageBody
            init_body = find_element(message_body, "C2SIMInitializationBody", 'c2sim')
            if not len(init_body):
                self.logger.error("C2SIMInitializationBody not found")
                return units
                
            # Now find ObjectDefinitions
            object_defs = find_elements(init_body, "ObjectDefinitions", 'c2sim')
            
            for obj_def in object_defs:
                entities = find_elements(obj_def, "Entity", 'c2sim')
                
                for entity in entities:
                    mil_org = find_element(entity, "ActorEntity/CollectiveEntity/MilitaryOrganization", 'c2sim')
                    if mil_org is None:
                        continue
                    
                    unit = self.process_military_organization(mil_org)
                    if unit:
                        units.append(unit)
                        
            self.logger.info(f"Parsed {len(units)} units from initialization XML")
            
        except Exception as e:
            self.logger.error(f"Error parsing initialization XML: {e}")
            
        return units
        
    def process_military_organization(self, mil_org: ET.Element) -> Optional[Dict[str, Any]]:
        try:
            # First get the Unit element
            unit_element = find_element(mil_org, "Unit", 'c2sim')
            if unit_element is None:
                self.logger.warning("No Unit element found in MilitaryOrganization")
                return None
            
            # Get required UUID and Name from the Unit element
            uuid = get_text(unit_element, "UUID", 'c2sim')
            name = get_text(unit_element, "Name", 'c2sim')
            
            if not uuid or not name:
                self.logger.warning("Missing required UUID or Name in Unit")
                return None
            
            # Get symbol code - using APP6CSymbol instead of EntityType
            symbol_code = self.default_sidc  # Default
            
            # Look for APP6CSymbol/APP6C-SIDC (primary path in the provided XML)
            app6c_sidc = get_text(unit_element, "APP6CSymbol/APP6C-SIDC", 'c2sim')
            if app6c_sidc:
                self.logger.info(f"Found APP6C-SIDC: {app6c_sidc}")
                symbol_code = app6c_sidc
            else:
                # Fallback to EntityType as before
                entity_types = find_elements(unit_element, "EntityType", 'c2sim')
                if entity_types:
                    sidc_string = get_text(entity_types[0], "APP6-SIDC/SIDCString", 'c2sim')
                    if sidc_string:
                        self.logger.info(f"Found APP6-SIDC/SIDCString: {sidc_string}")
                        symbol_code = sidc_string
            
            # Get operational status (from Unit)
            op_status = "0"  # Default to "Not known"
            health_statuses = find_elements(unit_element, "CurrentState/PhysicalState/EntityHealthStatus", 'c2sim')
            for health in health_statuses:
                op_status_elem = find_element(health, "OperationalStatus/OperationalStatusCode", 'c2sim')
                if op_status_elem is not None and op_status_elem.text:
                    op_status = self.translate_operational_status(op_status_elem.text)
                    break
            
            # Get location (from Unit)
            latitude = longitude = None
            locations = find_elements(unit_element, "CurrentState/PhysicalState/Location", 'c2sim')
            for location in locations:
                geodetic = find_element(location, "GeodeticCoordinate", 'c2sim')
                if geodetic is not None:
                    latitude = get_text(geodetic, "Latitude", 'c2sim')
                    longitude = get_text(geodetic, "Longitude", 'c2sim')
                    break
            
            # Create unit dictionary with all fields
            unit = {
                "uuid": uuid,
                "name": name,
                "symbolCode": symbol_code,
                "operationalStatus": op_status,
                "latitude": latitude,
                "longitude": longitude
            }
            
            return unit
            
        except Exception as e:
            self.logger.error(f"Error processing military organization: {e}")
            return None
    
    def c2sim_init_to_sitaware_symbols(self, units: List[Dict[str, Any]], 
                                        layer_id: str = None) -> List[Dict[str, Any]]:
        """
        Convert parsed unit dictionaries to SitaWare symbol JSON objects.
        
        Args:
            units: List of unit dictionaries
            layer_id: SitaWare layer ID (optional)
            
        Returns:
            List of SitaWare symbol JSON objects
        """
        symbols = []
        
        for unit in units:
            # Create symbol from unit data
            symbol = self.unit_to_symbol(unit, layer_id)
            if symbol:
                symbols.append(symbol)
        
        return symbols
    
    def unit_to_symbol(self, unit: Dict[str, Any], layer_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Convert a unit dictionary to a SitaWare symbol.
        
        Args:
            unit: Unit dictionary
            layer_id: SitaWare layer ID (optional)
            
        Returns:
            SitaWare symbol JSON object
        """
        try:
            # Create a copy of the template symbol
            symbol = copy.deepcopy(self.symbol_template)
            
            # Set the ID using the UUID
            symbol["id"] = f"9:{unit['uuid']}"
            
            # Set the layer ID if provided
            if layer_id:
                symbol["layerId"] = layer_id
            
            # Set properties
            props = symbol["properties"]
            
            # Set report time (current time in seconds since epoch)
            props["reportTime"] = str(int(time.time()))
            
            # Set symbol code
            props["symbolCode"] = unit.get("symbolCode", self.default_sidc)
            
            # Set c2Attributes
            c2_attrs = props["c2Attributes"]
            c2_attrs["name"] = unit["name"]
            c2_attrs["operationalStatus"] = unit["operationalStatus"]
            c2_attrs["reportingOrganisationName"] = None  # Set to None instead of "C2SIM"
            
            # Set coordinates
            geo = props["geometry"]
            coords = [unit["longitude"], unit["latitude"]]
            geo["coordinates"] = coords
            
            return symbol
            
        except Exception as e:
            self.logger.error(f"Error creating symbol for unit {unit.get('name')}: {e}")
            return None
    
    def parse_position_report(self, report_xml: str) -> Optional[Dict[str, Any]]:
        """
        Parse a C2SIM position report XML.
        
        Args:
            report_xml: Position report XML
            
        Returns:
            Dictionary with position data or None if parsing failed
        """
        try:
            root = parse_xml(report_xml)
            if root is None:
                return None
            
            # Find report content
            report_contents = find_elements(root, "ReportBody/ReportContent", 'c2sim')
            if not report_contents:
                self.logger.warning("No ReportContent found in position report")
                return None
            
            # Find position report content
            for report in report_contents:
                pos_report = find_element(report, "PositionReportContent", 'c2sim')
                if pos_report is not None:
                    return self.process_position_report(pos_report)
            
            self.logger.warning("No PositionReportContent found in report")
            return None
            
        except Exception as e:
            self.logger.error(f"Error parsing position report: {e}")
            return None
    
    def process_position_report(self, pos_report: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Extract data from a PositionReportContent element.
        
        Args:
            pos_report: PositionReportContent element
            
        Returns:
            Dictionary with position data
        """
        try:
            # Get subject entity (UUID)
            subject = find_element(pos_report, "SubjectEntity", 'c2sim')
            if subject is None or not subject.text:
                self.logger.warning("Missing SubjectEntity in position report")
                return None
            
            uuid = subject.text
            
            # Get report time
            report_time = str(int(time.time()))  # Default to current time
            time_elem = find_element(pos_report, "TimeOfObservation/DateTime/IsoDateTime", 'c2sim')
            if time_elem is not None and time_elem.text:
                # Convert ISO time to epoch seconds
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(time_elem.text.replace('Z', '+00:00'))
                    report_time = str(int(dt.timestamp()))
                except Exception as e:
                    self.logger.warning(f"Error parsing report time: {e}")
            
            # Get location
            geodetic = find_element(pos_report, "Location/GeodeticCoordinate", 'c2sim')
            if geodetic is None:
                self.logger.warning("Missing GeodeticCoordinate in position report")
                return None
            
            latitude = get_text(geodetic, "Latitude", 'c2sim')
            longitude = get_text(geodetic, "Longitude", 'c2sim')
            
            if not latitude or not longitude:
                self.logger.warning("Missing latitude or longitude in position report")
                return None
            
            # Get operational status
            op_status = "0"  # Default
            statuses = find_elements(pos_report, "EntityHealthStatus", 'c2sim')
            for status in statuses:
                op_status_code = get_text(status, "OperationalStatus/OperationalStatusCode", 'c2sim')
                if op_status_code:
                    op_status = self.translate_operational_status(op_status_code)
                    break
            
            # Create position data dictionary
            position_data = {
                "uuid": uuid,
                "reportTime": report_time,
                "latitude": latitude,
                "longitude": longitude,
                "operationalStatus": op_status
            }
            
            return position_data
            
        except Exception as e:
            self.logger.error(f"Error processing position report: {e}")
            return None
    
    def update_symbol_from_position(self, symbol: Dict[str, Any], 
                                   position_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a SitaWare symbol with position report data.
        
        Args:
            symbol: Existing SitaWare symbol JSON
            position_data: Position data from a position report
            
        Returns:
            Updated symbol JSON
        """
        try:
            updated = copy.deepcopy(symbol)
            
            # Update properties
            props = updated["properties"]
            
            # Update report time
            props["reportTime"] = position_data["reportTime"]
            
            # Update operational status
            props["c2Attributes"]["operationalStatus"] = position_data["operationalStatus"]
            
            # Update coordinates
            props["geometry"]["coordinates"] = [
                position_data["longitude"],
                position_data["latitude"]
            ]
            
            return updated
            
        except Exception as e:
            self.logger.error(f"Error updating symbol: {e}")
            return symbol  # Return original if update fails
    
    def create_order_xml(self, order_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a C2SIM order XML from order data.
        
        Args:
            order_data: Order data
            
        Returns:
            C2SIM order XML
        """
        self.logger.warning("Order XML creation not implemented")
        return None