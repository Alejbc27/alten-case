output "sa_email" {
  description = "Email of the created service account."
  value       = google_service_account.this.email
}

output "key_path" {
  description = "Local path where the SA JSON key was written. null cuando create_key=false (clave externa o ADC)."
  value       = var.create_key ? local_sensitive_file.sa_key[0].filename : null
}

output "private_key" {
  description = "Raw SA key JSON. Sensitive: also stored in Terraform state. null cuando create_key=false."
  value       = var.create_key ? google_service_account_key.this[0].private_key : null
  sensitive   = true
}
