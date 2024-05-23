FROM debian:12.5-slim
LABEL authors="tenuki"
MAINTAINER tenuki david.weil@coinfabrik.com

RUN apt-get update && apt-get install -y python3-pip git && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/app
COPY requirements.txt .
RUN pip install --break-system-packages -r requirements.txt

COPY . .

VOLUME /drunner_db_sqlite
#-v /var/run/docker.sock:/var/run/docker.sock

ENTRYPOINT ["dramatiq", "drunner", "-t", "1", "-p", "1"]