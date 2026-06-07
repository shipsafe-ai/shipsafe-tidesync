FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build dashboard static export if present
RUN if [ -d "dashboard" ] && [ -f "dashboard/package.json" ]; then \
    cd dashboard && npm ci && npm run build && npm run export; \
    fi

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
