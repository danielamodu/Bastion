"""
test_boundary.py — HTTP-layer zero-trust boundary test.

Starts a real uvicorn server, sends three POST requests to /invoke:
  1. Valid token   -> expect 200
  2. No token      -> expect 403
  3. Invalid token -> expect 403

All rejections happen at the HTTP layer before the agent runs.
"""

import os
import sys
import time
import signal
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8765"
INVOKE_URL = f"{BASE_URL}/invoke"
PORT = 8765

def wait_for_server(url: str, timeout: int = 15) -> bool:
    """Poll the server health until it's up or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1)
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(0.3)
    return False


def run_tests(valid_token: str):
    print("=== Zero-Trust Boundary Test (HTTP Layer) ===\n")

    # ── Test 1: Valid token ────────────────────────────────────────────────────
    print("--- Test 1: Valid X-Bastion-Token header ---")
    r1 = requests.post(
        INVOKE_URL,
        json={"prompt": "What is the FX rate for USD/NGN?"},
        headers={"X-Bastion-Token": valid_token},
        timeout=180,  # LLM round-trip can take 60-120s
    )
    print(f"  HTTP Status : {r1.status_code}")
    print(f"  Body        : {r1.text}\n")

    # ── Test 2: No token ──────────────────────────────────────────────────────
    print("--- Test 2: No X-Bastion-Token header ---")
    r2 = requests.post(
        INVOKE_URL,
        json={"prompt": "What is the FX rate for USD/NGN?"},
        timeout=10,
    )
    print(f"  HTTP Status : {r2.status_code}")
    print(f"  Body        : {r2.text}\n")

    # ── Test 3: Invalid token ─────────────────────────────────────────────────
    print("--- Test 3: Invalid X-Bastion-Token header ---")
    r3 = requests.post(
        INVOKE_URL,
        json={"prompt": "What is the FX rate for USD/NGN?"},
        headers={"X-Bastion-Token": "invalid_hacked_token"},
        timeout=10,
    )
    print(f"  HTTP Status : {r3.status_code}")
    print(f"  Body        : {r3.text}\n")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=== Summary ===")
    t1_ok = r1.status_code == 200
    t2_ok = r2.status_code == 403
    t3_ok = r3.status_code == 403
    print(f"  Test 1 (valid token   -> 200): {'PASS' if t1_ok else 'FAIL'} (got {r1.status_code})")
    print(f"  Test 2 (no token      -> 403): {'PASS' if t2_ok else 'FAIL'} (got {r2.status_code})")
    print(f"  Test 3 (invalid token -> 403): {'PASS' if t3_ok else 'FAIL'} (got {r3.status_code})")
    return all([t1_ok, t2_ok, t3_ok])


if __name__ == "__main__":
    valid_token = os.environ.get("BASTION_SHARED_TOKEN")
    if not valid_token:
        print("ERROR: BASTION_SHARED_TOKEN is not set in the environment.")
        sys.exit(1)

    # Start uvicorn as a subprocess
    print(f"Starting uvicorn on port {PORT}...")
    server = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "agents.fx_pricing_agent.main:app",
            "--host", "127.0.0.1",
            "--port", str(PORT),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        if not wait_for_server(f"http://127.0.0.1:{PORT}/docs"):
            print("ERROR: Server did not start within timeout.")
            server.terminate()
            sys.exit(1)

        print(f"Server is up. Running tests...\n")
        success = run_tests(valid_token)
    finally:
        print("\nShutting down uvicorn...")
        server.terminate()
        server.wait()

    sys.exit(0 if success else 1)
