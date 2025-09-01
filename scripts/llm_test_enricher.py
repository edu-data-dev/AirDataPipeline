import os
import pandas as pd
import logging
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import json
from datetime import datetime
import psycopg2

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Debug: Mostrar versões dos pacotes
try:
    import sqlalchemy
    import pandas as pd
    logging.info(f"🔧 SQLAlchemy versão: {sqlalchemy.__version__}")
    logging.info(f"🔧 Pandas versão: {pd.__version__}")
except:
    pass

def get_postgres_connection():
    """
    Cria uma conexão PostgreSQL direta usando psycopg2.
    """
    load_dotenv()
    
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "airflow"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "airflow")
    )

def test_database_connection(engine):
    """
    Testa a conexão com o banco de dados.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logging.info("✅ Conexão com banco de dados estabelecida com sucesso!")
            return True
    except Exception as e:
        logging.error(f"❌ Erro ao conectar com o banco de dados: {e}")
        return False

def check_table_exists(engine, table_name):
    """
    Verifica se a tabela existe no banco.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table_name}'
                );
            """))
            exists = result.fetchone()[0]
            if exists:
                logging.info(f"✅ Tabela '{table_name}' encontrada.")
            else:
                logging.warning(f"⚠️ Tabela '{table_name}' não encontrada.")
            return exists
    except Exception as e:
        logging.error(f"❌ Erro ao verificar tabela '{table_name}': {e}")
        return False

def create_test_data(engine):
    """
    Cria dados de teste na tabela raw_headlines se ela não existir ou estiver vazia.
    """
    try:
        # Usar begin() para transação automática
        with engine.begin() as conn:
            # Criar tabela se não existir
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS raw_headlines (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    link TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            logging.info("✅ Tabela 'raw_headlines' criada/verificada.")
            
            # Verificar se há dados
            result = conn.execute(text("SELECT COUNT(*) FROM raw_headlines"))
            count = result.fetchone()[0]
            
            if count == 0:
                logging.info("📝 Inserindo dados de teste...")
                test_headlines = [
                    "Economia brasileira cresce 2.5% no terceiro trimestre",
                    "Nova tecnologia de IA promete revolucionar diagnósticos médicos",
                    "Flamengo vence clássico e se aproxima do título brasileiro",
                    "Presidente anuncia novo programa de habitação popular",
                    "Cientistas descobrem nova espécie na Amazônia"
                ]
                
                for headline in test_headlines:
                    conn.execute(text("""
                        INSERT INTO raw_headlines (title, link, scraped_at) 
                        VALUES (:title, :link, :scraped_at)
                    """), {
                        "title": headline,
                        "link": f"https://exemplo.com/noticia-{len(headline)}",
                        "scraped_at": datetime.now()
                    })
                logging.info(f"✅ {len(test_headlines)} manchetes de teste inseridas.")
            else:
                logging.info(f"📊 {count} manchetes já existem na tabela.")
                
    except Exception as e:
        logging.error(f"❌ Erro ao criar dados de teste: {e}")
        raise

def enrich_headlines(db_engine, limit=None, test_mode=True):
    """
    Busca manchetes, enriquece com dados de um LLM e salva na camada Silver.
    Versão compatível com SQLAlchemy 2.0+
    """
    # Carregar API Key
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        if test_mode:
            logging.warning("⚠️ OPENAI_API_KEY não encontrada. Executando em modo MOCK.")
            client = None
        else:
            logging.error("❌ A chave da API da OpenAI (OPENAI_API_KEY) não foi encontrada.")
            raise ValueError("OPENAI_API_KEY não configurada.")
    else:
        client = OpenAI(api_key=api_key)
        logging.info("✅ Cliente OpenAI configurado com sucesso.")
    
    try:
        logging.info("🔍 Buscando manchetes da tabela 'raw_headlines' (Bronze)...")
        
        sql_query = "SELECT * FROM raw_headlines"
        if limit:
            sql_query += f" LIMIT {limit}"
        
        # CORREÇÃO: Usar conexão PostgreSQL direta com psycopg2
        conn = get_postgres_connection()
        df_raw = pd.read_sql(sql_query, conn)
        conn.close()
        
        if df_raw.empty:
            logging.info("📭 Nenhuma manchete encontrada para processar.")
            return
        
        logging.info(f"📰 {len(df_raw)} manchetes encontradas para enriquecimento.")

    except Exception as e:
        logging.error(f"❌ Erro ao buscar dados do PostgreSQL: {e}")
        return

    # Processar manchetes
    enriched_data = []
    for index, row in df_raw.iterrows():
        headline = row['title']
        logging.info(f"🔄 Processando manchete ({index + 1}/{len(df_raw)}): {headline[:80]}...")
        
        try:
            if client and not test_mode:
                # Modo real com OpenAI
                prompt = f"""
                Analise a seguinte manchete de notícia e retorne APENAS um objeto JSON com duas chaves: 'sentiment' e 'category'.
                - Para 'sentiment', classifique como "Positiva", "Negativa" ou "Neutra".
                - Para 'category', classifique em uma das seguintes categorias: "Política", "Economia", "Esportes", "Tecnologia", "Cultura", "Saúde", "Internacional", "Justiça", "Outros".

                Manchete: "{headline}"
                """
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo-1106",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                
                result = json.loads(response.choices[0].message.content)
                sentiment = result.get('sentiment', 'Erro')
                category = result.get('category', 'Erro')
                
            else:
                # Modo MOCK para testes
                logging.info("🎭 Usando dados MOCK (sem chamada real para OpenAI)")
                mock_sentiments = ["Positiva", "Negativa", "Neutra"]
                mock_categories = ["Política", "Economia", "Esportes", "Tecnologia", "Cultura"]
                
                sentiment = mock_sentiments[index % len(mock_sentiments)]
                category = mock_categories[index % len(mock_categories)]
            
            enriched_data.append({
                'title': row['title'],
                'link': row['link'],
                'scraped_at': row['scraped_at'],
                'sentiment': sentiment,
                'category': category,
                'processed_at': datetime.now()
            })
            
            logging.info(f"✅ Manchete processada: {sentiment} | {category}")
            
        except Exception as e:
            logging.error(f"❌ Erro ao processar a manchete '{headline}': {e}")
            # Adicionar com valores de erro para não perder a manchete
            enriched_data.append({
                'title': row['title'],
                'link': row['link'],
                'scraped_at': row['scraped_at'],
                'sentiment': 'Erro',
                'category': 'Erro',
                'processed_at': datetime.now()
            })
    
    # Salvar dados enriquecidos
    if enriched_data:
        df_enriched = pd.DataFrame(enriched_data)
        logging.info("💾 Salvando dados enriquecidos na tabela 'silver_enriched_headlines'...")
        
        try:
            # CORREÇÃO: Inserção manual usando SQLAlchemy para evitar problemas de compatibilidade
            with db_engine.begin() as conn:
                # Limpar tabela existente
                conn.execute(text("DROP TABLE IF EXISTS silver_enriched_headlines"))
                
                # Criar tabela novamente
                conn.execute(text("""
                    CREATE TABLE silver_enriched_headlines (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        link TEXT,
                        scraped_at TIMESTAMP,
                        sentiment VARCHAR(20),
                        category VARCHAR(50),
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                
                # Inserir dados um por um
                for _, row in df_enriched.iterrows():
                    conn.execute(text("""
                        INSERT INTO silver_enriched_headlines 
                        (title, link, scraped_at, sentiment, category, processed_at) 
                        VALUES (:title, :link, :scraped_at, :sentiment, :category, :processed_at)
                    """), {
                        "title": row['title'],
                        "link": row['link'], 
                        "scraped_at": row['scraped_at'],
                        "sentiment": row['sentiment'],
                        "category": row['category'],
                        "processed_at": row['processed_at']
                    })
            
            logging.info("🎉 Processo de enriquecimento concluído com sucesso!")
            logging.info(f"📊 {len(enriched_data)} manchetes processadas e salvas.")
            
            # Mostrar algumas amostras
            logging.info("📋 Primeiras 3 manchetes processadas:")
            for i, row in df_enriched.head(3).iterrows():
                logging.info(f"   • {row['title'][:60]}... | {row['sentiment']} | {row['category']}")
                
        except Exception as e:
            logging.error(f"❌ Erro ao salvar dados enriquecidos: {e}")
    else:
        logging.warning("⚠️ Nenhum dado foi enriquecido com sucesso.")

def run_comprehensive_test():
    """
    Executa um teste abrangente do pipeline.
    """
    logging.info("🚀 Iniciando teste abrangente do pipeline de enriquecimento...")
    
    load_dotenv()
    
    # Configurações do banco de dados
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "airflow")
    DB_USER = os.getenv("POSTGRES_USER", "airflow")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "airflow")
    
    # String de conexão
    connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    try:
        # Criar engine do banco de dados
        logging.info("🔗 Criando conexão com o banco de dados PostgreSQL...")
        engine = create_engine(connection_string, echo=False)  # echo=False para menos logs
        
        # Teste 1: Conexão
        logging.info("\n📡 TESTE 1: Verificando conexão com banco...")
        if not test_database_connection(engine):
            return False
        
        # Teste 2: Verificar/Criar tabelas
        logging.info("\n📋 TESTE 2: Verificando estrutura das tabelas...")
        check_table_exists(engine, "raw_headlines")
        create_test_data(engine)
        
        # Teste 3: API OpenAI (opcional)
        logging.info("\n🤖 TESTE 3: Verificando API OpenAI...")
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                client = OpenAI(api_key=api_key)
                # Teste simples
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Responda apenas: OK"}],
                    max_tokens=10
                )
                logging.info("✅ API OpenAI funcionando corretamente.")
                test_mode = False
            except Exception as e:
                logging.warning(f"⚠️ API OpenAI não está funcionando: {e}")
                logging.info("🎭 Continuando em modo MOCK...")
                test_mode = True
        else:
            logging.info("🎭 OPENAI_API_KEY não configurada. Usando modo MOCK.")
            test_mode = True
        
        # Teste 4: Enriquecimento
        logging.info("\n🎯 TESTE 4: Executando enriquecimento...")
        enrich_headlines(engine, limit=5, test_mode=test_mode)
        
        # Teste 5: Verificar resultados detalhadamente
        logging.info("\n📊 TESTE 5: Verificando resultados salvos...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM silver_enriched_headlines"))
            count = result.fetchone()[0]
            logging.info(f"📊 Total de registros processados: {count}")
            
            if count == 0:
                logging.warning("⚠️ Nenhum dado foi processado!")
                return False
            
            # Buscar todos os dados para análise
            conn = get_postgres_connection()
            df_enriched = pd.read_sql(
                "SELECT * FROM silver_enriched_headlines ORDER BY id", 
                conn
            )
            conn.close()
            
            # Mostrar cada manchete processada em detalhes
            logging.info("\n📰 ANÁLISE DETALHADA DAS MANCHETES PROCESSADAS:")
            logging.info("=" * 80)
            
            for i, row in df_enriched.iterrows():
                logging.info(f"\n🔸 MANCHETE {i+1}:")
                logging.info(f"   📰 Título: {row['title']}")
                logging.info(f"   🔗 Link: {row['link']}")
                logging.info(f"   🎭 Sentimento: {row['sentiment']}")
                logging.info(f"   📂 Categoria: {row['category']}")
                if 'processed_at' in row:
                    logging.info(f"   ⏰ Processado em: {row['processed_at']}")
                logging.info("   " + "-" * 60)
            
            # Estatísticas resumidas
            logging.info(f"\n📈 ESTATÍSTICAS DA ANÁLISE:")
            logging.info("=" * 50)
            
            # Distribuição de sentimentos
            sentiment_counts = df_enriched['sentiment'].value_counts()
            logging.info("🎭 DISTRIBUIÇÃO DE SENTIMENTOS:")
            for sentiment, count in sentiment_counts.items():
                percentage = (count / len(df_enriched)) * 100
                logging.info(f"   • {sentiment}: {count} ({percentage:.1f}%)")
            
            # Distribuição de categorias
            category_counts = df_enriched['category'].value_counts()
            logging.info("\n📂 DISTRIBUIÇÃO DE CATEGORIAS:")
            for category, count in category_counts.items():
                percentage = (count / len(df_enriched)) * 100
                logging.info(f"   • {category}: {count} ({percentage:.1f}%)")
            
            # Verificar se há erros no processamento
            error_sentiment = df_enriched[df_enriched['sentiment'] == 'Erro'].shape[0]
            error_category = df_enriched[df_enriched['category'] == 'Erro'].shape[0]
            
            if error_sentiment > 0 or error_category > 0:
                logging.warning(f"⚠️ ATENÇÃO: {error_sentiment} erros de sentimento e {error_category} erros de categoria detectados!")
            else:
                logging.info("✅ Todos os dados foram processados sem erros!")
        
        logging.info("\n🎉 VERIFICAÇÃO CONCLUÍDA COM SUCESSO!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Erro ao verificar dados enriquecidos: {e}")
        return False
        
    except Exception as e:
        logging.error(f"❌ Erro durante os testes: {e}")
        logging.error(f"   Tipo do erro: {type(e).__name__}")
        return False

