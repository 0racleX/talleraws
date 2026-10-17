data "aws_availability_zones" "available" {
  state = "available"
}

# AMI Amazon Linux 2023 via parametro publico de SSM (evita ec2:DescribeImages con filtros amplios)
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "random_id" "suffix" {
  byte_length = 4
}

############################
# 1) S3
############################
resource "aws_s3_bucket" "this" {
  bucket        = "${var.prefix}-${random_id.suffix.hex}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

############################
# Red (VPC propia, sin NAT Gateway: la NAT cuesta ~USD 0.045/h)
############################
resource "aws_vpc" "this" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.prefix}-vpc" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.prefix}-igw" }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = "10.20.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.prefix}-public-a" }
}

# RDS exige un subnet group con subredes en al menos 2 AZ
resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = "10.20.2.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
  tags              = { Name = "${var.prefix}-private-a" }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = "10.20.3.0/24"
  availability_zone = data.aws_availability_zones.available.names[1]
  tags              = { Name = "${var.prefix}-private-b" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.prefix}-rt-public" }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "ec2" {
  name        = "${var.prefix}-ec2-sg"
  description = "EC2 sin ingreso entrante"
  vpc_id      = aws_vpc.this.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.prefix}-rds-sg"
  description = "PostgreSQL solo desde el SG de la EC2"
  vpc_id      = aws_vpc.this.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
  }
}

############################
# 2) EC2
############################
resource "aws_instance" "this" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.ec2_instance_type
  subnet_id                   = aws_subnet.public_a.id
  vpc_security_group_ids      = [aws_security_group.ec2.id]
  associate_public_ip_address = false # una IPv4 publica cuesta ~USD 0.005/h; no se necesita
  monitoring                  = false

  metadata_options {
    http_tokens = "required" # IMDSv2
  }

  root_block_device {
    volume_size           = 8
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
  }

  tags = { Name = "${var.prefix}-ec2" }
}

############################
# 3) RDS PostgreSQL con contrasena administrada en Secrets Manager
############################
resource "aws_db_subnet_group" "this" {
  name       = "${var.prefix}-dbsubnets"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}

resource "aws_db_instance" "this" {
  identifier = "${var.prefix}-pg"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username

  # La contrasena la genera RDS y vive en Secrets Manager (secreto rds!db-<uuid>).
  # No hay atributo "password": nunca pasa por el codigo ni por el estado de Terraform.
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period  = 0 # sin backups automaticos => sin snapshots que cobrar
  skip_final_snapshot      = true
  delete_automated_backups = true
  deletion_protection      = false
  apply_immediately        = true

  performance_insights_enabled = false
  monitoring_interval          = 0
}
