# AirDataPipeline

<!-- Badges das principais tecnologias -->
<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Apache%20Airflow-017CEE?style=for-the-badge&logo=Apache%20Airflow&logoColor=whi└── dbt_project/
│   ├── models/
│   │   ├── staging/        # Modelos de preparação dos dados
│   │   │   └── stg_enriched_headlines.sql # Dados limpos + classificações
│   │   └── gold/           # Métricas analíticas finais
│   │       ├── daily_sentiment_analysis.sql # Agregação de sentimentos
│   │       └── daily_category_analysis.sql  # Agregação por categoria (NOVO)alt="Apache Airflow"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI"/>
  <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/DBT-FF694B?style=for-the-badge&logo=dbt&logoColor=white" alt="DBT"/>
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit"/>
  <img src="https://img.shields.io/badge/ETL-FF6B35?style=for-the-badge&logo=databricks&logoColor=white" alt="ETL Pipeline"/>
</p>
 

Um pipeline completo de Engenharia de Dados para coleta, processamento e visualização de notícias do portal G1, implementado com as principais ferramentas do mercado.

## 📋 Acompanhamento do Desenvolvimento

Para acompanhar o fluxo completo de desenvolvimento, execução e todas as tarefas realizadas neste projeto, acesse:

**[🔗 Trello - Projeto Engenharia de Dados 01](https://trello.com/b/JTQZjq00/projeto-eng-dados01)**

## 🎯 Visão Geral

Este projeto demonstra a implementação de um pipeline de dados moderno (Data Lakehouse) seguindo a arquitetura **Bronze → Silver → Gold**, com orquestração automatizada e visualização interativa.

### Arquitetura do Sistema

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Web Scraping  │───▶│   Airflow    │───▶│ PostgreSQL  │───▶│  LLM AI      │───▶│     DBT      │───▶│  Streamlit   │
│     (G1)        │    │ (Orquestração)│   │  (Bronze)   │    │(Enriquecimento)│   │(Silver/Gold) │    │ (Dashboard)  │
└─────────────────┘    └──────────────┘    └─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                                      │
                                                              ┌──────────────┐
                                                              │ • Sentimento │
                                                              │ • Categoria  │
                                                              │ • Confiança  │
                                                              └──────────────┘
```

## 🏗️ Componentes da Arquitetura

### 📰 **Fonte de Dados (Web Scraping)**
**Nosso fornecedor de matéria-prima**

- **Alvo**: Portal G1 (https://g1.globo.com/)
- **Tecnologia**: Python + Playwright (para conteúdo dinâmico) / BeautifulSoup + Requests (para conteúdo estático)
- **Dados coletados**: Manchetes, links, timestamp de coleta
- **Frequência**: Agendada via Airflow
- **Localização**: `scripts/scraper.py`

### 🧠 **Orquestrador (Apache Airflow)**
**O "cérebro" da operação**

- **Função**: Automatização e agendamento das tarefas
- **Recursos**: 
  - Execução agendada (ex: todos os dias às 8h)
  - Monitoramento de falhas e retries
  - Logs detalhados de execução
  - Interface web para acompanhamento
- **Localização**: `dags/`

### 🏛️ **Banco de Dados (PostgreSQL)**
**Nosso "armazém" - Bronze Layer**

- **Função**: Armazenamento dos dados brutos
- **Características**:
  - Dados exatamente como coletados
  - Sem transformações
  - Histórico completo preservado
- **Configuração**: Docker container

### 🤖 **Enriquecimento com IA (LLM)**
**Nossa "inteligência analítica"**

- **Função**: Análise e classificação automática das manchetes
- **Tecnologias**: OpenAI GPT / Anthropic Claude / Modelos locais (Ollama)
- **Processamento**:
  - **Análise de Sentimento**: Classifica cada manchete como:
    - 🟢 **Positiva**: Notícias otimistas, conquistas, boas notícias
    - 🔴 **Negativa**: Tragédias, conflitos, problemas sociais
    - ⚪ **Neutra**: Informações factuais, declarações, eventos neutros
  - **Categorização**: Classifica por tópicos:
    - 🏛️ **Política**: Governo, eleições, políticas públicas
    - ⚽ **Esportes**: Futebol, olimpíadas, competições
    - 💻 **Tecnologia**: Inovações, ciência, digital
    - 💰 **Economia**: Mercado, inflação, negócios
    - 🎭 **Cultura**: Arte, entretenimento, celebridades
    - 🏥 **Saúde**: Medicina, epidemias, bem-estar
    - 🌍 **Internacional**: Notícias globais, diplomacia
    - ⚖️ **Justiça**: Crimes, tribunais, legislação
- **Posicionamento**: Entre Bronze Layer (dados brutos) e Silver Layer (dados limpos)
- **Benefícios**:
  - Automação de classificação manual
  - Análises de tendências de sentimento
  - Segmentação inteligente de conteúdo
  - Insights sobre padrões noticiosos

### ⚙️ **Ferramenta de Transformação (DBT)**
**Nossa "linha de beneficiamento"**

- **Bronze → Silver**: Limpeza, padronização + dados enriquecidos pela IA
- **Silver → Gold**: Modelagem analítica e agregações por sentimento/categoria
- **Tecnologia**: SQL puro
- **Benefícios**:
  - Versionamento de transformações
  - Testes de qualidade de dados
  - Documentação automática
  - Métricas analíticas avançadas com IA
- **Localização**: `dbt_project/`

#### Modelos DBT Implementados

O DBT organiza as transformações em três camadas principais:

1. **Bronze** (Dados brutos):
   - `raw_headlines`: Carrega os dados brutos das manchetes do G1
   - `raw_enriched_headlines`: Dados brutos com enriquecimento de IA

2. **Silver** (Dados limpos):
   - `stg_enriched_headlines`: Dados limpos + classificações de IA

3. **Gold** (Camada analítica):
   - `daily_sentiment_analysis`: Agregação diária de sentimentos
   - `daily_category_analysis`: Agregação diária por categoria (NOVO)

#### Como Executar o DBT

Para configurar e executar as transformações DBT:

```bash
# Navegue até o diretório do projeto DBT
cd dbt_project

# Verifique se as conexões estão configuradas corretamente
dbt debug

# Execute todos os modelos
dbt run

# Execute modelos específicos
dbt run --models +silver.enriched_headlines+

# Execute modelos por tag
dbt run --models tag:daily

# Gere documentação
dbt docs generate
dbt docs serve
```

### 📊 **Camada de Visualização (Streamlit)**
**Nossa "vitrine"**

- **Função**: Dashboard interativo com insights de IA
- **Recursos**:
  - Visualização dos dados da camada Gold
  - **Análises de Sentimento**: Distribuição temporal de sentimentos
  - **Dashboard de Categorias**: Volume por tópico e tendências
  - **Métricas de IA**: Precisão da classificação e confiança
  - **Alertas**: Detecção de picos de sentimento negativo
  
#### 🆕 Novas Funcionalidades no Dashboard (Versão Melhorada)

- **Interface por Abas**: Organização em abas para melhor navegabilidade (Evolução Temporal, Distribuição por Categoria, Confiança do Modelo, Manchetes Recentes)
- **Filtros Avançados**: Seletores de intervalo de datas na barra lateral
- **Análise por Categoria**: Nova visualização dedicada à distribuição de categorias
  - Gráfico de barras mostrando volume por categoria
  - Evolução temporal das principais categorias
  - Mapa de calor (heatmap) de categorias por dia
- **Métricas de Confiança**: Nova seção mostrando a confiança do modelo de IA
  - Visualização da confiança média por sentimento
  - Histograma de distribuição de confiança
- **Visualização de Manchetes Recentes**: Tabela com as últimas notícias processadas
  - Links clicáveis para as notícias originais
  - Formatação visual por sentimento (verde para positivo, vermelho para negativo)
- **Indicadores de Tendência**: Análise comparativa mostrando evolução do sentimento
- **Visualizações Avançadas**: Gráficos de área para proporção de sentimentos
- **Estatísticas Detalhadas**: Métricas avançadas como média diária e tendências

- **Localização**: `streamlit_app/`
  - `dashboard.py`: Versão original

### 🐳 **Ambiente (Docker & Docker Compose)**
**Nossa "fábrica"**

- **Docker**: Containerização de cada componente
- **Docker Compose**: Orquestração de todos os serviços
- **Benefícios**:
  - Ambiente reproduzível
  - Isolamento de dependências
  - Deploy simplificado

## 🚀 Instalação e Configuração

### Pré-requisitos

- Python 3.10+
- Docker e Docker Compose
- Git

### 1. Clone o Repositório

```bash
git clone https://github.com/edu-data-dev/AirDataPipeline.git
cd AirDataPipeline
```

### 2. Configuração do Ambiente Python

```bash
# Criar ambiente virtual
python -m venv .venv

# Ativar ambiente virtual (Linux/Mac)
source .venv/bin/activate

# Ativar ambiente virtual (Windows)
.venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Instalar navegador para Playwright
python -m playwright install chromium
```

### 3. Configuração do Ambiente

```bash
# Copiar arquivo de configuração
cp .env.example .env

# Editar variáveis de ambiente conforme necessário
nano .env
```

## 📋 Uso do Sistema

#### Web Scraping Engine Playwright (conteúdo dinâmico)
```bash
python scripts/scraper.py --engine playwright
```

**Saída**: Arquivo CSV com timestamp (`g1_headlines_playwright_YYYYMMDD_HHMMSS.csv`)

### Exemplo de Dados Coletados

```csv
title,link,source,scraped_at
"Corpo de Luis Fernando Verissimo é velado na Assembleia do RS",https://g1.globo.com/rs/rio-grande-do-sul/noticia/2025/08/30/corpo-do-escritor-luis-fernando-verissimo-e-velado-na-assembleia-legislativa-em-porto-alegre.ghtml,G1,2025-08-30T18:00:06.860299
"É #FAKE que Trump morreu; presidente é visto a caminho de campo de golfe",https://g1.globo.com/fato-ou-fake/noticia/2025/08/30/e-fake-que-donald-trump-morreu-presidente-e-visto-a-caminho-de-golfe.ghtml,G1,2025-08-30T18:00:07.026369
```

### 4. Subir o Ambiente com Docker

```bash
# Construir e iniciar todos os serviços (primeira execução)
docker-compose up --build -d

# Para execuções posteriores (sem rebuild)
docker-compose up -d

# Verificar status dos containers
docker-compose ps

# Parar todos os serviços
docker-compose down

# Parar e remover volumes (dados serão perdidos)
docker-compose down -v

# Verificar logs de um serviço específico
docker-compose logs -f airflow_webserver
docker-compose logs -f postgres_db

# Verificar logs de todos os serviços
docker-compose logs -f
```

### 5. Executar o Dashboard Streamlit (Local)

```bash
# Ativar ambiente virtual
source .venv/bin/activate

# Navegar para o diretório do Streamlit
cd streamlit_app

# Executar o dashboard original
streamlit run dashboard.py

```

### Interfaces de Acesso

- **Airflow**: http://localhost:8080
- **Streamlit Dashboard**: http://localhost:8501
- **PostgreSQL**: localhost:5432

## 📁 Estrutura do Projeto

```
AirDataPipeline/
├── .env.example              # Exemplo de variáveis de ambiente
├── .gitignore               # Arquivos ignorados pelo Git
├── requirements.txt         # Dependências Python
├── docker-compose.yml       # Configuração dos containers
├── dockerfile               # Dockerfile para construção de imagens
├── README.md               # Este arquivo
├── data/
│   └── raw/                # Dados brutos coletados pelo scraper
├── dags/
│   ├── g1_scraping_dag.py  # Pipeline de coleta de notícias
│   └── g1_enrichement_dag.py # Pipeline de enriquecimento com IA
├── dbt_project/
│   ├── models/
│   │   ├── staging/        # Modelos de preparação dos dados
│   │   └── gold/           # Métricas analíticas finais
│   ├── tests/              # Testes de qualidade de dados
│   ├── macros/             # Macros reutilizáveis
│   ├── analyses/           # Análises ad-hoc
│   ├── seeds/              # Dados de referência
│   ├── snapshots/          # Snapshots de dados
│   └── dbt_project.yml     # Configuração do DBT
├── logs/
│   ├── dag_id=*/           # Logs dos DAGs do Airflow
│   └── scheduler/          # Logs do scheduler do Airflow
├── plugins/                # Plugins customizados do Airflow
├── scripts/
│   ├── scraper.py          # Web scraper do G1
│   ├── llm_enricher.py     # Enriquecimento com IA (sentimento/categoria)
│   └── llm_test_enricher.py # Testes do enriquecimento com IA
└── streamlit_app/
    ├── dashboard.py        # Dashboard original de visualização
```

## 🛠️ Tecnologias Utilizadas

| Componente | Tecnologia | Versão | Finalidade |
|------------|------------|--------|------------|
| **Linguagem** | 🐍 Python | 3.10+ | Desenvolvimento principal |
| **Web Scraping** | 🎭 Playwright | Latest | Conteúdo dinâmico JS |
| **Dados** | 🐼 Pandas | Latest | Manipulação de dados |
| **IA/LLM** | 🤖 OpenAI GPT | 4.0+ | Análise de sentimento e categorização |
| **Orquestração** | 🌬️ Apache Airflow | 2.x | Agendamento e monitoramento |
| **Banco de Dados** | 🐘 PostgreSQL | 15+ | Armazenamento (Bronze Layer) |
| **Transformação** | 🔧 DBT | 1.x | Modelagem (Silver/Gold) |
| **Visualização** | 📊 Streamlit | Latest | Dashboard interativo |
| **Visualização** | 📈 Plotly | Latest | Gráficos interativos avançados |
| **Containerização** | 🐳 Docker | Latest | Isolamento de ambiente |
| **Orquestração** | 🐙 Docker Compose | Latest | Gerenciamento de containers |

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

*Este projeto demonstra competências essenciais em Engenharia de Dados: coleta automatizada, orquestração, modelagem de dados e visualização, utilizando ferramentas padrão da indústria.*  