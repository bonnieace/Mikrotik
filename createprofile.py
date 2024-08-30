from librouteros import connect

# Connect to your MikroTik router
api = connect(
    host='your_router_ip',
    username='your_username',
    password='your_password',
    port=8728
)

# Create a Hotspot user profile
def create_hotspot_profile(name, limit_uptime=None, limit_bytes_in=None, limit_bytes_out=None):
    try:
        # Define the parameters for the new profile
        profile_params = {
            'name': name,
        }
        
        if limit_uptime:
            profile_params['limit-uptime'] = limit_uptime
        if limit_bytes_in:
            profile_params['limit-bytes-in'] = limit_bytes_in
        if limit_bytes_out:
            profile_params['limit-bytes-out'] = limit_bytes_out

        # Create the profile
        result = api.path('hotspot', 'profile').add(**profile_params)
        
        print(f"Profile created successfully: {result}")
    
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
create_hotspot_profile(
    name='example_profile',
    limit_uptime='1h',
    limit_bytes_in='100MB',
    limit_bytes_out='100MB'
)
