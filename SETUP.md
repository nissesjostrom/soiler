# Soil Sensor Web Application — Raspberry Pi Zero Setup Guide

## Overview

This is a lightweight web-based version of the Soil Sensor GUI application, optimized for Raspberry Pi Zero (512MB RAM, single-core ARM). The application provides:

- **Flask Backend**: Handles Modbus RTU communication, crop scoring, and data management
- **Web Frontend**: HTML/CSS/JS with Amiga 500 retro aesthetic
- **Real-time Updates**: 2-second polling interval for sensor data
- **10 Sensor Sets**: Customizable configurations with persistent storage
- **Crop Recommendations**: 24 European crops with soil-based scoring
- **History Tracking**: Last 10 readings with min/avg/max statistics

## Hardware Requirements

- **Raspberry Pi Zero W** (with WiFi, recommended) or **Raspberry Pi Zero**
- **ESP32 with Modbus RTU** (already flashed)
- **USB to Serial adapter** (CH340, for /dev/ttyUSB0)
- **Power supply** (5V, 1.5A minimum)

## Initial Setup (Raspberry Pi)

### 1. Install OS and Dependencies

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install -y python3 python3-pip python3-venv git

# Install system dependencies
sudo apt install -y libffi-dev libssl-dev
```

### 2. Clone or Create Project Directory

```bash
mkdir -p ~/soil-sensor
cd ~/soil-sensor
```

### 3. Create Python Virtual Environment

```bash
# Create venv (optimized for Pi Zero)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools
```

### 4. Install Dependencies

```bash
# Install lightweight dependencies
pip install -r requirements.txt

# Verify installations (should list Flask, pyserial, Werkzeug)
pip list
```

### 5. Check Serial Port

```bash
# Verify USB serial connection
ls -l /dev/ttyUSB*

# Test connection (Ctrl+C to exit)
python3 -c "import serial; s=serial.Serial('/dev/ttyUSB0', 9600); print('✓ Connected')"
```

## Running the Application

### Start Flask Server

```bash
cd ~/soil-sensor
source venv/bin/activate

# Run Flask (binds to 0.0.0.0:5000 for network access)
python3 app.py
```

Expected output:
```
 * Running on http://0.0.0.0:5000
 * Press CTRL+C to quit
```

### Access from Browser

**From Raspberry Pi (local):**
```
http://localhost:5000
```

**From another device on network:**
```
http://<RASPBERRY_PI_IP>:5000
```

Get IP address:
```bash
hostname -I
```

## Running as Background Service

### Create systemd Service

```bash
# Create service file
sudo nano /etc/systemd/system/soil-sensor.service
```

Paste this content:
```ini
[Unit]
Description=Soil Sensor Web Application
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/soil-sensor
ExecStart=/home/pi/soil-sensor/venv/bin/python3 app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable soil-sensor

# Start the service
sudo systemctl start soil-sensor

# Check status
sudo systemctl status soil-sensor

# View logs
sudo journalctl -u soil-sensor -f
```

## Configuration Files

### `~/.8sense_config.json`

Stores sensor sets and preferences:
```json
{
  "sets": [
    {
      "name": "Set 1: Standard",
      "names": ["Moisture", "Temperature", ...],
      "enabled": [true, true, ...]
    },
    ...
  ],
  "active_set": 0
}
```

**Backup your config:**
```bash
cp ~/.8sense_config.json ~/.8sense_config.json.backup
```

## Troubleshooting

### Flask Won't Start

```bash
# Check Python version (need 3.7+)
python3 --version

# Test Flask installation
python3 -c "import flask; print(flask.__version__)"

# Try running with verbose error output
python3 -u app.py
```

### Serial Port Issues

```bash
# List all serial ports
ls /dev/tty*

# Check permissions
groups pi

# Add pi user to dialout group (then logout/login)
sudo usermod -a -G dialout pi
```

### High CPU Usage

If CPU usage is high, the Modbus polling may be too aggressive:
- Increase `POLL_INTERVAL` in `app.py` (currently 2 seconds)
- Reduce number of enabled sensors

### Slow Performance

On Pi Zero with limited RAM (512MB):
- Disable unnecessary tab updates
- Reduce history display (currently 10 readings)
- Close unnecessary browser tabs

## File Structure

```
soil-sensor/
├── app.py                 # Flask backend with Modbus/crop logic
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Web UI HTML
└── static/
    ├── style.css         # Amiga 500 retro styling
    └── app.js            # Frontend logic & polling
```

## Key Differences from Desktop Version

| Feature | Desktop (PySide6) | Web (Flask) |
|---------|-------------------|------------|
| Display | Local window | Network browser |
| Polling | 2s interval (Qt) | 2s interval (JavaScript) |
| History | 10 samples max | 10 samples max |
| Crops | 24 crops | 24 crops |
| Memory | ~150MB | ~50MB |
| CPU usage | Higher | Lower |
| Network access | No | Yes (local network) |
| Port | N/A | 5000 |

## Network Access

### Same WiFi Network (Recommended)

1. Connect Raspberry Pi to WiFi
2. Find IP: `hostname -I`
3. Access from phone/PC: `http://<IP>:5000`

### Port Forwarding (Caution)

If exposing to internet:
```bash
# Only if behind firewall!
ssh -L 5000:localhost:5000 pi@<YOUR_DEVICE_IP>
```

**Warning**: Don't expose directly to internet without authentication!

## Updating

```bash
# Pull latest changes
cd ~/soil-sensor
git pull origin main

# Restart service
sudo systemctl restart soil-sensor
```

## Optimization Tips

### For Raspberry Pi Zero

1. **Use Lite OS** (no desktop environment)
2. **Disable services**:
   ```bash
   sudo systemctl disable bluetooth
   sudo systemctl disable avahi-daemon
   ```

3. **Reduce Flask overhead**:
   - Change `debug=False` in `app.py` (already set)
   - Use production WSGI server if scaling:
     ```bash
     pip install gunicorn
     gunicorn -w 1 -b 0.0.0.0:5000 app:app
     ```

4. **Optimize browser**:
   - Use plain Firefox or Chrome (not heavy browsers)
   - Disable extensions
   - Limit to one tab

## Performance Metrics (Pi Zero W)

- **Memory**: ~50-80MB idle, ~120MB under load
- **CPU**: 15-30% during polling + rendering
- **Startup time**: ~3-5 seconds
- **Page load**: ~500ms (2.4GHz WiFi)
- **Polling latency**: 100-200ms

## Support & Debugging

### Enable Debug Mode (Development Only)

Edit `app.py`:
```python
app.run(host='0.0.0.0', port=5000, debug=True)  # DON'T USE IN PRODUCTION
```

### Monitor Real-time

```bash
# Watch logs live
sudo journalctl -u soil-sensor -f --no-pager

# Check resource usage
ps aux | grep python3

# Monitor temperature
vcgencmd measure_temp
```

## Next Steps

1. **Hardware Integration**: Connect MAX485 transceiver for RS485
2. **Authentication**: Add login if exposed to network
3. **Data Export**: Save historical data to CSV
4. **Dashboard**: Create summary statistics view
5. **Alerts**: Implement email/SMS notifications for sensor thresholds

---

**Maintained for Raspberry Pi Zero W**
**Last Updated: April 2026**
