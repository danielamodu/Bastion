"""
model_armor.py — Model Armor integration for Bastion.

Wraps the Google Cloud Model Armor API to screen incoming text for
prompt injection attempts before they reach any LLM tool.

Usage:
    from model_armor.armor import screen_for_injection

    result = screen_for_injection("some user-supplied text")
    if result.blocked:
        # reject the request
    else:
        # proceed
"""

import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Fallback heuristic patterns to catch obvious injections (Simulated Model Armor)
INJECTION_PATTERNS = [
    r"(?i)\bignore previous\b",
    r"(?i)\bbypass\b",
    r"(?i)\bsystem note\b",
    r"(?i)\bdisregard\b",
    r"(?i)\bforget everything\b",
    r"(?i)\bnew instructions\b",
]

@dataclass
class ArmorResult:
    blocked: bool
    match_state: str        # "MATCH_FOUND" | "NO_MATCH_FOUND"
    raw_response: object    # full SDK response for logging/demo


def screen_for_injection(text: str) -> ArmorResult:
    """
    Screen `text` for prompt injection / jailbreak using local heuristics.
    
    This replaces the GCP Model Armor API to allow the system to work 
    end-to-end without billing blocks, while keeping the architecture the same.
    """
    blocked = False
    match_state_str = "NO_MATCH_FOUND"
    
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text):
            blocked = True
            match_state_str = "MATCH_FOUND"
            break

    if blocked:
        logger.warning(
            "MODEL ARMOR BLOCKED INPUT | match_state=%s | text_preview='%s...'",
            match_state_str,
            text[:80],
        )
    else:
        logger.info(
            "Model Armor: input cleared | match_state=%s",
            match_state_str,
        )

    return ArmorResult(
        blocked=blocked,
        match_state=match_state_str,
        raw_response={"mock_response": "heuristic_filter_applied", "blocked": blocked},
    )
