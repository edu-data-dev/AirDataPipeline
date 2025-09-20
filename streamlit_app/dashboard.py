import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from datetime import datetime, timedelta
import numpy as np

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
def load_sentiment_data():
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

@st.cache_data(ttl=3600)  # Cache de 1 hora
def load_category_data():
    """Carrega os dados de categoria das manchetes."""
    load_dotenv()
    
    DB_HOST = "localhost"  
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "airflow")
    DB_USER = os.getenv("POSTGRES_USER", "airflow")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "airflow")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        # Consulta adaptada para buscar diretamente da tabela silver
        query = """
        SELECT 
            CAST(processed_at AS DATE) AS date,
            category, 
            COUNT(*) AS count
        FROM silver_enriched_headlines
        GROUP BY CAST(processed_at AS DATE), category
        ORDER BY date DESC, count DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados de categoria: {str(e)}")
        # Retornar um DataFrame vazio em caso de erro
        return pd.DataFrame(columns=['date', 'category', 'count'])

@st.cache_data(ttl=3600)  # Cache de 1 hora
def load_confidence_data():
    """Carrega os dados de confiança do modelo de IA."""
    # Como não temos a coluna confidence_score disponível no modelo stg_enriched_headlines,
    # vamos retornar um DataFrame vazio ou buscar diretamente da tabela silver
    load_dotenv()
    
    DB_HOST = "localhost"  
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "airflow")
    DB_USER = os.getenv("POSTGRES_USER", "airflow")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "airflow")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        # Buscar diretamente da tabela silver_enriched_headlines que tem a coluna confidence_score
        query = """
        SELECT 
            CAST(processed_at AS DATE) AS date,
            sentiment,
            AVG(confidence_score) AS avg_confidence,
            MIN(confidence_score) AS min_confidence,
            MAX(confidence_score) AS max_confidence
        FROM silver_enriched_headlines
        GROUP BY CAST(processed_at AS DATE), sentiment
        ORDER BY date DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados de confiança: {str(e)}")
        # Retornar um DataFrame vazio em caso de erro
        return pd.DataFrame(columns=['date', 'sentiment', 'avg_confidence', 'min_confidence', 'max_confidence'])

