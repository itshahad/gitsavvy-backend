pip freeze > src/requirements.txt
fastapi dev src/main.py
celery -A src.worker:worker purge -f
chmod +x postgres/01-restore.sh

<!-- Migrations -->
alembic revision --autogenerate -m "add count columns to repos"
alembic upgrade head

<!-- DUMP DB -->
pg_dump -U gitsavvy -d gitsavvy_db -F c -f /tmp/backup.dump
docker cp gitsavvy_postgres:/tmp/backup.dump ./postgres/backup.dump

                                                                                                           
<!-- START PROJECT: -->
docker-compose up -d --build
                                                             
<!-- CREATE MISSING CONTAINERS -->
docker compose up -d --no-recreate

<!-- LOAD DB BACKUP IN POSTGRES CONTAINER EXEC -->
pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges /docker-entrypoint-initdb.d/backup.dump
