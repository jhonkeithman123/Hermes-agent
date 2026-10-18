FROM nousresearch/hermes-agent:latest

WORKDIR /app
COPY server.py /app/server.py
COPY start.sh /app/start.sh
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

EXPOSE 10000

ENTRYPOINT ["/bin/bash", "/app/start.sh"]
CMD ["gateway", "run"]