#!/usr/bin/env python3
"""
Soil Sensor Web Application — Flask
Modbus RTU via USB CH340, Slave ID 1, 9600 baud
Crop recommendations + time-range history graphing
Running on Raspberry Pi Zero
"""

from flask import Flask, render_template, jsonify, request
import serial
import threading
import json
import os
import time
from datetime import datetime
from collections import deque

app = Flask(__name__)

PORT = "/dev/ttyUSB0"
BAUD = 9600
SLAVE_ID = 1
DEFAULT_POLL_INTERVAL = 10.0  # seconds
POLL_INTERVAL = DEFAULT_POLL_INTERVAL
MODBUS_REGISTER_COUNT = 8

ALLOWED_POLL_INTERVALS = (10.0, 30.0, 60.0, 300.0, 1800.0, 3600.0)

HISTORY_RANGE_CONFIG = {
    'hour': {'maxlen': 60},
    'day': {'maxlen': 288},
    'week': {'maxlen': 168},
    'month': {'maxlen': 31},
    'year': {'maxlen': 12},
}
app.config['JSON_SORT_KEYS'] = False

MOBILE_USER_AGENT_HINTS = (
    'android', 'iphone', 'ipad', 'ipod', 'mobile', 'blackberry',
    'windows phone', 'opera mini', 'opera mobi', 'webos'
)

# Default sensor configuration (8 sensors total)
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
]

READINGS = DEFAULT_READINGS[:]
CONFIG_FILE = os.path.expanduser("~/.8sense_config.json")

