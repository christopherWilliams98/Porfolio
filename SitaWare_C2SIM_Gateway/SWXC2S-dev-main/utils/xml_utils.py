import logging
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any

# Configure logger
logger = logging.getLogger(__name__)

# Define namespaces used in C2SIM
NAMESPACES = {
    'c2sim': 'http://www.sisostds.org/schemas/C2SIM/1.1', #NOTE used by default by C2SIM server to send the initialization data
    'ibml09': 'http://netlab.gmu.edu/IBML',
    'cbml': 'http://www.sisostds.org/schemas/c-bml/1.0',
    'core': 'http://www.sisostds.org/schemas/c2sim/1.0',
    'msdl': 'urn:sisostds:scenario:military:data:draft:msdl:1'
}

# Register namespaces for pretty printing
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

def parse_xml(xml_string: str) -> Optional[ET.Element]:
    """
    Parcse XML string to El  ementTree, handling namespaces properly.
    
    Args:
        xml_string: XML content as string
        
    Returns:
        ET.Element if successful, None if parsing failed
    """
    try:
        return ET.fromstring(xml_string)
    except ET.ParseError as e:
        logger.error(f"Error parsing XML: {e}")
        if xml_string:
            logger.debug(f"Problematic XML: {xml_string[:200]}...")
        return None

def find_element(root: ET.Element, path: str, namespace: str = 'c2sim') -> Optional[ET.Element]:
    """
    Find a single element using namespace-aware path.
    
    Args:
        root: Root element to search from
        path: Path (e.g. 'DomainMessageBody/ReportBody')
        namespace: Namespace prefix to use (default: 'c2sim')
        
    Returns:
        Element if found, None otherwise
    """
    ns = NAMESPACES.get(namespace)
    if not ns:
        logger.warning(f"Unknown namespace prefix: {namespace}")
        return None
        
    # Convert path into namespace-aware path
    ns_path = []
    for segment in path.split('/'):
        if segment:
            ns_path.append(f"{{{ns}}}{segment}")
    
    # Navigate down the elements
    current = root
    for i, segment in enumerate(ns_path[:-1]):
        next_element = current.find(segment)
        if next_element is None:
            return None
        current = next_element
    
    # Find the final element
    return current.find(ns_path[-1]) if ns_path else None

def find_elements(root: ET.Element, path: str, namespace: str = 'c2sim') -> List[ET.Element]:
    """
    Find all matching elements using namespace-aware path.
    
    Args:
        root: Root element to search from
        path: Path (e.g. 'DomainMessageBody/ReportBody/ReportContent')
        namespace: Namespace prefix to use
        
    Returns:
        List of matching elements (may be empty)
    """
    ns = NAMESPACES.get(namespace)
    if not ns:
        logger.warning(f"Unknown namespace prefix: {namespace}")
        return []
        
    # Convert path into namespace-aware path
    parts = path.split('/')
    if not parts:
        return []
        
    # Navigate down to the parent of the elements we want to find

    current = root
    for i in range(len(parts) - 1):
        segment = f"{{{ns}}}{parts[i]}" 

        next_element = current.find(segment)
        if next_element is None:

            return []
        current = next_element 
    
    # Find all matching elements
    final_segment = f"{{{ns}}}{parts[-1]}"
    return current.findall(final_segment)

def get_text(element: ET.Element, path: str, namespace: str = 'c2sim') -> Optional[str]:
    """
    Get text content of an element at the given path.
    
    Args:
        element: Element to search from
        path: Path to the element whose text we want
        namespace: Namespace prefix to use
        
    Returns:
        Text content if found, None otherwise
    """
    child = find_element(element, path, namespace)
    return child.text if child is not None else None

def create_element(parent: ET.Element, name: str, text: Optional[str] = None, 
                  namespace: str = 'c2sim') -> ET.Element:
    """
    Create a new element with optional text content and add it to a parent element.
    
    Args:
        parent: Parent element
        name: Element name
        text: Optional text content
        namespace: Namespace prefix
        
    Returns:
        The newly created element
    """
    ns = NAMESPACES.get(namespace)
    if not ns:
        logger.warning(f"Unknown namespace prefix: {namespace}")
        # Fall back to no namespace
        element = ET.SubElement(parent, name)
    else:
        element = ET.SubElement(parent, f"{{{ns}}}{name}")
    
    if text is not None:
        element.text = text
        
    return element

def create_element_stack(parent: ET.Element, path: str, namespace: str = 'c2sim') -> ET.Element:
    """
    Create a stack of nested elements specified by a path.
    
    Args:
        parent: Parent element
        path: Path of elements to create (e.g. 'a/b/c')
        namespace: Namespace prefix
        
    Returns:
        The deepest created element
    """
    current = parent
    
    for segment in path.split('/'):
        if segment:
            current = create_element(current, segment, namespace=namespace)
            
    return current

def element_to_string(element: ET.Element) -> str:
    """
    Convert an ElementTree element to a string with proper XML declaration.
    
    Args:
        element: Element to convert
        
    Returns:
        XML string representation
    """
    return ET.tostring(element, encoding='utf-8', method='xml').decode('utf-8')

def create_c2sim_header(sender: str, receiver: str, performative: str, 
                       msg_id: Optional[str] = None, 
                       conv_id: Optional[str] = None) -> ET.Element:
    """
    Create a C2SIM message header.
    
    Args:
        sender: Sender ID
        receiver: Receiver ID
        performative: Performative type (e.g., 'Inform', 'Request')
        msg_id: Message ID (optional)
        conv_id: Conversation ID (optional)
        
    Returns:
        XML element with the header
    """
    import uuid
    
    if not msg_id:
        msg_id = str(uuid.uuid4())
    if not conv_id:
        conv_id = str(uuid.uuid4())
    
    # Create the root MessageHeader element
    root = ET.Element(f"{{{NAMESPACES['c2sim']}}}MessageHeader")
    
    # Add the child elements
    create_element(root, "Sender", sender, 'c2sim')
    create_element(root, "Receiver", receiver, 'c2sim')
    create_element(root, "CommunicativeActTypeCode", performative, 'c2sim')
    create_element(root, "MessageID", msg_id, 'c2sim')
    create_element(root, "ConversationID", conv_id, 'c2sim')
    
    return root

def wrap_with_c2sim_header(message_body: str, sender: str, receiver: str, 
                           performative: str) -> str:
    """
    Wrap a message body with a C2SIM message header.
    
    Args:
        message_body: XML message body
        sender: Sender ID
        receiver: Receiver ID
        performative: Performative type
        
    Returns:
        Complete C2SIM message with header
    """
    # Create header
    header = create_c2sim_header(sender, receiver, performative)
    header_str = element_to_string(header)
    
    # Strip XML declaration from header and body if present
    if header_str.startswith('<?xml'):
        header_str = header_str.split('?>', 1)[1].strip()
    
    if message_body.startswith('<?xml'):
        message_body = message_body.split('?>', 1)[1].strip()
    
    # Combine into full message with declaration
    message = f'<?xml version="1.0" encoding="UTF-8"?>\n<MessageBody xmlns="{NAMESPACES["c2sim"]}">\n{header_str}\n{message_body}\n</MessageBody>'
    
    return message