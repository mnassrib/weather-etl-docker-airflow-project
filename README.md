
# Configuration d'un Pipeline ETL avec Apache Airflow et MySQL via Docker

## Table des matières
1. [Introduction au projet](#introduction-au-projet)
2. [Structure du projet](#structure-du-projet)
3. [Configuration des variables d'environnement](#configuration-des-variables-denvironnement)
4. [Création des fichiers de configuration](#création-des-fichiers-de-configuration)
    - [Docker Compose](#docker-compose)
    - [Script d'initialisation MySQL](#script-dinitialisation-mysql)
5. [Configuration du DAG Airflow](#configuration-du-dag-airflow)
6. [Vérification et Déploiement](#vérification-et-déploiement)
7. [Conclusion](#conclusion)

## Introduction au projet

Ce projet a pour objectif de configurer un pipeline ETL (Extract, Transform, Load) utilisant Apache Airflow pour automatiser la collecte, la transformation, et le chargement de données météorologiques dans une base de données MySQL. Le projet est déployé à l'aide de Docker Compose, avec deux bases de données MySQL distinctes : l'une pour stocker les métadonnées d'Airflow et l'autre pour stocker les données météorologiques collectées depuis l'API publique d'OpenWeatherMap.

### Pourquoi ce projet ?

1. **Automatisation** : Utiliser Apache Airflow permet d'automatiser et de planifier l'extraction de données météorologiques, leur transformation et leur chargement dans une base de données.
2. **Séparation des responsabilités** : L'utilisation de deux bases de données distinctes permet de séparer les métadonnées de gestion d'Airflow des données applicatives spécifiques (ici, les données météorologiques).
3. **Scalabilité** : Grâce à Docker Compose, vous pouvez déployer ce projet facilement sur différents environnements, et le faire évoluer en ajoutant de nouveaux services ou en modifiant les configurations existantes.

## Structure du projet

Voici la structure du projet :

```
weather-etl-docker-airflow-project/
├── docker-compose.yml
├── .env
├── airflow/
│   ├── dags/
│   │   └── weather_etl.py
│   ├── logs/
│   ├── plugins/
│   ├── Dockerfile
│   └── requirements.txt
└── mysql/
    ├── init.sql
    └── my.cnf
```

### Description des répertoires et fichiers :

- **`docker-compose.yml`** : Fichier de configuration Docker Compose définissant les services, volumes, et réseaux nécessaires pour déployer l'application.
- **`.env`** : Fichier contenant les variables d'environnement utilisées pour configurer MySQL et Airflow.
- **`airflow/`** : Répertoire contenant les fichiers et configurations spécifiques à Airflow, y compris le DAG du pipeline ETL.
- **`mysql/init.sql`** : Script SQL pour initialiser les bases de données et les utilisateurs. Ce script est exécuté automatiquement au démarrage du conteneur MySQL via Docker Compose.
- **`mysql/my.cnf`** : Fichier de configuration MySQL optionnel. Il permet de personnaliser la configuration MySQL si nécessaire, mais il n'est pas utilisé directement dans ce projet.

## Configuration des variables d'environnement

Créez un fichier `.env` à la racine du projet avec le contenu suivant :

```env
# MySQL environment variables
MYSQL_ROOT_PASSWORD=rootpassword
MYSQL_DATABASE=airflow_db
MYSQL_HOST=mysql
MYSQL_USER=airflow
MYSQL_PASSWORD=123

# Weather Database environment variables
WEATHER_MYSQL_DATABASE=meteo
WEATHER_USER=airflow
WEATHER_PASSWORD=123

# Weather API environment variables
WEATHER_API_KEY=your_api_key
WEATHER_CITY=Marseille
WEATHER_LANG=fr
WEATHER_UNITS=metric
```

### Explication des variables d'environnement :

- **`MYSQL_ROOT_PASSWORD`** : Le mot de passe root pour le serveur MySQL. Utilisé pour créer les bases de données et les utilisateurs.
- **`MYSQL_DATABASE`** : Le nom de la base de données utilisée par Airflow pour stocker ses métadonnées.
- **`MYSQL_USER`** et **`MYSQL_PASSWORD`** : Les informations de connexion pour l'utilisateur MySQL utilisé par Airflow.
- **`WEATHER_MYSQL_DATABASE`** : Le nom de la base de données qui stocke les données météorologiques.
- **`WEATHER_USER`** et **`WEATHER_PASSWORD`** : Les informations de connexion pour l'utilisateur MySQL qui accède à la base de données météorologique.
- **`WEATHER_API_KEY`**, **`WEATHER_CITY`**, **`WEATHER_LANG`**, **`WEATHER_UNITS`** : Paramètres pour accéder à l'API OpenWeatherMap, notamment la clé API, la ville ciblée, la langue des données, et les unités (métriques, impériales).

## Création des fichiers de configuration

### Docker Compose

Voici le contenu du fichier `docker-compose.yml` :

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:5.7
    container_name: mysql
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
    volumes:
      - mysql-data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-p${MYSQL_ROOT_PASSWORD}"]
      interval: 10s
      timeout: 10s
      retries: 5
    networks:
      - airflow_network

  mysql-setup:
    image: mysql:5.7
    container_name: mysql-setup
    command: >
      bash -c "
      sleep 60 && 
      mysql -h mysql -u root -p${MYSQL_ROOT_PASSWORD} -e \"
        CREATE DATABASE IF NOT EXISTS ${WEATHER_MYSQL_DATABASE};
        CREATE USER IF NOT EXISTS '${WEATHER_USER}'@'%' IDENTIFIED BY '${WEATHER_PASSWORD}';
        GRANT ALL PRIVILEGES ON ${WEATHER_MYSQL_DATABASE}.* TO '${WEATHER_USER}'@'%';
        FLUSH PRIVILEGES;\"
      "
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      WEATHER_MYSQL_DATABASE: ${WEATHER_MYSQL_DATABASE}
      WEATHER_USER: ${WEATHER_USER}
      WEATHER_PASSWORD: ${WEATHER_PASSWORD}
    networks:
      - airflow_network
    depends_on:
      mysql:
        condition: service_healthy
    restart: "no"

  airflow-init:
    image: apache/airflow:2.3.0
    container_name: airflow-init
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: mysql://${MYSQL_USER}:${MYSQL_PASSWORD}@mysql:3306/${MYSQL_DATABASE}
      AIRFLOW__CORE__LOAD_EXAMPLES: 'False'
    entrypoint: /bin/bash
    command: -c "sleep 30 && airflow db upgrade && airflow users create --username admin --password admin --firstname Air --lastname Flow --role Admin --email admin@example.com"
    depends_on:
      mysql:
        condition: service_healthy
    networks:
      - airflow_network
    restart: "no"

  airflow-webserver:
    image: apache/airflow:2.3.0
    container_name: airflow-webserver
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: mysql://${MYSQL_USER}:${MYSQL_PASSWORD}@mysql:3306/${MYSQL_DATABASE}
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/plugins:/opt/airflow/plugins
    ports:
      - "8080:8080"
    depends_on:
      mysql:
        condition: service_healthy
      airflow-init:
        condition: service_completed_successfully
    networks:
      - airflow_network

volumes:
  mysql-data:

networks:
  airflow_network:
```

### Explication du fichier Docker Compose :

- **`mysql`** : Le service MySQL principal, configuré pour stocker les métadonnées d'Airflow et les données météorologiques. Il inclut un `healthcheck` pour vérifier que MySQL est prêt à accepter des connexions avant que les autres services ne démarrent.
- **`mysql-setup`** : Un service temporaire qui initialise la base de données `meteo` et configure l'utilisateur `airflow` avec les permissions appropriées.
- **`airflow-init`** : Ce service initialise la base de données Airflow et crée l'utilisateur administrateur d'Airflow.
- **`airflow-webserver`** : Le serveur web d'Airflow, qui expose l'interface utilisateur via le port `8080`.

### Script d'initialisation MySQL

Le script `mysql/init.sql` n'est pas nécessaire dans cette configuration car la création des bases de données et des utilisateurs est gérée directement par le service `mysql-setup`. Toutefois, vous pouvez conserver ce fichier pour des tâches d'initialisation supplémentaires ou pour des besoins spécifiques.

## Configuration du DAG Airflow

Dans le fichier `airflow/dags/weather_etl.py`, configurez votre pipeline ETL pour automatiser la collecte et le traitement des données météorologiques. Voici un exemple de code pour le DAG :

```python
import os
from airflow import DAG
from airflow

.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import requests
import mysql.connector
from mysql.connector import Error

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'weather_etl',
    default_args=default_args,
    description='ETL simple pour extraire, transformer et charger des données météorologiques',
    schedule_interval=timedelta(minutes=2),
    start_date=datetime(2024, 8, 7),
    catchup=False,
)

def create_table(**kwargs):
    connection = None
    try:
        connection = mysql.connector.connect(
            host=os.getenv('MYSQL_HOST'),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD'),
            database=os.getenv('WEATHER_MYSQL_DATABASE')
        )
        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS weather (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    city VARCHAR(255),
                    temperature FLOAT,
                    weather VARCHAR(255),
                    humidity INT,
                    pressure INT,
                    wind_speed FLOAT,
                    lt VARCHAR(255),
                    utc VARCHAR(255)
                );
                """
            )
            connection.commit()
            cursor.close()
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            connection.close()

def extract_weather_data(**kwargs):
    api_key = os.getenv('WEATHER_API_KEY')
    city = os.getenv('WEATHER_CITY')
    lang = os.getenv('WEATHER_LANG')
    units = os.getenv('WEATHER_UNITS')
    response = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city}&lang={lang}&appid={api_key}&units={units}")
    weather_data = response.json()
    kwargs['ti'].xcom_push(key='weather_data', value=weather_data)

def transform_weather_data(**kwargs):
    ti = kwargs['ti']
    weather_data = ti.xcom_pull(key='weather_data', task_ids='extract_weather_data')
    utc_timestamp = datetime.fromtimestamp(weather_data["dt"], tz=timezone.utc)
    local_timestamp = utc_timestamp + timedelta(seconds=weather_data['timezone'])
    transformed_data = {
        "city": weather_data["name"],
        "temperature": weather_data["main"]["temp"],
        "weather": weather_data["weather"][0]["description"],
        "humidity": weather_data["main"]["humidity"],
        "pressure": weather_data["main"]["pressure"],
        "wind_speed": weather_data["wind"]["speed"],
        "lt": local_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        "utc": utc_timestamp.strftime('%Y-%m-%d %H:%M:%S')
    }
    ti.xcom_push(key='transformed_data', value=transformed_data)

def load_weather_data(**kwargs):
    ti = kwargs['ti']
    transformed_data = ti.xcom_pull(key='transformed_data', task_ids='transform_weather_data')
    connection = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('WEATHER_MYSQL_DATABASE')
    )
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO weather (city, temperature, weather, humidity, pressure, wind_speed, lt, utc)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            transformed_data["city"], 
            transformed_data["temperature"], 
            transformed_data["weather"], 
            transformed_data["humidity"], 
            transformed_data["pressure"], 
            transformed_data["wind_speed"], 
            transformed_data["lt"],
            transformed_data["utc"]
        )
    )
    connection.commit()
    cursor.close()
    connection.close()

create_table_task = PythonOperator(
    task_id='create_table',
    python_callable=create_table,
    dag=dag,
)

extract_task = PythonOperator(
    task_id='extract_weather_data',
    python_callable=extract_weather_data,
    dag=dag,
)

transform_task = PythonOperator(
    task_id='transform_weather_data',
    python_callable=transform_weather_data,
    dag=dag,
)

load_task = PythonOperator(
    task_id='load_weather_data',
    python_callable=load_weather_data,
    dag=dag,
)

create_table_task >> extract_task >> transform_task >> load_task
```

### Explication des tâches du DAG :

- **`create_table`** : Crée la table `weather` dans la base de données `meteo` si elle n'existe pas déjà.
- **`extract_weather_data`** : Extrait les données météorologiques de l'API OpenWeatherMap.
- **`transform_weather_data`** : Transforme les données extraites en un format prêt à être chargé dans la base de données.
- **`load_weather_data`** : Charge les données transformées dans la table `weather`.

## Vérification et déploiement

1. **Accéder au dossier du projet** :
   - Ouvrez un terminal ou une invite de commande.
   - Utilisez la commande `cd` pour naviguer jusqu'au dossier où se trouve votre fichier `docker-compose.yml`. Par exemple :
   
     - **Sur Windows** :
       ```bash
       cd C:\Users\VotreNomUtilisateur\Documents\weather-etl-docker-airflow-project
       ```
   
     - **Sur macOS/Linux** :
       ```bash
       cd /home/votre_nom_utilisateur/Documents/weather-etl-docker-airflow-project
       ```
   
   - Vérifiez que vous êtes dans le bon dossier en listant les fichiers avec `ls` ou `dir` pour vous assurer que `docker-compose.yml` est présent.

2. **Vérification de la configuration** :
   - Assurez-vous que toutes les variables d'environnement sont correctement définies dans `.env`.
   - Vérifiez que tous les fichiers nécessaires sont présents dans leur emplacement respectif.

3. **Démarrage du projet** :
   - Démarrez les services avec Docker Compose :
   ```bash
   docker-compose up -d
   ```
   Cette commande démarre tous les services définis dans votre fichier `docker-compose.yml` en mode détaché (`-d`), ce qui signifie que les conteneurs s'exécuteront en arrière-plan.

4. **Accès à l'interface Airflow** :
   - Une fois tous les services démarrés, accédez à l'interface web d'Airflow via `http://localhost:8080` pour vérifier que le DAG est disponible et que les tâches s'exécutent correctement.

5. **Accès à l'interface Adminer** :
   - Accédez à l'interface web d'Adminer via `http://localhost:8081` pour gérer vos bases de données MySQL. Vous pouvez utiliser Adminer pour vérifier que les bases de données `airflow_db` et `meteo` ont été créées correctement, et que les tables appropriées existent dans la base de données `meteo`.

6. **Vérification des bases de données** :
   - Connectez-vous à MySQL pour vérifier que les bases de données `airflow_db` et `meteo` ont été créées, et que les tables appropriées ont été créées dans la base de données `meteo`.

   ```bash
   docker exec -it mysql mysql -u root -p
   SHOW DATABASES;
   ```

   ```sql
   USE meteo;
   SHOW TABLES;
   ```

## Conclusion

Ce guide vous a accompagné dans la configuration d'un pipeline ETL complet utilisant Airflow et MySQL, déployé avec Docker Compose. Grâce à cette configuration, vous pouvez automatiser l'extraction, la transformation et le chargement de données depuis une API publique vers une base de données MySQL dédiée. En suivant les étapes de ce manuel, vous avez mis en place une infrastructure robuste capable de gérer efficacement vos besoins en traitement de données. N'hésitez pas à ajuster la configuration en fonction de vos besoins spécifiques et à surveiller les performances de votre pipeline pour garantir son bon fonctionnement à long terme.

