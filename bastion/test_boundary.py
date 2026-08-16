import os
import asyncio
import logging
from agents.fx_pricing_agent.main import lookup_mock_fx_rate

# Configure minimal logging for clear output
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_boundary():
    print("=== Testing Zero-Trust Boundary ===")
    
    # 1. Successful Call (With Valid Token)
    print("\n--- Test 1: Successful Call (Valid Token) ---")
    valid_token = os.environ.get("BASTION_SHARED_TOKEN")
    if not valid_token:
        print("Warning: BASTION_SHARED_TOKEN is not set in the environment.")
        return
        
    result_success = lookup_mock_fx_rate("USD/NGN", token=valid_token)
    if "error" in result_success:
        print(f"FAILED: Expected success but got error: {result_success['error']}")
    else:
        print(f"SUCCESS: Rate retrieved successfully: {result_success}")

    # 2. Rejected Call (Without Token)
    print("\n--- Test 2: Rejected Call (No Token) ---")
    result_rejected = lookup_mock_fx_rate("USD/NGN", token=None)
    if "error" in result_rejected:
        print(f"SUCCESS (EXPECTED REJECTION): Call correctly rejected -> {result_rejected['error']}")
    else:
        print(f"FAILED: Call should have been rejected but succeeded: {result_rejected}")

    # 3. Rejected Call (Invalid Token)
    print("\n--- Test 3: Rejected Call (Invalid Token) ---")
    result_invalid = lookup_mock_fx_rate("USD/NGN", token="invalid_hacked_token")
    if "error" in result_invalid:
        print(f"SUCCESS (EXPECTED REJECTION): Call correctly rejected -> {result_invalid['error']}")
    else:
        print(f"FAILED: Call should have been rejected but succeeded: {result_invalid}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    test_boundary()
