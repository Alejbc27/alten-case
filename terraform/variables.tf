variable "gcp_project" {
  description = "GCP project id that owns the BigQuery datasets and service account."
  type        = string
  default     = "alten-case"
}

variable "gcp_region" {
  description = "GCP region used by the provider and as the BigQuery dataset location."
  type        = string
  default     = "europe-west1"
}

variable "gcs_bucket" {
  description = "Pre-existing GCS bucket for the remote backend. Passed via -backend-config at init; declared here as the documented single source of truth (backend blocks cannot read variables)."
  type        = string
  default     = null
}

variable "sa_account_id" {
  description = "Service account id, without the .iam.gserviceaccount.com suffix."
  type        = string
  default     = "alten-pipeline-sa"
}

variable "sa_key_output_path" {
  description = "Local path where the generated SA JSON key is written. Solo aplica cuando create_sa_key=true. Relativo al directorio terraform/."
  type        = string
  default     = "../.secrets/alten-pipeline-sa.json"
}

variable "create_sa_key" {
  description = "Si true, Terraform crea una Service Account Key JSON y la escribe en sa_key_output_path (la clave privada queda en el state). Si false (default), no crea ninguna clave: usá un JSON existente o Application Default Credentials."
  type        = bool
  default     = false
}

variable "dataset_names" {
  description = "BigQuery datasets to create. Map of logical key -> dataset id."
  type        = map(string)
  default = {
    sandbox     = "SANDBOX_alten_pipeline"
    integration = "INTEGRATION"
  }
}

variable "table_names" {
  description = "BigQuery tables to create. Map of logical key -> table id. Keys must match the hardcoded schemas in the bigquery module (raw_breweries, integration_prueba_tecnica)."
  type        = map(string)
  default = {
    raw_breweries              = "raw_breweries"
    integration_prueba_tecnica = "integration_prueba_tecnica"
  }
}
