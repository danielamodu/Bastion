import asyncio
import logging
import random
from typing import Any, Dict
from dotenv import load_dotenv

from google import antigravity as ag
from google.antigravity.hooks import policy

# Load environment variables
load_dotenv()

# Set up logging to see the tool invocation
logging.basicConfig(level=logging.INFO)

# Tool definition
def lookup_mock_fx_rate(currency_pair: str, token: str = None) -> Dict[str, Any]:
    """
    Returns a mock FX rate for the given currency pair.
    REQUIRES a valid token to access this institutional pricing data.
    """
    import os
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
    
    # Slight randomized variance (+/- 1%)
    base = base_rates.get(currency_pair.upper(), 1.0)
    variance = base * 0.01 * random.uniform(-1, 1)
    rate = base + variance
    
    return {
        "currency_pair": currency_pair.upper(),
        "rate": round(rate, 4),
        "source": "mock_pricing_agent",
        "status": "success"
    }

async def main():
    # TODO: switch back to vertex=True once the $150 GCP credit clears 
    # (~72hrs from redemption). Currently using GEMINI_API_KEY as a 
    # temporary fallback since the credit isn't active yet — this is 
    # NOT drawing against Cloud credits right now.
    config = ag.LocalAgentConfig(
        model="gemini-3.5-flash",
        vertex=False,
        tools=[lookup_mock_fx_rate],
        policies=[policy.allow_all()],
    )
    
    async with ag.Agent(config) as agent:
        prompt = "what's the current rate for USD/NGN?"
        logging.info(f"Sending prompt: {prompt}")
        response = await agent.chat(prompt)
        text = await response.text()
        logging.info(f"Response: {text}")

if __name__ == "__main__":
    asyncio.run(main())
