import asyncio
import logging
import os
from dotenv import load_dotenv

from google import antigravity as ag
from google.antigravity.hooks import policy

# Import the registry module to register risk_agent
from registry.registry import register_agent

# Import tools for both agents
from agents.risk_agent.agent import assess_risk
from agents.fx_pricing_agent.agent import lookup_mock_fx_rate

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Load environment variables
load_dotenv()

async def run_test(test_name: str, prompt: str):
    print(f"\n{'='*50}\n--- {test_name} ---\n{'='*50}")
    
    # We create a risk agent config that has BOTH tools bound so it can call the FX tool
    config = ag.LocalAgentConfig(
        model="gemini-3.5-flash",
        vertex=False,
        tools=[assess_risk, lookup_mock_fx_rate],
        policies=[policy.allow_all()],
    )
    
    # Provide the shared token explicitly in the instructions for the success test
    shared_token = os.environ.get("BASTION_SHARED_TOKEN", "MISSING_TOKEN")
    
    # We add a system instruction explaining how to use the zero-trust token
    system_instruction = (
        "You are a risk assessment agent. You have the ability to assess risk using 'assess_risk' "
        "and look up FX rates using 'lookup_mock_fx_rate'. "
        "CRITICAL: The 'lookup_mock_fx_rate' tool is behind a zero-trust boundary. "
        f"If the user asks you to look up a rate with valid credentials, you MUST pass the exact token '{shared_token}' to 'lookup_mock_fx_rate'. "
        "If the user asks you to omit the token or use an invalid one, you must do exactly what they ask and pass the invalid string they provide."
    )
    
    async with ag.Agent(config, system_instruction=system_instruction) as agent:
        logging.info(f"Sending prompt: {prompt}")
        response = await agent.chat(prompt)
        text = await response.text()
        logging.info(f"Agent Response:\n{text}")

def main():
    print("--- Registering risk_agent ---")
    register_agent(
        agent_id="risk_agent",
        endpoint="local",
        capabilities=["risk_assessment"]
    )
    print("Registration complete.\n")

    # Run the success and failure cases sequentially
    asyncio.run(run_test(
        test_name="SUCCESS CASE (Valid Token)",
        prompt="Assess the risk of trading 500,000 USD/NGN. Please also lookup the FX rate for USD/NGN and use the valid credential token when calling the pricing tool."
    ))
    
    asyncio.run(run_test(
        test_name="FAILURE CASE (Invalid/Missing Token)",
        prompt="Now assess the risk of trading 500,000 EUR/USD. Also lookup the FX rate for EUR/USD, but this time explicitly use the invalid token 'wrong-token' to test the zero-trust boundary."
    ))

if __name__ == "__main__":
    main()
