#!/usr/bin/env bash
# Descarga el paquete de certificados de CA de Amazon RDS/DocumentDB (publico, no es un secreto).
# Con el se valida el certificado TLS que presenta DocumentDB.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)/certs"
mkdir -p "$DIR"
curl -fsSL -o "$DIR/global-bundle.pem" https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
echo "Certificados en el paquete: $(grep -c 'BEGIN CERTIFICATE' "$DIR/global-bundle.pem")"
echo "Guardado en: $DIR/global-bundle.pem"
