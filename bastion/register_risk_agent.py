from registry.registry import register_agent

if __name__ == "__main__":
    print("--- Registering risk_agent ---")
    register_agent(
        agent_id="risk_agent",
        endpoint="local",
        capabilities=["risk_assessment"]
    )
    print("Registration complete.")
