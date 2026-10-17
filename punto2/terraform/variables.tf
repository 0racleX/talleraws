variable "region" {
  description = "Unica region usada en todo el ejercicio"
  type        = string
  default     = "us-east-2"
}

variable "prefix" {
  description = "Prefijo de nombres. El bucket debe empezar por lab- (lo exige la politica IAM)"
  type        = string
  default     = "lab-tf"
}

variable "ec2_instance_type" {
  description = "Tipo de instancia EC2 de menor costo"
  type        = string
  default     = "t3.micro"
}

variable "db_instance_class" {
  description = "Clase de instancia RDS de menor costo (Graviton)"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "GB de almacenamiento RDS (minimo 20 en gp3 para PostgreSQL)"
  type        = number
  default     = 20
}

variable "db_name" {
  type    = string
  default = "labdb"
}

variable "db_username" {
  description = "Usuario administrador. La CONTRASENA no existe como variable: la genera RDS."
  type        = string
  default     = "labadmin"
}
