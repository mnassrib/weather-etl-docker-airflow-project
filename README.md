
# Configuration d'un Pipeline ETL avec Apache Airflow et MySQL via Docker

## Table des matières
1. [Introduction au projet](#introduction-au-projet)
2. [Structure du projet](#structure-du-projet)
3. [Configuration des variables d'environnement](#configuration-des-variables-denvironnement)
4. [Création des fichiers de configuration](#création-des-fichiers-de-configuration)
    - [Docker Compose](#docker-compose)
    - [Script d'initialisation MySQL](#script-dinitialisation-mysql)
5. [Configuration du DAG Airflow](#configuration-du-dag-airflow)
6. [Vérification et déploiement](#vérification-et-déploiement)
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
services:
  mysql:
    image: mysql:5.7
    container_name: mysql
    command: --default-authentication-plugin=mysql_native_password --explicit_defaults_for_timestamp=1
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql-data:/var/lib/mysql
      - ./mysql/my.cnf:/etc/mysql/my.cnf 
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
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
        mysql -h mysql -u root -p${MYSQL_ROOT_PASSWORD} -e \"
          CREATE DATABASE IF NOT EXISTS ${WEATHER_MYSQL_DATABASE};
          CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
          GRANT ALL PRIVILEGES ON ${WEATHER_MYSQL_DATABASE}.* TO '${MYSQL_USER}'@'%';
          FLUSH PRIVILEGES;\"
        "
      environment:
        MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
        WEATHER_MYSQL_DATABASE: ${WEATHER_MYSQL_DATABASE}
        MYSQL_USER: ${MYSQL_USER}
        MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      networks:
        - airflow_network
      depends_on:
        mysql:
          condition: service_healthy
      restart: "no"

  adminer:
    image: adminer
    container_name: adminer
    ports:
      - "8081:8080"
    depends_on:
      - mysql
    environment:
      ADMINER_DEFAULT_SERVER: mysql
    networks:
      - airflow_network

  airflow-init:
    image: apache/airflow:2.3.0
    container_name: airflow-init
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: mysql://${MYSQL_USER}:${MYSQL_PASSWORD}@mysql:3306/${MYSQL_DATABASE}
      AIRFLOW__CORE__LOAD_EXAMPLES: 'False'
    entrypoint: /bin/bash
    command: -c "airflow db upgrade && airflow users create --username admin --password admin --firstname Air --lastname Flow --role Admin --email admin@example.com"
    depends_on:
      mysql:
        condition: service_healthy
    networks:
      - airflow_network
    restart: "no"

  airflow:
    build: ./airflow
    image: airflow
    container_name: airflow
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: mysql://${MYSQL_USER}:${MYSQL_PASSWORD}@mysql:3306/${MYSQL_DATABASE}
      AIRFLOW__CORE__LOAD_EXAMPLES: 'False'
      MYSQL_HOST: ${MYSQL_HOST}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      WEATHER_MYSQL_DATABASE: ${WEATHER_MYSQL_DATABASE}
      WEATHER_API_KEY: ${WEATHER_API_KEY}
      WEATHER_CITY: ${WEATHER_CITY}
      WEATHER_LANG: ${WEATHER_LANG}
      WEATHER_UNITS: ${WEATHER_UNITS}
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
    command: >
      bash -c "airflow scheduler & airflow webserver"
    networks:
      - airflow_network

volumes:
  mysql-data:

networks:
  airflow_network:
```

### Explication du fichier `docker-compose.yml`

Le fichier `docker-compose.yml` décrit la configuration d'un ensemble de services Docker interconnectés pour déployer un pipeline ETL (Extract, Transform, Load) utilisant Apache Airflow et MySQL. Voici une explication détaillée de chaque section du fichier :

#### Services

1. **MySQL** (`mysql`):
   - **Image** : Utilise l'image officielle MySQL 5.7.
   - **Container Name** : Le conteneur est nommé `mysql`.
   - **Command** : Spécifie des options pour MySQL, notamment l'utilisation de l'authentification native (`mysql_native_password`) et la gestion explicite des `timestamp`.
   - **Environment** : Les variables d'environnement pour configurer MySQL. Elles incluent le mot de passe root, le nom de la base de données par défaut, l'utilisateur MySQL, et le mot de passe utilisateur.
   - **Volumes** : Monte le répertoire de données MySQL (`mysql-data`) pour persister les données, et monte le fichier de configuration MySQL (`my.cnf`).
   - **Healthcheck** : Vérifie la disponibilité de MySQL en exécutant `mysqladmin ping` toutes les 10 secondes, avec un délai de 10 secondes et 5 tentatives avant de considérer le conteneur comme `unhealthy`.
   - **Networks** : Connecte le conteneur au réseau `airflow_network`.

2. **MySQL Setup** (`mysql-setup`):
   - **Image** : Utilise également l'image MySQL 5.7.
   - **Container Name** : Le conteneur est nommé `mysql-setup`.
   - **Command** : Exécute un script bash pour créer une nouvelle base de données (`WEATHER_MYSQL_DATABASE`), un utilisateur (`MYSQL_USER`), et accorde les privilèges nécessaires. Le conteneur attend que MySQL soit prêt (`service_healthy`) avant de s'exécuter.
   - **Environment** : Les variables d'environnement pour se connecter à MySQL et configurer la base de données et les utilisateurs.
   - **Depends_on** : Assure que `mysql-setup` ne démarre que lorsque MySQL est prêt (`service_healthy`).
   - **Restart** : Le conteneur ne redémarre pas automatiquement (`restart: "no"`).

3. **Adminer** (`adminer`):
   - **Image** : Utilise l'image officielle `adminer`, un outil d'administration de bases de données accessible via une interface web.
   - **Container Name** : Le conteneur est nommé `adminer`.
   - **Ports** : Mappe le port `8080` du conteneur sur le port `8081` de l'hôte, permettant d'accéder à Adminer via `http://localhost:8081`.
   - **Depends_on** : Le conteneur `adminer` dépend du conteneur MySQL.
   - **Environment** : Spécifie le serveur MySQL par défaut pour Adminer (`mysql`).
   - **Networks** : Connecte le conteneur au réseau `airflow_network`.

4. **Airflow Init** (`airflow-init`):
   - **Image** : Utilise l'image Apache Airflow 2.3.0.
   - **Container Name** : Le conteneur est nommé `airflow-init`.
   - **Environment** : Configure Airflow, notamment l'exécuteur utilisé (`LocalExecutor`) et la connexion à la base de données MySQL.
   - **Command** : Initialise la base de données Airflow avec `airflow db upgrade` et crée un utilisateur administrateur.
   - **Depends_on** : Assure que `airflow-init` ne démarre que lorsque MySQL est prêt (`service_healthy`).
   - **Restart** : Le conteneur ne redémarre pas automatiquement (`restart: "no"`).

5. **Airflow Webserver** (`airflow`):
   - **Build** : Utilise un Dockerfile personnalisé situé dans le répertoire `./airflow` pour construire l'image.
   - **Container Name** : Le conteneur est nommé `airflow`.
   - **Environment** : Configure Airflow, notamment la connexion à MySQL, les configurations de la base de données `WEATHER_MYSQL_DATABASE`, et les variables pour accéder à l'API OpenWeatherMap.
   - **Volumes** : Monte les répertoires contenant les DAGs, logs, et plugins d'Airflow.
   - **Ports** : Mappe le port `8080` du conteneur sur le port `8080` de l'hôte pour accéder à l'interface web d'Airflow.
   - **Depends_on** : Démarre uniquement après que MySQL soit prêt et que `airflow-init` ait terminé avec succès.
   - **Command** : Démarre le scheduler et le webserver d'Airflow.

#### Volumes

- **`mysql-data`** : Volume nommé pour persister les données MySQL entre les redémarrages de conteneurs.

#### Networks

- **`airflow_network`** : Réseau Docker partagé par tous les services pour permettre leur communication.

### Script d'initialisation MySQL

Le script `mysql/init.sql` n'est pas nécessaire dans cette configuration car la création des bases de données et des utilisateurs est gérée directement par le service `mysql-setup`. Toutefois, vous pouvez conserver ce fichier pour des tâches d'initialisation supplémentaires ou pour des besoins spécifiques.

## Configuration du DAG Airflow

Dans le fichier `airflow/dags/weather_etl.py`, configurez votre pipeline ETL pour automatiser la collecte et le traitement des données météorologiques. Voici un exemple de code pour le DAG :

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import requests
import mysql.connector
from mysql.connector import Error
import os

# Arguments par défaut pour les tâches
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Définition du DAG
dag = DAG(
    'weather_etl',
    default_args=default_args,
    description='ETL simple pour extraire, transformer et charger des données météorologiques',
    schedule_interval=timedelta(minutes=2),  # Planifie le DAG pour s'exécuter toutes les 2 minutes
    start_date=datetime(2024, 8, 7),
    catchup=False,
)

# Fonction pour créer la table dans MySQL
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
            print("Table 'weather' created or already exists.")
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.is_connected():
            connection.close()

# Fonction pour extraire les données météo de l'API
def extract_weather_data(**kwargs):
    api_key = os.getenv('WEATHER_API_KEY')
    city = os.getenv('WEATHER_CITY')
    lang = os.getenv('WEATHER_LANG')
    units = os.getenv('WEATHER_UNITS')
    response = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city}&lang={lang}&appid={api_key}&units={units}")
    weather_data = response.json()
    # Pusher weather_data dans XCom pour le rendre disponible aux tâches suivantes
    kwargs['ti'].xcom_push(key='weather_data', value=weather_data)

# Fonction pour transformer les données extraites
def transform_weather_data(**kwargs):
    ti = kwargs['ti']
    weather_data = ti.xcom_pull(key='weather_data', task_ids='extract_weather_data')

    # Convertir le timestamp UTC en heure locale
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
    # Pusher transformed_data dans XCom pour le rendre disponible à la tâche suivante
    ti.xcom_push(key='transformed_data', value=transformed_data)

# Fonction pour charger les données transformées dans MySQL
def load_weather_data(**kwargs):
    ti = kwargs['ti']
    transformed_data = ti.xcom_pull(key='transformed_data', task_ids='transform_weather_data')
    
    # Afficher les variables d'environnement pour le débogage
    print(f"Connecting to MySQL on {os.getenv('MYSQL_HOST')} with user {os.getenv('MYSQL_USER')} to database {os.getenv('WEATHER_MYSQL_DATABASE')}")
    
    connection = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('WEATHER_MYSQL_DATABASE')  # Vérifiez que cette variable est correcte
    )
    
    if connection.is_connected():
        print(f"Connected to database: {connection.database}")
    
    cursor = connection.cursor()

    # Vérifiez si les données existent déjà
    check_query = """
        SELECT COUNT(*) FROM weather 
        WHERE city = %s AND utc = %s
    """
    cursor.execute(check_query, (
        transformed_data["city"],
        transformed_data["utc"]
    ))
    result = cursor.fetchone()

    if result[0] == 0:
        # Insérez les données si elles n'existent pas déjà
        insert_query = """
            INSERT INTO weather (city, temperature, weather, humidity, pressure, wind_speed, lt, utc)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (
            transformed_data["city"], 
            transformed_data["temperature"], 
            transformed_data["weather"], 
            transformed_data["humidity"], 
            transformed_data["pressure"], 
            transformed_data["wind_speed"], 
            transformed_data["lt"],
            transformed_data["utc"]
        ))
        connection.commit()
        print(f"Inserted data: {transformed_data}")
    else:
        print(f"Data already exists: {transformed_data}")

    cursor.close()
    connection.close()

# Définition des tâches du DAG
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

# Définition de la séquence des tâches
create_table_task >> extract_task >> transform_task >> load_task
```

### Explication du fichier `weather_etl.py` / des tâches du DAG :

Le fichier `weather_etl.py` est un DAG (Directed Acyclic Graph) pour Apache Airflow. Il définit un pipeline ETL (Extract, Transform, Load) qui extrait des données météorologiques à partir de l'API OpenWeatherMap, les transforme et les charge dans une base de données MySQL. Voici une explication détaillée de chaque partie du script :

#### Importation des bibliothèques

Le script commence par importer les bibliothèques nécessaires :
- **`DAG`** et **`PythonOperator`** de `airflow` : Ces modules sont utilisés pour définir et gérer les tâches dans le DAG.
- **`datetime`, `timedelta`, `timezone`** : Importés pour gérer les dates et heures.
- **`requests`** : Utilisé pour faire des requêtes HTTP à l'API OpenWeatherMap.
- **`mysql.connector`** : Utilisé pour se connecter à la base de données MySQL.
- **`os`** : Utilisé pour accéder aux variables d'environnement.

#### Arguments par défaut du DAG

Les `default_args` définissent les paramètres par défaut pour toutes les tâches du DAG :
- **`owner`** : Le propriétaire du DAG (ici `airflow`).
- **`depends_on_past`** : Indique que chaque exécution du DAG ne dépend pas des exécutions précédentes.
- **`email_on_failure`** et **`email_on_retry`** : Désactivent l'envoi d'emails en cas d'échec ou de nouvelle tentative.
- **`retries`** : Le nombre de tentatives en cas d'échec.
- **`retry_delay`** : Le délai entre chaque tentative de réexécution (ici 5 minutes).

#### Définition du DAG

Le DAG est défini avec les paramètres suivants :
- **`dag_id`** : Le nom du DAG (`weather_etl`).
- **`default_args`** : Les arguments par défaut pour les tâches.
- **`description`** : Une courte description du DAG.
- **`schedule_interval`** : L'intervalle de planification du DAG (ici toutes les 2 minutes).
- **`start_date`** : La date de début d'exécution du DAG.
- **`catchup`** : Désactive l'exécution des périodes manquées si Airflow est arrêté.

#### Fonction pour créer la table MySQL

La fonction `create_table` se connecte à la base de données MySQL spécifiée et crée une table `weather` si elle n'existe pas déjà. Cette table est utilisée pour stocker les données météorologiques :
- **`city`** : Le nom de la ville.
- **`temperature`** : La température.
- **`weather`** : La description du temps (ex. "ensoleillé").
- **`humidity`**, **`pressure`**, **`wind_speed`** : Les autres paramètres météorologiques.
- **`lt`** et **`utc`** : L'heure locale et l'heure UTC des données.

#### Fonction pour extraire les données météorologiques

La fonction `extract_weather_data` récupère les données météorologiques en utilisant l'API OpenWeatherMap. Elle utilise les informations de configuration comme la clé API, la ville, la langue et les unités, toutes définies dans les variables d'environnement. Les données récupérées sont ensuite stockées dans `XCom` pour être accessibles aux tâches suivantes.

#### Fonction pour transformer les données

La fonction `transform_weather_data` transforme les données extraites en un format prêt à être chargé dans MySQL. Elle convertit le timestamp UTC en heure locale et formate les autres champs pour l'insertion dans la base de données. Les données transformées sont également stockées dans `XCom`.

#### Fonction pour charger les données dans MySQL

La fonction `load_weather_data` charge les données transformées dans la table MySQL. Elle effectue les actions suivantes :
- **Connexion à MySQL** : Utilise les variables d'environnement pour se connecter à la base de données.
- **Vérification des doublons** : Avant d'insérer les nouvelles données, elle vérifie si des données similaires existent déjà (basé sur `city` et `utc`).
- **Insertion des données** : Si les données n'existent pas déjà, elles sont insérées dans la table `weather`.

#### Définition des tâches du DAG

Chaque étape du pipeline ETL est définie comme une tâche séparée dans le DAG :
- **`create_table_task`** : Tâche pour créer la table dans MySQL.
- **`extract_task`** : Tâche pour extraire les données météorologiques.
- **`transform_task`** : Tâche pour transformer les données extraites.
- **`load_task`** : Tâche pour charger les données transformées dans MySQL.

#### Ordonnancement des tâches

Les tâches sont ordonnées de manière séquentielle :
- **`create_table_task >> extract_task >> transform_task >> load_task`** : Cette syntaxe indique que `create_table_task` doit s'exécuter en premier, suivi de `extract_task`, puis de `transform_task`, et enfin de `load_task`.

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

