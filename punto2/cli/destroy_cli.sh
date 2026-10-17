#!/usr/bin/env bash
# Elimina lo creado por deploy_cli.sh. Tolera que el despliegue haya quedado a medias.
set -uo pipefail
export AWS_DEFAULT_REGION=us-east-2
STATE="$(dirname "$0")/cli_state.env"
# shellcheck disable=SC1090
source "$STATE"

echo "== RDS"
if [ -n "${DB:-}" ] && aws rds describe-db-instances --db-instance-identifier "$DB" >/dev/null 2>&1; then
  aws rds delete-db-instance --db-instance-identifier "$DB" --skip-final-snapshot --delete-automated-backups >/dev/null
  aws rds wait db-instance-deleted --db-instance-identifier "$DB"
fi
aws rds delete-db-subnet-group --db-subnet-group-name lab-cli-dbsubnets 2>/dev/null && echo "subnet group eliminado"

echo "== EC2"
if [ -n "${INST:-}" ]; then
  aws ec2 terminate-instances --instance-ids "$INST" >/dev/null
  aws ec2 wait instance-terminated --instance-ids "$INST"
fi

echo "== Red"
[ -n "${SG_RDS:-}" ] && aws ec2 delete-security-group --group-id "$SG_RDS"
[ -n "${SG_EC2:-}" ] && aws ec2 delete-security-group --group-id "$SG_EC2"
[ -n "${ASSOC:-}" ] && aws ec2 disassociate-route-table --association-id "$ASSOC"
[ -n "${RT:-}" ] && aws ec2 delete-route-table --route-table-id "$RT"
for s in "${SUB_PUB:-}" "${SUB_A:-}" "${SUB_B:-}"; do [ -n "$s" ] && aws ec2 delete-subnet --subnet-id "$s"; done
if [ -n "${IGW:-}" ]; then
  aws ec2 detach-internet-gateway --internet-gateway-id "$IGW" --vpc-id "$VPC"
  aws ec2 delete-internet-gateway --internet-gateway-id "$IGW"
fi
[ -n "${VPC:-}" ] && aws ec2 delete-vpc --vpc-id "$VPC"

echo "== S3"
if [ -n "${BUCKET:-}" ]; then
  aws s3 rm "s3://$BUCKET" --recursive >/dev/null 2>&1
  aws s3api delete-bucket --bucket "$BUCKET"
fi

rm -f "$STATE"
echo "Listo. Ejecute scripts/check_leftovers.sh para verificar."
