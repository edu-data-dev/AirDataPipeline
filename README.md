# AirDataPipeline

<!-- Badges das principais tecnologias -->
<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Apache%20Airflow-017CEE?style=for-the-badge&logo=Apache%20Airflow&logoColor=white" alt="Apache Airflow"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI"/>
  <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/DBT-FF694B?style=for-the-badge&logo=dbt&logoColor=white" alt="DBT"/>
  <img src="https://img.shields.io/badge/ETL-FF6B35?style=for-the-badge&logo=databricks&logoColor=white" alt="ETL Pipeline"/>
</p>
 

Um pipeline completo de Engenharia de Dados para coleta, processamento e visualização de notícias do portal G1, implementado com as principais ferramentas do mercado.

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
                                                              │ • Tags       │
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
   - `clean_headlines`: Limpeza e normalização das manchetes
   - `enriched_headlines`: Dados limpos + classificações de IA
   - `news_categories`: Taxonomia padronizada das categorias de notícias
   - `sentiment_metrics`: Métricas de sentimento por manchete

3. **Gold** (Camada analítica):
   - `daily_sentiment_analysis`: Agregação diária de sentimentos por categoria
   - `category_distribution`: Distribuição de notícias por categoria ao longo do tempo
   - `trending_topics`: Identificação dos tópicos em alta por período
   - `sentiment_trends`: Análise de tendências de sentimento por período

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

#### Arquivo de Perfil DBT

O DBT requer um arquivo de configuração de perfil em `~/.dbt/profiles.yml`:

```yaml
dbt_project:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      user: airflow
      password: airflow
      port: 5432
      dbname: airflow
      schema: dbt_gold
      threads: 4
```

#### Testes e Qualidade de Dados

O projeto inclui testes para garantir a qualidade dos dados:

```bash
# Execute todos os testes
dbt test

# Execute testes específicos
dbt test --models silver.enriched_headlines
```

### 📊 **Camada de Visualização (Streamlit)**
**Nossa "vitrine"**

- **Função**: Dashboard interativo com insights de IA
- **Recursos**:
  - Visualização dos dados da camada Gold
  - **Análises de Sentimento**: Distribuição temporal de sentimentos
  - **Dashboard de Categorias**: Volume por tópico e tendências
  - **Palavra Cloud**: Termos mais frequentes por categoria
  - **Métricas de IA**: Precisão da classificação e confiança
  - **Alertas**: Detecção de picos de sentimento negativo
- **Localização**: `streamlit_app/`

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

### Web Scraping Manual

O scraper suporta duas engines:

#### Engine Requests (conteúdo estático)
```bash
python scripts/scraper.py --engine requests
```

#### Engine Playwright (conteúdo dinâmico - Recomendado)
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

### Exemplo de Dados Enriquecidos com IA (Futuro)

```csv
title,link,source,scraped_at,sentiment,sentiment_score,category,category_score
"Corpo de Luis Fernando Verissimo é velado na Assembleia do RS",https://g1.globo.com/...,G1,2025-08-30T18:00:06.860299,Negativa,0.85,Cultura,0.92
"É #FAKE que Trump morreu; presidente é visto a caminho de campo de golfe",https://g1.globo.com/...,G1,2025-08-30T18:00:07.026369,Neutra,0.78,Política,0.89
```

### Subir o Ambiente Completo

```bash
# Iniciar todos os serviços
docker-compose up -d

# Verificar status
docker-compose ps

# Acessar logs
docker-compose logs -f [serviço]
```

### Interfaces de Acesso

- **Airflow**: http://localhost:8080
- **Streamlit Dashboard**: http://localhost:8501
- **PostgreSQL**: localhost:5432

### Usando o DBT para Transformações de Dados

O DBT (Data Build Tool) é usado para transformar os dados coletados pelo scraper e enriquecidos pela IA em modelos analíticos prontos para visualização.

#### Configuração Inicial do DBT

```bash
# Certifique-se de que o arquivo de perfil está configurado
mkdir -p ~/.dbt
cat > ~/.dbt/profiles.yml << 'EOF'
dbt_project:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      user: airflow
      password: airflow
      port: 5432
      dbname: airflow
      schema: dbt_gold
      threads: 4
EOF
```

#### Fluxo de Trabalho com DBT

1. **Dados Brutos (Bronze)**:
   ```bash
   cd dbt_project
   dbt run --models bronze
   ```
   Este comando carrega os dados coletados do scraper para a camada bronze.

2. **Dados Limpos (Silver)**:
   ```bash
   dbt run --models silver
   ```
   Este comando transforma os dados brutos em dados limpos e estruturados, incorporando o enriquecimento da IA.

3. **Dados Analíticos (Gold)**:
   ```bash
   dbt run --models gold
   ```
   Este comando cria as métricas e agregações para análise e visualização.

4. **Execução Completa**:
   ```bash
   dbt run
   ```
   Este comando executa todas as transformações em sequência.

