#!/usr/bin/env bash
# Despliega en us-east-2: DocumentDB (serverless o aprovisionado) + EC2 bastion para el tunel SSH.
# Contrasena de DocumentDB: la genera y administra Secrets Manager (--manage-master-user-password).
#
# Uso:  export AWS_PROFILE=user_cli
#       ./deploy_docdb.sh serverless      # 0.5-2 DCU (recomendado)
#       ./deploy_docdb.sh provisioned     # db.t4g.medium
set -euo pipefail

MODE="${1:-serverless}"
case "$MODE" in serverless|provisioned) ;; *) echo "Uso: $0 serverless|provisioned" >&2; exit 1 ;; esac

export AWS_DEFAULT_REGION=us-east-2
export AWS_PAGER=""
P=lab-docdb
HERE="$(cd "$(dirname "$0")" && pwd)"
STATE="$HERE/docdb_state.env"            # solo IDs y nombres; esta en .gitignore
KEY_NAME="$P-key"
KEY_FILE="$HOME/.ssh/$KEY_NAME.pem"      # en el disco de Linux (en /mnt/c, chmod no funciona y ssh la rechaza)
ENGINE_VERSION="${ENGINE_VERSION:-5.0.0}"  # serverless exige >= 5.0.0
DB_USER=labadmin
TAG="Key=Project,Value=lab-punto3"
TAGSPEC_TAGS="[{Key=Project,Value=lab-punto3}]"

if [ -e "$STATE" ]; then
  echo "Ya existe $STATE. Ejecute ./destroy_docdb.sh antes de volver a desplegar." >&2; exit 1
fi
if [ "$MODE" = serverless ] && ! aws docdb create-db-cluster --generate-cli-skeleton input 2>/dev/null | grep -q ServerlessV2ScalingConfiguration; then
  echo "Su AWS CLI no conoce el escalado serverless de docdb. Actualice AWS CLI v2." >&2; exit 1
fi
: > "$STATE"; chmod 600 "$STATE"
save() { echo "$1=$2" >> "$STATE"; }
save MODE "$MODE"; save KEY_FILE "$KEY_FILE"

echo "Identidad: $(aws sts get-caller-identity --query Arn --output text)"

# ---- Red: se usa la VPC por defecto (sin costo) con 2 subredes en AZ distintas
VPC=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
[ "$VPC" != "None" ] || { echo "No hay VPC por defecto en us-east-2" >&2; exit 1; }
read -r SUB1 SUB2 < <(aws ec2 describe-subnets --filters Name=vpc-id,Values="$VPC" Name=default-for-az,Values=true \
  --query 'Subnets[:2].SubnetId' --output text)
save VPC "$VPC"
MYIP="${SSH_CIDR_IP:-$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')}"
echo "VPC $VPC | subredes $SUB1 $SUB2 | SSH permitido solo desde $MYIP/32"

# ---- Grupos de seguridad
SG_EC2=$(aws ec2 create-security-group --group-name "$P-ec2-sg" --description "SSH desde mi IP al bastion" \
  --vpc-id "$VPC" --tag-specifications "ResourceType=security-group,Tags=$TAGSPEC_TAGS" --query GroupId --output text)
save SG_EC2 "$SG_EC2"
SG_DB=$(aws ec2 create-security-group --group-name "$P-db-sg" --description "27017 solo desde el bastion" \
  --vpc-id "$VPC" --tag-specifications "ResourceType=security-group,Tags=$TAGSPEC_TAGS" --query GroupId --output text)
save SG_DB "$SG_DB"
aws ec2 authorize-security-group-ingress --group-id "$SG_EC2" --protocol tcp --port 22 --cidr "$MYIP/32" >/dev/null
aws ec2 authorize-security-group-ingress --group-id "$SG_DB" --protocol tcp --port 27017 --source-group "$SG_EC2" >/dev/null

