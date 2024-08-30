from librouteros import connect
from librouteros.exceptions import TrapError

# Connect to MikroTik Router
api = connect(username='admin', password='twinkles', host='192.168.88.1', port=8728)

# Access the hotspot user path
hotspot_users = api.path("ip", "hotspot", "user")

# Add a new hotspot user
try:
    hotspot_users.add(
        name="new_user",
        password="new_password",
        profile="default",
        limit_uptime="1h",
        address=""  # Optional, depending on requirements
    )
except TrapError as e:
    print(f"Error creating user: {e}")
