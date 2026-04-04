#!/usr/bin/env python3
"""
Soil sensor live dashboard — Modbus RTU via USB CH340
Slave ID 1, 9600 baud, registers 0x0000–0x0007
"""

import sys
import time
import serial
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box

PORT = "/dev/ttyUSB0"
BAUD = 9600
SLAVE_ID = 1
POLL_INTERVAL = 2.0  # seconds

READINGS = [
    # (name, unit, scale, min_warn, max_warn)
    ("Moisture",    "%",      10,   10,   80),
    ("Temperature", "°C",     10,    5,   40),
    ("EC",          "µS/cm",   1,    0, 2000),
    ("pH",          "",       10,  5.5,  7.5),
    ("Nitrogen",    "mg/kg",   1,    0,  200),
    ("Phosphorus",  "mg/kg",   1,    0,  200),
    ("Potassium",   "mg/kg",   1,    0,  200),
    ("Salinity",    "ppt",    10,    0,    2),
]

console = Console()


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def read_registers(port: serial.Serial) -> list[float] | None:
    req = bytes([SLAVE_ID, 0x03, 0x00, 0x00, 0x00, 0x08])
    c = crc16(req)
    req += bytes([c & 0xFF, c >> 8])

    port.reset_input_buffer()
    port.write(req)
    port.flush()

    resp = port.read(21)  # 1+1+1+16+2 = 21 bytes
    if len(resp) != 21:
        return None
    if resp[0] != SLAVE_ID or resp[1] != 0x03 or resp[2] != 16:
        return None
    resp_crc = (resp[20] << 8) | resp[19]
    if crc16(resp[:19]) != resp_crc:
        return None

    values = []
    for i, (_, _, scale, _, _) in enumerate(READINGS):
        raw = (resp[3 + i * 2] << 8) | resp[4 + i * 2]
        values.append(raw / scale if scale > 1 else float(raw))
    return values


def value_color(value: float, min_warn: float, max_warn: float) -> str:
    if value == 0.0:
        return "bright_black"
    if min_warn <= value <= max_warn:
        return "bright_green"
    return "bright_yellow"


def build_table(values: list[float] | None, status: str, elapsed: float) -> Panel:
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        expand=True,
        padding=(0, 1),
    )
    table.add_column("Sensor", style="bold white", min_width=12)
    table.add_column("Value", justify="right", min_width=12)
    table.add_column("Unit", style="dim", min_width=7)
    table.add_column("Range", style="dim", min_width=12)

    if values is None:
        for name, unit, _, lo, hi in READINGS:
            table.add_row(name, "[bright_black]--[/]", unit, f"{lo} – {hi}")
    else:
        for (name, unit, _, lo, hi), val in zip(READINGS, values):
            color = value_color(val, lo, hi)
            fmt = f".1f" if isinstance(val, float) and val != int(val) else ".0f"
            table.add_row(
                name,
                f"[{color}]{val:{fmt}}[/]",
                unit,
                f"{lo} – {hi}",
            )

    status_color = "green" if values else "red"
    footer = Text(f" {status}  |  updated every {POLL_INTERVAL:.0f}s  |  {elapsed:.1f}s since last read", style=f"dim {status_color}")
    return Panel(table, title="[bold]Soil Sensor Dashboard[/bold]", subtitle=footer, border_style="blue")


def main():
    try:
        port = serial.Serial(PORT, BAUD, timeout=1.5)
    except serial.SerialException as e:
        console.print(f"[red]Cannot open {PORT}: {e}[/red]")
        sys.exit(1)

    console.print(f"[green]Connected to {PORT} @ {BAUD} baud[/green]")

    values = None
    status = "waiting..."
    last_read = time.monotonic()

    with Live(build_table(values, status, 0), console=console, refresh_per_second=4) as live:
        while True:
            now = time.monotonic()
            elapsed = now - last_read

            if elapsed >= POLL_INTERVAL:
                result = read_registers(port)
                if result is not None:
                    values = result
                    status = "● connected"
                    last_read = now
                    elapsed = 0.0
                else:
                    status = "✗ no response"
                    last_read = now

            live.update(build_table(values, status, elapsed))
            time.sleep(0.25)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
