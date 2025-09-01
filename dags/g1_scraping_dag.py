from __future__ import annotations

import pendulum
from airflow.decorators import dag, task
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.operators.bash import BashOperator

@dag(
    dag_id="g1_scraping_pipeline",
    schedule_interval="0 8 * * *", 
    start_date=pendulum.datetime(2025, 8, 31, tz="America/Sao_Paulo"),
    catchup=False,
    tags=["scraping", "g1", "bronze"],
    doc_md="""
    ### Pipeline de Coleta de Notícias do G1
    Esta DAG é responsável por:
    1. Criar a tabela de destino no PostgreSQL (camada Bronze).
    2. Executar o script de web scraping para coletar as manchetes.
    3. Ingerir os dados coletados do arquivo CSV para a tabela no PostgreSQL.
    """
)
def g1_scraping_pipeline():
    """
    DAG que orquestra todo o processo de coleta e ingestão de dados do G1.
    """
    
    # Tarefa 1: Cria a tabela no PostgreSQL se ela não existir.
    # Usamos o PostgresOperator para executar uma query SQL.
    # A idempotência é garantida pelo "CREATE TABLE IF NOT EXISTS".
    create_raw_headlines_table = PostgresOperator(
        task_id="create_raw_headlines_table",
        postgres_conn_id="postgres_default",  # O ID da conexão que criamos na UI do Airflow
        sql="""
            CREATE TABLE IF NOT EXISTS raw_headlines (
                title TEXT,
                link TEXT PRIMARY KEY,
                source TEXT,
                scraped_at TIMESTAMP WITH TIME ZONE
            );
        """
    )

    # Tarefa 2: Executa o script de scraping.
    # Usamos o BashOperator para rodar um comando no terminal, como se fosse local.
    # O script já está acessível dentro do contêiner graças aos volumes que montamos.
    run_g1_scraper = BashOperator(
        task_id="run_g1_scraper",
        bash_command="python /opt/airflow/scripts/scraper.py --engine playwright"
    )

    @task
    def ingest_data_to_postgres():
        """
        Tarefa Python customizada para ler o CSV e inserir no Postgres.
        """
        import pandas as pd
        from sqlalchemy import create_engine
        import os

        # O scraper salva o arquivo na raiz. Dentro do container, o caminho é este.
        # Precisamos encontrar o arquivo CSV mais recente gerado pelo scraper.
        data_dir = '/opt/airflow/data/raw'
        if not os.path.exists(data_dir) or not os.listdir(data_dir):
            raise FileNotFoundError(f"Nenhum arquivo encontrado no diretório {data_dir}")
        all_files = [os.path.join(data_dir, f) for f in os.listdir(data_dir)]
        latest_file = max(all_files, key=os.path.getctime)
        
        print(f"Lendo o arquivo CSV: {latest_file}")
        df = pd.read_csv(latest_file)

        # Conecta ao PostgreSQL usando SQLAlchemy
        # As credenciais são obtidas da conexão do Airflow
        from airflow.providers.postgres.hooks.postgres import PostgresHook
        hook = PostgresHook(postgres_conn_id='postgres_default')
        engine = hook.get_sqlalchemy_engine()
        
        print("Inserindo dados na tabela 'raw_headlines'...")
        # Insere o DataFrame na tabela.
        # 'if_exists='replace'' apaga a tabela e insere os novos dados.
        # 'if_exists='append'' adicionaria os dados ao final.
        # Para a camada bronze, 'replace' é uma estratégia comum para a carga diária.
        df.to_sql('raw_headlines', engine, if_exists='replace', index=False)
        print("Ingestão de dados concluída com sucesso.")

    # Define a ordem de execução das tarefas
    create_raw_headlines_table >> run_g1_scraper >> ingest_data_to_postgres()

# Instancia a DAG para que o Airflow possa encontrá-la
g1_scraping_pipeline()