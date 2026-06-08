import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

def setup_logger(
    log_file: Optional[str] = "sw_c2sim_gw.log",
    log_level: str = "INFO",
    max_log_size: int = 10485760,  # 10 MB
    backup_count: int = 5,
    log_to_console: bool = True
) -> None:
    """
    Set up application logging with both file and console handlers.
    
    Args:
        log_file: Path to log file (None to disable file logging)
        log_level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        max_log_size: Maximum size of log file before rotation (bytes)
        backup_count: Number of backup logs to keep
        log_to_console: Whether to also log to console
    """
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Determine log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add file handler if log_file is specified
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_log_size,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Add console handler if requested
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Log startup message
    root_logger.info(f"Logging initialized at {log_level} level")

def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)