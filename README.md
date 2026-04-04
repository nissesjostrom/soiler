# Soil Sensor v2.0 — Web Edition

A lightweight web-based agricultural soil monitoring system for **Raspberry Pi Zero**, featuring real-time sensor data, crop recommendations, and 10-sample history tracking.

## 🌾 Features

- **Real-time Monitoring**: 2-second polling interval for 10 sensor types
- **Crop Recommendations**: AI-powered scoring for 24 European crops
- **History Tracking**: Store and visualize last 10 readings with statistics
- **Multi-Set Configuration**: 10 customizable sensor configurations
- **Amiga 500 Aesthetic**: Retro cyan/magenta/lime color scheme
- **Network Access**: Access from any device on your network
- **Lightweight**: 50-80MB RAM usage on Pi Zero

## 📋 System Requirements

- **Raspberry Pi Zero W** (with WiFi) or **Raspberry Pi Zero**
- **Python 3.7+**
- **ESP32 with Modbus RTU firmware** (pre-flashed)
- **Serial USB adapter** (CH340 on /dev/ttyUSB0)

## 🚀 Quick Start

### Traditional Method

```bash
# Install dependencies
pip3 install Flask pyserial

# Run application
python3 app.py
```

Access browser: **http://localhost:5000**

### Using Start Script

```bash
chmod +x start.sh
./start.sh
```

### Using Docker (Pi/x86_64)

```bash
# Build image
docker build -t soil-sensor .

# Run container
docker run -p 5000:5000 \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  soil-sensor
```

## 📁 Project Structure

```
soil-sensor/
├── app.py              # Flask backend (Modbus + crop logic)
├── requirements.txt    # Python dependencies
├── start.sh           # Quick start script
├── Dockerfile         # Docker configuration
├── SETUP.md           # Detailed installation guide
├── templates/
│   └── index.html     # Web UI template
└── static/
    ├── style.css      # Amiga theme styling
    └── app.js         # Frontend logic & polling
```

## 🔌 Hardware Setup

### Serial Connection

```
ESP32 USB ──→ CH340 ──→ /dev/ttyUSB0 (9600 baud)
```

Verify connection:
```bash
ls -l /dev/ttyUSB*
python3 -c "import serial; serial.Serial('/dev/ttyUSB0', 9600)"
```

## 🌐 Network Access

### Find Raspberry Pi on Network

```bash
hostname -I
```

### Access from Another Device

- **iPhone/Android**: Open browser → `http://<PI_IP>:5000`
- **PC/Mac**: Same as above
- **Network range**: 192.168.x.x (adjust for your WiFi)

## ⚙️ Configuration

### Sensor Sets

10 pre-configured sets:
1. **Standard** - All sensors enabled
2. **Soil Only** - Moisture, EC, pH, Nutrients
3. **Nutrients** - N, P, K focus
4. **Environment** - Temperature, EC, Light
5-10. **Custom 1-6** - User-configurable

Switch sets via dropdown in web UI.

### Persistent Storage

Configuration saved to `~/.8sense_config.json`:
```json
{
  "sets": [
    {
      "name": "Set 1: Standard",
      "names": ["Moisture", "Temperature", ...],
      "enabled": [true, true, ...]
    }
  ],
  "active_set": 0
}
```

## 📊 Sensor Types

| # | Sensor | Unit | Range |
|---|--------|------|-------|
| 1 | Moisture | % | 0-100 |
| 2 | Temperature | °C | -40 to 80 |
| 3 | EC | µS/cm | 0-2000 |
| 4 | pH | - | 0-14 |
| 5 | Nitrogen | mg/kg | 0-200 |
| 6 | Phosphorus | mg/kg | 0-200 |
| 7 | Potassium | mg/kg | 0-200 |
| 8 | Salinity | ppt | 0-2 |
| 9 | Conductivity | mS/cm | 0-500 |
| 10 | Light Intensity | lux | 0-100k |

