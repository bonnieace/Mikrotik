from fastapi import HTTPException
from librouteros import connect
from database import crud
from database.session import SessionLocal


def connect_to_router(router_id: int):
    db = SessionLocal()
    try:
        router = crud.get_router_by_id(db, router_id)
        if not router:
            raise HTTPException(status_code=404, detail=f"Router with id {router_id} not found")
    finally:
        db.close()
    try:
        api = connect(
            username=router.username,
            password=router.password,
            host=router.ip_address,
            port=router.port,
        )
        return api
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")

#fetch rx rt data from mikrotik in bridge interface
def fetch_rt_rx_tx_data(router_id: int):
    try:
        api = connect_to_router(router_id)
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


