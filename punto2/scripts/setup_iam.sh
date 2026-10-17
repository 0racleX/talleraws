#!/usr/bin/env bash
# Configura IAM (usuario user_cli + politica) con un usuario ADMINISTRADOR, una sola vez.
# Despues de esto, TODO lo demas se hace con user_cli, no con la cuenta raiz.
# Uso (desde una sesion de administrador, p. ej. CloudShell o un usuario IAM admin):
#   ./setup_iam.sh
set -euo pipefail
POLICY_NAME=user_cli_punto2_policy
DIR="$(cd "$(dirname "$0")/.." && pwd)"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

aws iam create-policy --policy-name "$POLICY_NAME" \
  --policy-document "file://$DIR/iam/user_cli_policy.json" || true
aws iam attach-user-policy --user-name user_cli \
  --policy-arn "arn:aws:iam::$ACCOUNT:policy/$POLICY_NAME"

# Crear la clave de acceso SOLO si user_cli no tiene una. Se muestra una vez: guardela con
#   aws configure --profile user_cli
# y NO la suba a Git ni la pegue en Secrets Manager.
echo "Claves existentes de user_cli:"
aws iam list-access-keys --user-name user_cli --query 'AccessKeyMetadata[].[AccessKeyId,Status]' --output text
echo "Si no hay ninguna: aws iam create-access-key --user-name user_cli"
