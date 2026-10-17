"""Utilidades comunes: lee el secreto de Secrets Manager EN EJECUCION y abre la conexion TLS por el tunel.

Autenticacion en AWS: cadena estandar de boto3 (export AWS_PROFILE=user_cli). Ninguna contrasena
vive en el codigo, en variables de entorno ni en archivos: se pide a Secrets Manager cada vez.
"""
import json
import os
from pathlib import Path

import boto3
from pymongo import MongoClient

REGION = "us-east-2"
ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "scripts" / "docdb_state.env"          # solo IDs, sin secretos
CA_FILE = ROOT / "certs" / "global-bundle.pem"             # CA publica de Amazon RDS/DocumentDB
LOCAL_PORT = int(os.environ.get("LOCAL_PORT", "27017"))     # extremo local del tunel SSH


def load_state() -> dict:
    state = {}
    for line in STATE_FILE.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            state[key.strip()] = value.strip()
    return state


def get_credentials(secret_arn: str) -> tuple[str, str]:
    """Recupera usuario y contrasena del secreto administrado por DocumentDB."""
    sm = boto3.client("secretsmanager", region_name=REGION)
    secret = json.loads(sm.get_secret_value(SecretId=secret_arn)["SecretString"])
    return secret["username"], secret["password"]


def get_client() -> MongoClient:
    state = load_state()
    user, password = get_credentials(state["SECRET_ARN"])
    if not CA_FILE.exists():
        raise SystemExit(f"Falta {CA_FILE}. Ejecute scripts/get_ca_bundle.sh")
    return MongoClient(
        host="localhost",
        port=LOCAL_PORT,
        username=user,
        password=password,
        authSource="admin",
        authMechanism=os.environ.get("DOCDB_AUTH_MECH", "SCRAM-SHA-1"),
        tls=True,
        tlsCAFile=str(CA_FILE),             # valida la cadena del certificado contra la CA de Amazon
        tlsAllowInvalidHostnames=True,      # el cliente ve "localhost" (tunel), no el nombre del cluster
        directConnection=True,              # una sola ruta: el tunel
        retryWrites=False,                  # DocumentDB < 8.0.2 no soporta retryable writes
        serverSelectionTimeoutMS=10000,
    )
