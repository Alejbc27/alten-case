output "dataset_ids" {
  description = "BigQuery dataset ids keyed by logical name."
  value       = module.bigquery.dataset_ids
}

output "table_ids" {
  description = "BigQuery table ids keyed by logical name."
  value       = module.bigquery.table_ids
}

output "service_account_email" {
  description = "Email of the pipeline service account."
  value       = module.service_account.sa_email
}

output "sa_key_path" {
  description = "Local path of the generated SA JSON key. null cuando create_sa_key=false."
  value       = module.service_account.key_path
}

output "sa_private_key" {
  description = "Raw SA key JSON (sensitive; also in state). null cuando create_sa_key=false."
  value       = module.service_account.private_key
  sensitive   = true
}
