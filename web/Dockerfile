FROM debian:12.5-slim
LABEL authors="tenuki"
MAINTAINER tenuki david.weil@coinfabrik.com

RUN apt-get update && apt-get install -y python3-pip && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/app
COPY requirements.txt /usr/app
RUN pip install --break-system-packages -r requirements.txt

COPY . /usr/app
ENV FLASK_APP app.py

VOLUME /drunner_db_sqlite

EXPOSE 5000
ENTRYPOINT ["flask", "run", "--host=0.0.0.0"]
