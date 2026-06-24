resource "google_bigquery_dataset" "this" {
  for_each   = var.datasets
  project    = var.project
  dataset_id = each.value
  location   = var.location

  delete_contents_on_destroy = false
}


locals {
  # Schema alineado con el estado REAL de la tabla en BigQuery. Las tablas
  # fueron creadas por el pipeline Python (load_table_from_json / CREATE OR
  # REPLACE TABLE), que infiere los modos como NULLABLE. Para que Terraform
  # documente esa realidad y NO fuerce destruir/recrear tablas con datos, los
  # modos se declaran NULLABLE incluso donde el código siempre popula el campo.
  raw_breweries_schema = jsonencode([
    { name = "id", type = "STRING", mode = "NULLABLE" },
    { name = "name", type = "STRING", mode = "NULLABLE" },
    { name = "brewery_type", type = "STRING", mode = "NULLABLE" },
    { name = "street", type = "STRING", mode = "NULLABLE" },
    { name = "city", type = "STRING", mode = "NULLABLE" },
    { name = "state", type = "STRING", mode = "NULLABLE" },
    { name = "country", type = "STRING", mode = "NULLABLE" },
    { name = "postal_code", type = "STRING", mode = "NULLABLE" },
    { name = "phone", type = "STRING", mode = "NULLABLE" },
    { name = "website_url", type = "STRING", mode = "NULLABLE" },
    { name = "longitude", type = "FLOAT64", mode = "NULLABLE" },
    { name = "latitude", type = "FLOAT64", mode = "NULLABLE" },
    { name = "ingestion_ts", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "ingestion_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "source_payload", type = "STRING", mode = "NULLABLE" },
  ])

  # La API no devuelve ``mode`` para columnas NULLABLE creadas por CREATE OR
  # REPLACE TABLE; por eso aqui se omite ``mode`` (NULLABLE es el default de
  # BigQuery) y asi el schema coincide exactamente con el estado importado.
  integration_prueba_tecnica_schema = jsonencode([
    { name = "brewery_id", type = "STRING" },
    { name = "name", type = "STRING" },
    { name = "brewery_type", type = "STRING" },
    { name = "city", type = "STRING" },
    { name = "state", type = "STRING" },
    { name = "country", type = "STRING" },
    { name = "phone", type = "STRING" },
    { name = "website_url", type = "STRING" },
    { name = "ingestion_ts", type = "TIMESTAMP" },
    { name = "transformation_date", type = "DATE" },
  ])

  # logical table key -> (owning dataset logical key, schema json)
  table_definitions = {
    raw_breweries = {
      dataset_key = "sandbox"
      schema      = local.raw_breweries_schema
    }
    integration_prueba_tecnica = {
      dataset_key = "integration"
      schema      = local.integration_prueba_tecnica_schema
    }
  }
}

resource "google_bigquery_table" "this" {
  for_each   = var.table_names
  project    = var.project
  dataset_id = google_bigquery_dataset.this[local.table_definitions[each.key].dataset_key].dataset_id
  table_id   = each.value
  schema     = local.table_definitions[each.key].schema

  # El estado real de las tablas importadas es deletion_protection=true. Se
  # expone como variable (default true) para documentar esa realidad y, a la
  # vez, permitir una destrucción controlada pasandola a false a proposito.
  deletion_protection = var.deletion_protection
}
