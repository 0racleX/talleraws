output "bucket_name" {
  value = aws_s3_bucket.this.bucket
}

output "ec2_instance_id" {
  value = aws_instance.this.id
}

output "rds_endpoint" {
  value = aws_db_instance.this.endpoint
}

# Solo el ARN del secreto (un identificador), NO su contenido.
output "rds_master_secret_arn" {
  value = aws_db_instance.this.master_user_secret[0].secret_arn
}
