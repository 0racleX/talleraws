import os, csv, time
from pathlib import Path
import boto3

REGION     = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
BUCKET     = os.environ["BUCKET"]
WORKGROUP  = os.environ["WORKGROUP"]
DATABASE   = os.environ["DATABASE"]
SECRET_ARN = os.environ["SECRET_ARN"]   # ARN del secreto (no es la contraseña)
ROLE_ARN   = os.environ["ROLE_ARN"]     # rol IAM que Redshift usa para leer S3

s3  = boto3.client("s3", region_name=REGION)
rsd = boto3.client("redshift-data", region_name=REGION)


# ---------- Utilidades de la Data API ----------
def ejecutar(sql):
    """Envía una instrucción SQL (asíncrona) autenticando con el secreto."""
    r = rsd.execute_statement(WorkgroupName=WORKGROUP, Database=DATABASE,
                              SecretArn=SECRET_ARN, Sql=sql)
    return r["Id"]


def esperar(stmt_id, timeout=900):
    """Consulta el estado hasta FINISHED / FAILED / ABORTED."""
    inicio = time.time()
    while True:
        d = rsd.describe_statement(Id=stmt_id)
        if d["Status"] in ("FINISHED", "FAILED", "ABORTED"):
            break
        if time.time() - inicio > timeout:
            raise TimeoutError(f"La instrucción {stmt_id} excedió {timeout}s")
        time.sleep(1.5)
    if d["Status"] != "FINISHED":
        raise RuntimeError(f"{d['Status']}: {d.get('Error')}\nSQL: {d['QueryString'][:300]}")
    return d


def valor(campo):
    if campo.get("isNull"):
        return None
    return next(iter(campo.values()))


def resultados(stmt_id):
    """Recupera todas las páginas del resultado de un SELECT."""
    columnas, filas, token = None, [], None
    while True:
        kw = {"Id": stmt_id}
        if token:
            kw["NextToken"] = token
        r = rsd.get_statement_result(**kw)
        if columnas is None:
            columnas = [c["name"] for c in r["ColumnMetadata"]]
        filas += [[valor(c) for c in reg] for reg in r["Records"]]
        token = r.get("NextToken")
        if not token:
            break
    return columnas, filas


def correr(titulo, sql, mostrar=False):
    sid = ejecutar(sql)
    d = esperar(sid)
    ms = d.get("Duration", 0) / 1e6
    print(f"[OK] {titulo:<38} id={sid}  filas={d.get('ResultRows')}  {ms:.0f} ms")
    if mostrar:
        return resultados(sid)


def imprimir(titulo, columnas, filas):
    print(f"\n=== {titulo} ===")
    anchos = [max(len(str(c)), *(len(str(f[i])) for f in filas)) if filas else len(str(c))
              for i, c in enumerate(columnas)]
    print("  " + " | ".join(str(c).ljust(a) for c, a in zip(columnas, anchos)))
    print("  " + "-+-".join("-" * a for a in anchos))
    for f in filas:
        print("  " + " | ".join(str(v).ljust(a) for v, a in zip(f, anchos)))
    print(f"  ({len(filas)} filas)")


