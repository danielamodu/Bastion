import os
import asyncio
from dotenv import load_dotenv
import google.antigravity as ag
from google.antigravity.connections.local.local_connection_config import LocalAgentConfig

# Load environment variables
load_dotenv()

async def main():
    # Retrieve the GCP project and region
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    region = os.environ.get("GOOGLE_CLOUD_REGION")
    
    if not project_id or not region:
        print("Error: GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_REGION is not set.")
        return

    # TODO: switch back to vertex=True once the $150 GCP credit clears 
    # (~72hrs from redemption). Currently using GEMINI_API_KEY as a 
    # temporary fallback since the credit isn't active yet — this is 
    # NOT drawing against Cloud credits right now.
    # Configure the local agent to use Gemini 3.5 via GEMINI_API_KEY (non-Vertex)
    config = LocalAgentConfig(
        model="gemini-3.5-flash",
        vertex=False,
        system_instructions="You are a helpful assistant. Please respond to the user in a friendly manner."
    )

    # Initialize the agent
    async with ag.Agent(config=config) as agent:
        # Send a prompt to the agent and get a response
        response = await agent.chat("Hello! Please confirm you are running and able to reason.")
        
        print("Agent Response:")
        print("-" * 20)
        print(await response.text())

if __name__ == "__main__":
    asyncio.run(main())
