"""
setup_template.py — Run once to create the Bastion Model Armor template.

Creates a template with:
  - Prompt injection + jailbreak detection (confidence: LOW_AND_ABOVE for broad coverage)
  - No RAI filters (keeping scope tight for this phase)

Run with: python setup_template.py
"""

import logging
import os

from google.cloud import modelarmor_v1
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import AlreadyExists
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "bastion-505622")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
TEMPLATE_ID = "bastion-prompt-guard"


def main():
    client = modelarmor_v1.ModelArmorClient(
        transport="rest",
        client_options=ClientOptions(
            api_endpoint=f"modelarmor.{LOCATION}.rep.googleapis.com"
        ),
    )

    template = modelarmor_v1.Template(
        filter_config=modelarmor_v1.FilterConfig(
            pi_and_jailbreak_filter_settings=modelarmor_v1.PiAndJailbreakFilterSettings(
                filter_enforcement=modelarmor_v1.PiAndJailbreakFilterSettings.PiAndJailbreakFilterEnforcement.ENABLED,
                confidence_level=modelarmor_v1.DetectionConfidenceLevel.LOW_AND_ABOVE,
            ),
        )
    )

    request = modelarmor_v1.CreateTemplateRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
        template_id=TEMPLATE_ID,
        template=template,
    )

    try:
        response = client.create_template(request=request)
        logging.info("Template created: %s", response.name)
    except AlreadyExists:
        logging.info("Template '%s' already exists — nothing to do.", TEMPLATE_ID)


if __name__ == "__main__":
    main()
