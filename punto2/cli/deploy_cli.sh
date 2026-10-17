#!/usr/bin/env bash
# Despliegue con AWS CLI: S3 + red + EC2 + RDS PostgreSQL (contrasena en Secrets Manager).
# Uso:  export AWS_PROFILE=user_cli ; ./deploy_cli.sh
set -euo pipefail

export AWS_DEFAULT_REGION=us-east-2
P=lab-cli
STATE="$(dirname "$0")/cli_state.env"   # solo IDs; esta en .gitignore
TAGS='{Key=Project,Value=lab-punto2},{Key=Method,Value=cli}'
: > "$STATE"
save() { echo "$1=$2" >> "$STATE"; }

echo "Identidad: $(aws sts get-caller-identity --query Arn --output text)"

# ---- S3
BUCKET="$P-$(openssl rand -hex 4)"
aws s3api create-bucket --bucket "$BUCKET" --create-bucket-configuration LocationConstraint=us-east-2
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
save BUCKET "$BUCKET"

# ---- Red
VPC=$(aws ec2 create-vpc --cidr-block 10.40.0.0/16 \
  --tag-specifications "ResourceType=vpc,Tags=[$TAGS,{Key=Name,Value=$P-vpc}]" --query Vpc.VpcId --output text)
save VPC "$VPC"
aws ec2 modify-vpc-attribute --vpc-id "$VPC" --enable-dns-hostnames '{"Value":true}'
IGW=$(aws ec2 create-internet-gateway --query InternetGateway.InternetGatewayId --output text)
aws ec2 attach-internet-gateway --internet-gateway-id "$IGW" --vpc-id "$VPC"
save IGW "$IGW"
AZ1=$(aws ec2 describe-availability-zones --query 'AvailabilityZones[0].ZoneName' --output text)
AZ2=$(aws ec2 describe-availability-zones --query 'AvailabilityZones[1].ZoneName' --output text)
SUB_PUB=$(aws ec2 create-subnet --vpc-id "$VPC" --cidr-block 10.40.1.0/24 --availability-zone "$AZ1" --query Subnet.SubnetId --output text)
SUB_A=$(aws ec2 create-subnet --vpc-id "$VPC" --cidr-block 10.40.2.0/24 --availability-zone "$AZ1" --query Subnet.SubnetId --output text)
SUB_B=$(aws ec2 create-subnet --vpc-id "$VPC" --cidr-block 10.40.3.0/24 --availability-zone "$AZ2" --query Subnet.SubnetId --output text)
save SUB_PUB "$SUB_PUB"; save SUB_A "$SUB_A"; save SUB_B "$SUB_B"
RT=$(aws ec2 create-route-table --vpc-id "$VPC" --query RouteTable.RouteTableId --output text)
aws ec2 create-route --route-table-id "$RT" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW" >/dev/null
ASSOC=$(aws ec2 associate-route-table --route-table-id "$RT" --subnet-id "$SUB_PUB" --query AssociationId --output text)
save RT "$RT"; save ASSOC "$ASSOC"
SG_EC2=$(aws ec2 create-security-group --group-name "$P-ec2-sg" --description "EC2 sin ingreso" --vpc-id "$VPC" --query GroupId --output text)
SG_RDS=$(aws ec2 create-security-group --group-name "$P-rds-sg" --description "PostgreSQL desde EC2" --vpc-id "$VPC" --query GroupId --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG_RDS" --protocol tcp --port 5432 --source-group "$SG_EC2" >/dev/null
save SG_EC2 "$SG_EC2"; save SG_RDS "$SG_RDS"

# ---- EC2
AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query Parameter.Value --output text)
INST=$(aws ec2 run-instances --image-id "$AMI" --instance-type t3.micro --count 1 \
  --network-interfaces "DeviceIndex=0,SubnetId=$SUB_PUB,Groups=$SG_EC2,AssociatePublicIpAddress=false" \
  --metadata-options HttpTokens=required \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=8,VolumeType=gp3,DeleteOnTermination=true,Encrypted=true}' \
  --tag-specifications "ResourceType=instance,Tags=[$TAGS,{Key=Name,Value=$P-ec2}]" \
  --query 'Instances[0].InstanceId' --output text)
save INST "$INST"
aws ec2 wait instance-running --instance-ids "$INST"
echo "EC2 en ejecucion: $INST"

# ---- RDS (contrasena administrada por Secrets Manager: --manage-master-user-password)
aws rds create-db-subnet-group --db-subnet-group-name "$P-dbsubnets" --db-subnet-group-description lab \
  --subnet-ids "$SUB_A" "$SUB_B" >/dev/null
aws rds create-db-instance --db-instance-identifier "$P-pg" \
  --engine postgres --engine-version 16 --db-instance-class db.t4g.micro \
  --allocated-storage 20 --storage-type gp3 --storage-encrypted \
  --db-name labdb --master-username labadmin --manage-master-user-password \
  --db-subnet-group-name "$P-dbsubnets" --vpc-security-group-ids "$SG_RDS" \
  --no-publicly-accessible --no-multi-az --backup-retention-period 0 --no-deletion-protection \
  --tags Key=Project,Value=lab-punto2 Key=Method,Value=cli >/dev/null
save DB "$P-pg"
echo "Esperando RDS (5-10 min)..."
aws rds wait db-instance-available --db-instance-identifier "$P-pg"
SECRET_ARN=$(aws rds describe-db-instances --db-instance-identifier "$P-pg" \
  --query 'DBInstances[0].MasterUserSecret.SecretArn' --output text)
save SECRET_ARN "$SECRET_ARN"
echo "RDS listo. Secreto: $SECRET_ARN"

# Lectura en ejecucion SIN imprimir la contrasena (solo el usuario)
aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --query SecretString --output text \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print("Secreto leido OK, usuario:", d["username"])'
