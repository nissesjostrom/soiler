# 8sense Home Assistant integration

This folder contains a custom Home Assistant integration that creates one 8sense device and exposes the soil API data as separate sensor entities.

## Included entities

- Moisture
- Temperature
- EC
- pH
- Nitrogen
- Phosphorus
- Potassium
- Salinity
- Status
- Active set
- Last update
- Top crop
- Top crop score

## Installation

1. Copy the folder `homeassistant/custom_components/eightsense` into your Home Assistant config directory as `custom_components/eightsense`.
2. Restart Home Assistant.
3. In Home Assistant, open **Settings → Devices & Services → Add Integration**.
4. Search for **8sense Soil Sensor**.
5. Enter the host or IP address of the machine running this Flask app and the API port, normally `5001`.

## API endpoint

The integration reads from:

- `GET /api/homeassistant`

Example:

- `http://192.168.1.50:5001/api/homeassistant`

## Notes

- The integration polls the local API and groups all sensor entities under one device.
- If a sensor is disabled in the active 8sense set, the entity stays in Home Assistant but becomes unavailable.
- Entity names follow the active set configuration from the 8sense app.
