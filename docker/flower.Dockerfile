FROM python:3.12-slim

# set work directory -> same as the one in docker-compose.yml
WORKDIR /usr/src/app/

# install dependencies
RUN pip install  --no-cache-dir celery flower redis

# copy project
COPY . /usr/src/app/