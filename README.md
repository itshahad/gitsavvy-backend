# How to start server? 

## 1- ensure you have docker installed in your device

## 2- request the db dump and env file from me "Shahad" 
* add the dump file to `postgres` folder
* add the `.env` file to project root folder

## 3- run the command `docker-compose up -d --build` in terminal

# How to load database `backup.dump` file? 
* add the dump file to `postgres` folder
* in docker: remove the postgres container and pgdata volume
* in vscode terminal: run the command `docker compose up -d --no-recreate` 
* open docker, in the running **postgres container**, go to `Exec` and run the following command:  
  `pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges /docker-entrypoint-initdb.d/backup.dump`

# How to access docs? 

## 1- for swagger docs:
run the server and access [localhost:8000/docs](http://localhost:8000/docs) in your browser

## 2- for postman docs:

you can find the file "GitSavvy.postman_collection.json" in root folder of project, import it in postman and you will find all endpoints


