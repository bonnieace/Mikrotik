from librouteros import connect
from librouteros.exceptions import TrapError

# Connect to MikroTik Router
api = connect(username='admin', password='twinkles', host='192.168.88.1', port=8728)



try:
    # Access the server profile path
    server_profiles = api.path("ip", "hotspot", "profile")
    
    # Fetch all available server profiles
    profiles = list(server_profiles.select('name'))
    
    # Print the names of the available profiles
    for profile in profiles:
        print(f"Profile Name: {profile['name']}")
    
except TrapError as e:
    print(f"Error fetching server profiles: {e}")
