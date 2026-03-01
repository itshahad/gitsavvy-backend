pip freeze > src/requirements.txt
fastapi dev src/main.py
celery -A src.worker:worker purge -f
chmod +x postgres/restore.sh

<!-- DUMP DB -->
pg_dump -U gitsavvy -d gitsavvy_db -F c -f /tmp/backup.dump
docker cp gitsavvy_postgres:/tmp/backup.dump ./postgres/backup.dump


<!-- START PROJECT: -->
docker-compose up -d --build