## 🌱 Crop Database

24 crops with soil requirements:
- Tomato, Lettuce, Pepper, Cabbage, Broccoli
- Cucumber, Carrot, Spinach, Potato, Onion
- Green Beans, Asparagus, Strawberry, Blueberry
- Garlic, Radish, Cauliflower, Olive, Beet
- Celery, Zucchini, Pumpkin, Raspberry

**Scoring**: 0-100% based on soil pH, moisture, EC, temperature, nitrogen

## 📈 API Endpoints

```
GET  /                 # Web UI
GET  /api/settings     # Sensor configuration
GET  /api/data         # Current sensor values & recommendations
POST /api/set/<id>     # Switch active sensor set
POST /api/config       # Update sensor names/enabled
```

## 🔧 Troubleshooting

### Flask Won't Start

```bash
# Check Python version
python3 --version

# Verify Flask installed
pip3 list | grep Flask

# Run with verbose output
python3 -u app.py
```

### Serial Port Not Found

```bash
# List available ports
ls /dev/tty*

# Check permissions
sudo usermod -a -G dialout $(whoami)
# (logout and login after)
```

### High CPU Usage

- Increase `POLL_INTERVAL` in app.py (default: 2.0s)
- Disable unused sensors
- Reduce browser tabs open

### Slow on Pi Zero

- Use Raspberry Pi OS Lite (no desktop)
- Disable WiFi power management (if unstable)
- Monitor temperature: `vcgencmd measure_temp`

## 🚨 Performance (Raspberry Pi Zero W)

- **Idle**: 45-60MB RAM, 5-10% CPU
- **Active**: 80-120MB RAM, 20-35% CPU
- **Polling**: 2s interval
- **Page Load**: ~500ms on 2.4GHz WiFi
- **Latency**: 100-200ms typical

## 🐳 Production Deployment

### Using Gunicorn

```bash
# Install production WSGI server
pip install gunicorn

# Run with 1 worker (Pi Zero limitation)
gunicorn -w 1 -b 0.0.0.0:5000 app:app
```

### As systemd Service

See [SETUP.md](SETUP.md) for detailed instructions.

## 📝 Development

### Enable Debug Mode

Edit `app.py`:
```python
app.run(host='0.0.0.0', port=5000, debug=True)  # NOT for production
```

### Monitor Logs

```bash
# Live logs
tail -f ~/.8sense_log.txt

# System logs (if using systemd)
sudo journalctl -u soil-sensor -f
```

## 🔄 Migrating from Desktop Version

**Desktop (PySide6):**
- File: `sensor_gui.py`
- Display: Local window only
- Memory: ~150MB

**Web (Flask):**
- File: `app.py`
- Display: Network browser
- Memory: ~50-80MB
- **New feature**: Remote access

## 📚 Documentation

- **[SETUP.md](SETUP.md)** - Detailed installation & systemd configuration
- **[EUROPEAN_CROPS_ANALYSIS.md](EUROPEAN_CROPS_ANALYSIS.md)** - Crop data & requirements

## 🐛 Known Issues

- ⏱️ Slight latency (~200ms) due to HTTP polling (not WebSocket)
- 📍 Only works on local network (no cloud integration)
- 🔐 No authentication (use on trusted networks only)

## 🚀 Future Enhancements

- [ ] WebSocket for real-time updates
- [ ] CSV data export
- [ ] Email/SMS alerts
- [ ] Moving averages & trend analysis
- [ ] Multi-location support
- [ ] Historical graphs

## 📜 License

Open source agricultural monitoring project (April 2026)

## 📧 Support

For issues:
1. Check [SETUP.md](SETUP.md) troubleshooting
2. Verify serial connection: `ls /dev/ttyUSB0`
3. Check Flask logs: `python3 -u app.py`

---

**Optimized for Raspberry Pi Zero** | **Web v2.0** | **April 2026**