# ---- Par de llaves SSH (la llave privada se guarda solo en su equipo)
mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
if [ -e "$KEY_FILE" ]; then echo "Ya existe $KEY_FILE; renombrela o borrela." >&2; exit 1; fi
aws ec2 create-key-pair --key-name "$KEY_NAME" --key-type ed25519 --query KeyMaterial --output text > "$KEY_FILE"
chmod 400 "$KEY_FILE"
save KEY_NAME "$KEY_NAME"

# ---- EC2 bastion (arm64 t4g.nano: la opcion mas barata)
AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 \
  --query Parameter.Value --output text)
INST=$(aws ec2 run-instances --image-id "$AMI" --instance-type t4g.nano --count 1 --key-name "$KEY_NAME" \
  --network-interfaces "DeviceIndex=0,SubnetId=$SUB1,Groups=$SG_EC2,AssociatePublicIpAddress=true" \
  --metadata-options HttpTokens=required \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Project,Value=lab-punto3},{Key=Name,Value=$P-bastion}]" \
  --query 'Instances[0].InstanceId' --output text)
save INST "$INST"
aws ec2 wait instance-running --instance-ids "$INST"
EC2_IP=$(aws ec2 describe-instances --instance-ids "$INST" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
save EC2_IP "$EC2_IP"
echo "Bastion en ejecucion: $INST ($EC2_IP)"

# ---- DocumentDB
aws docdb create-db-subnet-group --db-subnet-group-name "$P-subnets" --db-subnet-group-description "lab punto3" \
  --subnet-ids "$SUB1" "$SUB2" --tags "$TAG" >/dev/null
save SUBNET_GROUP "$P-subnets"

SERVERLESS_ARGS=()
CLASS=db.t4g.medium
if [ "$MODE" = serverless ]; then
  SERVERLESS_ARGS=(--serverless-v2-scaling-configuration MinCapacity=0.5,MaxCapacity=2)
  CLASS=db.serverless
fi

aws docdb create-db-cluster --db-cluster-identifier "$P-cluster" --engine docdb --engine-version "$ENGINE_VERSION" \
  --master-username "$DB_USER" --manage-master-user-password \
  --db-subnet-group-name "$P-subnets" --vpc-security-group-ids "$SG_DB" \
  --storage-type standard --storage-encrypted --backup-retention-period 1 --no-deletion-protection \
  "${SERVERLESS_ARGS[@]}" --tags "$TAG" >/dev/null
save CLUSTER "$P-cluster"

aws docdb create-db-instance --db-instance-identifier "$P-instance-1" --db-instance-class "$CLASS" \
  --db-cluster-identifier "$P-cluster" --engine docdb --tags "$TAG" >/dev/null
save INSTANCE "$P-instance-1"
echo "Esperando la instancia de DocumentDB ($MODE, $CLASS)... (5-15 min)"
aws docdb wait db-instance-available --db-instance-identifier "$P-instance-1"

ENDPOINT=$(aws docdb describe-db-clusters --db-cluster-identifier "$P-cluster" --query 'DBClusters[0].Endpoint' --output text)
SECRET_ARN=$(aws docdb describe-db-clusters --db-cluster-identifier "$P-cluster" \
  --query 'DBClusters[0].MasterUserSecret.SecretArn' --output text)
if [ "$SECRET_ARN" = "None" ] || [ -z "$SECRET_ARN" ]; then
  SECRET_ARN=$(aws secretsmanager list-secrets --query "SecretList[?starts_with(Name,'rds!cluster')].ARN | [0]" --output text)
fi
save ENDPOINT "$ENDPOINT"; save SECRET_ARN "$SECRET_ARN"
echo "DocumentDB listo: $ENDPOINT"
echo "Secreto administrado: $SECRET_ARN"

# Lectura del secreto en ejecucion SIN imprimir la contrasena
aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --query SecretString --output text \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print("Secreto leido OK, usuario:", d["username"])'

echo "Siguiente: ./get_ca_bundle.sh && ./open_tunnel.sh start"
