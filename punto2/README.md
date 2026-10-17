# Punto 2 – Despliegue con Terraform, Boto3 y AWS CLI

Un bucket S3, una instancia EC2 y una instancia RDS PostgreSQL (con la contraseña
administrada por Secrets Manager) en **una sola región: `us-east-2`**, creados con tres
métodos distintos y ejecutados **uno tras otro**, destruyendo cada versión antes de empezar la
siguiente. Todo se hace con el usuario IAM `user_cli`, nunca con la cuenta raíz.

## Estructura

```
iam/user_cli_policy.json     Política IAM de mínimo privilegio
terraform/                   versions.tf, variables.tf, main.tf, outputs.tf
boto3/deploy_boto3.py        create | read-secret | destroy
cli/deploy_cli.sh            creación con AWS CLI
cli/destroy_cli.sh           eliminación con AWS CLI
scripts/setup_iam.sh         crea y adjunta la política (lo corre un admin, una vez)
scripts/check_leftovers.sh   busca recursos facturables tras cada destroy
docs/respuestas.md           Terraform, autenticación, estado, comparación
docs/costos.md               estimación de costos y preguntas de costos
evidence/                    capturas y logs (ver evidence/README.md)
```

## 0. Requisitos

- AWS CLI v2, Terraform >= 1.6, Python >= 3.9 (`pip install -r boto3/requirements.txt`)
- Un usuario `user_cli` con la política de `iam/user_cli_policy.json` adjunta.

## 1. Configurar `user_cli` (una sola vez)

Un administrador (no la cuenta raíz para el trabajo diario) adjunta la política:

```bash
./scripts/setup_iam.sh
```

Luego, en tu máquina, guarda la clave de `user_cli` **en un perfil local**, no en Git ni en
Secrets Manager:

```bash
aws configure --profile user_cli      # region: us-east-2
export AWS_PROFILE=user_cli
aws sts get-caller-identity           # el ARN debe terminar en :user/user_cli
```

Prueba negativa (debe fallar, demuestra mínimo privilegio):

```bash
aws iam list-users                    # AccessDenied esperado
```

## 2. Versión Terraform

```bash
cd terraform
terraform init
terraform validate
terraform plan -out tfplan
terraform apply tfplan                # RDS tarda 5-10 min
terraform output
# Verificar que el estado no contiene contraseñas:
terraform show -json | grep -i '"password"'      # no debe devolver contraseñas
aws secretsmanager get-secret-value --secret-id "$(terraform output -raw rds_master_secret_arn)" \
  --query SecretString --output text | python3 -c 'import sys,json;print(json.load(sys.stdin)["username"])'
terraform destroy
cd .. && ./scripts/check_leftovers.sh
```

## 3. Versión Boto3

```bash
cd boto3
python deploy_boto3.py create
python deploy_boto3.py read-secret    # lee el secreto en ejecución, sin imprimir la contraseña
python deploy_boto3.py destroy
cd .. && ./scripts/check_leftovers.sh
```

## 4. Versión AWS CLI

```bash
cd cli
./deploy_cli.sh
./destroy_cli.sh
cd .. && ./scripts/check_leftovers.sh
```


## 5. Evidencias

Ver `evidence/README.md`. Captura **solo** salidas sin credenciales.

## Seguridad

- Ninguna contraseña en código, variables ni estado: RDS usa `manage_master_user_password` /
  `ManageMasterUserPassword` / `--manage-master-user-password`.
- Las claves de `user_cli` viven en `~/.aws/credentials`; **no** se guardan en Secrets Manager.
- `.gitignore` excluye `*.tfstate`, `.terraform/`, `*.tfvars`, llaves y archivos de estado.

## Respuestas y costos

- [docs/respuestas.md](docs/respuestas.md)
- [docs/costos.md](docs/costos.md)
