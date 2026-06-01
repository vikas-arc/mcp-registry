FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# Provide at runtime: JIRA_URL, JIRA_PERSONAL_TOKEN, CONFLUENCE_URL,
# CONFLUENCE_PERSONAL_TOKEN, (ATL_PORT, JIRA_SSL_VERIFY, ...)
EXPOSE 9004
CMD ["python", "server.py"]
