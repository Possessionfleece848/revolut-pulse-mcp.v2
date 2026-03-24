FROM python:3.12-slim

WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY app.py .

# Default: HTTP transport for cloud deploy
ENV MCP_TRANSPORT=http
ENV PORT=8000

EXPOSE 8000

CMD ["python", "app.py"]
