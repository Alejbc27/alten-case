# Terraform — BigQuery + Service Account

Modular Terraform for the Alten pipeline: two BigQuery datasets + tables, one
service account with minimum IAM, and a JSON key written to disk for
`GOOGLE_APPLICATION_CREDENTIALS`.

## Layout

```
terraform/
├── versions.tf / backend.tf / providers.tf   # engine + provider + remote state
├── variables.tf / main.tf / outputs.tf       # root orchestrator
├── terraform.tfvars.example                  # non-sensitive defaults
└── modules/
    ├── bigquery/         # datasets + explicit table schemas
    └── service_account/  # SA, IAM bindings, JSON key
```

## Prerequisites

- A **pre-existing GCS bucket** for remote state. Terraform does not create it.
- `terraform` >= 1.5 and the Google Cloud CLI authenticated as a project owner
  (enough to create datasets, tables, a service account and IAM bindings).

## Init (remote state)

Backend config is intentionally empty in `backend.tf`; pass the bucket and
prefix at init time:

```bash
cd terraform
terraform init \
  -backend-config="bucket=<your-bucket>" \
  -backend-config="prefix=alten-case/terraform"
```

To validate without touching remote state (CI / local checks):

```bash
terraform init -backend=false
terraform validate
```

## Apply

```bash
cp terraform.tfvars.example terraform.tfvars   # edit values
terraform apply
```

After apply, authenticate the Python pipeline with the generated key:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/../.secrets/alten-pipeline-sa.json"
```

The `local` provider creates the parent directory of `sa_key_output_path`; if
you use an older provider, create it first: `mkdir -p ../.secrets`.

## Security notes

- `terraform.tfvars`, `.terraform/`, `*.tfstate*`, `*.tfplan`, `.secrets/` and
  `*-sa.json` are git-ignored.
- `google_service_account_key.private_key` is stored in remote state. The GCS
  bucket must therefore be treated as secret-grade. Fine for this sandbox; not a
  production pattern (use Workload Identity / short-lived credentials in prod).
