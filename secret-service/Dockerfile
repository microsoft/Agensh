FROM python:3.13-slim
WORKDIR /app
COPY main.py /app/main.py
EXPOSE 8650
# Run as root inside container: the bind-mounted tokens dir is owned by
# root:root mode 0700 (bootstrap writes it). The container is only
# reachable on the docker network; threat model = same-host containers.
CMD ["python", "/app/main.py"]