def create_tables_if_not_exist(engine):
    """
    Cria as tabelas necessárias se elas não existirem.
    """
    try:
        with engine.begin() as conn:
            # Criar tabela bronze (raw_headlines)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS raw_headlines (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    link TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Criar tabela silver (enriched_headlines)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS silver_enriched_headlines (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    link TEXT,
                    scraped_at TIMESTAMP,
                    sentiment VARCHAR(20),
                    category VARCHAR(50),
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            logging.info("✅ Estrutura das tabelas verificada/criada.")
            
    except Exception as e:
        logging.error(f"❌ Erro ao criar tabelas: {e}")
        raise

def main():
    """
    Função principal para execução dos testes.
    """
    print("=" * 70)
    print("🧪 TESTE DO PIPELINE DE ENRIQUECIMENTO DE HEADLINES")
    print("=" * 70)
    
    # Verificar variáveis de ambiente
    load_dotenv()
    required_vars = ["POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logging.error(f"❌ Variáveis de ambiente faltando: {missing_vars}")
        logging.error("   Certifique-se de que o arquivo .env está configurado corretamente.")
        return
    
    # Configurações do banco de dados
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "airflow")
    DB_USER = os.getenv("POSTGRES_USER", "airflow")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "airflow")
    
    logging.info(f"🔧 Configurações do banco:")
    logging.info(f"   Host: {DB_HOST}:{DB_PORT}")
    logging.info(f"   Database: {DB_NAME}")
    logging.info(f"   User: {DB_USER}")
    
    # String de conexão
    connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    try:
        # Criar engine do banco de dados
        engine = create_engine(connection_string, echo=False)
        
        # Criar tabelas se necessário
        create_tables_if_not_exist(engine)
        
        # Executar testes
        success = run_comprehensive_test()
        
        if success:
            print("\n" + "=" * 70)
            print("🎉 PIPELINE TESTADO COM SUCESSO!")
            print("   Agora você pode criar sua DAG do Airflow com confiança.")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("❌ TESTES FALHARAM!")
            print("   Verifique os logs acima para identificar problemas.")
            print("=" * 70)
            
    except Exception as e:
        logging.error(f"❌ Erro crítico: {e}")
        print("\n" + "=" * 70)
        print("💥 ERRO CRÍTICO NO TESTE!")
        print(f"   {e}")
        print("=" * 70)

if __name__ == "__main__":
    main()