#!/usr/bin/env bash
# Tunel SSH:  localhost:PUERTO  ->  EC2 bastion  ->  endpoint de DocumentDB:27017
# Uso: ./open_tunnel.sh start | stop | status      (LOCAL_PORT=27018 ./open_tunnel.sh start si 27017 esta ocupado)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/docdb_state.env"
LOCAL_PORT="${LOCAL_PORT:-27017}"
BIND="${BIND:-127.0.0.1}"
SOCK=/tmp/docdb-tunnel.sock
SSH_OPTS=(-i "$KEY_FILE" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/tmp/docdb_known_hosts
          -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -S "$SOCK")

case "${1:-start}" in
  start)
    if ssh "${SSH_OPTS[@]}" -O check "ec2-user@$EC2_IP" 2>/dev/null; then echo "El tunel ya esta abierto."; exit 0; fi
    for i in 1 2 3 4 5 6 7 8; do
      if ssh "${SSH_OPTS[@]}" -M -f -N -L "$BIND:$LOCAL_PORT:$ENDPOINT:27017" "ec2-user@$EC2_IP"; then
        echo "Tunel abierto: $BIND:$LOCAL_PORT -> $ENDPOINT:27017 (via $EC2_IP)"; exit 0
      fi
      echo "SSH aun no responde (intento $i/8), reintentando en 10 s..."; sleep 10
    done
    echo "No se pudo abrir el tunel." >&2; exit 1 ;;
  stop)
    ssh "${SSH_OPTS[@]}" -O exit "ec2-user@$EC2_IP" 2>/dev/null && echo "Tunel cerrado." || echo "No habia tunel abierto." ;;
  status)
    ssh "${SSH_OPTS[@]}" -O check "ec2-user@$EC2_IP" ;;
  *) echo "Uso: $0 start|stop|status" >&2; exit 1 ;;
esac
