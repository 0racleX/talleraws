# Respuestas

## 1. ¿Qué es Terraform y cómo define, planifica, crea y elimina infraestructura?

Terraform (HashiCorp) es una herramienta de **infraestructura como código declarativa**. Se
describe el estado deseado en archivos HCL (`.tf`) y Terraform calcula qué hacer para llegar
a él. Habla con AWS a través de un **provider** (`hashicorp/aws`), que usa las mismas APIs que
el SDK y el CLI.

| Fase | Comando | Qué hace |
|---|---|---|
| Definir | archivos `.tf` | Recursos, variables, outputs y data sources |
| Inicializar | `terraform init` | Descarga providers y prepara el directorio |
| Verificar | `terraform validate` | Revisa sintaxis y referencias |
| Planificar | `terraform plan` | Compara código, estado y AWS real; muestra qué se crea/cambia/destruye sin tocar nada |
| Crear | `terraform apply` | Ejecuta el plan siguiendo el **grafo de dependencias** (VPC antes que subredes, etc.) |
| Eliminar | `terraform destroy` | Borra todo lo gestionado, en orden inverso de dependencias |

Ventajas clave: es **declarativo e idempotente** (volver a aplicar no duplica), el plan permite
revisar antes de gastar, y el **estado** (`terraform.tfstate`) le dice qué recursos ya posee.

## 2. Permisos necesarios de `user_cli`

Ver `iam/user_cli_policy.json`. Resumen por servicio:

| Servicio | Acciones principales | Por qué |
|---|---|---|
| S3 | Create/DeleteBucket, Put/GetBucket* (versioning, tagging, encryption, public access block…), List, Put/Get/DeleteObject | Terraform lee muchos atributos del bucket tras crearlo; el borrado exige vaciarlo |
| EC2 / red | Create/Delete de VPC, subnet, IGW, route table, security group; Authorize/Revoke; RunInstances, TerminateInstances; Describe*; CreateTags | Componentes de red y la instancia |
| SSM | `ssm:GetParameter` sobre `/aws/service/ami-amazon-linux-latest/*` | Obtener la AMI vigente |
| RDS | Create/Delete/Modify/DescribeDBInstance, CRUD de DB subnet group, tags, `iam:CreateServiceLinkedRole` (RDS) | Crear y borrar la base |
| Secrets Manager | `CreateSecret`, `TagResource`, `GetSecretValue`, `DescribeSecret`, `DeleteSecret` limitados a `rds!db-*` | RDS crea el secreto administrado en nombre del llamante |
| KMS | `DescribeKey`, `CreateGrant`, `GenerateDataKey`, `Decrypt` (clave `aws/*`) | Cifrado del secreto y del almacenamiento |
| STS | `GetCallerIdentity` | Verificar con qué identidad se actúa |

Restricciones aplicadas: región `us-east-2` por condición `aws:RequestedRegion`, buckets solo
`lab-*`, secretos solo `rds!db-*`, y **sin** `iam:*` salvo el rol vinculado de RDS.

## 3. ¿Cómo autentica `user_cli` a las herramientas?

`user_cli` es un usuario IAM con una **clave de acceso de larga duración** (Access Key ID +
Secret Access Key) guardada localmente en `~/.aws/credentials` bajo el perfil `user_cli`.

- **AWS CLI** y **Boto3** usan la *cadena estándar de credenciales*: variables de entorno →
  perfil (`AWS_PROFILE`) → SSO → rol de instancia. Cada petición se **firma con SigV4** usando
  la clave secreta (la clave no viaja por la red).
- **Terraform** usa el mismo mecanismo: el provider `aws` está basado en el SDK de AWS y lee
  `AWS_PROFILE`; por eso `provider "aws"` no contiene claves.
- Las claves **no pueden ir en Secrets Manager** como si fueran la contraseña de la base de datos:
  para leer un secreto ya hay que estar autenticado. Es un problema del huevo y la gallina. La
  credencial inicial siempre vive fuera (perfil local, variables de entorno, o mejor aún
  credenciales temporales de IAM Identity Center o un rol). Dentro de AWS (EC2, Lambda), el
  mecanismo correcto es un **rol IAM** con credenciales temporales, sin claves.
- Lo que sí va en Secrets Manager: la contraseña de la base de datos, que los programas leen
  **en ejecución** con `get_secret_value`, usando la identidad ya autenticada.

## 4. Archivo de estado de Terraform

El estado guarda **todos los atributos** de cada recurso, y a menudo en texto plano. Por eso:

- Con `manage_master_user_password = true` el estado contiene el **ARN** y la clave KMS del
  secreto, **no** la contraseña. No existe `password` ni variable para ella.
- Si se hubiera usado `password = var.x` o `random_password`, el valor quedaría en el estado.
  Lo mismo ocurre con `data "aws_secretsmanager_secret_version"` aplicado a un recurso: lo
  leído se persiste. Se evitó ambas cosas.
- Comprobación: `terraform show -json | grep -i password` no debe mostrar valores.
- El estado es local y está en `.gitignore`. En un entorno real se usaría un backend remoto
  (S3 cifrado + bloqueo) con acceso restringido; aquí no se usa para no crear recursos extra.

## 5. Comparación de métodos

| Criterio | Terraform | Boto3 | AWS CLI |
|---|---|---|---|
| Estilo | Declarativo | Imperativo (programa) | Imperativo (comandos/shell) |
| Plan previo | Sí (`plan`) | No | No |
| Orden de dependencias | Automático (grafo) | Manual | Manual |
| Eliminación | Un comando, completa | Hay que programarla en orden inverso | Script en orden inverso |
| Idempotencia | Nativa | Hay que implementarla | Hay que implementarla |
| Estado | Archivo de estado (hay que protegerlo) | Mío (JSON de IDs) | Mío (archivo .env de IDs) |
| Líneas de código | ~170 (HCL) | ~190 (Python) | ~80 + 30 |
| Esperas (waiters) | Internas | Explícitas | `aws ... wait` |
| Errores a medias | Reanuda con `apply` | Recursos huérfanos si falla | Recursos huérfanos si falla |
| Mejor para | Infraestructura repetible y mantenida | Lógica compleja, integración en apps | Pruebas rápidas, automatización simple |

**Conclusión.** Para una arquitectura que se crea y destruye varias veces, Terraform es el más
seguro: planifica, ordena y limpia sin intervención. Boto3 da el mayor control pero obliga a
programar dependencias y limpieza. El CLI es lo más rápido de escribir, pero también lo más
frágil si algo falla a medio camino.

## 6. Preguntas de costos

Ver [costos.md](costos.md).
