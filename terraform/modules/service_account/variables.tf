variable "account_id" {
  description = "Service account id, without the .iam.gserviceaccount.com suffix."
  type        = string
}

variable "project" {
  description = "GCP project id that owns the service account."
  type        = string
}

variable "dataset_ids" {
  description = "Datasets on which the service account gets roles/bigquery.dataEditor. Map of logical key -> dataset id (iterated with for_each)."
  type        = map(string)
}

variable "key_output_path" {
  description = "Local path where the generated JSON key is written. Only used when create_key=true. The local provider creates the parent directory."
  type        = string
}

variable "create_key" {
  description = "Si true, crea google_service_account_key y local_sensitive_file (la clave privada queda en el state). Si false (default defensivo), no crea ninguna clave: se asume un JSON existente o Application Default Credentials."
  type        = bool
  default     = false
}
