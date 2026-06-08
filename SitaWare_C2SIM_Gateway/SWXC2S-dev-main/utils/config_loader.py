import os
import yaml
import logging
from typing import Dict, Any, Optional

class ConfigLoader:
    """
    Loads and manages configuration for the SitaWare-C2SIM gateway.
    """
    
    @staticmethod
    def load_config(path: str) -> Dict[str, Any]:
        """
        Loads YAML configuration from a file.
        
        Args:
            path: Path to the configuration file
            
        Returns:
            Dictionary with configuration values
        """
        logger = logging.getLogger(__name__)
        
        try:
            if not os.path.exists(path):
                logger.error(f"Configuration file not found: {path}")
                return {}
                
            with open(path, 'r') as f:
                loaded = yaml.safe_load(f)
                logger.info(f"Configuration loaded from {path}")
                return loaded if loaded else {}
                
        except Exception as e:
            logger.error(f"Error loading config from {path}: {e}")
            return {}

    @staticmethod
    def get_c2sim_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the 'c2sim_server' portion of the config.
        
        Args:
            config: Full configuration dictionary
            
        Returns:
            C2SIM server configuration section
        """
        return config.get('c2sim_server', {})

    @staticmethod
    def get_oidp_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the OIDP authentication configuration.
        
        Args:
            config: Full configuration dictionary
            
        Returns:
            OIDP configuration section or empty dict if not found
        """
        c2sim_config = ConfigLoader.get_c2sim_config(config)
        return c2sim_config.get('oidp', {})
    
    @staticmethod
    def is_oidp_enabled(config: Dict[str, Any]) -> bool:
        """
        Check if OIDP authentication is enabled.
        
        Args:
            config: Full configuration dictionary
            
        Returns:
            True if OIDP authentication is enabled, False otherwise
        """
        c2sim_config = ConfigLoader.get_c2sim_config(config)
        return c2sim_config.get('use_oidp', False)

    @staticmethod
    def get_sitaware_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the 'sitaware_server' portion of the config.
        
        Args:
            config: Full configuration dictionary
            
        Returns:
            SitaWare server configuration section
        """
        return config.get('sitaware_server', {})
    
    @staticmethod
    def get_logging_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the 'logging' portion of the config.
        
        Args:
            config: Full configuration dictionary
            
        Returns:
            Logging configuration section
        """
        return config.get('logging', {})
    
    @staticmethod
    def find_config_file(filename: str = 'config.yaml') -> Optional[str]:
        """
        Find the configuration file in common locations.
        
        Args:
            filename: Name of the configuration file
            
        Returns:
            Path to the configuration file if found, None otherwise
        """
    
        search_paths = [
            filename,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), 
            os.path.join(os.path.expanduser('~'), filename), 
            os.path.join('/etc', filename),  
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', filename), 
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                return path
                
        return None