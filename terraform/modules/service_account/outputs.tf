output "sa_email" {
  description = "Email of the created service account."
  value       = google_service_account.this.email
}

output "key_path" {
  description = "Local path where the SA JSON key was written."
  value       = local_sensitive_file.sa_key.filename
}

output "private_key" {
  description = "Raw SA key JSON. Sensitive: also stored in Terraform state."
  value       = google_service_account_key.this.private_key
  sensitive   = true
}
