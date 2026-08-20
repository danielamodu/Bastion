import asyncio
import logging
import os
from typing import Any, Dict
from dotenv import load_dotenv

from google import antigravity as ag
from google.antigravity.hooks import policy
from model_armor.armor import screen_for_injection

# Load environment variables
load_dotenv()

# Set up logging to see the tool invocation
logging.basicConfig(level=logging.INFO)

# Tool definition
def assess_risk(currency_pair: str, amount: float) -> Dict[str, Any]:
    """
    Returns a mock risk assessment score and flag for a given currency pair and transaction amount.
    Input is screened by Model Armor before processing.
    """
    logging.info(f"TOOL INVOKED: assess_risk(currency_pair='{currency_pair}', amount={amount})")

    # ── MODEL ARMOR GUARD ────────────────────────────────────────────────────
    # Screen currency_pair for prompt injection — this is the counterparty
    # data entry point and the most realistic injection surface.
    armor_result = screen_for_injection(currency_pair)
    if armor_result.blocked:
        logging.warning(
            "MODEL ARMOR BLOCKED | match_state=%s | input='%s'",
            armor_result.match_state, currency_pair
        )
        return {
            "error": "BLOCKED: Prompt injection detected in input.",
            "armor_match_state": armor_result.match_state,
            "blocked_input_preview": currency_pair[:120],
        }
    # ── END GUARD ────────────────────────────────────────────────────────────

    
    # Very simple mock logic
    risk_score = 0.1
    if amount > 100000:
        risk_score += 0.4
    
    if currency_pair.upper() == "USD/NGN":
        risk_score += 0.3
        
    flag = "high" if risk_score >= 0.7 else ("medium" if risk_score >= 0.4 else "low")
    
    return {
        "currency_pair": currency_pair.upper(),
        "amount": amount,
        "risk_score": round(risk_score, 2),
        "risk_flag": flag,
        "source": "mock_risk_agent"
    }

async def main():
    config = ag.LocalAgentConfig(
        model="gemini-3.5-flash",
        vertex=False,
        tools=[assess_risk],
        policies=[policy.allow_all()],
    )
    
    async with ag.Agent(config) as agent:
        prompt = "Assess the risk for a 500,000 USD/NGN transaction."
        logging.info(f"Sending prompt: {prompt}")
        response = await agent.chat(prompt)
        text = await response.text()
        logging.info(f"Response: {text}")

if __name__ == "__main__":
    asyncio.run(main())
