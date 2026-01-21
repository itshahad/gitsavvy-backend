FROM python:3.12-slim

# set work directory -> same as the one in docker-compose.yml
WORKDIR /usr/src/app/

# prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# prevents Python from buffering stdout and stderr, cause buffering can delay log messages
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/app/requirements.txt
RUN pip install  --no-cache-dir -r requirements.txt

# copy project
COPY . /usr/src/app/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
