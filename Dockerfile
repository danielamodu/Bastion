FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/fx_pricing_agent /app/agents/fx_pricing_agent

ENV PYTHONPATH=/app

CMD ["uvicorn", "agents.fx_pricing_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
