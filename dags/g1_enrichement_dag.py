from __future__ import annotations

import pendulum
from airflow.decorators import dag, task
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.operators.bash import BashOperator

@dag(
    dag_id="g1_enrichment_pipeline",
    schedule_interval="0 9 * * *",  # Executa às 9h, 1 hora depois do scraping
    start_date=pendulum.datetime(2025, 9, 5, tz="America/Sao_Paulo"),
    catchup=False,
    tags=["enrichment", "llm", "g1", "silver", "ai"],
    doc_md="""
    ### Pipeline de Enriquecimento de Notícias do G1 com IA
    Esta DAG é responsável por:
    1. Aguardar a conclusão bem-sucedida da DAG g1_scraping_pipeline (sensor).
    2. Criar a tabela silver de dados enriquecidos no PostgreSQL.
    3. Executar o script de enriquecimento com LLM para analisar manchetes.
    4. Processar manchetes ainda não analisadas da camada Bronze.
    5. Classificar sentimento e categorizar usando OpenAI GPT.
    6. Salvar os dados enriquecidos na camada Silver.
    
    **Configuração:**
    - SCHEDULE: 9h diário (1 hora após o scraping às 8h)
    - SAFETY CHECK: ExternalTaskSensor aguarda scraping finalizar
    - MANUAL: Pode ser executada manualmente
    
    **Dependências:**
    - AGUARDA: g1_scraping_pipeline executar com sucesso
    - Necessita das variáveis de ambiente: OPENAI_API_KEY, POSTGRES_*
    
    **Tabelas envolvidas:**
    - Input: raw_headlines (Bronze layer)
    - Output: silver_enriched_headlines (Silver layer)
    """
)
def g1_enrichment_pipeline():
    """
    DAG que orquestra o processo de enriquecimento de manchetes com IA.
    """
    
    # Tarefa 1: Criar tabela silver se não existir - ESTRUTURA CORRIGIDA
    create_silver_table = PostgresOperator(
        task_id="create_silver_enriched_table",
        postgres_conn_id="postgres_default",
        sql="""
            CREATE TABLE IF NOT EXISTS silver_enriched_headlines (
                id SERIAL PRIMARY KEY,
                raw_link TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT,
                source TEXT,
                scraped_at TIMESTAMP,
                sentiment VARCHAR(20),
                category VARCHAR(50),
                confidence_score FLOAT,
                processing_time_seconds FLOAT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                model_used VARCHAR(50) DEFAULT 'gpt-3.5-turbo-1106'
            );
            
            -- Criar índice para evitar duplicatas usando raw_link
            CREATE UNIQUE INDEX IF NOT EXISTS idx_silver_raw_link 
            ON silver_enriched_headlines(raw_link);
            
            -- Criar índices para consultas
            CREATE INDEX IF NOT EXISTS idx_silver_sentiment 
            ON silver_enriched_headlines(sentiment);
            
            CREATE INDEX IF NOT EXISTS idx_silver_category 
            ON silver_enriched_headlines(category);
            
            CREATE INDEX IF NOT EXISTS idx_silver_processed_at 
            ON silver_enriched_headlines(processed_at);
        """
    )

    # Tarefa 2: Verificar se há dados novos para processar - QUERY CORRIGIDA
    @task
    def check_pending_headlines():
        """
        Verifica se existem manchetes pendentes de processamento.
        """
        from airflow.providers.postgres.hooks.postgres import PostgresHook
        import logging
        
        logger = logging.getLogger(__name__)
        hook = PostgresHook(postgres_conn_id='postgres_default')
        
        # Query corrigida para usar link como chave
        query = """
        SELECT COUNT(*) as pending_count
        FROM raw_headlines r
        LEFT JOIN silver_enriched_headlines s ON r.link = s.raw_link
        WHERE s.raw_link IS NULL
        """
        
        result = hook.get_first(query)
        pending_count = result[0] if result else 0
        
        logger.info(f"Encontradas {pending_count} manchetes pendentes de enriquecimento")
        
        if pending_count == 0:
            logger.info("Nenhuma manchete nova para processar. Pulando enriquecimento.")
            return False
        
        return True

    # Tarefa 3: Executar enriquecimento com LLM
    run_llm_enricher = BashOperator(
        task_id="run_llm_enricher",
        bash_command="cd /opt/airflow && python scripts/llm_enricher.py",
        env={
            'PYTHONPATH': '/opt/airflow',
        }
    )

    # Tarefa 4: Validar qualidade dos dados enriquecidos
    @task
    def validate_enriched_data():
        """
        Valida a qualidade dos dados enriquecidos recém-processados.
        """
        from airflow.providers.postgres.hooks.postgres import PostgresHook
        import logging
        
        logger = logging.getLogger(__name__)
        hook = PostgresHook(postgres_conn_id='postgres_default')
        
        # Verificar dados processados hoje
        validation_queries = [
            ("Total processado hoje", """
                SELECT COUNT(*) FROM silver_enriched_headlines 
                WHERE DATE(processed_at) = CURRENT_DATE
            """),
            ("Registros com erro hoje", """
                SELECT COUNT(*) FROM silver_enriched_headlines 
                WHERE DATE(processed_at) = CURRENT_DATE 
                AND (sentiment = 'Erro' OR category = 'Erro')
            """),
            ("Taxa de confiança média hoje", """
                SELECT ROUND(AVG(confidence_score)::numeric, 3) FROM silver_enriched_headlines 
                WHERE DATE(processed_at) = CURRENT_DATE 
                AND sentiment != 'Erro'
            """),
            ("Distribuição de sentimentos hoje", """
                SELECT sentiment, COUNT(*) FROM silver_enriched_headlines 
                WHERE DATE(processed_at) = CURRENT_DATE 
                GROUP BY sentiment
            """)
        ]
        
        validation_results = {}
        
        for description, query in validation_queries:
            try:
                if "Distribuição" in description:
                    results = hook.get_records(query)
                    validation_results[description] = results
                    logger.info(f"{description}: {results}")
                else:
                    result = hook.get_first(query)
                    value = result[0] if result and result[0] is not None else 0
                    validation_results[description] = value
                    logger.info(f"{description}: {value}")
            except Exception as e:
                logger.error(f"Erro ao executar validação '{description}': {e}")
                validation_results[description] = "Erro"
        
        # Verificações de qualidade
        total_today = validation_results.get("Total processado hoje", 0)
        errors_today = validation_results.get("Registros com erro hoje", 0)
        avg_confidence = validation_results.get("Taxa de confiança média hoje", 0)
        
        if total_today == 0:
            logger.warning("Nenhum registro foi processado hoje!")
        
        if total_today > 0:
            error_rate = (errors_today / total_today) * 100
            logger.info(f"Taxa de erro hoje: {error_rate:.1f}%")
            
            if error_rate > 10:  # Se mais de 10% tiveram erro
                logger.warning(f"Taxa de erro alta: {error_rate:.1f}%")
            
            if avg_confidence and avg_confidence < 0.7:
                logger.warning(f"Confiança média baixa: {avg_confidence}")
        
        return validation_results

    # Tarefa 5: Gerar relatório de processamento
    @task
    def generate_processing_report():
        """
        Gera relatório detalhado do processamento.
        """
        from airflow.providers.postgres.hooks.postgres import PostgresHook
        import logging
        import json
        
        logger = logging.getLogger(__name__)
        hook = PostgresHook(postgres_conn_id='postgres_default')
        
        # Estatísticas gerais
        stats_queries = {
            "total_raw": "SELECT COUNT(*) FROM raw_headlines",
            "total_processed": "SELECT COUNT(*) FROM silver_enriched_headlines",
            "processed_today": """
                SELECT COUNT(*) FROM silver_enriched_headlines 
                WHERE DATE(processed_at) = CURRENT_DATE
            """,
            "avg_processing_time": """
                SELECT ROUND(AVG(processing_time_seconds)::numeric, 3) 
                FROM silver_enriched_headlines 
                WHERE DATE(processed_at) = CURRENT_DATE
            """
        }
        
        report = {}
        for key, query in stats_queries.items():
            try:
                result = hook.get_first(query)
                report[key] = result[0] if result and result[0] is not None else 0
            except Exception as e:
                logger.error(f"Erro ao executar query '{key}': {e}")
                report[key] = 0
        
        # Calcular pendentes
        report["pending"] = report["total_raw"] - report["total_processed"]
        
        # Relatório de categorias hoje
        try:
            category_results = hook.get_records("""
                SELECT category, COUNT(*) FROM silver_enriched_headlines 
                WHERE DATE(processed_at) = CURRENT_DATE 
                AND category != 'Erro'
                GROUP BY category 
                ORDER BY COUNT(*) DESC
            """)
            report["categories_today"] = category_results
        except:
            report["categories_today"] = []
        
        # Log do relatório
        logger.info("📊 RELATÓRIO DE ENRIQUECIMENTO:")
        logger.info(f"   Total manchetes: {report['total_raw']}")
        logger.info(f"   Total processadas: {report['total_processed']}")
        logger.info(f"   Processadas hoje: {report['processed_today']}")
        logger.info(f"   Pendentes: {report['pending']}")
        logger.info(f"   Tempo médio por manchete: {report['avg_processing_time']}s")
        
        if report['categories_today']:
            logger.info("   Categorias processadas hoje:")
            for category, count in report['categories_today'][:5]:  # Top 5
                logger.info(f"     • {category}: {count}")
        
        return report

    # Definir dependências
    check_task = check_pending_headlines()
    validate_task = validate_enriched_data()
    report_task = generate_processing_report()
    
    # Fluxo simplificado sem sensor externo
    create_silver_table >> check_task
    check_task >> run_llm_enricher >> validate_task >> report_task

# Instanciar a DAG
g1_enrichment_pipeline()