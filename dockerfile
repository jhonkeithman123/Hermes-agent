FROM nousresearch/hermes-agent:latest

WORKDIR /app
COPY server.py /app/server.py
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 10000

ENTRYPOINT ["/app/start.sh"]
CMD ["gateway", "run"]