"""
test_audit_trace.py — Phase 4: Agent Observability demo.

Simulates the full risk_agent -> fx_pricing_agent call chain and
instruments every step with Cloud Trace spans:

  ROOT: bastion.risk_assessment
    ├─ registry.discover_agent
    ├─ auth.token_check
    ├─ http.call_fx_pricing_agent
    └─ result.record

Runs TWO scenarios:
  1. Successful call  (valid token -> 200 -> rate returned)
  2. Rejected call    (no token   -> 403 -> access denied)

Both produce a complete trace visible at:
  https://console.cloud.google.com/traces/list?project=bastion-505622
"""

import logging
import os
import time

import requests
from dotenv import load_dotenv

from audit.tracer import BastionTracer
from registry.registry import discover_agent

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

FX_AGENT_URL = "http://127.0.0.1:8765/invoke"
SEPARATOR = "=" * 72


def run_scenario(label: str, use_valid_token: bool):
    """Simulate one risk_agent call to fx_pricing_agent, fully traced."""
    print(f"\n{SEPARATOR}")
    print(f"SCENARIO: {label}")
    print(SEPARATOR)

    token = os.environ.get("BASTION_SHARED_TOKEN") if use_valid_token else None

    with BastionTracer(f"bastion.risk_assessment.{label.replace(' ', '_')}") as tracer:

        # ── Span 1: Registry lookup ───────────────────────────────────────────
        with tracer.span("registry.discover_agent") as span:
            span.add_label("capability", "fx_rate_lookup")
            agent_record = discover_agent("fx_rate_lookup")
            if agent_record:
                span.add_label("resolved_agent", agent_record.get("agent_id", "unknown"))
                span.set_status("FOUND")
                print(f"  [registry] Resolved: {agent_record}")
            else:
                span.set_status("NOT_FOUND")
                print("  [registry] No agent found for fx_rate_lookup")
                return

        # ── Span 2: Token check ───────────────────────────────────────────────
        with tracer.span("auth.token_check") as span:
            span.add_label("token_present", str(token is not None))
            if token:
                span.set_status("PASS")
                print(f"  [auth] Token present — proceeding")
            else:
                span.set_status("FAIL — no token")
                print(f"  [auth] No token — call will be rejected at HTTP layer")

        # ── Span 3: HTTP call to fx_pricing_agent ─────────────────────────────
        with tracer.span("http.call_fx_pricing_agent") as span:
            span.add_label("url", FX_AGENT_URL)
            span.add_label("token_present", str(token is not None))

            headers = {}
            if token:
                headers["X-Bastion-Token"] = token

            try:
                resp = requests.post(
                    FX_AGENT_URL,
                    json={"prompt": "What is the current rate for USD/NGN?"},
                    headers=headers,
                    timeout=180,
                )
                span.add_label("http_status", str(resp.status_code))
                span.add_label("response_body", resp.text[:200])

                if resp.status_code == 200:
                    span.set_status("SUCCESS")
                    print(f"  [http] Status: {resp.status_code} → {resp.json()}")
                else:
                    span.set_status(f"REJECTED_{resp.status_code}")
                    print(f"  [http] Status: {resp.status_code} → {resp.text}")
            except requests.exceptions.ReadTimeout:
                span.set_status("TIMEOUT")
                print("  [http] Request timed out")

        # ── Span 4: Record result ─────────────────────────────────────────────
        with tracer.span("result.record") as span:
            outcome = "success" if use_valid_token else "rejected_403"
            span.add_label("outcome", outcome)
            span.add_label("scenario", label)
            span.set_status(outcome.upper())
            print(f"  [result] Recorded outcome: {outcome}")

    print(f"\n  ✓ Trace complete. trace_id={tracer.trace_id}")
    print(f"    View: https://console.cloud.google.com/traces/list?project=bastion-505622")


if __name__ == "__main__":
    import subprocess, sys, time as _time

    print("\n🔍 BASTION — Phase 4: Agent Observability / Audit Trace Demo\n")

    # Start the FastAPI server
    print("Starting fx_pricing_agent FastAPI server on :8765 ...")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "agents.fx_pricing_agent.main:app",
         "--host", "127.0.0.1", "--port", "8765"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Wait for it to be ready
    deadline = _time.time() + 15
    while _time.time() < deadline:
        try:
            requests.get("http://127.0.0.1:8765/docs", timeout=1)
            break
        except Exception:
            _time.sleep(0.3)
    print("Server ready.\n")

    try:
        # Scenario 1: valid token → success
        run_scenario("valid_token_success", use_valid_token=True)

        # Brief pause so the traces land in different seconds
        _time.sleep(2)

        # Scenario 2: no token → rejected
        run_scenario("no_token_rejected", use_valid_token=False)

    finally:
        print("\nShutting down server...")
        server.terminate()
        server.wait()

    print(f"\n{SEPARATOR}")
    print("Phase 4 complete.")
    print("Both traces are now visible in Cloud Trace:")
    print("  https://console.cloud.google.com/traces/list?project=bastion-505622")
    print(SEPARATOR)
