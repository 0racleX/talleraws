#!/usr/bin/env python3
"""Construye la cadena de conexion de MongoDB Compass con la contrasena de Secrets Manager.

Por defecto copia la URI al PORTAPAPELES (no la muestra, para que no salga en capturas ni en el historial).
    python compass_uri.py             # copia la URI completa; pegue en Compass y despues limpie el portapapeles
    python compass_uri.py --safe      # imprime la URI con <PASSWORD> (apta para capturas y documentacion)
"""
import argparse
import shutil
import subprocess
import sys
from urllib.parse import quote_plus

from common import CA_FILE, LOCAL_PORT, get_credentials, load_state


def ca_path_for_compass() -> str:
    """Compass corre en Windows: en WSL se traduce la ruta del .pem con wslpath."""
    if shutil.which("wslpath"):
        return subprocess.run(["wslpath", "-w", str(CA_FILE)], capture_output=True, text=True, check=True).stdout.strip()
    return str(CA_FILE)


def build_uri(user: str, password: str) -> str:
    return (
        f"mongodb://{quote_plus(user)}:{quote_plus(password)}@localhost:{LOCAL_PORT}/"
        f"?authSource=admin&authMechanism=SCRAM-SHA-1&directConnection=true&retryWrites=false"
        f"&tls=true&tlsCAFile={quote_plus(ca_path_for_compass())}&tlsAllowInvalidHostnames=true"
    )


def copy_to_clipboard(text: str) -> bool:
    for cmd in (["clip.exe"], ["pbcopy"], ["xclip", "-selection", "clipboard"]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, input=text.encode(), check=True)
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--safe", action="store_true", help="imprime la URI con <PASSWORD>")
    args = parser.parse_args()

    user, password = get_credentials(load_state()["SECRET_ARN"])
    if args.safe:
        print(build_uri(user, "<PASSWORD>").replace("%3CPASSWORD%3E", "<PASSWORD>"))
        return
    if copy_to_clipboard(build_uri(user, password)):
        print("URI copiada al portapapeles (contiene la contrasena: no la pegue en capturas).")
    else:
        sys.exit("No hay utilidad de portapapeles (clip.exe/pbcopy/xclip). Use --safe y escriba la contrasena a mano en Compass.")


if __name__ == "__main__":
    main()
