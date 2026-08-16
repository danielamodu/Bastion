#!/bin/bash
cd ~/bastion
GEMINI_KEY=$(grep GEMINI_API_KEY .env | cut -d '=' -f 2- | tr -d '"' | tr -d '\r')
~/google-cloud-sdk/bin/gcloud run deploy fx-pricing-agent \
  --source . \
  --region us-central1 \
  --project bastion-505622 \
  --set-env-vars GEMINI_API_KEY=$GEMINI_KEY
