# Dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5001

# Pokreni Flask aplikaciju
CMD ["python", "app.py"]