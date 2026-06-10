FROM python:3.11-slim

WORKDIR /app

# git needed to fetch the official Fivetran MCP server
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Pre-install the official Fivetran MCP server (fivetran/fivetran-mcp) so the
# Fivetran control-plane reads can flow through the real MCP protocol over stdio.
# server.py launches as `python /opt/fivetran-mcp/server.py`; it needs mcp + httpx
# + python-dotenv (installed via requirements below).
RUN git clone --depth 1 https://github.com/fivetran/fivetran-mcp /opt/fivetran-mcp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FIVETRAN_MCP_SERVER=/opt/fivetran-mcp/server.py

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
