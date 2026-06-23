output "dataset_ids" {
  description = "Created dataset ids keyed by logical name."
  value       = { for k, d in google_bigquery_dataset.this : k => d.dataset_id }
}

output "table_ids" {
  description = "Created table ids keyed by logical name (project:dataset.table)."
  value       = { for k, t in google_bigquery_table.this : k => "${t.project}:${t.dataset_id}.${t.table_id}" }
}