def guardar_csv(nombre, columnas, filas):
    Path("resultados").mkdir(exist_ok=True)
    with open(f"resultados/{nombre}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(columnas)
        w.writerows(filas)


# ---------- 1. Subir archivos a S3 ----------
print("\n--- 1. Subida a S3 ---")
for archivo in ("clientes.csv", "pedidos.csv"):
    s3.upload_file(f"datos/{archivo}", BUCKET, f"datos/{archivo}")
    print(f"[OK] s3://{BUCKET}/datos/{archivo}")

# ---------- 2. Crear tablas ----------
print("\n--- 2. Creación de tablas ---")
correr("DROP pedidos",  "DROP TABLE IF EXISTS pedidos")
correr("DROP clientes", "DROP TABLE IF EXISTS clientes")
correr("CREATE clientes", """
CREATE TABLE clientes (
    cliente_id     INTEGER NOT NULL PRIMARY KEY,
    nombre         VARCHAR(100),
    ciudad         VARCHAR(60),
    pais           VARCHAR(40),
    fecha_registro DATE
)""")
correr("CREATE pedidos", """
CREATE TABLE pedidos (
    pedido_id       INTEGER NOT NULL PRIMARY KEY,
    cliente_id      INTEGER NOT NULL REFERENCES clientes(cliente_id),
    fecha_pedido    DATE,
    producto        VARCHAR(60),
    categoria       VARCHAR(40),
    cantidad        INTEGER,
    precio_unitario DECIMAL(10,2)
)""")
correr("GRANT lectura (Query Editor)", "GRANT SELECT ON clientes, pedidos TO PUBLIC")

# ---------- 3. Carga con COPY ----------
print("\n--- 3. Carga con COPY ---")
for tabla in ("clientes", "pedidos"):
    correr(f"COPY {tabla}", f"""
        COPY {tabla}
        FROM 's3://{BUCKET}/datos/{tabla}.csv'
        IAM_ROLE '{ROLE_ARN}'
        FORMAT AS CSV IGNOREHEADER 1
        REGION '{REGION}'""")

for tabla in ("clientes", "pedidos"):
    c, f = correr(f"COUNT {tabla}", f"SELECT COUNT(*) AS filas FROM {tabla}", mostrar=True)
    print(f"     {tabla}: {f[0][0]} filas cargadas")

# ---------- 4. Consultas ----------
print("\n--- 4. Consultas ---")
CONSULTAS = {
 "Q1_filtro": ("Q1 (FILTRO): pedidos grandes de Electronica en el 2do semestre 2025", """
    SELECT pedido_id, fecha_pedido, producto, cantidad, precio_unitario,
           cantidad * precio_unitario AS total
    FROM pedidos
    WHERE categoria = 'Electronica'
      AND fecha_pedido >= '2025-07-01'
      AND cantidad * precio_unitario > 1000
    ORDER BY total DESC
    LIMIT 10"""),
 "Q2_union": ("Q2 (UNION): ultimos pedidos de clientes colombianos", """
    SELECT c.nombre, c.ciudad, p.producto, p.fecha_pedido,
           p.cantidad * p.precio_unitario AS total
    FROM pedidos p
    JOIN clientes c ON c.cliente_id = p.cliente_id
    WHERE c.pais = 'Colombia'
    ORDER BY p.fecha_pedido DESC
    LIMIT 10"""),
 "Q3_agregacion": ("Q3 (UNION + AGREGACION): ventas por pais y ciudad", """
    SELECT c.pais, c.ciudad,
           COUNT(DISTINCT c.cliente_id)                 AS clientes_con_compras,
           COUNT(*)                                     AS pedidos,
           SUM(p.cantidad * p.precio_unitario)          AS ventas_totales,
           ROUND(AVG(p.cantidad * p.precio_unitario),2) AS ticket_promedio
    FROM pedidos p
    JOIN clientes c ON c.cliente_id = p.cliente_id
    GROUP BY c.pais, c.ciudad
    ORDER BY ventas_totales DESC"""),
 "Q4_top_clientes": ("Q4 (UNION + AGREGACION + HAVING): top 5 clientes por gasto", """
    SELECT c.cliente_id, c.nombre, c.ciudad,
           COUNT(*)                            AS pedidos,
           SUM(p.cantidad * p.precio_unitario) AS gasto_total
    FROM pedidos p
    JOIN clientes c ON c.cliente_id = p.cliente_id
    GROUP BY c.cliente_id, c.nombre, c.ciudad
    HAVING COUNT(*) >= 5
    ORDER BY gasto_total DESC
    LIMIT 5"""),
}
for clave, (titulo, sql) in CONSULTAS.items():
    cols, filas = correr(clave, sql, mostrar=True)
    imprimir(titulo, cols, filas)
    guardar_csv(clave, cols, filas)

print("\nProceso terminado.")
