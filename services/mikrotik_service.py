import asyncio
from fastapi import FastAPI, HTTPException
from librouteros import connect
from librouteros.exceptions import TrapError
import random
import string
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
import time

# Load environment variables
load_dotenv()

# MikroTik connection details
MIKROTIK_HOST = os.getenv("MIKROTIK_HOST")
MIKROTIK_PORT = int(os.getenv("MIKROTIK_PORT", "8728"))
MIKROTIK_USER = os.getenv("MIKROTIK_USER")
MIKROTIK_PASSWORD = os.getenv("MIKROTIK_PASSWORD")

# FastAPI app
app = FastAPI()


# Utility function to connect to the router
def connect_to_router():
    missing = [name for name, val in [
        ("MIKROTIK_HOST", MIKROTIK_HOST),
        ("MIKROTIK_USER", MIKROTIK_USER),
        ("MIKROTIK_PASSWORD", MIKROTIK_PASSWORD),
    ] if not val]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing required MikroTik configuration: {', '.join(missing)}"
        )
    try:
        api = connect(
            username=MIKROTIK_USER,
            password=MIKROTIK_PASSWORD,
            host=MIKROTIK_HOST,
            port=MIKROTIK_PORT
        )
        return api
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")

#fetch rx rt data from mikrotik in bridge interface
def fetch_rt_rx_tx_data():
    try:
        api = connect_to_router()  # Assumes a working librouteros connection.
        # Access the "interface/monitor-traffic" resource.
        resource = api.path("interface", "monitor-traffic")
        
        # Execute the "once" command to get a snapshot for the 'bridge' interface.
        result = list(resource.call("once", {"interface": "bridge"}))
        
        if not result:
            raise Exception("Empty response from MikroTik API")
        
        data = result[0]  # Get the first result (a dict)
        
        return {
            "rx_bits_per_second": data.get("rx-bits-per-second", 0),
            "tx_bits_per_second": data.get("tx-bits-per-second", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch RT RX/TX data: {str(e)}")


