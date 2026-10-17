#!/usr/bin/env python3
"""Prueba de conexion: secreto -> tunel SSH -> TLS -> DocumentDB. No imprime la contrasena."""
from common import STATE_FILE, get_client, get_credentials, load_state


def main():
    state = load_state()
    user, _ = get_credentials(state["SECRET_ARN"])
    print(f"Secreto leido de Secrets Manager (usuario: {user}; contrasena no se muestra)")

    client = get_client()
    print("ping:", client.admin.command("ping"))
    info = client.server_info()
    print("version del servidor (emulacion MongoDB):", info.get("version"))
    print("TLS activo y certificado validado con global-bundle.pem")
    print("bases de datos visibles:", client.list_database_names())


if __name__ == "__main__":
    main()
