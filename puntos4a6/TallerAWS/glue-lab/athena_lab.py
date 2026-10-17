import os, sys, time, csv
from pathlib import Path
import boto3

REGION    = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
DB        = os.environ["DB"]
WORKGROUP = os.environ["WORKGROUP"]
BUCKET    = os.environ["BUCKET"]
athena = boto3.client("athena", region_name=REGION)


def correr(sql, titulo):
    qid = athena.start_query_execution(QueryString=sql, QueryExecutionContext={"Database": DB},
                                       WorkGroup=WORKGROUP)["QueryExecutionId"]
    while True:
        q = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        estado = q["Status"]["State"]
        if estado in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if estado != "SUCCEEDED":
        raise RuntimeError(f"{titulo}: {estado} - {q['Status'].get('StateChangeReason')}")
    st = q["Statistics"]
    print(f"[OK] {titulo:<42} id={qid}  escaneado={st.get('DataScannedInBytes', 0)} bytes  "
          f"{st.get('EngineExecutionTimeInMillis', 0)} ms")
    if q.get("StatementType") == "DDL":
        return None, None
    filas = []
    for pag in athena.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        for fila in pag["ResultSet"]["Rows"]:
            filas.append([c.get("VarCharValue") for c in fila["Data"]])
    return filas[0], filas[1:]


def mostrar(titulo, cols, filas, archivo):
    print(f"\n=== {titulo} ===")
    anchos = [max(len(str(c)), *(len(str(f[i])) for f in filas)) if filas else len(str(c))
              for i, c in enumerate(cols)]
    print("  " + " | ".join(str(c).ljust(a) for c, a in zip(cols, anchos)))
    print("  " + "-+-".join("-" * a for a in anchos))
    for f in filas:
        print("  " + " | ".join(str(v).ljust(a) for v, a in zip(f, anchos)))
    print(f"  ({len(filas)} filas)\n")
    Path("resultados").mkdir(exist_ok=True)
    with open(f"resultados/{archivo}.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(cols); w.writerows(filas)


CONSULTAS = [
 ("Q1 FILTRO: ventas de Electronica con 2+ unidades", "q1_filtro", """
    SELECT venta_id, fecha_venta, ciudad, producto, cantidad, precio_unitario,
           cantidad * precio_unitario AS total
    FROM ventas
    WHERE categoria = 'Electronica' AND cantidad >= 2
    ORDER BY total DESC LIMIT 10"""),
 ("Q2 AGRUPACION: ingresos por ciudad", "q2_agrupacion", """
    SELECT ciudad, COUNT(*) AS ventas, SUM(cantidad) AS unidades,
           ROUND(SUM(cantidad * precio_unitario), 2) AS ingresos,
           ROUND(AVG(cantidad * precio_unitario), 2) AS ticket_promedio
    FROM ventas GROUP BY ciudad ORDER BY ingresos DESC"""),
 ("Q3 AGRUPACION POR PARTICION: ventas por mes", "q3_por_mes", """
    SELECT mes, COUNT(*) AS ventas, ROUND(SUM(cantidad * precio_unitario), 2) AS ingresos
    FROM ventas GROUP BY mes ORDER BY mes"""),
 ("Q4 VERIFICACION: codigos postales conservan el cero", "q4_postal", """
    SELECT DISTINCT ciudad, codigo_postal FROM ventas ORDER BY ciudad"""),
 ("Q5a CON filtro de particion (mes = 2026-01)", "q5a_con_particion",
    "SELECT COUNT(*) AS filas FROM ventas WHERE mes = '2026-01'"),
 ("Q5b SIN filtro de particion", "q5b_sin_particion",
    "SELECT COUNT(*) AS filas FROM ventas"),
]

MANUAL = [
 ("DDL: crear tabla manual ventas_manual", None, f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS ventas_manual (
        venta_id bigint, fecha_venta date, ciudad string, codigo_postal string,
        producto string, categoria string, cantidad int,
        precio_unitario decimal(10,2), cliente_vip boolean)
    PARTITIONED BY (mes string)
    ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
    STORED AS TEXTFILE
    LOCATION 's3://{BUCKET}/ventas/'
    TBLPROPERTIES ('skip.header.line.count'='1')"""),
 ("DDL: registrar particiones (MSCK REPAIR)", None, "MSCK REPAIR TABLE ventas_manual"),
 ("Comparacion: conteo por tabla", "m1_comparacion", """
    SELECT 'ventas (crawler)' AS tabla, COUNT(*) AS filas FROM ventas
    UNION ALL
    SELECT 'ventas_manual', COUNT(*) FROM ventas_manual"""),
 ("Manual: ventas por mes", "m2_manual_por_mes", """
    SELECT mes, COUNT(*) AS ventas FROM ventas_manual GROUP BY mes ORDER BY mes"""),
]

modo = sys.argv[1] if len(sys.argv) > 1 else "antes"
lista = MANUAL if modo == "manual" else CONSULTAS
if modo == "despues":
    lista = [c for c in CONSULTAS if c[1] in ("q3_por_mes", "q5a_con_particion", "q5b_sin_particion")]

for titulo, archivo, sql in lista:
    cols, filas = correr(sql, titulo)
    if cols:
        mostrar(titulo, cols, filas, f"{modo}_{archivo}")
