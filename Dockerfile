FROM python:3.10-slim
RUN apt update && apt install -y \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python","server.py"]
