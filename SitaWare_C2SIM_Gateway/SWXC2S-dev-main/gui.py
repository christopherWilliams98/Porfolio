import sys
import os
import yaml
import logging
import queue
import threading
import time
from typing import Dict, Any, Optional, Tuple, List, Callable

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QCheckBox, QSpinBox, QComboBox, QPushButton,
    QLabel, QGroupBox, QFileDialog, QMessageBox, QDialog, QTextEdit,
    QProgressBar, QSplitter, QFrame, QGridLayout, QPlainTextEdit, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QThread
from PyQt6.QtGui import QColor, QTextCursor, QTextCharFormat, QPalette

class GatewaySignals(QObject):
    update_c2sim_status = pyqtSignal(str)
    update_sitaware_status = pyqtSignal(str)
    update_processing_status = pyqtSignal(str)  
    update_processing_count = pyqtSignal(int, int)  
    clear_processing_count = pyqtSignal()  
    finished = pyqtSignal()  
    error = pyqtSignal(str)  
    
    c2sim_rest_connected = pyqtSignal(bool)
    c2sim_stomp_connected = pyqtSignal(bool)
    sitaware_connected = pyqtSignal(bool)
    
    c2sim_server_status = pyqtSignal(str)
    initialization_received = pyqtSignal(bool)

