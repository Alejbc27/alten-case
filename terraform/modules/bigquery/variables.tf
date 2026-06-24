variable "project" {
  description = "GCP project id that owns the BigQuery datasets and tables."
  type        = string
}

variable "location" {
  description = "BigQuery dataset location (e.g. europe-west1)."
  type        = string
}

variable "datasets" {
  description = "Datasets to create. Map of logical key -> dataset id. Keys sandbox and integration are referenced by the table placement below."
  type        = map(string)
}

variable "table_names" {
  description = "Tables to create. Map of logical key -> table id. Logical keys must be raw_breweries and integration_prueba_tecnica so the hardcoded schema lookup resolves."
  type        = map(string)
}

variable "deletion_protection" {
  description = "BigQuery table deletion protection. Defaults to true to match the real imported tables and avoid accidental destroy. Set to false explicitly to allow controlled destruction."
  type        = bool
  default     = true
}
