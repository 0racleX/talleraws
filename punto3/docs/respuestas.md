# Respuestas – Punto 3: Amazon DocumentDB

## 1. DocumentDB frente a MongoDB: diferencias que afectan a una aplicación existente

DocumentDB **no es MongoDB**: es un servicio de AWS con su propio motor y almacenamiento que implementa la API
de MongoDB (emula las versiones 3.6, 4.0, 5.0 y 8.0). Por eso una aplicación que funciona contra MongoDB puede
fallar o comportarse distinto. Diferencias comprobadas en la [documentación oficial](https://docs.aws.amazon.com/documentdb/latest/developerguide/functional-differences.html):

| # | Diferencia | Efecto en una aplicación existente |
|---|---|---|
| 1 | **Retryable writes** solo desde el motor 8.0.2 ([anuncio](https://aws.amazon.com/about-aws/whats-new/2026/09/amazon-documentdb-retryable-writes/)). En versiones anteriores falla con el error 301 `Retryable writes are not supported`. | Los drivers modernos activan `retryWrites=true` por defecto: hay que desactivarlo (`retryWrites=false`, lo que hace `python/common.py`) o usar 8.0.2+. Ni siquiera con 8.0.2 funciona para `updateMany`/`deleteMany`. |
| 2 | **Índices:** solo una construcción de índice por colección a la vez; la opción `background` se ignora; un índice `sparse` solo se usa si la consulta incluye `$exists`; los índices `$regex` exigen `hint()` con el nombre del campo. | Los scripts de migración que crean varios índices en paralelo fallan, y consultas que en MongoDB usan el índice pueden hacer un recorrido completo. |
| 3 | **Operadores y órdenes:** `$natural: -1` (lectura inversa) devuelve error; `$elemMatch` dentro de `$all` no se admite; `$lookup` solo admite igualdad y subconsultas no correlacionadas (las correlacionadas, desde 8.0.2); no existen las bases `admin`/`local` ni colecciones `system.*`. | Consultas, agregaciones y herramientas de administración que usan esas funciones hay que reescribirlas. Conviene revisar la [lista de API soportadas](https://docs.aws.amazon.com/documentdb/latest/devguide/mongo-apis.html) antes de migrar. |
| 4 | **Orden de resultados:** no hay orden implícito, y `$sort` solo se conserva si es la última etapa del pipeline. | Código que dependía del orden de inserción debe ordenar explícitamente. |
| 5 | **Red y seguridad:** solo existe dentro de una VPC (sin endpoint público), TLS activado por defecto y un único endpoint de cluster con réplicas de lectura (`readPreference=secondaryPreferred`). | Se necesita un túnel o un host dentro de la VPC (es lo que se hace en esta práctica), certificado de CA y cambios de cadena de conexión. |
| 6 | **Herramientas:** `mongodump`/`mongorestore` omiten la base `admin` y solo se recomiendan hasta la versión 100.11.0 de MongoDB Database Tools; los planes de `explain()` difieren. | Copias de seguridad y diagnóstico de rendimiento cambian de procedimiento. |

Las diferencias 1, 2 y 5 son las que más afectan a una aplicación típica (conexión, escrituras y migración).

## 2. ¿Aprovisionado o Serverless?

Para esta práctica, **Serverless al mínimo de 0,5 DCU** (USD 0,041/h frente a USD 0,076/h de `db.t4g.medium`;
~46 % menos). El detalle, el punto de equilibrio (~0,92 DCU) y las advertencias están en [costos.md](costos.md).

## 3. Cómo se conecta Compass a un DocumentDB que no tiene acceso público

DocumentDB solo es alcanzable desde su VPC. Se resuelve con una EC2 **bastion** y un **túnel SSH**:

1. **Security groups:** `lab-docdb-ec2-sg` permite SSH (22) **solo desde su IP pública** (`/32`);
   `lab-docdb-db-sg` permite 27017 **solo desde el security group de la EC2**, no desde Internet.
2. **EC2 `t4g.nano`** en una subred pública, con una llave SSH creada para la práctica (la privada queda en
   `~/.ssh` con permisos 400).
3. **Túnel:** `ssh -L 27017:<endpoint-docdb>:27017 ec2-user@<ip-ec2>`; el puerto local 27017 pasa a ser la puerta de entrada a DocumentDB.
4. **TLS:** DocumentDB exige TLS. Se descarga `global-bundle.pem` (CA pública de Amazon) y el cliente valida con él el certificado del servidor.
5. **Nombre de host:** el cliente se conecta a `localhost`, pero el certificado es del endpoint del cluster. Por eso se usa
   `tlsAllowInvalidHostnames=true` **manteniendo la validación de la cadena de certificados**. Alternativa más estricta:
   mapear el endpoint a `127.0.0.1` en el archivo `hosts` y conectar con su nombre real.
6. **Credenciales:** la contraseña la genera DocumentDB y vive en Secrets Manager. Python la lee con
   `get_secret_value`; para Compass, `compass_uri.py` copia la URI al portapapeles sin mostrarla.

El diagrama está en [diagrama_conexion.md](diagrama_conexion.md).

## 4. Autenticación y secretos

- `user_cli` autentica **boto3 y AWS CLI** con su clave de acceso local (perfil `user_cli`); las peticiones se
  firman con SigV4. No se guardan en Secrets Manager: para leer un secreto ya hay que estar autenticado.
- La contraseña de la base de datos **sí** va en Secrets Manager (`--manage-master-user-password`): DocumentDB la
  crea, la guarda en un secreto `rds!cluster-…` y la elimina con el cluster. El código nunca la contiene.
- SSH usa otra credencial distinta: la llave privada de la EC2, solo local.

## 5. Costos

Ver [costos.md](costos.md).
