#!/usr/bin/env python3
"""
Soil Sensor GUI Dashboard — PySide6 (Qt for Python)
Modbus RTU via USB CH340, Slave ID 1, 9600 baud
Crop recommendations + 10-sample history with statistics
"""

import sys
import time
import serial
import threading
import json
import os
from datetime import datetime
from collections import deque
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QGridLayout, QHBoxLayout,
    QLabel, QFrame, QStatusBar, QScrollArea, QTabWidget, QLineEdit, QCheckBox,
    QComboBox, QPushButton, QDialog, QSpinBox, QFormLayout
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread
from PySide6.QtGui import QFont, QColor, QBrush, QPalette


PORT = "/dev/ttyUSB0"
BAUD = 9600
SLAVE_ID = 1
POLL_INTERVAL = 2000  # ms

# Default sensor configuration (10 sensors total)
DEFAULT_READINGS = [
    # (name, unit, scale, min_warn, max_warn)
    ("Moisture", "%", 10, 10, 80),
    ("Temperature", "°C", 10, 5, 40),
    ("EC", "µS/cm", 1, 0, 2000),
    ("pH", "", 10, 5.5, 7.5),
    ("Nitrogen", "mg/kg", 1, 0, 200),
    ("Phosphorus", "mg/kg", 1, 0, 200),
    ("Potassium", "mg/kg", 1, 0, 200),
    ("Salinity", "ppt", 10, 0, 2),
    ("Conductivity", "mS/cm", 100, 0, 500),
    ("Light Intensity", "lux", 1, 0, 100000),
]

READINGS = DEFAULT_READINGS[:]  # Working copy, modified at runtime
CONFIG_FILE = os.path.expanduser("~/.8sense_config.json")

# Crop recommendation database with soil requirements
CROPS = {
    # (name, yield_tonnes_per_ha, market_value_per_kg, optimal_pH, optimal_moisture, optimal_EC, min_N)
    "Tomato": {"pH": (6.0, 7.5), "moisture": (65, 75), "EC": (1.5, 2.5), "N": 150, "yield": 80, "value": 2.0, "icon": "🍅"},
    "Lettuce": {"pH": (6.5, 7.5), "moisture": (70, 85), "EC": (0.8, 1.5), "N": 150, "yield": 70, "value": 2.0, "icon": "🥬"},
    "Pepper": {"pH": (6.0, 7.5), "moisture": (65, 75), "EC": (1.0, 2.0), "N": 120, "yield": 50, "value": 3.0, "icon": "🫑"},
    "Cabbage": {"pH": (6.0, 7.5), "moisture": (65, 80), "EC": (0.5, 1.2), "N": 100, "yield": 60, "value": 0.8, "icon": "🥬"},
    "Broccoli": {"pH": (6.0, 7.5), "moisture": (65, 75), "EC": (0.8, 1.5), "N": 150, "yield": 30, "value": 2.5, "icon": "🥦"},
    "Cucumber": {"pH": (6.0, 7.0), "moisture": (70, 85), "EC": (1.0, 1.8), "N": 150, "yield": 60, "value": 1.5, "icon": "🥒"},
    "Carrot": {"pH": (6.0, 7.5), "moisture": (60, 75), "EC": (0.6, 1.2), "N": 80, "yield": 50, "value": 0.8, "icon": "🥕"},
    "Spinach": {"pH": (6.5, 7.5), "moisture": (65, 80), "EC": (1.0, 1.5), "N": 150, "yield": 40, "value": 2.0, "icon": "🥬"},
    "Potato": {"pH": (6.0, 7.0), "moisture": (65, 80), "EC": (0.8, 1.5), "N": 120, "yield": 50, "value": 0.6, "icon": "🥔"},
    "Onion": {"pH": (6.0, 7.5), "moisture": (50, 70), "EC": (0.6, 1.2), "N": 80, "yield": 50, "value": 0.7, "icon": "🧅"},
    "Green Beans": {"pH": (6.0, 7.5), "moisture": (60, 75), "EC": (0.8, 1.5), "N": 80, "yield": 12, "value": 3.0, "icon": "🫘"},
    "Asparagus": {"pH": (6.5, 7.5), "moisture": (60, 70), "EC": (0.5, 1.0), "N": 80, "yield": 4, "value": 4.0, "icon": "🌱"},
    "Strawberry": {"pH": (6.0, 7.0), "moisture": (70, 80), "EC": (1.0, 1.8), "N": 150, "yield": 35, "value": 5.0, "icon": "🍓"},
    "Blueberry": {"pH": (4.5, 5.5), "moisture": (70, 85), "EC": (0.4, 0.8), "N": 100, "yield": 8, "value": 6.0, "icon": "🫐"},
    "Garlic": {"pH": (6.0, 7.5), "moisture": (50, 65), "EC": (0.4, 1.0), "N": 60, "yield": 10, "value": 2.0, "icon": "🧄"},
    "Radish": {"pH": (6.0, 7.0), "moisture": (55, 70), "EC": (0.4, 0.8), "N": 80, "yield": 35, "value": 1.0, "icon": "🫰"},
    "Cauliflower": {"pH": (6.0, 7.5), "moisture": (65, 75), "EC": (0.8, 1.5), "N": 150, "yield": 35, "value": 2.5, "icon": "🥦"},
    "Olive": {"pH": (7.0, 8.5), "moisture": (40, 60), "EC": (1.0, 2.0), "N": 80, "yield": 4, "value": 3.0, "icon": "🫒"},
    "Beet": {"pH": (6.5, 7.5), "moisture": (70, 85), "EC": (1.0, 2.0), "N": 100, "yield": 50, "value": 0.7, "icon": "🍠"},
    "Celery": {"pH": (6.5, 7.5), "moisture": (75, 85), "EC": (1.2, 2.0), "N": 150, "yield": 50, "value": 1.5, "icon": "🌾"},
    "Zucchini": {"pH": (6.0, 7.5), "moisture": (70, 85), "EC": (1.0, 1.8), "N": 150, "yield": 50, "value": 1.5, "icon": "🥒"},
    "Pumpkin": {"pH": (6.0, 7.5), "moisture": (65, 80), "EC": (0.8, 1.5), "N": 100, "yield": 40, "value": 0.5, "icon": "🎃"},
    "Raspberry": {"pH": (6.0, 7.0), "moisture": (65, 75), "EC": (1.0, 1.5), "N": 120, "yield": 10, "value": 4.0, "icon": "🫐"},
}

