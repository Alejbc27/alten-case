# ----------------------------------------------------------------------------
# Service account
# ----------------------------------------------------------------------------
resource "google_service_account" "this" {
  project      = var.project
  account_id   = var.account_id
  display_name = "Alten pipeline service account"
}

# ----------------------------------------------------------------------------
# IAM — minimum permissions to load data into BigQuery
# ----------------------------------------------------------------------------

# Project-level: permission to run BigQuery jobs (load/query).
resource "google_project_iam_member" "bq_job_user" {
  project = var.project
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.this.email}"
}

# Dataset-level: read/write data on every managed dataset.
resource "google_bigquery_dataset_iam_member" "data_editor" {
  for_each   = var.dataset_ids
  project    = var.project
  dataset_id = each.value
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.this.email}"
}

# ----------------------------------------------------------------------------
# JSON key — written to disk for GOOGLE_APPLICATION_CREDENTIALS
#
# SECURITY: the private key is also persisted in Terraform state. The remote
# GCS backend (and thus state) must be treated as secret-grade. Acceptable for
# a sandbox; prefer Workload Identity in production.
# ----------------------------------------------------------------------------
resource "google_service_account_key" "this" {
  service_account_id = google_service_account.this.name
  public_key_type    = "TYPE_X509_PEM_FILE"
  private_key_type   = "TYPE_GOOGLE_CREDENTIALS_FILE"
}

resource "local_sensitive_file" "sa_key" {
  filename        = var.key_output_path
  content         = google_service_account_key.this.private_key
  file_permission = "0600"
}
