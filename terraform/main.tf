# Root orchestrator. Module calls are added as each module lands.

module "bigquery" {
  source = "./modules/bigquery"

  project     = var.gcp_project
  location    = var.gcp_region
  datasets    = var.dataset_names
  table_names = var.table_names
}
