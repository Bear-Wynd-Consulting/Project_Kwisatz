FROM ollama/ollama:latest

# Add curl for health checks and entrypoint readiness polling
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
# Strip Windows CRLF line endings in case the file was edited on Windows
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
