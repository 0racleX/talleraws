#!/usr/bin/env bash
# Comprueba que no queden componentes facturables del punto 3 en us-east-2.
# Uso: export AWS_PROFILE=user_cli ; ./check_leftovers.sh
export AWS_DEFAULT_REGION=us-east-2
export AWS_PAGER=""

echo "Identidad: $(aws sts get-caller-identity --query Arn --output text)"
echo "--- Instancias EC2 vivas (no terminated)"
aws ec2 describe-instances --filters "Name=tag:Project,Values=lab-punto3" \
  --query 'Reservations[].Instances[?State.Name!=`terminated`].[InstanceId,State.Name]' --output text
echo "--- Volumenes EBS"
aws ec2 describe-volumes --filters "Name=tag:Project,Values=lab-punto3" --query 'Volumes[].VolumeId' --output text
echo "--- Clusters DocumentDB"
aws docdb describe-db-clusters --filters Name=engine,Values=docdb --query 'DBClusters[].DBClusterIdentifier' --output text
echo "--- Instancias DocumentDB"
aws docdb describe-db-instances --filters Name=engine,Values=docdb --query 'DBInstances[].DBInstanceIdentifier' --output text
echo "--- Snapshots de cluster DocumentDB"
aws docdb describe-db-cluster-snapshots --query 'DBClusterSnapshots[].DBClusterSnapshotIdentifier' --output text
echo "--- Subnet groups lab-docdb"
aws docdb describe-db-subnet-groups --query 'DBSubnetGroups[?starts_with(DBSubnetGroupName,`lab-docdb`)].DBSubnetGroupName' --output text
echo "--- Secretos rds!cluster-* (pueden quedar 'pendientes de eliminacion')"
aws secretsmanager list-secrets --include-planned-deletion \
  --query 'SecretList[?starts_with(Name,`rds!cluster`)].[Name,DeletedDate]' --output text
echo "--- Grupos de seguridad lab-docdb-*"
aws ec2 describe-security-groups --filters "Name=group-name,Values=lab-docdb-*" --query 'SecurityGroups[].GroupId' --output text
echo "--- Key pairs lab-docdb-*"
aws ec2 describe-key-pairs --filters "Name=key-name,Values=lab-docdb-*" --query 'KeyPairs[].KeyName' --output text
echo "--- Elastic IPs / NAT Gateways"
aws ec2 describe-addresses --query 'Addresses[].PublicIp' --output text
aws ec2 describe-nat-gateways --filter Name=state,Values=available,pending --query 'NatGateways[].NatGatewayId' --output text
echo "(Todas las secciones deben salir vacias.)"