# Crop database
CROPS = {
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

COMMERCIAL_FERTILIZERS = [
    {"name": "Balanced All-Purpose", "label": "10-10-10", "ratio": (10.0, 10.0, 10.0), "use": "general maintenance"},
    {"name": "Water-Soluble Balanced", "label": "20-20-20", "ratio": (20.0, 20.0, 20.0), "use": "fast all-purpose feeding"},
    {"name": "Starter Feed", "label": "5-10-10", "ratio": (5.0, 10.0, 10.0), "use": "root establishment"},
    {"name": "Bloom Booster", "label": "10-30-20", "ratio": (10.0, 30.0, 20.0), "use": "flowering and fruiting"},
    {"name": "Lawn Feed", "label": "15-5-10", "ratio": (15.0, 5.0, 10.0), "use": "leaf-heavy growth"},
    {"name": "Foliage Formula", "label": "3-1-2", "ratio": (3.0, 1.0, 2.0), "use": "vegetative growth"},
    {"name": "Houseplant Feed", "label": "24-8-16", "ratio": (24.0, 8.0, 16.0), "use": "container feeding"},
    {"name": "Fruit & Flower", "label": "4-6-8", "ratio": (4.0, 6.0, 8.0), "use": "flower and fruit support"},
]

# Global state
SENSOR_SETS = {}
ACTIVE_SET = 0
UI_THEME = 'retro'
OPERATION_MODE = 'continuous'
SENSOR_POLL_INTERVAL = DEFAULT_POLL_INTERVAL
current_values = None
history_ranges = {name: deque(maxlen=config['maxlen']) for name, config in HISTORY_RANGE_CONFIG.items()}
history_buckets = {name: None for name in HISTORY_RANGE_CONFIG}
sensor_status = "► INITIALIZING..."
last_update = None
port = None
serial_thread = None
stop_event = threading.Event()
port_lock = threading.Lock()

# Configuration functions
def init_default_sets():
    """Initialize 10 default sensor sets."""
    global SENSOR_SETS
    SENSOR_SETS = {
        0: {"name": "Set 1: Standard", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        1: {"name": "Set 2: Soil Only", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True, False, True, True, True, True, True, False]},
        2: {"name": "Set 3: Nutrients", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [False, False, False, False, True, True, True, False]},
        3: {"name": "Set 4: Environment", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [False, True, False, False, False, False, False, True]},
        4: {"name": "Set 5: Custom 1", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        5: {"name": "Set 6: Custom 2", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        6: {"name": "Set 7: Custom 3", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        7: {"name": "Set 8: Custom 4", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        8: {"name": "Set 9: Custom 5", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
        9: {"name": "Set 10: Custom 6", "names": [name for name, *_ in DEFAULT_READINGS], "enabled": [True] * len(DEFAULT_READINGS)},
    }


def normalize_sensor_set(set_data, fallback_name):
    """Normalize persisted sensor-set data to match current defaults."""
    names = list(set_data.get('names', []))[:len(DEFAULT_READINGS)]
    enabled = list(set_data.get('enabled', []))[:len(DEFAULT_READINGS)]
    default_names = [name for name, *_ in DEFAULT_READINGS]

    if len(names) < len(DEFAULT_READINGS):
        names.extend(default_names[len(names):])
    if len(enabled) < len(DEFAULT_READINGS):
        enabled.extend([True] * (len(DEFAULT_READINGS) - len(enabled)))

    return {
        'name': set_data.get('name', fallback_name),
        'names': names,
        'enabled': enabled,
    }

def load_sensor_sets():
    """Load all 10 sensor sets from file."""
    global SENSOR_SETS, ACTIVE_SET, UI_THEME, OPERATION_MODE, SENSOR_POLL_INTERVAL, POLL_INTERVAL
    init_default_sets()
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                if 'sets' in config:
                    for i, set_data in enumerate(config['sets'][:10]):
                        if i < 10:
                            SENSOR_SETS[i] = normalize_sensor_set(set_data, SENSOR_SETS[i]['name'])
                ACTIVE_SET = config.get('active_set', 0)
                UI_THEME = config.get('ui_theme', 'retro')
                OPERATION_MODE = config.get('operation_mode', 'continuous')
                if OPERATION_MODE not in ('analysis', 'continuous'):
                    OPERATION_MODE = 'continuous'
                SENSOR_POLL_INTERVAL = float(config.get('sensor_poll_interval', DEFAULT_POLL_INTERVAL))
                if SENSOR_POLL_INTERVAL not in ALLOWED_POLL_INTERVALS:
                    SENSOR_POLL_INTERVAL = DEFAULT_POLL_INTERVAL
                POLL_INTERVAL = SENSOR_POLL_INTERVAL
        except Exception as e:
            print(f"Error loading sets: {e}")

def save_sensor_sets():
    """Save all 10 sensor sets to file."""
    try:
        config = {
            'sets': [normalize_sensor_set(SENSOR_SETS[i], f"Set {i + 1}") for i in range(10)],
            'active_set': ACTIVE_SET,
            'ui_theme': UI_THEME,
            'operation_mode': OPERATION_MODE,
            'sensor_poll_interval': SENSOR_POLL_INTERVAL,
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving sets: {e}")


def set_operation_mode(mode: str):
    """Update the active operating mode."""
    global OPERATION_MODE, sensor_status

    OPERATION_MODE = mode if mode in ('analysis', 'continuous') else 'continuous'
    if port is not None and port.is_open:
        if OPERATION_MODE == 'analysis':
            sensor_status = '◼ Analysis mode — waiting for manual run'
        else:
            sensor_status = '● Continuous mode'


def set_sensor_poll_interval(interval_seconds):
    """Update the global sensor polling interval."""
    global SENSOR_POLL_INTERVAL, POLL_INTERVAL

    try:
        interval_value = float(interval_seconds)
    except (TypeError, ValueError):
        interval_value = DEFAULT_POLL_INTERVAL

    if interval_value not in ALLOWED_POLL_INTERVALS:
        interval_value = DEFAULT_POLL_INTERVAL

    SENSOR_POLL_INTERVAL = interval_value
    POLL_INTERVAL = interval_value

def get_active_set_data():
    """Get names and enabled list for active set."""
    if ACTIVE_SET in SENSOR_SETS:
        s = SENSOR_SETS[ACTIVE_SET]
        return s.get('names', [name for name, *_ in DEFAULT_READINGS]), \
               s.get('enabled', [True] * len(DEFAULT_READINGS))
    return [name for name, *_ in DEFAULT_READINGS], [True] * len(DEFAULT_READINGS)

def update_readings(names, enabled):
    """Update READINGS list based on saved names and enabled sensors."""
    global READINGS
    READINGS = []
    for i, (_, unit, scale, min_w, max_w) in enumerate(DEFAULT_READINGS):
        if i < len(names) and i < len(enabled) and enabled[i]:
            READINGS.append((i, names[i], unit, scale, min_w, max_w))

def get_sensor_value_by_default_index(values, default_index):
    """Return a sensor value by its original DEFAULT_READINGS index."""
    if not values:
        return None

    for idx, (source_index, *_rest) in enumerate(READINGS):
        if source_index == default_index and idx < len(values):
            return values[idx]
    return None

def get_bucket_start(timestamp: datetime, range_name: str) -> datetime:
    """Return normalized bucket start time for a history range."""
    if range_name == 'hour':
        return timestamp.replace(second=0, microsecond=0)
    if range_name == 'day':
        minute = (timestamp.minute // 5) * 5
        return timestamp.replace(minute=minute, second=0, microsecond=0)
    if range_name == 'week':
        return timestamp.replace(minute=0, second=0, microsecond=0)
    if range_name == 'month':
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_name == 'year':
        return timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return timestamp.replace(second=0, microsecond=0)

def format_bucket_label(timestamp: datetime, range_name: str) -> str:
    """Format a display label for a history bucket."""
    if range_name == 'hour':
        return timestamp.strftime('%H:%M')
    if range_name == 'day':
        return timestamp.strftime('%H:%M')
    if range_name == 'week':
        return timestamp.strftime('%a %H:%M')
    if range_name == 'month':
        return timestamp.strftime('%d %b')
    if range_name == 'year':
        return timestamp.strftime('%b %Y')
    return timestamp.isoformat(timespec='seconds')

def create_history_bucket(bucket_start: datetime, values):
    """Create an accumulation bucket for averaged history values."""
    length = len(values)
    return {
        'timestamp': bucket_start,
        'sums': [0.0] * length,
        'counts': [0] * length,
    }

def add_values_to_bucket(bucket, values):
    """Accumulate numeric values into a history bucket."""
    for index, value in enumerate(values):
        if isinstance(value, (int, float)):
            bucket['sums'][index] += float(value)
            bucket['counts'][index] += 1

def serialize_bucket(bucket, range_name: str):
    """Convert a bucket into API-safe averaged history data."""
    averaged_values = []
    for total, count in zip(bucket['sums'], bucket['counts']):
        averaged_values.append(total / count if count else None)

    return {
        'timestamp': bucket['timestamp'].isoformat(),
        'label': format_bucket_label(bucket['timestamp'], range_name),
        'values': averaged_values,
    }

def add_history_sample(values, timestamp: datetime):
    """Add one sample to all graph history ranges."""
    global history_buckets

    for range_name in HISTORY_RANGE_CONFIG:
        bucket_start = get_bucket_start(timestamp, range_name)
        bucket = history_buckets[range_name]

        if bucket is None or bucket['timestamp'] != bucket_start:
            if bucket is not None:
                history_ranges[range_name].append(serialize_bucket(bucket, range_name))
            bucket = create_history_bucket(bucket_start, values)
            history_buckets[range_name] = bucket

        add_values_to_bucket(bucket, values)

def get_serialized_history_ranges():
    """Return finalized history plus the current in-progress bucket."""
    serialized = {}
    for range_name in HISTORY_RANGE_CONFIG:
        items = list(history_ranges[range_name])
        bucket = history_buckets[range_name]
        if bucket is not None:
            items.append(serialize_bucket(bucket, range_name))
        serialized[range_name] = items
    return serialized

def clear_history_ranges():
    """Reset all stored history when sensor configuration changes."""
    global history_ranges, history_buckets
    history_ranges = {
        name: deque(maxlen=config['maxlen'])
        for name, config in HISTORY_RANGE_CONFIG.items()
    }
    history_buckets = {name: None for name in HISTORY_RANGE_CONFIG}

def is_mobile_user_agent(user_agent: str) -> bool:
    """Return True when the request likely comes from a mobile device."""
    if not user_agent:
        return False

    normalized = user_agent.lower()
    return any(hint in normalized for hint in MOBILE_USER_AGENT_HINTS)

def calculate_crop_score(crop: dict, moisture: float, temp: float, ec: float, ph: float, nitrogen: float) -> float:
    """Score a crop based on current soil conditions (0-100)."""
    score = 100.0
    
    ph_opt_min, ph_opt_max = crop["pH"]
    if ph < ph_opt_min or ph > ph_opt_max:
        ph_margin = min(abs(ph - ph_opt_min), abs(ph - ph_opt_max))
        score -= min(30, ph_margin * 5)
    
    moisture_opt_min, moisture_opt_max = crop["moisture"]
    if moisture < moisture_opt_min or moisture > moisture_opt_max:
        moisture_margin = min(abs(moisture - moisture_opt_min), abs(moisture - moisture_opt_max))
        score -= min(25, moisture_margin * 0.5)
    
    ec_opt_min, ec_opt_max = crop["EC"]
    if ec < ec_opt_min or ec > ec_opt_max:
        ec_margin = min(abs(ec - ec_opt_min), abs(ec - ec_opt_max))
        score -= min(20, ec_margin * 0.3)
    
    if 15 <= temp <= 25:
        score += 5
    elif 10 <= temp < 15 or 25 < temp <= 30:
        score -= 10
    
    if nitrogen < crop["N"] * 0.5:
        score -= 15
    elif nitrogen < crop["N"]:
        score -= 5
    
    return max(0, min(100, score))


def normalize_ratio(values):
    """Normalize numeric values so they sum to 1.0."""
    numeric_values = [max(float(value), 0.0) for value in values]
    total = sum(numeric_values)
    if total <= 0:
        return None
    return [value / total for value in numeric_values]


def build_npk_analysis(values):
    """Build an NPK ratio summary and compare it to common commercial fertilizers."""
    nitrogen = get_sensor_value_by_default_index(values, 4)
    phosphorus = get_sensor_value_by_default_index(values, 5)
    potassium = get_sensor_value_by_default_index(values, 6)

    if None in (nitrogen, phosphorus, potassium):
        return None

    actual_values = [max(float(nitrogen), 0.0), max(float(phosphorus), 0.0), max(float(potassium), 0.0)]
    normalized_actual = normalize_ratio(actual_values)
    if normalized_actual is None:
        return None

    max_value = max(actual_values) or 1.0
    ratio_to_peak = [round(value / max_value, 2) for value in actual_values]

    comparisons = []
    for fertilizer in COMMERCIAL_FERTILIZERS:
        normalized_fertilizer = normalize_ratio(fertilizer['ratio'])
        if normalized_fertilizer is None:
            continue

        distance = sum(
            abs(actual_part - fertilizer_part)
            for actual_part, fertilizer_part in zip(normalized_actual, normalized_fertilizer)
        )
        comparisons.append({
            'name': fertilizer['name'],
            'label': fertilizer['label'],
            'use': fertilizer['use'],
            'distance': round(distance, 3),
            'shares': [round(part * 100, 1) for part in normalized_fertilizer],
        })

    comparisons.sort(key=lambda item: item['distance'])

    return {
        'values': {
            'nitrogen': round(actual_values[0], 1),
            'phosphorus': round(actual_values[1], 1),
            'potassium': round(actual_values[2], 1),
        },
        'ratio_to_peak': ratio_to_peak,
        'shares': {
            'nitrogen': round(normalized_actual[0] * 100, 1),
            'phosphorus': round(normalized_actual[1] * 100, 1),
            'potassium': round(normalized_actual[2] * 100, 1),
        },
        'closest_matches': comparisons[:4],
        'comparison_note': 'Commercial fertilizer labels are compared by relative N-P-K proportions.',
    }

# Modbus RTU functions
def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc

def read_registers():
    """Read sensor values via Modbus RTU."""
    if port is None or not port.is_open:
        return None
    try:
        with port_lock:
            req = bytes([SLAVE_ID, 0x03, 0x00, 0x00, 0x00, 0x08])
            c = crc16(req)
            req += bytes([c & 0xFF, c >> 8])

            port.reset_input_buffer()
            port.write(req)
            port.flush()

            resp = port.read(21)
            if len(resp) != 21:
                return None
            if resp[0] != SLAVE_ID or resp[1] != 0x03 or resp[2] != 16:
                return None
            resp_crc = (resp[20] << 8) | resp[19]
            if crc16(resp[:19]) != resp_crc:
                return None

            values = []
            for source_index, _, _, scale, _, _ in READINGS:
                if source_index >= MODBUS_REGISTER_COUNT:
                    values.append(None)
                    continue

                raw_offset = 3 + source_index * 2
                raw = (resp[raw_offset] << 8) | resp[raw_offset + 1]
                values.append(raw / scale if scale > 1 else float(raw))
            return values
    except Exception as e:
        print(f"Read error: {e}")
        return None


def perform_sensor_read(update_history: bool = True):
    """Run one sensor read and update shared state."""
    global current_values, sensor_status, last_update

    values = read_registers()
    if values is None:
        current_values = None
        sensor_status = '✗ No response'
        return False

    current_values = values
    last_update = datetime.now().isoformat()
    if update_history:
        add_history_sample(values, datetime.now())
    sensor_status = '● Continuous mode' if OPERATION_MODE == 'continuous' else '✔ Analysis captured'
    return True

def sensor_worker():
    """Background worker thread for sensor polling."""
    global port, current_values, sensor_status, last_update
    
    try:
        port = serial.Serial(PORT, BAUD, timeout=1.5)
        sensor_status = '● Continuous mode' if OPERATION_MODE == 'continuous' else '◼ Analysis mode — waiting for manual run'
    except serial.SerialException as e:
        sensor_status = f"✗ Error: {e}"
        return

    last_read = time.time()
    
    while not stop_event.is_set():
        now = time.time()
        if OPERATION_MODE == 'continuous' and now - last_read >= POLL_INTERVAL:
            perform_sensor_read(update_history=True)
            last_read = now
        time.sleep(0.1)

    if port and port.is_open:
        port.close()

# Flask routes
@app.route('/')
def index():
    """Serve the web UI."""
    return render_template(
        'index.html',
        is_mobile=is_mobile_user_agent(request.headers.get('User-Agent', ''))
    )

@app.route('/api/settings')
def get_settings():
    """Get current settings and configuration."""
    return jsonify({
        'sensor_sets': SENSOR_SETS,
        'active_set': ACTIVE_SET,
        'ui_theme': UI_THEME,
        'operation_mode': OPERATION_MODE,
        'sensor_poll_interval': SENSOR_POLL_INTERVAL,
        'allowed_poll_intervals': [int(value) for value in ALLOWED_POLL_INTERVALS],
        'readings': [{'name': name, 'unit': unit, 'min': min_w, 'max': max_w}
                     for _, name, unit, _, min_w, max_w in READINGS],
        'default_readings': [{'name': name, 'unit': unit} for name, unit, *_ in DEFAULT_READINGS]
    })

@app.route('/api/data')
def get_data():
    """Get current sensor data."""
    sensor_values = []
    if current_values is not None:
        for (_, name, unit, _, min_w, max_w), value in zip(READINGS, current_values):
            sensor_values.append({
                'name': name,
                'unit': unit,
                'value': value,
                'min': min_w,
                'max': max_w,
                'status': 'unavailable' if value is None else ('good' if min_w <= value <= max_w else 'warning')
            })
    
    npk_analysis = build_npk_analysis(current_values)

    # Calculate crop recommendations
    crops = []
    moisture = get_sensor_value_by_default_index(current_values, 0)
    temp = get_sensor_value_by_default_index(current_values, 1)
    ec_raw = get_sensor_value_by_default_index(current_values, 2)
    ph = get_sensor_value_by_default_index(current_values, 3)
    nitrogen = get_sensor_value_by_default_index(current_values, 4)

    if None not in (moisture, temp, ec_raw, ph, nitrogen):
        ec = ec_raw / 1000 if ec_raw > 0 else 0.5
        
        scores = {}
        for crop_name, crop_data in CROPS.items():
            score = calculate_crop_score(crop_data, moisture, temp, ec, ph, nitrogen)
            scores[crop_name] = score
        
        sorted_crops = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for rank, (crop_name, score) in enumerate(sorted_crops[:6], 1):
            crop_data = CROPS[crop_name]
            crops.append({
                'rank': rank,
                'name': crop_name,
                'icon': crop_data['icon'],
                'score': score,
                'yield': crop_data['yield'],
                'value': crop_data['value']
            })
    
    serialized_history_ranges = get_serialized_history_ranges()

    return jsonify({
        'status': sensor_status,
        'operation_mode': OPERATION_MODE,
        'sensor_poll_interval': SENSOR_POLL_INTERVAL,
        'last_update': last_update,
        'values': sensor_values,
        'crops': crops,
        'npk_analysis': npk_analysis,
        'history': serialized_history_ranges.get('day', []),
        'history_ranges': serialized_history_ranges
    })

@app.route('/api/set/<int:set_id>', methods=['POST'])
def set_active_set(set_id):
    """Switch to a different sensor set."""
    global ACTIVE_SET
    if 0 <= set_id < 10:
        ACTIVE_SET = set_id
        save_sensor_sets()
        names, enabled = get_active_set_data()
        update_readings(names, enabled)
        clear_history_ranges()
        return jsonify({'success': True, 'active_set': ACTIVE_SET})
    return jsonify({'success': False}), 400

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update sensor configuration."""
    global UI_THEME
    data = request.json
    current_set = normalize_sensor_set(
        SENSOR_SETS.get(ACTIVE_SET, {}),
        f"Set {ACTIVE_SET + 1}"
    )
    
    if 'set_name' in data:
        current_set['name'] = data['set_name']
    
    if 'names' in data:
        current_set['names'] = data['names']
    
    if 'enabled' in data:
        current_set['enabled'] = data['enabled']

    SENSOR_SETS[ACTIVE_SET] = normalize_sensor_set(current_set, current_set['name'])

    if 'ui_theme' in data and data['ui_theme'] in ('retro', 'garden', 'speakeasy', 'studio54'):
        UI_THEME = data['ui_theme']
    if 'operation_mode' in data:
        set_operation_mode(data['operation_mode'])
    if 'sensor_poll_interval' in data:
        set_sensor_poll_interval(data['sensor_poll_interval'])
    
    save_sensor_sets()
    names, enabled = get_active_set_data()
    update_readings(names, enabled)
    clear_history_ranges()
    
    return jsonify({'success': True})


@app.route('/api/mode', methods=['POST'])
def update_mode():
    """Switch between analysis and continuous modes."""
    data = request.json or {}
    mode = data.get('operation_mode', 'continuous')
    if mode not in ('analysis', 'continuous'):
        return jsonify({'success': False, 'error': 'invalid mode'}), 400

    set_operation_mode(mode)
    save_sensor_sets()
    return jsonify({'success': True, 'operation_mode': OPERATION_MODE})


@app.route('/api/analyze', methods=['POST'])
def run_analysis():
    """Run a single manual sensor capture in analysis mode."""
    if OPERATION_MODE != 'analysis':
        return jsonify({'success': False, 'error': 'analysis mode is not active'}), 400

    success = perform_sensor_read(update_history=True)
    return jsonify({'success': success, 'status': sensor_status, 'last_update': last_update})

if __name__ == '__main__':
    # Load configuration
    load_sensor_sets()
    names, enabled = get_active_set_data()
    update_readings(names, enabled)
    clear_history_ranges()
    
    # Start sensor worker thread
    serial_thread = threading.Thread(target=sensor_worker, daemon=True)
    serial_thread.start()
    
    # Run Flask app (on 0.0.0.0 for network access)
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
