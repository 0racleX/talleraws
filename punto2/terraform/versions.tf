terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# Las credenciales NO se escriben aqui. El provider las toma de la cadena
# estandar de AWS: variables de entorno o el perfil "user_cli" de ~/.aws.
#   export AWS_PROFILE=user_cli
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project = "lab-punto2"
      Method  = "terraform"
    }
  }
}
