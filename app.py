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

HISTORY_RANGE_CONFIG = {
    'day': {'maxlen': 288},
    'week': {'maxlen': 168},
    'month': {'maxlen': 31},
    'year': {'maxlen': 12},
}
app.config['JSON_SORT_KEYS'] = False

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

# Global state
SENSOR_SETS = {}
ACTIVE_SET = 0
current_values = None
history_ranges = {name: deque(maxlen=config['maxlen']) for name, config in HISTORY_RANGE_CONFIG.items()}
history_buckets = {name: None for name in HISTORY_RANGE_CONFIG}
sensor_status = "► INITIALIZING..."
last_update = None
port = None
serial_thread = None
stop_event = threading.Event()

# Configuration functions
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
    init_default_sets()
    
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

def sensor_worker():
    """Background worker thread for sensor polling."""
    global port, current_values, sensor_status, last_update
    
    try:
        port = serial.Serial(PORT, BAUD, timeout=1.5)
        sensor_status = "● Connected"
    except serial.SerialException as e:
        sensor_status = f"✗ Error: {e}"
        return

    last_read = time.time()
    
    while not stop_event.is_set():
        now = time.time()
        if now - last_read >= POLL_INTERVAL:
            values = read_registers()
            if values is not None:
                current_values = values
                last_update = datetime.now().isoformat()
                add_history_sample(values, datetime.now())
                sensor_status = "● Connected"
            else:
                current_values = None
                sensor_status = "✗ No response"
            last_read = now
        time.sleep(0.1)

    if port and port.is_open:
        port.close()

# Flask routes
@app.route('/')
def index():
    """Serve the web UI."""
    return render_template('index.html')

@app.route('/api/settings')
def get_settings():
    """Get current settings and configuration."""
    return jsonify({
        'sensor_sets': SENSOR_SETS,
        'active_set': ACTIVE_SET,
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
        'last_update': last_update,
        'values': sensor_values,
        'crops': crops,
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
    data = request.json
    
    if 'set_name' in data:
        SENSOR_SETS[ACTIVE_SET]['name'] = data['set_name']
    
    if 'names' in data:
        SENSOR_SETS[ACTIVE_SET]['names'] = data['names']
    
    if 'enabled' in data:
        SENSOR_SETS[ACTIVE_SET]['enabled'] = data['enabled']
    
    save_sensor_sets()
    names, enabled = get_active_set_data()
    update_readings(names, enabled)
    clear_history_ranges()
    
    return jsonify({'success': True})

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
