import os, boto3
glue = boto3.client("glue")
DB, TABLE = os.environ["DB"], "ventas"

CORRECCIONES = {"codigo_postal": "string", "fecha_venta": "date", "cantidad": "int",
                "precio_unitario": "decimal(10,2)", "cliente_vip": "boolean"}

t = glue.get_table(DatabaseName=DB, Name=TABLE)["Table"]
cols = t["StorageDescriptor"]["Columns"]

print("ANTES:")
for c in cols: print(f"  {c['Name']:<18} {c['Type']}")
for c in cols:
    if c["Name"] in CORRECCIONES:
        c["Type"] = CORRECCIONES[c["Name"]]
print("DESPUES:")
for c in cols: print(f"  {c['Name']:<18} {c['Type']}")

permitidos = ["Name","Description","Owner","Retention","StorageDescriptor","PartitionKeys",
              "TableType","Parameters","ViewOriginalText","ViewExpandedText"]
glue.update_table(DatabaseName=DB, TableInput={k: v for k, v in t.items() if k in permitidos})

entradas = []
for pag in glue.get_paginator("get_partitions").paginate(DatabaseName=DB, TableName=TABLE):
    for p in pag["Partitions"]:
        sd = p["StorageDescriptor"]; sd["Columns"] = cols
        entradas.append({"PartitionValueList": p["Values"],
                         "PartitionInput": {"Values": p["Values"], "StorageDescriptor": sd,
                                            "Parameters": p.get("Parameters", {})}})
if entradas:
    glue.batch_update_partition(DatabaseName=DB, TableName=TABLE, Entries=entradas)
print(f"Tabla y {len(entradas)} particion(es) actualizadas.")
