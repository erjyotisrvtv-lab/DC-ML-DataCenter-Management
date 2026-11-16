
from netmiko import ConnectHandler
from getpass import getpass
from datetime import datetime
import csv
import re
import os

router = {
    "device_type": "cisco_ios",
    "host": "192.168.171.10",
    "username": "admin",
    "password": getpass("Enter SSH password: ")
}

with ConnectHandler(**router) as conn:
    cpu_output = conn.send_command("show processes cpu")

    memory_output = conn.send_command(
        "show memory statistics",
        read_timeout=30
    )

    traffic_output = conn.send_command(
        "show interfaces GigabitEthernet0/0"
    )

    print("MEMORY OUTPUT START")
    print(memory_output)
    print("MEMORY OUTPUT END")
    traffic_output = conn.send_command(
        "show interfaces GigabitEthernet0/0"
    )

cpu_match = re.search(
    r"five seconds:\s*(\d+)%",
    cpu_output,
    re.IGNORECASE
)

input_match = re.search(
    r"(\d+)\s+packets input,\s*(\d+)\s+bytes",
    traffic_output
)

output_match = re.search(
    r"(\d+)\s+packets output,\s*(\d+)\s+bytes",
    traffic_output
)

# Cisco IOSv Processor memory utilization
memory_match = re.search(
    r"Processor\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)",
    memory_output
)

memory_percent = None

if memory_match:
    total_memory = int(memory_match.group(1))
    used_memory = int(memory_match.group(2))

    if total_memory > 0:
        memory_percent = round(
            (used_memory / total_memory) * 100, 2
        )

print("Memory Usage:", memory_percent)
print("Memory_Percent:", memory_percent)

row = {
    "timestamp": datetime.now().isoformat(timespec="seconds"),
    "router": "LEAF1",
    "cpu_percent": int(cpu_match.group(1)) if cpu_match else None,
    "input_bytes": int(input_match.group(2)) if input_match else None,
    "output_bytes": int(output_match.group(2)) if output_match else None,
    "memory_raw": memory_output.replace("\n", " | ")
}

filename = "dc_metrics.csv"
file_exists = os.path.exists(filename)

fieldnames = [
    "timestamp",
    "router",
    "cpu_percent",
    "input_bytes",
    "output_bytes",
    "memory_percent",
    "memory_raw"
]

with open(filename, "a", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)

    if file.tell() == 0:
        writer.writeheader()

    writer.writerow(row)
                    
print("SUCCESS! Data saved to dc_metrics.csv")
print(row)
