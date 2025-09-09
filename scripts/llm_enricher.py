import os
import pandas as pd
import logging
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import json
from datetime import datetime
import sys
import psycopg2

def setup_logging():
    """
    Configura o sistema de logging para produção.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('llm_enricher.log', mode='a')
        ]
    )
    return logging.getLogger(__name__)

def get_database_engine():
    """
    Cria e retorna a engine de conexão com o banco de dados.
    """
    load_dotenv()
    
    # Configurações do banco de dados
    DB_HOST = os.getenv("POSTGRES_HOST", "postgres")  # Usando 'postgres' como padrão (nome do serviço no Docker)
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "airflow")
    DB_USER = os.getenv("POSTGRES_USER", "airflow")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "airflow")
    
    # String de conexão
    connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    try:
        engine = create_engine(
            connection_string,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=300
        )
        return engine
    except Exception as e:
        raise Exception(f"Erro ao conectar com o banco de dados: {e}")

def get_postgres_connection():
    """
    Cria uma conexão PostgreSQL direta usando psycopg2.
    """
    load_dotenv()
    
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),  # Usando 'postgres' como padrão (nome do serviço no Docker)
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "airflow"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "airflow")
    )

def get_openai_client(logger):
    """
    Configura e retorna o cliente OpenAI.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY não configurada nas variáveis de ambiente.")
        raise ValueError("OPENAI_API_KEY não encontrada")
    
    try:
        client = OpenAI(api_key=api_key)
        # Teste básico de conectividade
        test_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "OK"}],
            max_tokens=5
        )
        logger.info("Cliente OpenAI configurado e testado com sucesso.")
        return client
    except Exception as e:
        logger.error(f"Erro ao configurar cliente OpenAI: {e}")
        raise

