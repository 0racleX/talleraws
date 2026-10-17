#!/usr/bin/env bash
# Crea la politica COMPLEMENTARIA del punto 3 y la adjunta a user_cli. La corre un ADMINISTRADOR IAM.
# Requiere que user_cli ya tenga la politica del punto 2 (EC2, red, SSM para AMI, KMS, rol vinculado de RDS).
set -euo pipefail
POLICY_NAME=user_cli_punto3_policy
DIR="$(cd "$(dirname "$0")/.." && pwd)"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

aws iam create-policy --policy-name "$POLICY_NAME" \
  --policy-document "file://$DIR/iam/user_cli_punto3_policy.json" || true
aws iam attach-user-policy --user-name user_cli \
  --policy-arn "arn:aws:iam::$ACCOUNT:policy/$POLICY_NAME"
aws iam list-attached-user-policies --user-name user_cli
