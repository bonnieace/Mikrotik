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
MIKROTIK_PORT = int(os.getenv("MIKROTIK_PORT"))
MIKROTIK_USER = os.getenv("MIKROTIK_USER")
MIKROTIK_PASSWORD = os.getenv("MIKROTIK_PASSWORD")

# FastAPI app
app = FastAPI()


# Utility function to connect to the router
def connect_to_router():
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
