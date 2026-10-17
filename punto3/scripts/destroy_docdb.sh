#!/usr/bin/env bash
# Elimina todo lo creado por deploy_docdb.sh. Tolera despliegues incompletos y se puede repetir.
# Borrar DocumentDB tarda 5-15 min: NO pulse Ctrl+C; el script muestra el estado cada 30 s.
# Uso: export AWS_PROFILE=user_cli ; ./destroy_docdb.sh
set -uo pipefail
export AWS_DEFAULT_REGION=us-east-2
export AWS_PAGER=""
HERE="$(cd "$(dirname "$0")" && pwd)"
STATE="$HERE/docdb_state.env"
[ -e "$STATE" ] || { echo "No hay $STATE: nada que eliminar (revise con ./check_leftovers.sh)."; exit 0; }
# shellcheck disable=SC1090
source "$STATE"

# Ctrl+C detiene TODO el script (antes solo cortaba la espera y seguia como si hubiera terminado)
trap 'echo; echo "Interrumpido: los recursos pueden seguir existiendo y cobrando. Vuelva a ejecutar ./destroy_docdb.sh"; exit 130' INT

# wait_gone <etiqueta> <comando describe que devuelve el estado>; termina cuando el recurso ya no existe
wait_gone() {
  local label="$1"; shift
  local st
  for _ in $(seq 1 120); do
    st=$("$@" 2>/dev/null) || { echo "  $label: eliminado"; return 0; }
    echo "  $label: $st ... ($(date +%H:%M:%S))"
    sleep 30
  done
  echo "  $label: sigue existiendo tras 60 min; revise la consola" >&2
  return 1
}

echo "== Tunel"
"$HERE/open_tunnel.sh" stop 2>/dev/null || true

echo "== DocumentDB (5-15 min, no interrumpir)"
if [ -n "${INSTANCE:-}" ] && aws docdb describe-db-instances --db-instance-identifier "$INSTANCE" >/dev/null 2>&1; then
  aws docdb delete-db-instance --db-instance-identifier "$INSTANCE" >/dev/null 2>&1 || true
  wait_gone "instancia $INSTANCE" aws docdb describe-db-instances --db-instance-identifier "$INSTANCE" \
    --query 'DBInstances[0].DBInstanceStatus' --output text
fi
if [ -n "${CLUSTER:-}" ] && aws docdb describe-db-clusters --db-cluster-identifier "$CLUSTER" >/dev/null 2>&1; then
  aws docdb delete-db-cluster --db-cluster-identifier "$CLUSTER" --skip-final-snapshot >/dev/null 2>&1 || true
  wait_gone "cluster $CLUSTER" aws docdb describe-db-clusters --db-cluster-identifier "$CLUSTER" \
    --query 'DBClusters[0].Status' --output text
fi
[ -n "${SUBNET_GROUP:-}" ] && aws docdb delete-db-subnet-group --db-subnet-group-name "$SUBNET_GROUP" 2>/dev/null && echo "subnet group eliminado"

echo "== EC2"
if [ -n "${INST:-}" ]; then
  aws ec2 terminate-instances --instance-ids "$INST" >/dev/null
  aws ec2 wait instance-terminated --instance-ids "$INST" && echo "bastion terminado"
fi
if [ -n "${KEY_NAME:-}" ]; then
  aws ec2 delete-key-pair --key-name "$KEY_NAME" && echo "key pair eliminado"
fi
[ -n "${KEY_FILE:-}" ] && rm -f "$KEY_FILE" && echo "llave privada local borrada"

echo "== Grupos de seguridad (reintenta mientras AWS libera las interfaces de red)"
for sg in "${SG_DB:-}" "${SG_EC2:-}"; do
  [ -n "$sg" ] || continue
  for _ in $(seq 1 12); do
    aws ec2 delete-security-group --group-id "$sg" 2>/dev/null && { echo "sg $sg eliminado"; break; }
    sleep 10
  done
done

rm -f "$STATE" /tmp/docdb_known_hosts
echo "Listo. Ejecute ./check_leftovers.sh para verificar."