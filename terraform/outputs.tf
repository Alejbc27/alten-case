output "dataset_ids" {
  description = "BigQuery dataset ids keyed by logical name."
  value       = module.bigquery.dataset_ids
}

output "table_ids" {
  description = "BigQuery table ids keyed by logical name."
  value       = module.bigquery.table_ids
}
