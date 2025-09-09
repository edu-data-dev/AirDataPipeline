
-- Este é o nosso primeiro modelo. Ele seleciona os dados da nossa fonte
-- e aplica algumas transformações básicas.

select
    -- A função source() nos permite referenciar a tabela que declaramos no sources.yml
    link as headline_link,
    title as headline_title,
    sentiment,
    category,
    processed_at as processed_timestamp,
    scraped_at as scraped_timestamp

from {{ source('public', 'silver_enriched_headlines') }}