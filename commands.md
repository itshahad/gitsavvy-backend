pip freeze > src/requirements.txt
fastapi dev src/main.py
docker-compose up -d --build


psql -U gitsavvy -d gitsavvy_db
CREATE EXTENSION vector;
