FROM docker:29-cli
RUN apk add --no-cache python3
WORKDIR /app
COPY deploy/compose.yml /app/deploy/compose.yml
COPY deploy/dashboard /app/deploy/dashboard
EXPOSE 8090
CMD ["python3", "/app/deploy/dashboard/server.py", "--host", "0.0.0.0", "--data-dir", "/data"]
