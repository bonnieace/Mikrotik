from fastapi import FastAPI, HTTPException
from services.payment_service import initiate_stk_push

app = FastAPI()

@app.post("/stkpush/initiate")
async def initiate_stk_push_endpoint(phone_number: str, amount: int):
    try:
        result = await initiate_stk_push(phone_number, amount)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))