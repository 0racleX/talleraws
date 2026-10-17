#!/bin/bash
set -e
export AWS_DEFAULT_REGION=us-east-1

echo "1) VPC"
VPC_ID=$(aws ec2 create-vpc --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=neptune-lab-vpc}]' \
  --query 'Vpc.VpcId' --output text)
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames
echo "   $VPC_ID"

echo "2) Internet Gateway"
IGW_ID=$(aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=neptune-lab-igw}]' \
  --query 'InternetGateway.InternetGatewayId' --output text)
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID
echo "   $IGW_ID"

echo "3) Subnets en dos zonas"
AZ1=$(aws ec2 describe-availability-zones --query 'AvailabilityZones[0].ZoneName' --output text)
AZ2=$(aws ec2 describe-availability-zones --query 'AvailabilityZones[1].ZoneName' --output text)
SUBNET1=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 --availability-zone $AZ1 \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=neptune-lab-subnet-1}]' \
  --query 'Subnet.SubnetId' --output text)
SUBNET2=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.2.0/24 --availability-zone $AZ2 \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=neptune-lab-subnet-2}]' \
  --query 'Subnet.SubnetId' --output text)
echo "   $SUBNET1 ($AZ1)  $SUBNET2 ($AZ2)"

echo "4) Tabla de rutas"
RT_ID=$(aws ec2 create-route-table --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=neptune-lab-rt}]' \
  --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $RT_ID --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID >/dev/null
ASSOC1=$(aws ec2 associate-route-table --route-table-id $RT_ID --subnet-id $SUBNET1 --query AssociationId --output text)
ASSOC2=$(aws ec2 associate-route-table --route-table-id $RT_ID --subnet-id $SUBNET2 --query AssociationId --output text)
echo "   $RT_ID"

echo "5) Security group (solo mi IP)"
MY_IP=$(curl -s https://checkip.amazonaws.com)
SG_ID=$(aws ec2 create-security-group --group-name neptune-lab-sg \
  --description "Neptune 8182 desde mi IP" --vpc-id $VPC_ID --query GroupId --output text)
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 8182 --cidr ${MY_IP}/32 >/dev/null
echo "   $SG_ID  (IP autorizada: $MY_IP)"

echo "6) Guardando IDs en ids.env"
cat > ids.env <<EOT
export AWS_DEFAULT_REGION=us-east-1
export VPC_ID=$VPC_ID
export IGW_ID=$IGW_ID
export SUBNET1=$SUBNET1
export SUBNET2=$SUBNET2
export RT_ID=$RT_ID
export ASSOC1=$ASSOC1
export ASSOC2=$ASSOC2
export SG_ID=$SG_ID
export MY_IP=$MY_IP
EOT
echo "LISTO"
