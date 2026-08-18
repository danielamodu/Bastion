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
from dataclasses import dataclass

from google.cloud import modelarmor_v1
from google.api_core.client_options import ClientOptions

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "bastion-505622")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
TEMPLATE_ID = "bastion-prompt-guard"
TEMPLATE_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/templates/{TEMPLATE_ID}"

logger = logging.getLogger(__name__)


def _get_client() -> modelarmor_v1.ModelArmorClient:
    """Return a regional Model Armor client."""
    return modelarmor_v1.ModelArmorClient(
        transport="rest",
        client_options=ClientOptions(
            api_endpoint=f"modelarmor.{LOCATION}.rep.googleapis.com"
        ),
    )


@dataclass
class ArmorResult:
    blocked: bool
    match_state: str        # "MATCH_FOUND" | "NO_MATCH_FOUND"
    raw_response: object    # full SDK response for logging/demo


def screen_for_injection(text: str) -> ArmorResult:
    """
    Send `text` to Model Armor and check for prompt injection / jailbreak.

    Returns an ArmorResult; caller must check .blocked before proceeding.
    Raises on API errors so callers can decide how to handle failures.
    """
    client = _get_client()

    request = modelarmor_v1.SanitizeUserPromptRequest(
        name=TEMPLATE_NAME,
        user_prompt_data=modelarmor_v1.DataItem(text=text),
    )

    response = client.sanitize_user_prompt(request=request)
    result = response.sanitization_result

    # filter_match_state is an enum; convert to string for logging
    match_state_str = modelarmor_v1.FilterMatchState(
        result.filter_match_state
    ).name

    blocked = match_state_str == "MATCH_FOUND"

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
        raw_response=response,
    )
