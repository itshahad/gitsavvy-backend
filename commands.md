pip freeze > src/requirements.txt
fastapi dev src/main.py
docker-compose up -d --build