@st.cache_data(ttl=3600)  # Cache de 1 hora
def load_recent_headlines(limit=10):
    """Carrega as manchetes mais recentes com sua análise."""
    load_dotenv()
    
    DB_HOST = "localhost"  
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "airflow")
    DB_USER = os.getenv("POSTGRES_USER", "airflow")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "airflow")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        # Consulta adaptada para buscar diretamente da tabela silver
        query = f"""
        SELECT 
            title AS headline_title, 
            link AS headline_link,
            sentiment,
            category,
            confidence_score,
            processed_at AS processed_timestamp
        FROM silver_enriched_headlines
        ORDER BY processed_at DESC
        LIMIT {limit}
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar manchetes recentes: {str(e)}")
        # Retornar um DataFrame vazio em caso de erro
        return pd.DataFrame(columns=['headline_title', 'headline_link', 'sentiment', 
                                    'category', 'confidence_score', 'processed_timestamp'])

# --- Filtros e Seletores de Data ---
def create_date_filters(df):
    # Sidebar para filtros
    st.sidebar.title("Filtros e Configurações")
    
    # Datas disponíveis
    available_dates = sorted(df['analysis_date'].unique())
    
    if not available_dates:
        return None, None
    
    min_date = available_dates[0]
    max_date = available_dates[-1]
    
    # Verificar se temos mais de um dia de dados
    if len(available_dates) > 1:
        # Definir o valor padrão como a última semana ou o intervalo disponível
        default_start = max(min_date, max_date - timedelta(days=7))
        default_value = [default_start, max_date]
    else:
        # Se só temos um dia, usar esse dia como início e fim
        default_value = [max_date, max_date]
    
    date_range = st.sidebar.date_input(
        "Selecione o intervalo de datas",
        value=default_value,
        min_value=min_date,
        max_value=max_date
    )
    
    # Garantir que temos duas datas selecionadas
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = date_range[0]
        end_date = date_range[0]
    
    return start_date, end_date

# --- Título do Dashboard ---
st.title("🤖 Dashboard de Análise de Sentimento de Notícias do G1")
st.markdown("Este dashboard exibe os insights gerados pelo pipeline de dados, desde a coleta até a análise com IA.")

# --- Carregamento dos Dados ---
try:
    # Tentamos carregar os dados mais importantes primeiro
    df_sentiment = load_sentiment_data()
    
    if df_sentiment.empty:
        st.warning("Ainda não há dados de sentimento para exibir. Execute o pipeline do Airflow primeiro.")
    else:
        # Se temos dados de sentimento, tentamos carregar os dados complementares
        try:
            df_category = load_category_data()
        except Exception as e:
            st.warning(f"Não foi possível carregar os dados de categoria: {e}")
            df_category = pd.DataFrame(columns=['date', 'category', 'count'])
            
        try:
            df_confidence = load_confidence_data()
        except Exception as e:
            st.warning(f"Não foi possível carregar os dados de confiança: {e}")
            df_confidence = pd.DataFrame(columns=['date', 'sentiment', 'avg_confidence', 'min_confidence', 'max_confidence'])
            
        try:
            df_headlines = load_recent_headlines(20)
        except Exception as e:
            st.warning(f"Não foi possível carregar as manchetes recentes: {e}")
            df_headlines = pd.DataFrame(columns=['headline_title', 'headline_link', 'sentiment', 'category', 'processed_timestamp'])
        # Converter análise_date para datetime
        df_sentiment['analysis_date'] = pd.to_datetime(df_sentiment['analysis_date'])
        
        # Filtros de data
        start_date, end_date = create_date_filters(df_sentiment)
        
        if start_date and end_date:
            # Filtrar dados pelo intervalo de data
            filtered_df = df_sentiment[(df_sentiment['analysis_date'] >= pd.Timestamp(start_date)) & 
                                     (df_sentiment['analysis_date'] <= pd.Timestamp(end_date))]
            
            # Filtrar dados de categoria e confiança
            df_category['date'] = pd.to_datetime(df_category['date'])
            filtered_category = df_category[(df_category['date'] >= pd.Timestamp(start_date)) & 
                                          (df_category['date'] <= pd.Timestamp(end_date))]
            
            df_confidence['date'] = pd.to_datetime(df_confidence['date'])
            filtered_confidence = df_confidence[(df_confidence['date'] >= pd.Timestamp(start_date)) & 
                                             (df_confidence['date'] <= pd.Timestamp(end_date))]
            
            # --- Métricas Principais (KPIs) ---
            st.header("Resumo do Período Selecionado")
            
            # Agregações para o período
            total_headlines = filtered_df['total_headlines'].sum()
            total_positive = filtered_df['positive_headlines'].sum()
            total_negative = filtered_df['negative_headlines'].sum()
            total_neutral = filtered_df['neutral_headlines'].sum()
            
            # Cálculo de percentuais
            if total_headlines > 0:
                pct_positive = total_positive / total_headlines * 100
                pct_negative = total_negative / total_headlines * 100
                pct_neutral = total_neutral / total_headlines * 100
            else:
                pct_positive = pct_negative = pct_neutral = 0
            
            # Layout de métricas
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total de Manchetes", f"{total_headlines}")
            col2.metric("Positivas", f"🟢 {total_positive} ({pct_positive:.1f}%)")
            col3.metric("Negativas", f"🔴 {total_negative} ({pct_negative:.1f}%)")
            col4.metric("Neutras", f"⚪ {total_neutral} ({pct_neutral:.1f}%)")
            
            # --- Gráficos de Análise ---
            st.header("Análise de Sentimento ao Longo do Tempo")
            
            # Mostrar dados em abas
            tab1, tab2, tab3, tab4 = st.tabs(["Evolução Temporal", "Distribuição por Categoria", "Confiança do Modelo", "Manchetes Recentes"])
            
            with tab1:
                if filtered_df.empty:
                    st.info("Não há dados para o período selecionado.")
                else:
                    # Preparar dados para o gráfico
                    df_melted = pd.melt(
                        filtered_df, 
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

                # Gráfico de linha temporal
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
                
                # Gráfico de área para mostrar proporções
                fig_area = px.area(
                    df_melted,
                    x='analysis_date',
                    y='count',
                    color='sentiment_type',
                    labels={'count': 'Número de Manchetes', 'analysis_date': 'Data', 'sentiment_type': 'Sentimento'},
                    title='Proporção de Sentimentos ao Longo do Tempo',
                    color_discrete_map={
                        'Positivas': 'green',
                        'Negativas': 'red',
                        'Neutras': 'grey'
                    }
                )
                fig_area.update_layout(
                    xaxis_title='Data', 
                    yaxis_title='Contagem de Manchetes',
                    hovermode='x unified'
                )
                st.plotly_chart(fig_area, use_container_width=True)
                
            with tab2:
                if filtered_category.empty:
                    st.info("Não há dados de categoria para o período selecionado.")
                else:
                    # Agregar dados por categoria
                    category_counts = filtered_category.groupby('category')['count'].sum().reset_index()
                    category_counts = category_counts.sort_values('count', ascending=False)
                    
                    # Gráfico de barras por categoria
                    fig_category = px.bar(
                        category_counts,
                        x='category',
                        y='count',
                        title='Distribuição de Notícias por Categoria',
                        color='category',
                        labels={'count': 'Número de Manchetes', 'category': 'Categoria'}
                    )
                    fig_category.update_layout(
                        xaxis_title='Categoria',
                        yaxis_title='Contagem de Manchetes',
                        xaxis={'categoryorder':'total descending'}
                    )
                    st.plotly_chart(fig_category, use_container_width=True)
                    
                    # Evolução das principais categorias ao longo do tempo
                    top_categories = category_counts.head(5)['category'].tolist()
                    top_category_data = filtered_category[filtered_category['category'].isin(top_categories)]
                    
                    # Pivot para plotar série temporal por categoria
                    category_pivot = top_category_data.pivot_table(
                        index='date', 
                        columns='category', 
                        values='count',
                        fill_value=0
                    ).reset_index()
                    
                    # Melted para usar com plotly
                    category_melted = pd.melt(
                        category_pivot, 
                        id_vars=['date'],
                        var_name='category',
                        value_name='count'
                    )
                    
                    fig_category_time = px.line(
                        category_melted,
                        x='date',
                        y='count',
                        color='category',
                        title='Evolução das Principais Categorias ao Longo do Tempo',
                        labels={'count': 'Número de Manchetes', 'date': 'Data', 'category': 'Categoria'}
                    )
                    fig_category_time.update_layout(
                        xaxis_title='Data',
                        yaxis_title='Contagem de Manchetes',
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig_category_time, use_container_width=True)
                    
                    # Gráfico de calor para categorias por dia
                    # Criar uma tabela de contingência
                    heatmap_data = filtered_category.pivot_table(
                        index='category', 
                        columns=pd.Grouper(key='date', freq='D'),
                        values='count', 
                        fill_value=0
                    )
                    
                    # Ordenar categorias por total
                    heatmap_data['total'] = heatmap_data.sum(axis=1)
                    heatmap_data = heatmap_data.sort_values('total', ascending=False).drop('total', axis=1)
                    
                    # Criar gráfico de calor
                    fig_heatmap = px.imshow(
                        heatmap_data,
                        labels=dict(x="Data", y="Categoria", color="Contagem"),
                        title="Mapa de Calor: Categorias por Dia",
                        color_continuous_scale="Viridis"
                    )
                    fig_heatmap.update_layout(
                        xaxis_title='Data',
                        yaxis_title='Categoria'
                    )
                    st.plotly_chart(fig_heatmap, use_container_width=True)
                    
            with tab3:
                if filtered_confidence.empty:
                    st.info("Não há dados de confiança para o período selecionado.")
                else:
                    # Confiança média por sentimento
                    if not filtered_confidence.empty and 'avg_confidence' in filtered_confidence.columns:
                        # Remover valores nulos
                        filtered_confidence = filtered_confidence.dropna(subset=['avg_confidence'])
                        
                        if not filtered_confidence.empty:
                            try:
                                fig_confidence = px.line(
                                    filtered_confidence,
                                    x='date',
                                    y='avg_confidence',
                                    color='sentiment',
                                    title='Confiança Média do Modelo por Sentimento',
                                    labels={'avg_confidence': 'Confiança Média', 'date': 'Data', 'sentiment': 'Sentimento'}
                                    # Removendo error_y temporariamente pois pode causar erros
                                )
                                fig_confidence.update_layout(
                                    xaxis_title='Data',
                                    yaxis_title='Confiança Média',
                                    hovermode='x unified'
                                )
                                st.plotly_chart(fig_confidence, use_container_width=True)
                            except Exception as e:
                                st.error(f"Erro ao gerar o gráfico de confiança: {e}")
                                st.info("Tentando criar gráfico simplificado...")
                                
                                try:
                                    # Versão simplificada do gráfico
                                    st.line_chart(filtered_confidence.pivot_table(
                                        index='date', 
                                        columns='sentiment', 
                                        values='avg_confidence'
                                    ))
                                except:
                                    st.error("Não foi possível gerar o gráfico de confiança.")
                        else:
                            st.info("Dados insuficientes para gerar o gráfico de confiança.")
                    else:
                        st.info("Dados de confiança não disponíveis.")
                    
                    # Histograma de confiança
                    # Verificar se temos dados suficientes para criar o histograma
                    if not filtered_confidence.empty and 'avg_confidence' in filtered_confidence.columns:
                        # Remover valores nulos se houver
                        filtered_confidence = filtered_confidence.dropna(subset=['avg_confidence'])
                        
                        if not filtered_confidence.empty:
                            # Agregar dados de confiança
                            confidence_hist = filtered_confidence.groupby('sentiment')['avg_confidence'].apply(list).reset_index()
                            
                            # Criar histograma para cada sentimento
                            fig_hist = go.Figure()
                            for i, row in confidence_hist.iterrows():
                                # Verifica se há valores na lista
                                if len(row['avg_confidence']) > 0:
                                    fig_hist.add_trace(go.Histogram(
                                        x=row['avg_confidence'],
                                        name=row['sentiment'],
                                        opacity=0.7,
                                        xbins=dict(start=0, end=1, size=0.05)
                                    ))
                            
                            # Só exibir se houver traços no gráfico
                            if len(fig_hist.data) > 0:
                                fig_hist.update_layout(
                                    title="Distribuição da Confiança por Sentimento",
                                    xaxis_title="Confiança",
                                    yaxis_title="Frequência",
                                    barmode='overlay'
                                )
                                st.plotly_chart(fig_hist, use_container_width=True)
                            else:
                                st.info("Dados insuficientes para gerar o histograma de confiança.")
                        else:
                            st.info("Dados insuficientes para gerar o histograma de confiança.")
                    else:
                        st.info("Dados de confiança não disponíveis.")
                    
            with tab4:
                if df_headlines.empty:
                    st.info("Não há manchetes disponíveis.")
                else:
                    st.subheader("Manchetes Recentes")
                    
                    # Formatar a data e hora
                    df_headlines['processed_timestamp'] = pd.to_datetime(df_headlines['processed_timestamp']).dt.strftime('%d/%m/%Y %H:%M')
                    
                    # Função para destacar os sentimentos
                    def highlight_sentiment(val):
                        if val == 'Positiva':
                            return 'background-color: rgba(0, 128, 0, 0.2)'
                        elif val == 'Negativa':
                            return 'background-color: rgba(255, 0, 0, 0.2)'
                        elif val == 'Neutra':
                            return 'background-color: rgba(128, 128, 128, 0.1)'
                        return ''
                    
                    # Formatar confiança como percentual (verifica se a coluna existe)
                    if 'confidence_score' in df_headlines.columns:
                        df_headlines['confiança'] = df_headlines['confidence_score'].apply(lambda x: f"{x*100:.1f}%" if pd.notnull(x) else "N/A")
                    else:
                        df_headlines['confiança'] = "N/A"
                    
                    # Selecionar e renomear colunas para exibição
                    display_headlines = df_headlines[['headline_title', 'sentiment', 'category', 'confiança', 'processed_timestamp']]
                    display_headlines.columns = ['Manchete', 'Sentimento', 'Categoria', 'Confiança', 'Processado em']
                    
                    # Exibir com formatação
                    st.dataframe(
                        display_headlines.style.applymap(highlight_sentiment, subset=['Sentimento']),
                        use_container_width=True
                    )
                    
                    # Links clicáveis para as notícias
                    st.subheader("Links para as Notícias")
                    for i, row in df_headlines.iterrows():
                        title = row['headline_title']
                        link = row['headline_link']
                        sentiment = row['sentiment']
                        category = row['category']
                        
                        # Ícone baseado no sentimento
                        icon = "🟢" if sentiment == "Positiva" else "🔴" if sentiment == "Negativa" else "⚪"
                        
                        # Exibir link clicável com informações
                        st.markdown(f"{icon} **[{title}]({link})** - *{category}*")
            
            # --- Estatísticas Adicionais ---
            st.header("Estatísticas Adicionais")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfico de pizza para o período todo
                labels = ['Positivas', 'Negativas', 'Neutras']
                values = [total_positive, total_negative, total_neutral]
                
                fig_pie = px.pie(
                    values=values,
                    names=labels,
                    title=f'Distribuição do Sentimento ({start_date.strftime("%d/%m/%Y")} a {end_date.strftime("%d/%m/%Y")})',
                    color_discrete_map={
                        'Positivas': 'green',
                        'Negativas': 'red',
                        'Neutras': 'grey'
                    }
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # Estatísticas adicionais
                if total_headlines > 0:
                    st.subheader("Resumo Estatístico")
                    st.write(f"**Total de manchetes analisadas:** {total_headlines}")
                    st.write(f"**Média diária de manchetes:** {total_headlines / len(filtered_df):.1f}")
                    
                    # Calcular tendência (comparar primeira e segunda metade do período)
                    if len(filtered_df) >= 2:
                        mid_point = len(filtered_df) // 2
                        first_half = filtered_df.iloc[:mid_point]
                        second_half = filtered_df.iloc[mid_point:]
                        
                        first_half_positive_pct = first_half['positive_headlines'].sum() / first_half['total_headlines'].sum() * 100 if first_half['total_headlines'].sum() > 0 else 0
                        second_half_positive_pct = second_half['positive_headlines'].sum() / second_half['total_headlines'].sum() * 100 if second_half['total_headlines'].sum() > 0 else 0
                        
                        positive_trend = second_half_positive_pct - first_half_positive_pct
                        
                        trend_icon = "📈" if positive_trend > 1 else "📉" if positive_trend < -1 else "➡️"
                        st.write(f"**Tendência de notícias positivas:** {trend_icon} {positive_trend:.1f}%")
                        
                        # Dia com mais manchetes positivas
                        max_positive_day = filtered_df.loc[filtered_df['positive_headlines'].idxmax()]
                        max_positive_date = max_positive_day['analysis_date'].strftime('%d/%m/%Y')
                        st.write(f"**Dia com mais notícias positivas:** {max_positive_date} ({max_positive_day['positive_headlines']} manchetes)")
                        
                        # Dia com mais manchetes negativas
                        max_negative_day = filtered_df.loc[filtered_df['negative_headlines'].idxmax()]
                        max_negative_date = max_negative_day['analysis_date'].strftime('%d/%m/%Y')
                        st.write(f"**Dia com mais notícias negativas:** {max_negative_date} ({max_negative_day['negative_headlines']} manchetes)")

        # --- Tabela de Dados Completa ---
        st.header("Dados Detalhados")
        
        # Formatar a data para exibição
        df_display = df_sentiment.copy()
        df_display['analysis_date'] = pd.to_datetime(df_display['analysis_date']).dt.strftime('%d/%m/%Y')
        
        # Renomear colunas para português
        df_display = df_display.rename(columns={
            'analysis_date': 'Data',
            'positive_headlines': 'Positivas',
            'negative_headlines': 'Negativas',
            'neutral_headlines': 'Neutras',
            'total_headlines': 'Total'
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
