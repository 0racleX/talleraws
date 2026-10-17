import json, boto3

def obtener_secreto(nombre, region="us-east-2"):
    cliente = boto3.client("secretsmanager", region_name=region)
    respuesta = cliente.get_secret_value(SecretId=nombre)
    return json.loads(respuesta["SecretString"])

if __name__ == "__main__":
    s = obtener_secreto("eia/taller/credenciales-prueba")
    print("Usuario:", s["username"])
    print("Clave recuperada, longitud:", len(s["password"]))  # no imprimir la clave