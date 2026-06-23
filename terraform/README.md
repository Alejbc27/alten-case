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

## Service Account Key: opcional

La clave JSON de la cuenta de servicio es **opcional**. Hay dos modos,
controlados por la variable `create_sa_key`:

### `create_sa_key = false` (default recomendado)

Terraform crea la Service Account y los bindings IAM, pero **no** crea ninguna
clave nueva ni escribe archivos locales. Usalo cuando ya tengas un JSON
descargado manualmente desde la consola, o cuando uses
Application Default Credentials.

Configura tu `.env` con la ruta del JSON existente:

```bash
# .env
GOOGLE_APPLICATION_CREDENTIALS=/ruta/a/tu-sa-existente.json
```

Ventaja: ninguna clave privada nueva termina en el `terraform.tfstate`.

### `create_sa_key = true`

Terraform genera una `google_service_account_key`, la escribe en
`sa_key_output_path` (por defecto `../.secrets/alten-pipeline-sa.json`) y la usa
para ejecutar el pipeline:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/../.secrets/alten-pipeline-sa.json"
```

Aviso: `google_service_account_key.private_key` queda guardada en el state
remoto. El bucket GCS del state debe tratarse como sensible.

Si tu versión del provider `local` no crea el directorio automáticamente,
crealo antes:

```bash
mkdir -p ../.secrets
```

## Seguridad

- `terraform.tfvars`, `.terraform/`, `*.tfstate*`, `*.tfplan`, `.secrets/` y
  `*-sa.json` están ignorados por Git.
- Con `create_sa_key = false` (default) ninguna clave privada se gestiona ni
  almacena en Terraform: es el modo recomendado para esta prueba/sandbox.
- Con `create_sa_key = true`, `google_service_account_key.private_key` queda
  guardada en el state remoto. Por eso el bucket GCS del state debe tratarse
  como sensible.
- En producción conviene usar Workload Identity o credenciales de corta
  duración.