class GatewayWindow(QMainWindow):
    start_gateway = pyqtSignal(dict)
    
    def __init__(self, initial_config: Dict[str, Any] = None, config_path: str = None):
        super().__init__()
        
        self.config = initial_config or {}
        self.config_updated = False
        self.config_path = config_path or "config.yaml"
        self.gateway_running = False
        
        self.signals = GatewaySignals()
        
        self.signals.update_c2sim_status.connect(self.update_c2sim_status)
        self.signals.update_sitaware_status.connect(self.update_sitaware_status)
        self.signals.update_processing_status.connect(self.update_processing_status)
        self.signals.update_processing_count.connect(self.update_processing_count)
        self.signals.clear_processing_count.connect(self.clear_processing_count)
        self.signals.finished.connect(self.on_gateway_finished)
        self.signals.error.connect(self.on_gateway_error)
        
        self.signals.c2sim_rest_connected.connect(self.update_c2sim_rest_status)
        self.signals.c2sim_stomp_connected.connect(self.update_c2sim_stomp_status)
        self.signals.sitaware_connected.connect(self.update_sitaware_connection_status)
        self.signals.c2sim_server_status.connect(self.update_c2sim_server_status)
        self.signals.initialization_received.connect(self.update_initialization_status)
        
        self.setWindowTitle("SitaWare-C2SIM Gateway")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        self.init_ui()
        self.load_config_to_ui()
        
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        
        self.setup_config_buttons()
        main_layout.addLayout(self.config_buttons_layout)
        
        self.config_tabs = QTabWidget()
        self.c2sim_tab = QWidget()
        self.sitaware_tab = QWidget()
        self.options_tab = QWidget()
        
        self.config_tabs.addTab(self.c2sim_tab, "C2SIM Server")
        self.config_tabs.addTab(self.sitaware_tab, "SitaWare Server")
        self.config_tabs.addTab(self.options_tab, "Options")
        
        self.setup_c2sim_tab()
        self.setup_sitaware_tab()
        self.setup_options_tab()
        
        main_layout.addWidget(self.config_tabs)
        
        self.setup_status_section()
        main_layout.addWidget(self.status_group)
        
        self.setup_gateway_buttons()
        main_layout.addLayout(self.gateway_buttons_layout)
        
        self.info_label = QLabel(f"Configuration: {self.config_path}")
        main_layout.addWidget(self.info_label)
    
    def setup_config_buttons(self):
        self.config_buttons_layout = QHBoxLayout()
        
        self.load_btn = QPushButton("Load Config")
        self.save_btn = QPushButton("Save Config")
        self.save_as_btn = QPushButton("Save As...")
        
        self.load_btn.clicked.connect(self.load_config)
        self.save_btn.clicked.connect(self.save_config)
        self.save_as_btn.clicked.connect(self.save_config_as)
        
        self.config_buttons_layout.addWidget(self.load_btn)
        self.config_buttons_layout.addWidget(self.save_btn)
        self.config_buttons_layout.addWidget(self.save_as_btn)
        self.config_buttons_layout.addStretch()
    
    def setup_gateway_buttons(self):
        self.gateway_buttons_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Gateway")
        self.stop_btn = QPushButton("Stop Gateway")
        
        self.stop_btn.setEnabled(False)
        
        self.start_btn.clicked.connect(self.start_gateway_clicked)
        self.stop_btn.clicked.connect(self.stop_gateway_clicked)
        
        self.gateway_buttons_layout.addStretch()
        self.gateway_buttons_layout.addWidget(self.start_btn)
        self.gateway_buttons_layout.addWidget(self.stop_btn)
    
    def setup_c2sim_tab(self):
        layout = QVBoxLayout()
        
        server_group = QGroupBox("C2SIM Server Connection")
        server_layout = QFormLayout()
        
        self.c2sim_host = QLineEdit()
        self.c2sim_rest_port = QSpinBox()
        self.c2sim_rest_port.setRange(1, 65535)
        self.c2sim_rest_port.setValue(8080)
        
        self.c2sim_stomp_port = QSpinBox()
        self.c2sim_stomp_port.setRange(1, 65535)
        self.c2sim_stomp_port.setValue(61613)
        
        self.c2sim_topic = QLineEdit()
        self.c2sim_topic.setText("/topic/C2SIM")
        
        server_layout.addRow("Host:", self.c2sim_host)
        server_layout.addRow("REST Port:", self.c2sim_rest_port)
        server_layout.addRow("STOMP Port:", self.c2sim_stomp_port)
        server_layout.addRow("Topic:", self.c2sim_topic)
        
        server_group.setLayout(server_layout)
        
        cred_group = QGroupBox("Authentication")
        cred_layout = QFormLayout()
        
        self.c2sim_submitter = QLineEdit()
        self.c2sim_submitter.setText("SWC2SGW")
        
        self.c2sim_password = QLineEdit()
        self.c2sim_password.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.c2sim_version = QLineEdit()
        self.c2sim_version.setText("4.8.4.9")
        
        cred_layout.addRow("Submitter ID:", self.c2sim_submitter)
        cred_layout.addRow("Password:", self.c2sim_password)
        cred_layout.addRow("Version:", self.c2sim_version)
        
        cred_group.setLayout(cred_layout)
        
        oidp_group = QGroupBox("OIDP Authentication")
        oidp_layout = QFormLayout()
        
        self.use_oidp = QCheckBox("Enable OIDP Authentication")
        
        self.oidp_host = QLineEdit()
        self.oidp_port = QSpinBox()
        self.oidp_port.setRange(1, 65535)
        self.oidp_port.setValue(30011)
        
        self.oidp_client_id = QLineEdit()
        self.oidp_client_id.setPlaceholderText("Your OIDP client ID")
        
        self.oidp_client_secret = QLineEdit()
        self.oidp_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.oidp_client_secret.setPlaceholderText("Your OIDP client secret")
        
        oidp_layout.addRow("", self.use_oidp)
        oidp_layout.addRow("OIDP Host:", self.oidp_host)
        oidp_layout.addRow("OIDP Port:", self.oidp_port)
        oidp_layout.addRow("Client ID:", self.oidp_client_id)
        oidp_layout.addRow("Client Secret:", self.oidp_client_secret)
        
        self.use_oidp.stateChanged.connect(self.toggle_oidp_fields)
        
        oidp_group.setLayout(oidp_layout)
        
        layout.addWidget(server_group)
        layout.addWidget(cred_group)
        layout.addWidget(oidp_group)
        layout.addStretch()
        
        self.c2sim_tab.setLayout(layout)
        
        self.toggle_oidp_fields(self.use_oidp.checkState())

    def toggle_oidp_fields(self, state):
        """Enable or disable OIDP fields based on checkbox state"""
        enabled = (state == Qt.CheckState.Checked)
        self.oidp_host.setEnabled(enabled)
        self.oidp_port.setEnabled(enabled)
        self.oidp_client_id.setEnabled(enabled)
        self.oidp_client_secret.setEnabled(enabled)
    
    def setup_sitaware_tab(self):
        layout = QVBoxLayout()
        
        server_group = QGroupBox("SitaWare Server Connection")
        server_layout = QFormLayout()
        
        self.sitaware_host = QLineEdit()
        self.sitaware_port = QSpinBox()
        self.sitaware_port.setRange(1, 65535)
        self.sitaware_port.setValue(443)
        
        self.verify_ssl = QCheckBox("Verify SSL certificates")
        
        server_layout.addRow("Host:", self.sitaware_host)
        server_layout.addRow("API Port:", self.sitaware_port)
        server_layout.addRow("", self.verify_ssl)
        
        server_group.setLayout(server_layout)
        
        cred_group = QGroupBox("Authentication")
        cred_layout = QFormLayout()
        
        self.sitaware_username = QLineEdit()
        self.sitaware_username.setText("admin")
        
        self.sitaware_password = QLineEdit()
        self.sitaware_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.sitaware_password.setText("admin")
        
        self.default_layer = QLineEdit()
        self.default_layer.setText("default")
        
        cred_layout.addRow("Username:", self.sitaware_username)
        cred_layout.addRow("Password:", self.sitaware_password)
        cred_layout.addRow("Default Layer:", self.default_layer)
        
        cred_group.setLayout(cred_layout)
        
        layout.addWidget(server_group)
        layout.addWidget(cred_group)
        layout.addStretch()
        
        self.sitaware_tab.setLayout(layout)
    
    def setup_options_tab(self):
        layout = QVBoxLayout()
        
        trans_group = QGroupBox("Translation Options")
        trans_layout = QFormLayout()
        
        self.default_sidc = QLineEdit()
        self.default_sidc.setText("SFGPUCI----E***")
        
        trans_layout.addRow("Default SIDC:", self.default_sidc)
        
        trans_group.setLayout(trans_layout)
        
        log_group = QGroupBox("Logging Options")
        log_layout = QFormLayout()
        
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level.setCurrentText("INFO")
        
        self.log_file = QLineEdit()
        self.log_file.setText("sw_c2sim_gw.log")
        
        self.log_browse = QPushButton("Browse...")
        self.log_browse.clicked.connect(self.browse_log_file)
        
        log_file_layout = QHBoxLayout()
        log_file_layout.addWidget(self.log_file)
        log_file_layout.addWidget(self.log_browse)
        
        log_layout.addRow("Log Level:", self.log_level)
        log_layout.addRow("Log File:", log_file_layout)
        
        log_group.setLayout(log_layout)
        
        other_group = QGroupBox("Other Options")
        other_layout = QFormLayout()
        
        self.auto_start = QCheckBox("Auto-start C2SIM server if not running")
        
        other_layout.addRow("", self.auto_start)
        
        other_group.setLayout(other_layout)
        
        layout.addWidget(trans_group)
        layout.addWidget(log_group)
        layout.addWidget(other_group)
        layout.addStretch()
        
        self.options_tab.setLayout(layout)
    
    def setup_status_section(self):
        """Setup the status section with clean compartments"""
        self.status_group = QGroupBox("Gateway Status")
        main_status_layout = QVBoxLayout()
        
        connection_layout = QHBoxLayout()
        
        sitaware_box = QGroupBox("SitaWare")
        sitaware_layout = QVBoxLayout()
        self.sitaware_status = QLabel("Not Connected")
        self.set_status_style(self.sitaware_status, False)
        sitaware_layout.addWidget(self.sitaware_status)
        sitaware_box.setLayout(sitaware_layout)
        
        gateway_box = QGroupBox("Gateway")
        gateway_layout = QVBoxLayout()
        self.c2sim_server_status_label = QLabel("Server Status: Unknown")
        self.init_status = QLabel("Initialization: Not Started")
        gateway_layout.addWidget(self.c2sim_server_status_label)
        gateway_layout.addWidget(self.init_status)
        gateway_box.setLayout(gateway_layout)
        
        c2sim_box = QGroupBox("C2SIM")
        c2sim_layout = QVBoxLayout()
        self.c2sim_rest_status = QLabel("REST: Not Connected")
        self.c2sim_stomp_status = QLabel("STOMP: Not Connected")
        self.set_status_style(self.c2sim_rest_status, False)
        self.set_status_style(self.c2sim_stomp_status, False)
        c2sim_layout.addWidget(self.c2sim_rest_status)
        c2sim_layout.addWidget(self.c2sim_stomp_status)
        c2sim_box.setLayout(c2sim_layout)
        
        connection_layout.addWidget(sitaware_box)
        connection_layout.addWidget(gateway_box)
        connection_layout.addWidget(c2sim_box)
        
        main_status_layout.addLayout(connection_layout)
        
        processing_group = QGroupBox("Processing Status")
        processing_layout = QVBoxLayout()
        
        self.processing_status_label = QLabel("Idle")
        self.processing_status_label.setStyleSheet("font-weight: bold;")
        
        self.processing_count_label = QLabel("")
        
        processing_layout.addWidget(self.processing_status_label)
        processing_layout.addWidget(self.processing_count_label)
        
        processing_group.setLayout(processing_layout)
        
        main_status_layout.addWidget(processing_group)
        
        self.status_group.setLayout(main_status_layout)
    
    def set_status_style(self, label, connected):
        """Set the visual style for connection status labels"""
        if connected:
            label.setStyleSheet("color: green; font-weight: bold;")
        else:
            label.setStyleSheet("color: red;")
    
    def browse_log_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Select Log File", 
            self.log_file.text(),
            "Log Files (*.log);;All Files (*)"
        )
        if file_path:
            self.log_file.setText(file_path)
    
    def load_config_to_ui(self):
        if not self.config:
            return
        
        c2sim_cfg = self.config.get('c2sim_server', {})
        if c2sim_cfg:
            self.c2sim_host.setText(c2sim_cfg.get('host', ''))
            self.c2sim_rest_port.setValue(int(c2sim_cfg.get('rest_port', 8080)))
            self.c2sim_stomp_port.setValue(int(c2sim_cfg.get('stomp_port', 61613)))
            self.c2sim_topic.setText(c2sim_cfg.get('topic', '/topic/C2SIM'))
            self.c2sim_submitter.setText(c2sim_cfg.get('submitter_id', 'SWC2SGW'))
            self.c2sim_password.setText(c2sim_cfg.get('password', ''))
            self.c2sim_version.setText(c2sim_cfg.get('version', '4.8.4.9'))
            
            self.use_oidp.setChecked(c2sim_cfg.get('use_oidp', False))
            
            oidp_cfg = c2sim_cfg.get('oidp', {})
            self.oidp_host.setText(oidp_cfg.get('host', ''))
            self.oidp_port.setValue(int(oidp_cfg.get('port', 30011)))
            self.oidp_client_id.setText(oidp_cfg.get('client_id', ''))
            self.oidp_client_secret.setText(oidp_cfg.get('client_secret', ''))
            
            self.toggle_oidp_fields(self.use_oidp.checkState())
        
        sw_cfg = self.config.get('sitaware_server', {})
        if sw_cfg:
            self.sitaware_host.setText(sw_cfg.get('host', ''))
            self.sitaware_port.setValue(int(sw_cfg.get('api_port', 443)))
            self.verify_ssl.setChecked(sw_cfg.get('verify_ssl', False))
            self.sitaware_username.setText(sw_cfg.get('username', 'admin'))
            self.sitaware_password.setText(sw_cfg.get('password', 'admin'))
            self.default_layer.setText(sw_cfg.get('default_layer', 'default'))
        
        trans_cfg = self.config.get('translation', {})
        if trans_cfg:
            self.default_sidc.setText(trans_cfg.get('default_sidc', 'SFGPUCI----E***'))
        
        log_cfg = self.config.get('logging', {})
        if log_cfg:
            self.log_level.setCurrentText(log_cfg.get('log_level', 'INFO'))
            self.log_file.setText(log_cfg.get('log_file', 'sw_c2sim_gw.log'))
        
        self.auto_start.setChecked(self.config.get('auto_start_c2sim', False))

    def collect_config_from_ui(self) -> Dict[str, Any]:
        """Collect configuration from UI elements and return as a dictionary"""
        config = {}
        
        config['c2sim_server'] = {
            'host': self.c2sim_host.text(),
            'rest_port': self.c2sim_rest_port.value(),
            'stomp_port': self.c2sim_stomp_port.value(),
            'topic': self.c2sim_topic.text(),
            'submitter_id': self.c2sim_submitter.text(),
            'password': self.c2sim_password.text(),
            'version': self.c2sim_version.text(),
            'use_oidp': self.use_oidp.isChecked()
        }
        
        if self.use_oidp.isChecked():
            config['c2sim_server']['oidp'] = {
                'host': self.oidp_host.text(),
                'port': self.oidp_port.value(),
                'client_id': self.oidp_client_id.text(),
                'client_secret': self.oidp_client_secret.text()
            }
        
        config['sitaware_server'] = {
            'host': self.sitaware_host.text(),
            'api_port': self.sitaware_port.value(),
            'username': self.sitaware_username.text(),
            'password': self.sitaware_password.text(),
            'verify_ssl': self.verify_ssl.isChecked(),
            'default_layer': self.default_layer.text()
        }
        
        config['translation'] = {
            'default_sidc': self.default_sidc.text()
        }
        
        config['logging'] = {
            'log_level': self.log_level.currentText(),
            'log_file': self.log_file.text(),
            'max_log_size': 10485760, 
            'backup_count': 5
        }
        
        config['auto_start_c2sim'] = self.auto_start.isChecked()
        
        return config
    
    def load_config(self):
        """Load configuration from a file selected by the user"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Configuration File", 
            os.path.dirname(self.config_path),
            "YAML Files (*.yaml);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r') as f:
                config = yaml.safe_load(f)
            
            self.config_path = file_path
            self.info_label.setText(f"Configuration: {self.config_path}")
            
            self.config = config
            self.load_config_to_ui()
            
            QMessageBox.information(
                self, 
                "Configuration Loaded", 
                f"Configuration loaded from {file_path}",
                QMessageBox.StandardButton.Ok
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error Loading Configuration", 
                f"An error occurred while loading the configuration: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
    
    def save_config(self):
        """Save configuration to current file"""
        config = self.collect_config_from_ui()
        
        if not self._validate_config(config):
            return
            
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            self.config_updated = True
            self.config = config
            
            QMessageBox.information(
                self, 
                "Configuration Saved", 
                f"Configuration saved to {self.config_path}",
                QMessageBox.StandardButton.Ok
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error Saving Configuration", 
                f"An error occurred while saving the configuration: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
    
    def save_config_as(self):
        """Save configuration to a user-specified file"""
        config = self.collect_config_from_ui()
        
        if not self._validate_config(config):
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Configuration File", 
            self.config_path,
            "YAML Files (*.yaml);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            self.config_path = file_path
            self.info_label.setText(f"Configuration: {self.config_path}")
            
            self.config_updated = True
            self.config = config
            
            QMessageBox.information(
                self, 
                "Configuration Saved", 
                f"Configuration saved to {file_path}",
                QMessageBox.StandardButton.Ok
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error Saving Configuration", 
                f"An error occurred while saving the configuration: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
    
    def start_gateway_clicked(self):
        """Start the gateway with current configuration"""
        config = self.collect_config_from_ui()
        if not self._validate_config(config):
            return
        
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            self.config = config
            self.config_updated = True
        except Exception as e:
            QMessageBox.warning(
                self, 
                "Warning", 
                f"Could not save configuration: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
        
        self.gateway_running = True
        self.update_ui_state()
        
        self.reset_status_indicators()
        
        self.status_timer.start(2000) 
        
        self.start_gateway.emit(config)
    
    def stop_gateway_clicked(self):
        """Stop the gateway"""
        self.gateway_running = False
        self.update_ui_state()
        
        self.status_timer.stop()
    
    def update_ui_state(self):
        """Update UI elements based on gateway state"""
        running = self.gateway_running
        
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        
        self.config_tabs.setEnabled(not running)
        self.save_btn.setEnabled(not running)
        self.save_as_btn.setEnabled(not running)
        self.load_btn.setEnabled(not running)
    
    def reset_status_indicators(self):
        """Reset all status indicators to initial state"""
        self.c2sim_rest_status.setText("REST: Not Connected")
        self.c2sim_stomp_status.setText("STOMP: Not Connected")
        self.sitaware_status.setText("Not Connected")
        self.c2sim_server_status_label.setText("Server Status: Unknown")
        self.init_status.setText("Initialization: Not Started")
        
        self.set_status_style(self.c2sim_rest_status, False)
        self.set_status_style(self.c2sim_stomp_status, False)
        self.set_status_style(self.sitaware_status, False)
        
        self.processing_status_label.setText("Idle")
        self.processing_count_label.setText("")
    
    def update_status(self):
        """Periodic status update"""
        pass
    
    def update_c2sim_rest_status(self, connected: bool):
        """Update C2SIM REST connection status"""
        self.c2sim_rest_status.setText(f"REST: {'Connected' if connected else 'Not Connected'}")
        self.set_status_style(self.c2sim_rest_status, connected)
    
    def update_c2sim_stomp_status(self, connected: bool):
        """Update C2SIM STOMP connection status"""
        self.c2sim_stomp_status.setText(f"STOMP: {'Connected' if connected else 'Not Connected'}")
        self.set_status_style(self.c2sim_stomp_status, connected)
    
    def update_sitaware_connection_status(self, connected: bool):
        """Update SitaWare connection status"""
        self.sitaware_status.setText(f"{'Connected' if connected else 'Not Connected'}")
        self.set_status_style(self.sitaware_status, connected)
    
    def update_c2sim_server_status(self, status: str):
        """Update C2SIM server status"""
        self.c2sim_server_status_label.setText(f"Server Status: {status}")
    
    def update_initialization_status(self, received: bool):
        """Update initialization status"""
        self.init_status.setText(f"Initialization: {'Received' if received else 'Not Started'}")
        if received:
            self.init_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.init_status.setStyleSheet("color: orange;")
    
    def update_c2sim_status(self, status: str):
        """Update general C2SIM status"""
        print(f"C2SIM Status: {status}")
    
    def update_sitaware_status(self, status: str):
        """Update general SitaWare status"""
        print(f"SitaWare Status: {status}")
    
    def update_processing_status(self, status: str):
        """Update the current processing status"""
        self.processing_status_label.setText(status)
    
    def update_processing_count(self, current: int, total: int):
        """Update the current processing counter"""
        if total > 0:
            self.processing_count_label.setText(f"{current}/{total}")
        else:
            self.processing_count_label.setText("")
            
    def clear_processing_count(self):
        """Clear the processing counter"""
        self.processing_count_label.setText("")
    
    def on_gateway_finished(self):
        """Handle gateway operation completion"""
        self.gateway_running = False
        self.update_ui_state()
        self.status_timer.stop()
        self.processing_status_label.setText("Idle")
        self.processing_count_label.setText("")
    
    def on_gateway_error(self, error_msg: str):
        """Handle critical gateway error"""
        self.gateway_running = False
        self.update_ui_state()
        self.status_timer.stop()
        self.processing_status_label.setText("Error")
        QMessageBox.critical(
            self, 
            "Gateway Error", 
            f"A critical error occurred in the gateway: {error_msg}",
            QMessageBox.StandardButton.Ok
        )
    
    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """Basic validation of configuration"""
        c2sim = config.get('c2sim_server', {})
        sitaware = config.get('sitaware_server', {})
        
        if not c2sim.get('host'):
            QMessageBox.warning(
                self, 
                "Invalid Configuration", 
                "C2SIM server host is required",
                QMessageBox.StandardButton.Ok
            )
            return False
        
        if not sitaware.get('host'):
            QMessageBox.warning(
                self, 
                "Invalid Configuration", 
                "SitaWare server host is required",
                QMessageBox.StandardButton.Ok
            )
            return False
        
        return True
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.gateway_running:
            reply = QMessageBox.question(
                self, 
                "Confirm Exit", 
                "The gateway is currently running. Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_gateway_clicked()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

class GatewayRunner(QThread):
    def __init__(self, signals: GatewaySignals):
        super().__init__()
        self.signals = signals
        self.config = None
        self.running = False
    
    def run(self):
        """Run the gateway operation"""
        self.running = True
        
        self.signals.c2sim_rest_connected.emit(True)
        self.signals.update_processing_status.emit("Connecting to C2SIM server")
        
        if self.running:
            self.signals.finished.emit()
        
        self.running = False
    
    def stop(self):
        """Stop the gateway operation"""
        self.running = False


def start_gateway_gui(config_path: Optional[str] = None) -> Tuple[GatewayWindow, GatewayRunner]:
    """
    Start the gateway GUI.
    
    Args:
        config_path: Path to existing configuration file
        
    Returns:
        Tuple of (window, runner) for integration with main application
    """
    config = {}
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config from {config_path}: {e}")
    
    app = QApplication.instance() or QApplication(sys.argv)
    
    window = GatewayWindow(config, config_path)
    runner = GatewayRunner(window.signals)
    
    window.start_gateway.connect(lambda cfg: run_gateway(runner, cfg))
    
    window.show()
    
    return window, runner

def run_gateway(runner: GatewayRunner, config: Dict[str, Any]):
    """Start the gateway runner with the given configuration"""
    runner.config = config
    runner.start()

def start_application(config_path: Optional[str] = None):
    """Start the application and enter the event loop"""
    window, runner = start_gateway_gui(config_path)
    sys.exit(QApplication.instance().exec())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    start_application("config.yaml")