import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import plotly.express as px
import psycopg2

# --- Configuração da Página ---
st.set_page_config(
    page_title="Dashboard de Análise de Notícias",
    page_icon="🤖",
    layout="wide"
)

# --- Funções de Conexão e Cache ---

@st.cache_resource
def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    load_dotenv()
    db_host = os.getenv("POSTGRES_HOST", "postgres")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_user = os.getenv("POSTGRES_USER", "airflow")
    db_pass = os.getenv("POSTGRES_PASSWORD", "airflow")
    db_name = os.getenv("POSTGRES_DB", "airflow")

    connection_string = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(connection_string)
    return engine

@st.cache_data(ttl=3600)  # Cache de 1 hora
def load_data():
    """Carrega os dados da tabela analítica da camada Gold."""
    load_dotenv()
    
    # Para o dashboard, vamos usar localhost já que está rodando fora do Docker
    DB_HOST = "localhost"  
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "airflow")
    DB_USER = os.getenv("POSTGRES_USER", "airflow")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "airflow")
    
    try:
        # Usando psycopg2 diretamente
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        query = "SELECT * FROM dbt_gold.daily_sentiment_analysis ORDER BY analysis_date ASC"
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
    except Exception as e:
        st.error(f"Erro específico na conexão: {str(e)}")
        raise e

# --- Título do Dashboard ---
st.title("🤖 Dashboard de Análise de Sentimento de Notícias do G1")
st.markdown("Este dashboard exibe os insights gerados pelo pipeline de dados, desde a coleta até a análise com IA.")

# --- Carregamento dos Dados ---
try:
    df = load_data()
    
    if df.empty:
        st.warning("Ainda não há dados processados para exibir. Execute o pipeline do Airflow primeiro.")
    else:
        # --- Métricas Principais (KPIs) ---
        st.header("Resumo do Último Dia Processado")

        # Pega os dados da última data disponível
        latest_data = df.iloc[-1]
        latest_date = pd.to_datetime(latest_data['analysis_date']).strftime('%d/%m/%Y')

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Data de Análise", latest_date)
        col2.metric("Manchetes Positivas", f"🟢 {latest_data['positive_headlines']}")
        col3.metric("Manchetes Negativas", f"🔴 {latest_data['negative_headlines']}")
        col4.metric("Manchetes Neutras", f"⚪ {latest_data['neutral_headlines']}")

        # --- Gráfico de Série Temporal ---
        st.header("Análise de Sentimento ao Longo do Tempo")

        # Preparar dados para o gráfico
        df_melted = pd.melt(
            df, 
            id_vars=['analysis_date'], 
            value_vars=['positive_headlines', 'negative_headlines', 'neutral_headlines'],
            var_name='sentiment_type', 
            value_name='count'
        )
        
        # Mapear nomes mais legíveis
        sentiment_map = {
            'positive_headlines': 'Positivas',
            'negative_headlines': 'Negativas', 
            'neutral_headlines': 'Neutras'
        }
        df_melted['sentiment_type'] = df_melted['sentiment_type'].map(sentiment_map)

        fig = px.line(
            df_melted,
            x='analysis_date',
            y='count',
            color='sentiment_type',
            labels={'count': 'Número de Manchetes', 'analysis_date': 'Data', 'sentiment_type': 'Sentimento'},
            title='Evolução Diária do Sentimento das Notícias',
            color_discrete_map={
                'Positivas': 'green',
                'Negativas': 'red',
                'Neutras': 'grey'
            }
        )
        fig.update_layout(
            xaxis_title='Data', 
            yaxis_title='Contagem de Manchetes',
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- Gráfico de Pizza do Último Dia ---
        st.header("Distribuição de Sentimentos - Último Dia")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de pizza
            labels = ['Positivas', 'Negativas', 'Neutras']
            values = [
                latest_data['positive_headlines'],
                latest_data['negative_headlines'],
                latest_data['neutral_headlines']
            ]
            
            fig_pie = px.pie(
                values=values,
                names=labels,
                title=f'Distribuição do Sentimento - {latest_date}',
                color_discrete_map={
                    'Positivas': 'green',
                    'Negativas': 'red',
                    'Neutras': 'grey'
                }
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # Estatísticas adicionais
            total_headlines = sum(values)
            if total_headlines > 0:
                st.subheader("Estatísticas do Último Dia")
                st.write(f"**Total de manchetes analisadas:** {total_headlines}")
                st.write(f"**Percentual positivo:** {(values[0]/total_headlines*100):.1f}%")
                st.write(f"**Percentual negativo:** {(values[1]/total_headlines*100):.1f}%")
                st.write(f"**Percentual neutro:** {(values[2]/total_headlines*100):.1f}%")

        # --- Tabela de Dados ---
        st.header("Dados Detalhados")
        
        # Formatar a data para exibição
        df_display = df.copy()
        df_display['analysis_date'] = pd.to_datetime(df_display['analysis_date']).dt.strftime('%d/%m/%Y')
        
        # Renomear colunas para português
        df_display = df_display.rename(columns={
            'analysis_date': 'Data',
            'positive_headlines': 'Positivas',
            'negative_headlines': 'Negativas',
            'neutral_headlines': 'Neutras'
        })
        
        st.dataframe(
            df_display.style.highlight_max(axis=0, subset=['Positivas', 'Negativas', 'Neutras']),
            use_container_width=True
        )

except Exception as e:
    st.error(f"Erro ao carregar os dados: {str(e)}")
    st.info("Verifique se:")
    st.write("- O banco de dados está rodando")
    st.write("- As credenciais do .env estão corretas")
    st.write("- A tabela dbt_gold.daily_sentiment_analysis existe")
    st.write("- O pipeline do Airflow já foi executado pelo menos uma vez")