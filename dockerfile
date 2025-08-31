# Arquivo: Dockerfile
# Descrição: Define a imagem customizada do Airflow com nossas dependências.
FROM apache/airflow:2.9.2

# ==========================================
# SEÇÃO DE DEPENDÊNCIAS DO SISTEMA (COMO ROOT)
# ==========================================
# Trocamos para o usuário ROOT para ter permissão de instalar pacotes
USER root

# Comando de instalação mais robusto para evitar problemas de dependência
# e com a lista de pacotes correta.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # Bibliotecas para o Playwright
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && apt-get clean

# =============================================
# SEÇÃO DE DEPENDÊNCIAS PYTHON (COMO AIRFLOW)
# =============================================
# Retornamos para o usuário padrão do Airflow por segurança
USER airflow

# Copia o requirements.txt para a imagem
COPY requirements.txt /

# Instala as dependências Python
RUN pip install --no-cache-dir -r /requirements.txt && \
    # Instala o navegador Chromium para o Playwright
    playwright install chromium