def get_unprocessed_headlines(engine, logger, batch_size=50):
    """
    Obtém manchetes que ainda não foram processadas.
    """
    try:
        query = text("""
        SELECT r.*
        FROM raw_headlines r
        LEFT JOIN silver_enriched_headlines s ON r.link = s.raw_link
        WHERE s.raw_link IS NULL
        LIMIT :limit
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {"limit": batch_size})
            df = pd.DataFrame(result.fetchall())
            if df.empty:
                logger.info("Nenhuma manchete pendente encontrada.")
            else:
                logger.info(f"Encontradas {len(df)} manchetes pendentes.")
            return df
    except Exception as e:
        logger.error(f"Erro ao buscar manchetes não processadas: {e}")
        return pd.DataFrame()

def create_silver_table_if_not_exists(engine, logger):
    """
    Cria a tabela silver_enriched_headlines se ela não existir.
    """
    try:
        with engine.begin() as conn:
            conn.execute(text("""
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
                
                -- Criar índice para evitar duplicatas usando link como chave
                CREATE UNIQUE INDEX IF NOT EXISTS idx_silver_raw_link 
                ON silver_enriched_headlines(raw_link);
            """))
        logger.info("Tabela silver_enriched_headlines verificada/criada.")
    except Exception as e:
        logger.error(f"Erro ao criar tabela silver: {e}")
        raise

def analyze_headline_with_openai(client, headline, logger):
    """
    Analisa uma manchete usando OpenAI e retorna o resultado.
    """
    prompt = f"""
    Analise a seguinte manchete de notícia brasileira e retorne APENAS um objeto JSON com estas chaves:
    - 'sentiment': "Positiva", "Negativa" ou "Neutra"
    - 'category': uma das opções: "Política", "Economia", "Esportes", "Tecnologia", "Cultura", "Saúde", "Internacional", "Justiça", "Educação", "Meio Ambiente", "Segurança", "Outros"
    - 'confidence': um número entre 0.0 e 1.0 indicando sua confiança na classificação

    Seja preciso e considere o contexto brasileiro.

    Manchete: "{headline}"
    """
    
    try:
        start_time = datetime.now()
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=150
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        result = json.loads(response.choices[0].message.content)
        
        # Validar resultado
        sentiment = result.get('sentiment', 'Erro')
        category = result.get('category', 'Erro')
        confidence = float(result.get('confidence', 0.0))
        
        # Validação adicional
        valid_sentiments = ['Positiva', 'Negativa', 'Neutra']
        valid_categories = ['Política', 'Economia', 'Esportes', 'Tecnologia', 'Cultura', 
                          'Saúde', 'Internacional', 'Justiça', 'Educação', 'Meio Ambiente', 
                          'Segurança', 'Outros']
        
        if sentiment not in valid_sentiments:
            sentiment = 'Erro'
        if category not in valid_categories:
            category = 'Erro'
        if not (0.0 <= confidence <= 1.0):
            confidence = 0.0
            
        return {
            'sentiment': sentiment,
            'category': category,
            'confidence': confidence,
            'processing_time': processing_time
        }
        
    except Exception as e:
        logger.error(f"Erro ao processar manchete com OpenAI: {e}")
        return {
            'sentiment': 'Erro',
            'category': 'Erro',
            'confidence': 0.0,
            'processing_time': 0.0
        }

def process_headlines_batch(df_headlines, client, logger, batch_name=""):
    """
    Processa um lote de manchetes e retorna os dados enriquecidos.
    """
    enriched_data = []
    total_headlines = len(df_headlines)
    
    logger.info(f"Iniciando processamento do lote {batch_name} com {total_headlines} manchetes...")
    
    for index, row in df_headlines.iterrows():
        headline = row['title']
        logger.info(f"Processando [{index + 1}/{total_headlines}]: {headline[:100]}...")
        
        try:
            # Analisar com OpenAI
            analysis = analyze_headline_with_openai(client, headline, logger)
            
            # Preparar dados para inserção
            enriched_record = {
                'raw_link': row['link'],  # Usando link como chave
                'title': row['title'],
                'link': row['link'],
                'source': row['source'] if 'source' in row else 'g1',
                'scraped_at': row['scraped_at'],
                'sentiment': analysis['sentiment'],
                'category': analysis['category'],
                'confidence_score': analysis['confidence'],
                'processing_time_seconds': analysis['processing_time'],
                'processed_at': datetime.now()
            }
            
            enriched_data.append(enriched_record)
            
            # Log do resultado
            if analysis['sentiment'] != 'Erro':
                logger.info(f"✅ Processada: {analysis['sentiment']} | {analysis['category']} | Confiança: {analysis['confidence']:.2f}")
            else:
                logger.warning(f"⚠️ Erro no processamento da manchete: {headline[:50]}...")
            
            # Pausa pequena para evitar rate limiting
            import time
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Erro ao processar manchete '{headline[:50]}...': {e}")
            # Adicionar registro de erro para não perder a manchete
            enriched_data.append({
                'raw_link': row['link'],  # Usando link como chave
                'title': row['title'],
                'link': row['link'],
                'source': row['source'] if 'source' in row else 'g1',
                'scraped_at': row['scraped_at'],
                'sentiment': 'Erro',
                'category': 'Erro',
                'confidence_score': 0.0,
                'processing_time_seconds': 0.0,
                'processed_at': datetime.now()
            })
    
    logger.info(f"Lote {batch_name} processado: {len(enriched_data)} registros preparados.")
    return enriched_data

def save_enriched_data(enriched_data, engine, logger):
    """
    Salva os dados enriquecidos na tabela silver usando inserção manual.
    """
    if not enriched_data:
        logger.info("Nenhum dado para salvar.")
        return 0
    
    try:
        # Usar inserção manual usando SQLAlchemy para evitar problemas de compatibilidade
        with engine.begin() as conn:
            # Inserir dados um por um
            for data in enriched_data:
                try:
                    conn.execute(text("""
                        INSERT INTO silver_enriched_headlines 
                        (raw_link, title, link, source, scraped_at, sentiment, category, confidence_score, processing_time_seconds, processed_at, model_used) 
                        VALUES (:raw_link, :title, :link, :source, :scraped_at, :sentiment, :category, :confidence_score, :processing_time_seconds, :processed_at, :model_used)
                        ON CONFLICT (raw_link) DO NOTHING
                    """), {
                        "raw_link": data['raw_link'],
                        "title": data['title'],
                        "link": data['link'],
                        "source": data['source'],
                        "scraped_at": data['scraped_at'],
                        "sentiment": data['sentiment'],
                        "category": data['category'],
                        "confidence_score": data['confidence_score'],
                        "processing_time_seconds": data['processing_time_seconds'],
                        "processed_at": data['processed_at'],
                        "model_used": "gpt-3.5-turbo-1106"
                    })
                except Exception as insert_error:
                    logger.error(f"Erro ao inserir registro raw_link {data['raw_link']}: {insert_error}")
                    continue
        
        success_count = len([d for d in enriched_data if d['sentiment'] != 'Erro'])
        error_count = len([d for d in enriched_data if d['sentiment'] == 'Erro'])
        
        logger.info(f"✅ Dados salvos: {len(enriched_data)} total, {success_count} sucessos, {error_count} erros.")
        return len(enriched_data)
        
    except Exception as e:
        logger.error(f"Erro ao salvar dados enriquecidos: {e}")
        raise

def generate_processing_summary(engine, logger):
    """
    Gera um resumo do processamento atual.
    """
    try:
        conn = get_postgres_connection()
        
        # Estatísticas gerais
        total_raw_df = pd.read_sql("SELECT COUNT(*) as count FROM raw_headlines", conn)
        total_processed_df = pd.read_sql("SELECT COUNT(*) as count FROM silver_enriched_headlines", conn)
        
        total_raw = total_raw_df.iloc[0]['count']
        total_processed = total_processed_df.iloc[0]['count']
        pending = total_raw - total_processed
        
        # Estatísticas de sentimento (hoje)
        today_stats = pd.read_sql("""
            SELECT sentiment, COUNT(*) as count
            FROM silver_enriched_headlines 
            WHERE DATE(processed_at) = CURRENT_DATE
            GROUP BY sentiment
        """, conn)
        
        # Estatísticas de categoria (hoje)
        category_stats = pd.read_sql("""
            SELECT category, COUNT(*) as count
            FROM silver_enriched_headlines 
            WHERE DATE(processed_at) = CURRENT_DATE
            GROUP BY category
            ORDER BY count DESC
            LIMIT 5
        """, conn)
        
        conn.close()
        
        logger.info("📊 RESUMO DO PROCESSAMENTO:")
        logger.info(f"   Total de manchetes coletadas: {total_raw}")
        logger.info(f"   Total processadas: {total_processed}")
        logger.info(f"   Pendentes: {pending}")
        
        if not today_stats.empty:
            logger.info("   Processamento hoje:")
            for _, row in today_stats.iterrows():
                logger.info(f"     • {row['sentiment']}: {row['count']}")
        
        if not category_stats.empty:
            logger.info("   Categorias mais frequentes hoje:")
            for _, row in category_stats.iterrows():
                logger.info(f"     • {row['category']}: {row['count']}")
                
    except Exception as e:
        logger.error(f"Erro ao gerar resumo: {e}")

def main():
    """
    Função principal do enriquecimento de manchetes.
    """
    # Configurar logging
    logger = setup_logging()
    
    try:
        logger.info("🚀 Iniciando processo de enriquecimento de manchetes...")
        
        # 1. Configurar conexões
        logger.info("⚙️ Configurando conexões...")
        engine = get_database_engine()
        client = get_openai_client(logger)
        
        # 2. Preparar estrutura do banco
        create_silver_table_if_not_exists(engine, logger)
        
        # 3. Buscar manchetes não processadas
        logger.info("🔍 Buscando manchetes não processadas...")
        df_unprocessed = get_unprocessed_headlines(engine, logger)
        
        if df_unprocessed.empty:
            logger.info("✅ Nenhuma manchete nova para processar. Processo finalizado.")
            generate_processing_summary(engine, logger)
            return
        
        # 4. Processar em lotes (para evitar problemas de memória)
        BATCH_SIZE = 50  # Processar 50 manchetes por vez
        total_processed = 0
        total_batches = (len(df_unprocessed) + BATCH_SIZE - 1) // BATCH_SIZE
        
        for batch_num in range(0, len(df_unprocessed), BATCH_SIZE):
            current_batch = batch_num // BATCH_SIZE + 1
            batch_df = df_unprocessed.iloc[batch_num:batch_num + BATCH_SIZE]
            
            logger.info(f"📦 Processando lote {current_batch}/{total_batches} ({len(batch_df)} manchetes)...")
            
            # Processar lote
            enriched_data = process_headlines_batch(
                batch_df, 
                client, 
                logger, 
                batch_name=f"{current_batch}/{total_batches}"
            )
            
            # Salvar lote
            saved_count = save_enriched_data(enriched_data, engine, logger)
            total_processed += saved_count
            
            logger.info(f"✅ Lote {current_batch}/{total_batches} concluído. Total processado até agora: {total_processed}")
        
        # 5. Gerar resumo final
        logger.info("📊 Gerando resumo final...")
        generate_processing_summary(engine, logger)
        
        logger.info(f"🎉 Processo concluído com sucesso! Total processado: {total_processed} manchetes.")
        
    except Exception as e:
        logger.error(f"❌ Erro crítico no processo: {e}")
        raise
    finally:
        logger.info("🔚 Finalizando processo de enriquecimento.")

if __name__ == "__main__":
    main()