# Global sensor set manager
SENSOR_SETS = {}
ACTIVE_SET = 0

# Configuration management functions
def init_default_sets():
    """Initialize 10 default sensor sets."""
    global SENSOR_SETS
    SENSOR_SETS = {
        0: {"name": "Set 1: Standard", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        1: {"name": "Set 2: Soil Only", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True, False, True, True, True, True, True, False, False, False]},
        2: {"name": "Set 3: Nutrients", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [False, False, False, False, True, True, True, False, False, False]},
        3: {"name": "Set 4: Environment", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [False, True, False, False, False, False, False, False, True, True]},
        4: {"name": "Set 5: Custom 1", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        5: {"name": "Set 6: Custom 2", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        6: {"name": "Set 7: Custom 3", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        7: {"name": "Set 8: Custom 4", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        8: {"name": "Set 9: Custom 5", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        9: {"name": "Set 10: Custom 6", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
    }

def load_sensor_sets():
    """Load all 10 sensor sets from file."""
    global SENSOR_SETS, ACTIVE_SET
    init_default_sets()  # Start with defaults
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                if 'sets' in config:
                    for i, set_data in enumerate(config['sets'][:10]):
                        if i < 10:
                            SENSOR_SETS[i] = set_data
                ACTIVE_SET = config.get('active_set', 0)
        except Exception as e:
            print(f"Error loading sets: {e}")

def save_sensor_sets():
    """Save all 10 sensor sets to file."""
    try:
        config = {'sets': [SENSOR_SETS[i] for i in range(10)], 'active_set': ACTIVE_SET}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving sets: {e}")

def get_active_set_data():
    """Get names and enabled list for active set."""
    if ACTIVE_SET in SENSOR_SETS:
        s = SENSOR_SETS[ACTIVE_SET]
        return s.get('names', [name for name, *_ in DEFAULT_READINGS]), \
               s.get('enabled', [True] * len(DEFAULT_READINGS))
    return [name for name, *_ in DEFAULT_READINGS], [True] * len(DEFAULT_READINGS)

def set_active_set(set_index):
    """Switch to a different sensor set."""
    global ACTIVE_SET
    if 0 <= set_index < 10:
        ACTIVE_SET = set_index
        save_sensor_sets()
        names, enabled = get_active_set_data()
        update_readings(names, enabled)

def update_readings(names, enabled):
    """Update READINGS list based on saved names and enabled sensors."""
    global READINGS
    READINGS = []
    for i, (_, unit, scale, min_w, max_w) in enumerate(DEFAULT_READINGS):
        if i < len(names) and i < len(enabled) and enabled[i]:
            READINGS.append((names[i], unit, scale, min_w, max_w))

def calculate_crop_score(crop: dict, moisture: float, temp: float, ec: float, ph: float, nitrogen: float) -> float:
    """Score a crop based on current soil conditions (0-100)."""
    score = 100.0
    
    # pH scoring
    ph_opt_min, ph_opt_max = crop["pH"]
    if ph < ph_opt_min or ph > ph_opt_max:
        ph_margin = min(abs(ph - ph_opt_min), abs(ph - ph_opt_max))
        score -= min(30, ph_margin * 5)
    
    # Moisture scoring
    moisture_opt_min, moisture_opt_max = crop["moisture"]
    if moisture < moisture_opt_min or moisture > moisture_opt_max:
        moisture_margin = min(abs(moisture - moisture_opt_min), abs(moisture - moisture_opt_max))
        score -= min(25, moisture_margin * 0.5)
    
    # EC scoring
    ec_opt_min, ec_opt_max = crop["EC"]
    if ec < ec_opt_min or ec > ec_opt_max:
        ec_margin = min(abs(ec - ec_opt_min), abs(ec - ec_opt_max))
        score -= min(20, ec_margin * 0.3)
    
    # Temperature range bonus (15-25°C is ideal)
    if 15 <= temp <= 25:
        score += 5
    elif 10 <= temp < 15 or 25 < temp <= 30:
        score -= 10
    
    # Nitrogen scoring
    if nitrogen < crop["N"] * 0.5:
        score -= 15
    elif nitrogen < crop["N"]:
        score -= 5
    
    return max(0, min(100, score))


class SensorSettingsDialog(QDialog):
    """Dialog for editing sensor names and enabling/disabling sensors."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sensor Configuration")
        self.setGeometry(100, 100, 600, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #000033;
            }
            QLabel {
                color: #00FFFF;
            }
            QLineEdit {
                background-color: #1a1a4d;
                color: #00FF00;
                border: 2px solid #00FFFF;
                padding: 4px;
            }
            QCheckBox {
                color: #00FFFF;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #00FFFF;
                background-color: #000033;
            }
            QCheckBox::indicator:checked {
                background-color: #00FF00;
            }
            QPushButton {
                background-color: #FF00FF;
                color: #000033;
                border: 2px solid #FF00FF;
                padding: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF66FF;
            }
        """)
        
        self.sensor_inputs = []
        self.sensor_checks = []
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("⚙ SENSOR CONFIGURATION ⚙")
        title_font = QFont("Courier New", 12)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Set name editor section
        set_name_layout = QHBoxLayout()
        set_name_label = QLabel("SET NAME:")
        set_name_label.setStyleSheet("color: #00FFFF; font-weight: bold;")
        set_name_layout.addWidget(set_name_label)
        
        self.set_name_input = QLineEdit()
        current_set_name = SENSOR_SETS[ACTIVE_SET]['name'] if ACTIVE_SET in SENSOR_SETS else "Unknown Set"
        self.set_name_input.setText(current_set_name)
        self.set_name_input.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a4d;
                color: #00FF00;
                border: 2px solid #FF00FF;
                padding: 4px;
                font-weight: bold;
            }
        """)
        set_name_layout.addWidget(self.set_name_input, stretch=1)
        
        layout.addLayout(set_name_layout)
        layout.addSpacing(10)
        
        # Scroll area for sensor configs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Load current set config
        names, enabled = get_active_set_data()
        
        # Create input fields for each sensor
        for i, (default_name, unit, *_) in enumerate(DEFAULT_READINGS):
            h_layout = QHBoxLayout()
            
            # Checkbox to enable/disable
            check = QCheckBox()
            check.setChecked(enabled[i] if i < len(enabled) else True)
            self.sensor_checks.append(check)
            h_layout.addWidget(check)
            
            # Sensor number label
            num_label = QLabel(f"S{i+1}:")
            num_label.setMinimumWidth(30)
            h_layout.addWidget(num_label)
            
            # Name input
            input_field = QLineEdit()
            input_field.setText(names[i] if i < len(names) else default_name)
            input_field.setPlaceholderText(default_name)
            self.sensor_inputs.append(input_field)
            h_layout.addWidget(input_field, stretch=1)
            
            # Unit label
            unit_label = QLabel(f"[{unit}]")
            unit_label.setMinimumWidth(80)
            unit_label.setStyleSheet("color: #FF00FF;")
            h_layout.addWidget(unit_label)
            
            scroll_layout.addLayout(h_layout)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 SAVE & APPLY")
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)
        
        reset_btn = QPushButton("↺ RESET TO DEFAULTS")
        reset_btn.clicked.connect(self.reset_defaults)
        button_layout.addWidget(reset_btn)
        
        close_btn = QPushButton("✗ CLOSE")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def save_config(self):
        """Save sensor configuration to active set."""
        names = [field.text() or f"Sensor_{i+1}" for i, field in enumerate(self.sensor_inputs)]
        enabled = [check.isChecked() for check in self.sensor_checks]
        set_name = self.set_name_input.text().strip() or f"Set {ACTIVE_SET + 1}"
        
        # Update active set with new config
        if ACTIVE_SET in SENSOR_SETS:
            SENSOR_SETS[ACTIVE_SET]['names'] = names
            SENSOR_SETS[ACTIVE_SET]['enabled'] = enabled
            SENSOR_SETS[ACTIVE_SET]['name'] = set_name
        
        save_sensor_sets()
        update_readings(names, enabled)
        
        # Signal parent to reload dashboard and update set selector
        if self.parent() and hasattr(self.parent(), 'reload_dashboard'):
            self.parent().reload_dashboard()
        if self.parent() and hasattr(self.parent(), 'update_set_selector'):
            self.parent().update_set_selector()
    
    def reset_defaults(self):
        """Reset all sensor names to defaults."""
        for i, input_field in enumerate(self.sensor_inputs):
            default_name = DEFAULT_READINGS[i][0]
            input_field.setText(default_name)
        
        for check in self.sensor_checks:
            check.setChecked(True)


class SensorWorker(QObject):
    """Background worker thread for sensor polling."""
    data_updated = Signal(list)  # emits list of values or None on error
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.port = None
        self.last_read = 0

    def crc16(self, data: bytes) -> int:
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        return crc

    def read_registers(self):
        if self.port is None or not self.port.is_open:
            return None
        try:
            req = bytes([SLAVE_ID, 0x03, 0x00, 0x00, 0x00, 0x08])
            c = self.crc16(req)
            req += bytes([c & 0xFF, c >> 8])

            self.port.reset_input_buffer()
            self.port.write(req)
            self.port.flush()

            resp = self.port.read(21)
            if len(resp) != 21:
                return None
            if resp[0] != SLAVE_ID or resp[1] != 0x03 or resp[2] != 16:
                return None
            resp_crc = (resp[20] << 8) | resp[19]
            if self.crc16(resp[:19]) != resp_crc:
                return None

            values = []
            for i, (_, _, scale, _, _) in enumerate(READINGS):
                raw = (resp[3 + i * 2] << 8) | resp[4 + i * 2]
                values.append(raw / scale if scale > 1 else float(raw))
            return values
        except Exception as e:
            print(f"Read error: {e}")
            return None

    def run(self):
        """Main worker loop."""
        try:
            self.port = serial.Serial(PORT, BAUD, timeout=1.5)
            self.status_changed.emit(f"Connected to {PORT}")
        except serial.SerialException as e:
            self.status_changed.emit(f"Error: {e}")
            return

        while self.running:
            now = time.time() * 1000
            if now - self.last_read >= POLL_INTERVAL:
                values = self.read_registers()
                if values:
                    self.data_updated.emit(values)
                    self.status_changed.emit("● Connected")
                else:
                    self.data_updated.emit(None)
                    self.status_changed.emit("✗ No response")
                self.last_read = now
            time.sleep(0.1)

        if self.port and self.port.is_open:
            self.port.close()

    def stop(self):
        self.running = False


class SensorCard(QFrame):
    """Individual sensor reading card — Amiga 500 retro style."""
    def __init__(self, name: str, unit: str, min_warn: float, max_warn: float):
        super().__init__()
        self.name = name
        self.unit = unit
        self.min_warn = min_warn
        self.max_warn = max_warn
        self.value = None

        # Amiga-style: thick chunky borders, bright cyan/magenta
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(3)
        self.setStyleSheet("""
            SensorCard {
                background-color: #000033;
                border: 3px solid #00FFFF;
                border-radius: 0px;
                padding: 12px;
            }
        """)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Name label — cyan header
        name_label = QLabel(name)
        name_font = QFont("Courier New")
        name_font.setPointSize(9)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #00FFFF; background-color: #000033; padding: 4px;")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        # Value label — lime green for good contrast
        self.value_label = QLabel("--")
        value_font = QFont("Courier New")
        value_font.setPointSize(18)
        value_font.setBold(True)
        self.value_label.setFont(value_font)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("color: #00FF00; background-color: #000033; padding: 6px;")
        layout.addWidget(self.value_label)

        # Unit label — magenta
        unit_label = QLabel(unit)
        unit_font = QFont("Courier New")
        unit_font.setPointSize(8)
        unit_font.setBold(True)
        unit_label.setFont(unit_font)
        unit_label.setStyleSheet("color: #FF00FF; background-color: #000033;")
        unit_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(unit_label)

        # Range label — yellow (dim)
        range_label = QLabel(f"[{min_warn}–{max_warn}]")
        range_font = QFont("Courier New")
        range_font.setPointSize(7)
        range_label.setFont(range_font)
        range_label.setStyleSheet("color: #FFFF00; background-color: #000033;")
        range_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(range_label)

    def set_value(self, value: float | None):
        """Update the displayed value and color — Amiga 80s style."""
        self.value = value
        if value is None:
            self.value_label.setText("--")
            self.value_label.setStyleSheet("color: #333333; background-color: #000033;")
        else:
            fmt = f".1f" if isinstance(value, float) and value != int(value) else ".0f"
            self.value_label.setText(f"{value:{fmt}}")

            # Amiga color coding: Lime green (good), Yellow (warning), Dark (zero)
            if value == 0.0:
                color = "#333333"  # dark gray for zeros
            elif self.min_warn <= value <= self.max_warn:
                color = "#00FF00"  # bright lime green = good
            else:
                color = "#FFFF00"  # bright yellow = warning

            self.value_label.setStyleSheet(f"color: {color}; background-color: #000033;")


class CropRecommendationBox(QFrame):
    """Large recommendation box showing best crops for current conditions."""
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(3)
        self.setStyleSheet("""
            CropRecommendationBox {
                background-color: #000033;
                border: 3px solid #FF00FF;
                border-radius: 0px;
                padding: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Title label
        title = QLabel("🌾 CROP RECOMMENDATIONS 🌾")
        title_font = QFont("Courier New", 12)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #00FF00; background-color: transparent;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Scrollable recommendation area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #000033;
                border: 2px solid #00FFFF;
            }
            QScrollBar:vertical {
                background-color: #000033;
                border: 1px solid #00FFFF;
                width: 14px;
            }
            QScrollBar::handle:vertical {
                background-color: #FF00FF;
                border-radius: 7px;
                min-height: 20px;
            }
        """)

        self.recommendation_content = QLabel("")
        self.recommendation_content.setWordWrap(True)
        self.recommendation_content.setStyleSheet("""
            color: #00FF00;
            background-color: #000033;
            padding: 8px;
        """)
        rec_font = QFont("Courier New", 9)
        self.recommendation_content.setFont(rec_font)
        self.recommendation_content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.recommendation_content)

        layout.addWidget(scroll)

    def update_recommendations(self, moisture: float | None, temp: float | None, ec: float | None, 
                               ph: float | None, nitrogen: float | None):
        """Score all crops and display top recommendations."""
        if None in [moisture, temp, ec, ph, nitrogen]:
            self.recommendation_content.setText("⏳ Awaiting sensor data...")
            return

        # Score all crops
        scores = {}
        for crop_name, crop_data in CROPS.items():
            score = calculate_crop_score(crop_data, moisture, temp, ec, ph, nitrogen)
            scores[crop_name] = score

        # Sort by score
        sorted_crops = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_crops = sorted_crops[:6]  # Top 6 recommendations

        # Format recommendations
        rec_text = "TOP CROPS FOR YOUR SOIL:\n"
        rec_text += "─" * 50 + "\n\n"

        for rank, (crop_name, score) in enumerate(top_crops, 1):
            crop_data = CROPS[crop_name]
            icon = crop_data.get("icon", "🌱")
            
            # Color code by score
            if score >= 80:
                symbol = "✓✓✓"  # Excellent
            elif score >= 60:
                symbol = "✓✓"   # Good
            elif score >= 40:
                symbol = "✓"    # Okay
            else:
                symbol = "△"    # Poor

            profitability = (crop_data["yield"] * crop_data["value"]) / 1000  # €k/hectare
            rec_text += f"{rank}. {icon} {crop_name.upper():15} {symbol}  [{score:.0f}%]\n"
            rec_text += f"   Yield: {crop_data['yield']:.0f}t/ha | Value: €{profitability:.1f}k/ha\n"
            
            # Show what's limiting
            limiting = []
            ph_opt_min, ph_opt_max = crop_data["pH"]
            if not (ph_opt_min <= ph <= ph_opt_max):
                limiting.append(f"pH {ph:.1f} (need {ph_opt_min:.1f}-{ph_opt_max:.1f})")
            
            moisture_opt_min, moisture_opt_max = crop_data["moisture"]
            if not (moisture_opt_min <= moisture <= moisture_opt_max):
                limiting.append(f"Moisture {moisture:.0f}% (need {moisture_opt_min:.0f}-{moisture_opt_max:.0f}%)")
            
            if nitrogen < crop_data["N"] * 0.7:
                limiting.append(f"Low N: {nitrogen:.0f}mg/kg (need >{crop_data['N']:.0f})")
            
            if limiting:
                rec_text += f"   ⚠ Limiting: {', '.join(limiting)}\n"
            
            rec_text += "\n"

        # Add soil analysis summary
        rec_text += "─" * 50 + "\n"
        rec_text += "SOIL PROFILE:\n"
        
        if 6.0 <= ph <= 7.5:
            rec_text += f"✓ pH {ph:.1f} — Excellent for most crops\n"
        elif 5.5 <= ph < 6.0:
            rec_text += f"△ pH {ph:.1f} — Slightly acidic\n"
        elif 7.5 < ph <= 8.0:
            rec_text += f"△ pH {ph:.1f} — Slightly alkaline\n"
        else:
            rec_text += f"✗ pH {ph:.1f} — Consider lime/sulfur amendment\n"

        if 60 <= moisture <= 75:
            rec_text += f"✓ Moisture {moisture:.0f}% — Optimal\n"
        elif moisture < 40:
            rec_text += f"✗ Moisture {moisture:.0f}% — Too dry, add compost\n"
        else:
            rec_text += f"✗ Moisture {moisture:.0f}% — Too wet, improve drainage\n"

        if nitrogen >= 100:
            rec_text += f"✓ N {nitrogen:.0f}mg/kg — Adequate\n"
        else:
            rec_text += f"✗ N {nitrogen:.0f}mg/kg — Add fertilizer\n"

        self.recommendation_content.setText(rec_text)


class HistoryBox(QFrame):
    """Display last 10 sensor readings with statistics."""
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(3)
        self.setStyleSheet("""
            HistoryBox {
                background-color: #000033;
                border: 3px solid #FFFF00;
                border-radius: 0px;
                padding: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Title label
        title = QLabel("📊 SENSOR HISTORY (Max 10) 📊")
        title_font = QFont("Courier New", 12)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #FFFF00; background-color: transparent;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Scrollable history area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #000033;
                border: 2px solid #FFFF00;
            }
            QScrollBar:vertical {
                background-color: #000033;
                border: 1px solid #FFFF00;
                width: 14px;
            }
            QScrollBar::handle:vertical {
                background-color: #00FF00;
                border-radius: 7px;
                min-height: 20px;
            }
        """)

        self.history_content = QLabel("")
        self.history_content.setWordWrap(True)
        self.history_content.setStyleSheet("""
            color: #00FF00;
            background-color: #000033;
            padding: 8px;
        """)
        hist_font = QFont("Courier New", 8)
        self.history_content.setFont(hist_font)
        self.history_content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.history_content)

        layout.addWidget(scroll)

    def update_history(self, history: deque):
        """Display historical readings and calculate statistics."""
        if not history:
            self.history_content.setText("⏳ No readings yet...")
            return

        # Calculate statistics per sensor
        stats = [{} for _ in range(8)]
        for reading in history:
            for i in range(8):
                if i not in stats[i]:
                    stats[i] = {"min": reading[i], "max": reading[i], "sum": 0, "count": 0}
                stats[i]["min"] = min(stats[i]["min"], reading[i])
                stats[i]["max"] = max(stats[i]["max"], reading[i])
                stats[i]["sum"] += reading[i]
                stats[i]["count"] += 1

        # Format history display
        hist_text = f"READINGS: {len(history)}/10\n"
        hist_text += "─" * 65 + "\n\n"

        # Show each reading with timestamp
        for idx, reading in enumerate(history, 1):
            timestamp = reading[-1]  # Last element is timestamp string
            hist_text += f"{idx}. [{timestamp}]\n"
            for i, (name, unit, _, _, _) in enumerate(READINGS):
                value = reading[i]
                fmt = f".1f" if isinstance(value, float) and value != int(value) else ".0f"
                hist_text += f"   {name:12} {value:{fmt}} {unit}\n"
            hist_text += "\n"

        # Show statistics
        hist_text += "─" * 65 + "\n"
        hist_text += "STATISTICS (Min / Avg / Max):\n"
        hist_text += "─" * 65 + "\n"

        for i, (name, unit, _, _, _) in enumerate(READINGS):
            if i in stats and stats[i]["count"] > 0:
                min_v = stats[i]["min"]
                avg_v = stats[i]["sum"] / stats[i]["count"]
                max_v = stats[i]["max"]
                fmt = ".1f" if isinstance(min_v, float) and min_v != int(min_v) else ".0f"
                hist_text += f"{name:14} {min_v:{fmt}} / {avg_v:{fmt}} / {max_v:{fmt}} {unit}\n"

        self.history_content.setText(hist_text)


class SensorDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Load sensor sets first
        load_sensor_sets()
        names, enabled = get_active_set_data()
        update_readings(names, enabled)
        
        self.setWindowTitle("SOIL SENSOR v1.0 — Amiga 500")
        self.setGeometry(100, 100, 1600, 900)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #000033;
            }
            QLabel {
                color: #00FFFF;
            }
            QStatusBar {
                background-color: #000033;
                color: #00FFFF;
                border-top: 2px solid #00FFFF;
            }
        """)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)

        # Title bar — Amiga Workbench style with settings button
        title_frame = QFrame()
        title_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        title_frame.setLineWidth(2)
        title_frame.setStyleSheet("""
            QFrame {
                background-color: #000033;
                border: 2px solid #00FFFF;
                border-bottom: 2px solid #FF00FF;
                padding: 10px;
            }
        """)
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(12, 8, 12, 8)

        # Settings button - left side
        settings_btn = QPushButton("⚙ SETTINGS")
        settings_btn.setMaximumWidth(120)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF00FF;
                color: #000033;
                border: 2px solid #FF00FF;
                font-family: 'Courier New';
                font-weight: bold;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #FF66FF;
            }
        """)
        settings_btn.clicked.connect(self.open_settings)
        title_layout.addWidget(settings_btn)
        
        # Title - center with SET selector
        title_layout_inner = QHBoxLayout()
        
        title = QLabel("≡ SOIL SENSOR TERMINAL v1.0 ≡")
        title_font = QFont("Courier New", 14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #00FFFF; background-color: transparent;")
        title.setAlignment(Qt.AlignCenter)
        title_layout_inner.addWidget(title)
        
        # Set selector dropdown
        title_layout_inner.addSpacing(20)
        set_label = QLabel("SET:")
        set_label.setStyleSheet("color: #00FFFF; font-family: 'Courier New'; font-weight: bold;")
        title_layout_inner.addWidget(set_label)
        
        self.set_selector = QComboBox()
        self.set_selector.setMaximumWidth(200)
        for i in range(10):
            self.set_selector.addItem(SENSOR_SETS[i]['name'], i)
        self.set_selector.setCurrentIndex(ACTIVE_SET)
        self.set_selector.currentIndexChanged.connect(self.on_set_changed)
        self.set_selector.setStyleSheet("""
            QComboBox {
                background-color: #000033;
                color: #00FFFF;
                border: 2px solid #00FFFF;
                font-family: 'Courier New';
                font-weight: bold;
                padding: 4px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
            }
            QComboBox QAbstractItemView {
                background-color: #000033;
                color: #00FFFF;
                selection-background-color: #FF00FF;
                border: 2px solid #FF00FF;
            }
        """)
        title_layout_inner.addWidget(self.set_selector)
        title_layout_inner.addStretch()
        
        # Create a widget to hold the inner layout
        title_inner_widget = QWidget()
        title_inner_widget.setLayout(title_layout_inner)
        title_layout.addWidget(title_inner_widget, stretch=1)
        
        # Empty spacer for symmetry
        spacer = QLabel("")
        spacer.setMaximumWidth(120)
        title_layout.addWidget(spacer)

        self.main_layout.addWidget(title_frame)

        # Content layout - will be built dynamically
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(16)
        
        # Left side: Grid of sensor cards (will be created dynamically)
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(12)
        self.cards = []
        self.build_sensor_grid()
        self.left_layout.addLayout(self.grid_layout)
        self.left_widget.setMinimumWidth(600)
        self.content_layout.addWidget(self.left_widget, stretch=0)

        # Right side: Tabs for Recommendations and History
        right_tabs = QTabWidget()
        right_tabs.setStyleSheet("""
            QTabWidget {
                background-color: #000033;
                color: #00FFFF;
            }
            QTabBar::tab {
                background-color: #000033;
                color: #00FFFF;
                border: 2px solid #00FFFF;
                padding: 8px 20px;
                margin-right: 2px;
                font-family: 'Courier New';
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #00FFFF;
                color: #000033;
                border: 2px solid #00FFFF;
            }
        """)

        self.recommendation_box = CropRecommendationBox()
        self.history_box = HistoryBox()

        right_tabs.addTab(self.recommendation_box, "🌾 CROPS")
        right_tabs.addTab(self.history_box, "📊 HISTORY")

        right_tabs.setMinimumWidth(500)
        self.content_layout.addWidget(right_tabs, stretch=1)

        self.main_layout.addLayout(self.content_layout, stretch=1)

        # Status bar — retro Amiga style
        status = self.statusBar()
        status.showMessage("► INITIALIZING...")
        status.setStyleSheet("""
            QStatusBar {
                background-color: #000033;
                color: #00FF00;
                border-top: 2px solid #00FFFF;
                font-family: 'Courier New';
                font-weight: bold;
            }
        """)

        # Store current sensor values (size based on enabled sensors)
        self.current_values = [None] * len(READINGS)
        # History: deque with max 10 readings, each is list of values + timestamp
        self.reading_history = deque(maxlen=10)

        # Worker thread
        self.worker = SensorWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.data_updated.connect(self.on_data_updated)
        self.worker.status_changed.connect(self.on_status_changed)

        self.worker_thread.start()
    
    def build_sensor_grid(self):
        """Build or rebuild the sensor card grid based on enabled sensors."""
        # Clear old cards
        while self.grid_layout.count():
            self.grid_layout.takeAt(0).widget().deleteLater()
        self.cards = []
        
        # Create new cards
        for i, (name, unit, scale, min_w, max_w) in enumerate(READINGS):
            card = SensorCard(name, unit, min_w, max_w)
            row = i // 4
            col = i % 4
            self.grid_layout.addWidget(card, row, col)
            self.cards.append(card)
    
    def open_settings(self):
        """Open sensor settings dialog."""
        dialog = SensorSettingsDialog(self)
        dialog.exec()
    
    def reload_dashboard(self):
        """Reload dashboard with new sensor configuration."""
        self.current_values = [None] * len(READINGS)
        self.reading_history.clear()
        self.build_sensor_grid()
    
    def update_set_selector(self):
        """Update set selector dropdown with latest names."""
        # Disconnect signal to avoid triggering on_set_changed
        self.set_selector.currentIndexChanged.disconnect()
        
        # Clear and repopulate
        self.set_selector.clear()
        for i in range(10):
            self.set_selector.addItem(SENSOR_SETS[i]['name'], i)
        
        # Set to current active set
        self.set_selector.setCurrentIndex(ACTIVE_SET)
        
        # Reconnect signal
        self.set_selector.currentIndexChanged.connect(self.on_set_changed)

    def on_data_updated(self, values: list | None):
        """Update card displays with new sensor data and store in history."""
        if values is None:
            for card in self.cards:
                card.set_value(None)
            self.current_values = [None] * 8
        else:
            for card, value in zip(self.cards, values):
                card.set_value(value)
            self.current_values = values
            
            # Add to history with timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            history_entry = list(values) + [timestamp]
            self.reading_history.append(history_entry)
            
            # Update history display
            self.history_box.update_history(self.reading_history)
            
            # Update crop recommendations based on soil conditions
            # Map sensor values to parameters: moisture, temp, ec, ph, nitrogen
            if len(values) >= 8:
                moisture = values[0]  # Moisture %
                temp = values[1]      # Temperature °C
                ec = values[2]        # EC µS/cm (convert to mS/cm for scoring)
                ph = values[3]        # pH
                nitrogen = values[4]  # Nitrogen mg/kg
                
                # Convert EC from µS/cm to mS/cm for crop requirements
                ec_ms = ec / 1000 if ec > 0 else 0.5
                
                self.recommendation_box.update_recommendations(moisture, temp, ec_ms, ph, nitrogen)

    def on_set_changed(self, index: int):
        """Handle sensor set change via dropdown."""
        if 0 <= index < 10:
            set_active_set(index)
            names, enabled = get_active_set_data()
            update_readings(names, enabled)
            self.reload_dashboard()

    def on_status_changed(self, status: str):
        """Update status bar with Amiga retro formatting."""
        # Convert to Amiga terminal style
        if "Connected" in status:
            msg = "► CONNECTED | MODBUS RTU @ 9600,8,N,1"
        elif "No response" in status:
            msg = "✗ NO RESPONSE | AWAITING SENSOR..."
        else:
            msg = f"► {status.upper()}"
        self.statusBar().showMessage(msg)

    def closeEvent(self, event):
        """Clean shutdown."""
        self.worker.stop()
        self.worker_thread.quit()
        self.worker_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    dashboard = SensorDashboard()
    dashboard.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
