FROM python:3.11-slim

WORKDIR /app

RUN apt update && apt install -y aria2

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN chmod +x start.sh

CMD ["bash", "start.sh"]