5. **Validação de Qualidade**:
   ```bash
   dbt test
   ```
   Este comando executa testes para garantir a qualidade dos dados em todas as camadas.

## 📁 Estrutura do Projeto

```
projeto_eng_dados-01/
├── .env.example              # Exemplo de variáveis de ambiente
├── .gitignore               # Arquivos ignorados pelo Git
├── requirements.txt         # Dependências Python
├── docker-compose.yml       # Configuração dos containers
├── README.md               # Este arquivo
├── scripts/
│   ├── scraper.py          # Web scraper do G1
│   └── llm_enricher.py     # Enriquecimento com IA (sentimento/categoria)
├── dags/
│   ├── scraping_dag.py     # Pipeline de coleta
│   └── enrichment_dag.py   # Pipeline de enriquecimento IA
├── dbt_project/
│   ├── models/
│   │   ├── bronze/         # Dados brutos
│   │   ├── silver/         # Dados limpos + IA
│   │   └── gold/           # Métricas analíticas
│   ├── tests/              # Testes de qualidade
│   └── dbt_project.yml     # Configuração DBT
└── streamlit_app/
    ├── pages/
    │   ├── sentiment_analysis.py  # Dashboard de sentimentos
    │   └── category_trends.py     # Análise por categorias
    └── main.py             # Dashboard principal
```

## 🔧 Funcionalidades Implementadas

### ✅ Web Scraping
- [x] Coleta de manchetes do G1
- [x] Suporte a conteúdo dinâmico (Playwright)
- [x] Fallback para conteúdo estático (Requests + BeautifulSoup)
- [x] Deduplicação automática
- [x] Timestamps de coleta
- [x] Logs detalhados
- [x] Interface CLI com argumentos

### ✅ Infraestrutura
- [x] Containerização com Docker
- [x] Gerenciamento de dependências
- [x] Controle de versão configurado
- [x] Ambiente virtual Python
- [x] Configuração via variáveis de ambiente

### 🚧 Em Desenvolvimento
- [ ] Módulo de enriquecimento com IA
- [ ] DAGs do Airflow (coleta + IA)
- [x] Modelagem DBT com dados de IA
  - [x] Camada Bronze: Carregamento de dados brutos
  - [x] Camada Silver: Limpeza e enriquecimento
  - [x] Camada Gold: Agregações e métricas analíticas
  - [x] Testes de qualidade dos dados
  - [ ] Documentação completa dos modelos
- [ ] Dashboard Streamlit com análises de sentimento
- [ ] Testes automatizados
- [ ] CI/CD Pipeline

### 🔮 Recursos de IA Planejados
- [ ] **Análise de Sentimento**: Classificação automática Positiva/Negativa/Neutra
- [ ] **Categorização**: Política, Esportes, Tecnologia, Economia, Cultura, Saúde, Internacional, Justiça
- [ ] **Métricas de Confiança**: Score de certeza da classificação
- [ ] **Detecção de Trending Topics**: Identificação de assuntos em alta
- [ ] **Alertas Inteligentes**: Notificações sobre picos de sentimento negativo
- [ ] **Resumos Automáticos**: Sínteses diárias por categoria

## 🛠️ Tecnologias Utilizadas

| Componente | Tecnologia | Versão | Finalidade |
|------------|------------|--------|------------|
| **Linguagem** | 🐍 Python | 3.10+ | Desenvolvimento principal |
| **Web Scraping** | 🎭 Playwright | Latest | Conteúdo dinâmico JS |
| **Web Scraping** | 🍲 BeautifulSoup + Requests | Latest | Conteúdo estático |
| **Dados** | 🐼 Pandas | Latest | Manipulação de dados |
| **IA/LLM** | 🤖 OpenAI GPT | 4.0+ | Análise de sentimento e categorização |
| **IA/LLM** | 🧠 Anthropic Claude | 3.5+ | Alternativa para classificação |
| **IA Local** | 🦙 Ollama | Latest | Modelos locais (opcional) |
| **Orquestração** | 🌬️ Apache Airflow | 2.x | Agendamento e monitoramento |
| **Banco de Dados** | 🐘 PostgreSQL | 15+ | Armazenamento (Bronze Layer) |
| **Transformação** | 🔧 DBT | 1.x | Modelagem (Silver/Gold) |
| **Visualização** | 📊 Streamlit | Latest | Dashboard interativo |
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

## 📧 Contato

**Projeto**: AirDataPipeline  
**Repositório**: https://github.com/edu-data-dev/AirDataPipeline



## 📋 Quadro de Tarefas e Fluxo do Projeto

Para acompanhar o fluxo de criação, execução e todas as tarefas realizadas, acesse o quadro do Trello:

[🔗 Trello - Projeto Engenharia de Dados 01](https://trello.com/b/JTQZjq00/projeto-eng-dados01)
*Este projeto demonstra competências essenciais em Engenharia de Dados: coleta automatizada, orquestração, modelagem de dados e visualização, utilizando ferramentas padrão da indústria.*