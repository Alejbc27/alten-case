# ----------------------------------------------------------------------------
# Remote state: pre-existing GCS bucket.
#
# The bucket MUST already exist; Terraform never creates it (no bootstrap
# cycle). Because a backend block cannot reference variables, the bucket and
# prefix are passed at init time so the value never lives in version control:
#
#   terraform init \
#     -backend-config="bucket=<your-bucket>" \
#     -backend-config="prefix=alten-case/terraform"
#
# SECURITY: google_service_account_key stores private key material in state.
# Treat the GCS bucket (and therefore the state object) as secret-grade access.
# Acceptable for a sandbox/proof-of-concept; not a production pattern.
# ----------------------------------------------------------------------------
terraform {
  backend "gcs" {}
}
