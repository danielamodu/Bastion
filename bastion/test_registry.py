import os
from dotenv import load_dotenv

# Load .env explicitly to ensure GOOGLE_CLOUD_PROJECT is available
load_dotenv()

from registry.registry import register_agent, discover_agent

def main():
    print("--- Testing Registration ---")
    register_agent(
        agent_id="fx_pricing_agent",
        endpoint="local",
        capabilities=["fx_rate_lookup"]
    )
    print("Registration complete.\n")
    
    print("--- Testing Discovery ---")
    record = discover_agent("fx_rate_lookup")
    
    print("Discovery Result:")
    print(record)

if __name__ == "__main__":
    main()
