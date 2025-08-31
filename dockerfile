# Usamos a imagem estável do Airflow 2.9.2 como base
FROM apache/airflow:2.9.2

# Instalamos o provider do Postgres como o usuário padrão 'airflow'
RUN pip install apache-airflow-providers-postgres