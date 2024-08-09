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
