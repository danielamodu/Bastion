from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
import random
import logging
import os
from dotenv import load_dotenv

from google import antigravity as ag
from google.antigravity.hooks import policy

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Bastion FX Pricing Agent")

class PromptRequest(BaseModel):
    prompt: str

def lookup_mock_fx_rate(currency_pair: str, token: str = None) -> Dict[str, Any]:
    """
    Returns a mock FX rate for the given currency pair.
    REQUIRES a valid token to access this institutional pricing data.
    """
    logging.info(f"TOOL INVOKED: lookup_mock_fx_rate(currency_pair='{currency_pair}', token='{token}')")
    
    # ZERO-TRUST BOUNDARY CHECK
    expected_token = os.environ.get("BASTION_SHARED_TOKEN")
    if token != expected_token or not expected_token:
        logging.warning("REJECTED: Invalid or missing credential for pricing lookup.")
        return {
            "error": "Access Denied: Invalid or missing credential. You must provide a valid scoped credential (token) to access institutional pricing data."
        }
        
    base_rates = {
        "USD/NGN": 1500.0,
        "EUR/USD": 1.08,
        "GBP/USD": 1.25,
    }
    
    base = base_rates.get(currency_pair.upper(), 1.0)
    variance = base * 0.01 * random.uniform(-1, 1)
    rate = base + variance
    
    return {
        "currency_pair": currency_pair.upper(),
        "rate": round(rate, 4),
        "source": "mock_pricing_agent"
    }

@app.post("/invoke")
async def invoke_agent(req: PromptRequest):
    if not req.prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    config = ag.LocalAgentConfig(
        model="gemini-3.5-flash",
        vertex=False,
        tools=[lookup_mock_fx_rate],
        policies=[policy.allow_all()],
    )
    
    try:
        async with ag.Agent(config) as agent:
            logging.info(f"Sending prompt: {req.prompt}")
            response = await agent.chat(req.prompt)
            text = await response.text()
            logging.info(f"Response: {text}")
            return {"response": text}
    except Exception as e:
        logging.error(f"Error invoking agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
