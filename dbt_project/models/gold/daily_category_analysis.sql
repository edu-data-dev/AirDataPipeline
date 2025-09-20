{{
  config(
    materialized='table'
  )
}}

-- Esta query cria uma tabela analítica com a contagem diária de notícias por categoria
select
    -- Converte o timestamp para apenas a data, para agruparmos por dia.
    cast(processed_timestamp as date) as analysis_date,
    category,
    
    -- Contagem de manchetes por categoria para cada dia
    count(headline_link) as category_count,
    
    -- Calculamos a proporção em relação ao total do dia
    count(headline_link) / sum(count(headline_link)) over (partition by cast(processed_timestamp as date)) as category_percentage

from
    {{ ref('stg_enriched_headlines') }}
where
    category is not null

group by
    analysis_date,
    category

order by
    analysis_date desc,
    category_count desc
