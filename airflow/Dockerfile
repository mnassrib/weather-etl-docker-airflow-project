# Utiliser une version spécifique d'Apache Airflow pour éviter les ruptures lors des mises à jour
FROM apache/airflow:2.5.1-python3.8

# Installer les dépendances supplémentaires
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
