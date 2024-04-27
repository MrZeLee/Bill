FROM python:3.12.3-slim-bookworm

WORKDIR /app

# Copy requirements.txt file
COPY requirements.txt ./

COPY ./src ./src

RUN pip install -r requirements.txt

CMD ["python3", "./src/main.py"]
