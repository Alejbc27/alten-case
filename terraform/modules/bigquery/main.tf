resource "google_bigquery_dataset" "this" {
  for_each   = var.datasets
  project    = var.project
  dataset_id = each.value
  location   = var.location

  delete_contents_on_destroy = false
}


locals {
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
    { name = "ingestion_ts", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "ingestion_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "source_payload", type = "STRING", mode = "REQUIRED" },
  ])

  integration_prueba_tecnica_schema = jsonencode([
    { name = "brewery_id", type = "STRING", mode = "REQUIRED" },
    { name = "name", type = "STRING", mode = "NULLABLE" },
    { name = "brewery_type", type = "STRING", mode = "NULLABLE" },
    { name = "city", type = "STRING", mode = "NULLABLE" },
    { name = "state", type = "STRING", mode = "NULLABLE" },
    { name = "country", type = "STRING", mode = "NULLABLE" },
    { name = "phone", type = "STRING", mode = "NULLABLE" },
    { name = "website_url", type = "STRING", mode = "NULLABLE" },
    { name = "ingestion_ts", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "transformation_date", type = "DATE", mode = "NULLABLE" },
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

  deletion_protection = false
}
