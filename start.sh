#!/bin/bash
# Quick start script for Soil Sensor Web Application

set -e

echo "🚀 Starting Soil Sensor Web Application v2.0"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

echo "✓ Python 3: $(python3 --version)"

# Check working directory
cd "$(dirname "$0")"
echo "✓ Working directory: $(pwd)"

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

# Check serial port
if [ ! -e "/dev/ttyUSB0" ]; then
    echo "⚠️  Warning: /dev/ttyUSB0 not found. Check USB connection."
    echo "   Run: ls /dev/tty* to list available serial ports"
fi

# Show configuration
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  SOIL SENSOR WEB APPLICATION v2.0"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Serial Port:    /dev/ttyUSB0 (9600 baud)"
echo "  Configuration:  ~/.8sense_config.json"
echo "  Web Server:     http://0.0.0.0:5001"
echo ""
echo "  📱 Access from browser:"
echo "     Local:  http://localhost:5001"
echo "     Network: http://$(hostname -I | awk '{print $1}'):5001"
echo ""
echo "  📋 Press Ctrl+C to stop"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Start Flask
python3 app.py
