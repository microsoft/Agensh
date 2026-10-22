# Package the shared-context API; MySQL state is provided by the Compose stack.
FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY shared_lessons.py verifier.py unfold.py gquery.py main.py /app/
EXPOSE 8660
CMD ["python", "/app/main.py"]
