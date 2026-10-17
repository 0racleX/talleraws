#!/usr/bin/env bash
# Verifica que no queden componentes facturables en us-east-2 (usar tras cada destroy).
# Uso: export AWS_PROFILE=user_cli ; ./check_leftovers.sh
export AWS_DEFAULT_REGION=us-east-2
export AWS_PAGER=""

echo "Identidad: $(aws sts get-caller-identity --query Arn --output text)"
echo "--- Instancias EC2 vivas (no terminated)"
aws ec2 describe-instances --filters "Name=tag:Project,Values=lab-punto2" \
  --query 'Reservations[].Instances[?State.Name!=`terminated`].[InstanceId,State.Name]' --output text
echo "--- Volumenes EBS"
aws ec2 describe-volumes --filters "Name=tag:Project,Values=lab-punto2" --query 'Volumes[].VolumeId' --output text
echo "--- Instancias RDS"
aws rds describe-db-instances --query 'DBInstances[].DBInstanceIdentifier' --output text
echo "--- Snapshots RDS manuales"
aws rds describe-db-snapshots --query 'DBSnapshots[].DBSnapshotIdentifier' --output text
echo "--- Backups automaticos retenidos"
aws rds describe-db-instance-automated-backups --query 'DBInstanceAutomatedBackups[].DBInstanceIdentifier' --output text
echo "--- Secretos rds!db-* (pueden quedar en 'pendiente de eliminacion')"
aws secretsmanager list-secrets --include-planned-deletion \
  --query 'SecretList[?starts_with(Name,`rds!db`)].[Name,DeletedDate]' --output text
echo "--- VPCs del laboratorio"
aws ec2 describe-vpcs --filters "Name=tag:Project,Values=lab-punto2" --query 'Vpcs[].VpcId' --output text
echo "--- Elastic IPs / NAT Gateways"
aws ec2 describe-addresses --query 'Addresses[].PublicIp' --output text
aws ec2 describe-nat-gateways --filter Name=state,Values=available,pending --query 'NatGateways[].NatGatewayId' --output text
echo "--- Buckets lab-*"
aws s3api list-buckets --query 'Buckets[?starts_with(Name,`lab-`)].Name' --output text
echo "(Todas las secciones deben salir vacias.)"
