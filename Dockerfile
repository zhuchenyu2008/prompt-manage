FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data && \
    chmod 755 /app/data

EXPOSE 3501

ENV FLASK_APP=app.py
ENV FLASK_ENV=production

CMD ["python", "app.py"]