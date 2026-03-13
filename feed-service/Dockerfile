# Dockerfile
FROM python:3.13-slim

WORKDIR /app

# Kopiraj kod u kontejner
COPY . .

# Instaliraj zavisnosti
RUN pip install --no-cache-dir -r requirements.txt

# Expose port koji servis koristi
EXPOSE 5002

# Pokreni Flask aplikaciju
CMD ["python", "app.py"]