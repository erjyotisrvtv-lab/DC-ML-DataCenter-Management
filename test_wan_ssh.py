
import getpass
from netmiko import ConnectHandler

routers = {
    "WAN-CORE1": "192.168.171.40",
    "WAN-CORE2": "192.168.171.41",
}

username = input("WAN SSH username [admin]: ").strip() or "admin"
password = getpass.getpass("Enter WAN SSH password: ")

for name, ip in routers.items():
    print(f"\nConnecting to {name} ({ip})")

    try:
        with ConnectHandler(
            device_type="cisco_ios",
            host=ip,
            username=username,
            password=password,
            use_keys=False,
            allow_agent=False,
            conn_timeout=20,
            auth_timeout=20,
            banner_timeout=20,
        ) as conn:
            print(f"{name}: SSH LOGIN SUCCESSFUL")
            print(conn.send_command("show ip bgp summary"))

    except Exception as e:
        print(f"{name}: {type(e).__name__}: {e}")
