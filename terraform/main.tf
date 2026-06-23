# Root orchestrator. Module calls are added as each module lands.

module "bigquery" {
  source = "./modules/bigquery"

  project     = var.gcp_project
  location    = var.gcp_region
  datasets    = var.dataset_names
  table_names = var.table_names
}

module "service_account" {
  source = "./modules/service_account"

  account_id      = var.sa_account_id
  project         = var.gcp_project
  dataset_ids     = module.bigquery.dataset_ids
  key_output_path = var.sa_key_output_path
}
