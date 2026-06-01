FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web.py agent_cli.py ./
COPY static ./static

# Provide at runtime: OPENAI_API_KEY, REGISTRY_URL, AGENT_MODEL, (AGENT_API_KEY)
EXPOSE 8800
CMD ["uvicorn", "web:app", "--host", "0.0.0.0", "--port", "8800"]
