# Arquivo: Dockerfile
# Descrição: Define a imagem customizada do Airflow com nossas dependências.
FROM apache/airflow:2.9.2

# ====================================================================
# PASSO 1: INSTALAR DEPENDÊNCIAS PYTHON PRIMEIRO (COMO USUÁRIO AIRFLOW)
# ====================================================================
# É necessário instalar o playwright antes de podermos usar seus comandos.
USER airflow
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

# ====================================================================
# PASSO 2: INSTALAR DEPENDÊNCIAS DE SISTEMA (COMO ROOT)
# ====================================================================
# Trocamos para o usuário ROOT para ter permissão de instalar pacotes de sistema.
USER root

# Este é o comando chave: ele usa o Playwright (já instalado) para
# instalar todas as dependências de sistema que o Chromium precisa.
# É o método oficial e mais garantido.
RUN playwright install-deps

# ====================================================================
# PASSO 3: INSTALAR O NAVEGADOR (COMO USUÁRIO AIRFLOW)
# ====================================================================
# Voltamos para o usuário padrão do Airflow por segurança.
USER airflow

# Agora que as dependências de sistema estão prontas, instalamos o binário do navegador.
RUN playwright install chromium