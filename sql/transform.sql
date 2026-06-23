--parte2-3: transformación idempotente de breweries (raw -> integration).
--Reemplaza la tabla destino de forma atómica en cada ejecución;
--re-ejecutar sobre los mismos datos crudos produce exactamente el mismo resultado.
CREATE OR REPLACE TABLE `alten-case.INTEGRATION.integration_prueba_tecnica` AS
WITH
  -- 1) Lectura del sandbox: brewery_id se extrae del payload JSON (columna
  --    plana `id` no garantizada), el resto son columnas planas visibles.
  source_breweries AS (
    SELECT
      JSON_VALUE(source_payload, '$.id') AS brewery_id,
      name,
      brewery_type,
      city,
      state,
      country,
      phone,
      website_url,
      ingestion_ts,
      ingestion_run_id
    FROM `alten-case.SANDBOX_alten_pipeline.raw_breweries`
    WHERE JSON_VALUE(source_payload, '$.id') IS NOT NULL
  ),

  -- 2) Ranking por brewery_id: gana la ingesta más reciente.
  ranked_breweries AS (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY brewery_id
        ORDER BY ingestion_ts DESC, ingestion_run_id DESC
      ) AS rn
    FROM source_breweries
  ),

  -- 3) Deduplicación: nos quedamos con el ganador de cada brewery_id.
  deduplicated_breweries AS (
    SELECT
      brewery_id,
      name,
      brewery_type,
      city,
      state,
      country,
      phone,
      website_url,
      ingestion_ts
    FROM ranked_breweries
    WHERE rn = 1
  )

-- Salida final + metadato de cuándo se ejecutó la transformación.
SELECT
  *,
  CURRENT_DATE() AS transformation_date
FROM deduplicated_breweries;
