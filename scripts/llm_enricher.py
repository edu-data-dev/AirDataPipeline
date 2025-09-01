# Arquivo: scripts/llm_enricher.py
# Descrição: Script para enriquecer as manchetes com análise de sentimento e categoria usando um LLM.

import os
import pandas as pd
import logging
from openai import OpenAI
from airflow.providers.postgres.hooks.postgres import PostgresHook
from dotenv import load_dotenv

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def enrich_headlines():
    """
    Busca manchetes da camada Bronze, enriquece com dados de um LLM e salva na camada Silver.
    """
    # Carrega as variáveis de ambiente (como a OPENAI_API_KEY) do arquivo .env
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.error("A chave da API da OpenAI (OPENAI_API_KEY) não foi encontrada no ambiente.")
        raise ValueError("OPENAI_API_KEY não configurada.")

    client = OpenAI(api_key=api_key)

    # 1. Buscar dados da camada Bronze (PostgreSQL)
    hook = PostgresHook(postgres_conn_id='postgres_default')
    engine = hook.get_sqlalchemy_engine()
    
    try:
        logging.info("Buscando manchetes da tabela 'raw_headlines' (Bronze)...")
        df_raw = pd.read_sql("SELECT * FROM raw_headlines", engine)
        
        if df_raw.empty:
            logging.info("Nenhuma manchete nova para processar.")
            return
        
        logging.info(f"{len(df_raw)} manchetes encontradas para enriquecimento.")

    except Exception as e:
        logging.error(f"Erro ao buscar dados do PostgreSQL: {e}")
        return

    enriched_data = []

    # 2. Iterar sobre cada manchete e chamar a API do LLM
    for index, row in df_raw.iterrows():
        headline = row['title']
        logging.info(f"Processando manchete ({index + 1}/{len(df_raw)}): {headline[:80]}...")
        
        try:
            # Este é o "prompt" - a instrução que damos ao modelo de IA
            prompt = f"""
            Analise a seguinte manchete de notícia e retorne APENAS um objeto JSON com duas chaves: 'sentiment' e 'category'.
            - Para 'sentiment', classifique como "Positiva", "Negativa" ou "Neutra".
            - Para 'category', classifique em uma das seguintes categorias: "Política", "Economia", "Esportes", "Tecnologia", "Cultura", "Saúde", "Internacional", "Justiça", "Outros".

            Manchete: "{headline}"
            """
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-1106",  # Um modelo rápido e eficiente
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}, # Garantimos que a resposta seja um JSON válido
                temperature=0.0 # Baixa temperatura para respostas mais consistentes e menos criativas
            )
            
            # Extrai e parseia o resultado JSON
            result = pd.read_json(response.choices[0].message.content, typ='series')
            
            enriched_data.append({
                'title': row['title'],
                'link': row['link'],
                'scraped_at': row['scraped_at'],
                'sentiment': result.get('sentiment', 'Erro'),
                'category': result.get('category', 'Erro')
            })

        except Exception as e:
            logging.error(f"Erro ao processar a manchete '{headline}' com a API: {e}")
            enriched_data.append({
                'title': row['title'],
                'link': row['link'],
                'scraped_at': row['scraped_at'],
                'sentiment': 'Erro de API',
                'category': 'Erro de API'
            })
    
    # 3. Salvar os dados enriquecidos na camada Silver
    if enriched_data:
        df_enriched = pd.DataFrame(enriched_data)
        logging.info("Salvando dados enriquecidos na tabela 'silver_enriched_headlines'...")
        
        # Cria a tabela e insere os novos dados
        df_enriched.to_sql('silver_enriched_headlines', engine, if_exists='replace', index=False)
        
        logging.info("Processo de enriquecimento concluído com sucesso!")

if __name__ == '__main__':
    enrich_headlines()