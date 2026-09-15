import platform
import socket
from datetime import datetime

import psutil


def get_system_info():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    battery = psutil.sensors_battery()

    return {
        "device_name": socket.gethostname(),
        "operating_system": platform.system(),
        "operating_system_version": platform.version(),
        "python_version": platform.python_version(),
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram_total_gb": round(memory.total / (1024 ** 3), 2),
        "ram_used_gb": round(memory.used / (1024 ** 3), 2),
        "ram_percent": memory.percent,
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "battery_percent": battery.percent if battery else None,
        "plugged_in": battery.power_plugged if battery else None,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def format_system_info(info):
    battery = "No disponible"

    if info["battery_percent"] is not None:
        charging = "conectada" if info["plugged_in"] else "en batería"
        battery = f'{info["battery_percent"]}% ({charging})'

    return (
        f'Dispositivo: {info["device_name"]}\n'
        f'Sistema: {info["operating_system"]} {info["operating_system_version"]}\n'
        f'Python: {info["python_version"]}\n'
        f'CPU: {info["cpu_percent"]}%\n'
        f'RAM: {info["ram_used_gb"]} GB / {info["ram_total_gb"]} GB ({info["ram_percent"]}%)\n'
        f'Disco C: {info["disk_used_gb"]} GB / {info["disk_total_gb"]} GB ({info["disk_percent"]}%)\n'
        f'Batería: {battery}\n'
        f'Hora: {info["timestamp"]}'
    )