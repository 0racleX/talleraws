# Punto 3 – Amazon DocumentDB con túnel SSH, TLS y Secrets Manager

Un cluster de DocumentDB (serverless y, para comparar, aprovisionado) en **`us-east-2`**, accesible desde
MongoDB Compass y desde Python a través de una EC2 bastion y un túnel SSH, con la contraseña administrada por
Secrets Manager. Todo se ejecuta con el usuario IAM `user_cli`, nunca con la cuenta raíz.

## Estructura

```
iam/user_cli_punto3_policy.json   Política IAM complementaria (DocumentDB, secreto rds!cluster-*, key pairs)
scripts/setup_iam.sh              Crea y adjunta la política (lo corre un administrador, una vez)
scripts/deploy_docdb.sh           Despliega EC2 bastion + DocumentDB (serverless | provisioned)
scripts/get_ca_bundle.sh          Descarga el certificado de CA para TLS
scripts/open_tunnel.sh            Abre/cierra el túnel SSH (start | stop | status)
scripts/destroy_docdb.sh          Elimina todo, tolera despliegues incompletos
scripts/check_leftovers.sh        Busca componentes facturables tras el destroy
scripts/calc_costos.py            Calculadora de costos
python/common.py                  Lee el secreto en ejecución y abre la conexión TLS
python/connect_check.py           Prueba de conexión
python/docdb_demo.py              Base, colección, 12 documentos, filtro, ordenación y agregación
python/compass_uri.py             Copia la URI de Compass al portapapeles (sin mostrarla)
docs/respuestas.md                Diferencias con MongoDB, conexión, autenticación
docs/costos.md                    Estimación de costos y respuestas
docs/diagrama_conexion.md         Diagrama de conexión
evidence/                         Capturas y registro (ver evidence/README.md)
results/                          Salida de docdb_demo.py
```

## 0. Requisitos

- Haber hecho el punto 2: `user_cli` con su política y el perfil `user_cli` configurado (`us-east-2`).
- AWS CLI v2 reciente (el escalado serverless de `docdb` es nuevo), `ssh`, `curl`, Python ≥ 3.9 y MongoDB Compass.
- Entorno Python: `conda activate punto2 && pip install -r python/requirements.txt`.

## 1. Permisos de `user_cli`

Un administrador adjunta la política complementaria (la del punto 2 sigue adjunta):

```bash
./scripts/setup_iam.sh
```

Documentado en `docs/respuestas.md`: DocumentDB usa el espacio de nombres `rds:` de IAM, su secreto se llama
`rds!cluster-…` (no `rds!db-…` como el de RDS) y la llave SSH exige `ec2:CreateKeyPair`/`DeleteKeyPair`.

## 2. Despliegue (variante serverless)

```bash
export AWS_PROFILE=user_cli
cd scripts
./deploy_docdb.sh serverless        # 5-15 min
./get_ca_bundle.sh
./open_tunnel.sh start
```

## 3. Conexión y consultas

```bash
cd ../python
python connect_check.py
python docdb_demo.py
python compass_uri.py               # copia la URI; en Compass: New connection → pegar → Connect
```

En Compass, la URI incluye `tls=true`, la ruta de la CA y `tlsAllowInvalidHostnames=true`. Si prefiere el
formulario: *Advanced Connection Options → TLS/SSL → seleccionar `global-bundle.pem` y marcar "Allow invalid
hostnames"*, y en *General* activar *Direct Connection*. Para capturas use `python compass_uri.py --safe`.

## 4. Eliminación

```bash
cd ../scripts
./destroy_docdb.sh
./check_leftovers.sh                # todas las secciones vacías
```

## 5. Variante aprovisionada (comparación)

Repita 2 y 4 con `./deploy_docdb.sh provisioned` (basta con llegar a "DocumentDB listo", mostrar la clase
`db.t4g.medium` y destruir). No hace falta repetir las consultas.

## Seguridad

- La contraseña de DocumentDB la genera y guarda Secrets Manager; el código la recupera en ejecución y nunca la imprime.
- Las claves de `user_cli` viven en `~/.aws/credentials`; no se guardan en Secrets Manager.
- SSH solo se acepta desde su IP (`/32`); DocumentDB solo acepta 27017 desde el security group de la EC2.
- `.gitignore` excluye `*.pem`, `docdb_state.env` y `certs/`. La llave privada se crea en `~/.ssh` y se borra en el destroy.

## Problemas conocidos

- **`retryWrites`**: el motor 5.0.0 no admite retryable writes; el código usa `retryWrites=false`. Con motor 8.0.2+ no haría falta (`ENGINE_VERSION=8.0.2 ./deploy_docdb.sh …`).
- **Puerto 27017 ocupado** (p. ej. MongoDB local): `LOCAL_PORT=27018 ./open_tunnel.sh start` y la misma variable al ejecutar Python.
- **Compass en Windows no alcanza `localhost` de WSL**: `BIND=0.0.0.0 ./open_tunnel.sh start`.
- **Su IP cambió**: el SSH deja de funcionar; ejecute destroy y despliegue de nuevo, o actualice la regla del security group.

## Respuestas y costos

- [docs/respuestas.md](docs/respuestas.md) · [docs/costos.md](docs/costos.md) · [docs/diagrama_conexion.md](docs/diagrama_conexion.md)
