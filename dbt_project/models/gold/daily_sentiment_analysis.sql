{{
  config(
    materialized='table'
  )
}}

-- Esta é a query que define nossa tabela analítica final.
select
    -- Converte o timestamp para apenas a data, para agruparmos por dia.
    cast(processed_timestamp as date) as analysis_date,

    -- Contagem condicional para cada tipo de sentimento.
    -- Isso cria uma coluna para cada sentimento com a contagem de manchetes do dia
    count(case when sentiment = 'Positiva' then 1 end) as positive_headlines,
    count(case when sentiment = 'Negativa' then 1 end) as negative_headlines,
    count(case when sentiment = 'Neutra' then 1 end) as neutral_headlines,

    -- Contagem total de manchetes processadas no dia.
    count(headline_link) as total_headlines

from
    -- A função ref() nos permite selecionar dados do nosso modelo de staging.
   
    {{ ref('stg_enriched_headlines') }}

group by
    analysis_date

order by
    analysis_date desc