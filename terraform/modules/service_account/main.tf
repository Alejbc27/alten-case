resource "google_service_account" "this" {
  project      = var.project
  account_id   = var.account_id
  display_name = "Alten pipeline service account"
}


resource "google_project_iam_member" "bq_job_user" {
  project = var.project
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.this.email}"
}

resource "google_bigquery_dataset_iam_member" "data_editor" {
  for_each   = var.dataset_ids
  project    = var.project
  dataset_id = each.value
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.this.email}"
}


# La clave JSON solo se crea bajo demanda: cuando create_key=false no se genera
# ninguna clave nueva ni se escribe archivo local, y la SA se autentica con un
# JSON existente o con Application Default Credentials.
resource "google_service_account_key" "this" {
  count              = var.create_key ? 1 : 0
  service_account_id = google_service_account.this.name
  public_key_type    = "TYPE_X509_PEM_FILE"
  private_key_type   = "TYPE_GOOGLE_CREDENTIALS_FILE"
}

resource "local_sensitive_file" "sa_key" {
  count           = var.create_key ? 1 : 0
  filename        = var.key_output_path
  content         = google_service_account_key.this[0].private_key
  file_permission = "0600"
}
