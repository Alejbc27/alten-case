# Terraform — BigQuery y cuenta de servicio

Infraestructura mínima para la prueba técnica: crea los datasets y tablas de
BigQuery, una cuenta de servicio con permisos mínimos y una clave JSON local para
usar con `GOOGLE_APPLICATION_CREDENTIALS`.

## Estructura

```
terraform/
├── versions.tf / backend.tf / providers.tf   # versión, provider y state remoto
├── variables.tf / main.tf / outputs.tf       # orquestador principal
├── terraform.tfvars.example                  # valores de ejemplo no sensibles
└── modules/
    ├── bigquery/         # datasets y schemas explícitos de tablas
    └── service_account/  # cuenta de servicio, IAM y clave JSON
```

## Requisitos previos

- Un **bucket GCS ya creado** para guardar el state remoto. Terraform no lo crea.
- `terraform` >= 1.5.
- Autenticación en GCP con permisos para crear datasets, tablas, Service Accounts
  y bindings IAM.

## Inicializar Terraform

`backend.tf` no fija el bucket para evitar hardcodear valores locales. Pasalo al
inicializar:

```bash
cd terraform
terraform init \
  -backend-config="bucket=<tu-bucket>" \
  -backend-config="prefix=alten-case/terraform"
```

Para validar sin tocar el state remoto:

```bash
terraform init -backend=false
terraform validate
```

## Aplicar cambios

```bash
cp terraform.tfvars.example terraform.tfvars
# Editar terraform.tfvars con los valores reales
terraform apply
```

Después del `apply`, usá la clave generada para ejecutar el pipeline Python:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/../.secrets/alten-pipeline-sa.json"
```

Si tu versión del provider `local` no crea el directorio automáticamente, crealo
antes:

```bash
mkdir -p ../.secrets
```

## Seguridad

- `terraform.tfvars`, `.terraform/`, `*.tfstate*`, `*.tfplan`, `.secrets/` y
  `*-sa.json` están ignorados por Git.
- `google_service_account_key.private_key` queda guardada en el state remoto.
  Por eso el bucket GCS del state debe tratarse como sensible.
- Para esta prueba/sandbox es aceptable. En producción conviene usar Workload
  Identity o credenciales de corta duración.
