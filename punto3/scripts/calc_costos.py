#!/usr/bin/env python3
"""Calculadora de costos del punto 3 (no usa AWS). Edite PRECIOS y HORAS y ejecute: python calc_costos.py

Fuentes: pagina oficial https://aws.amazon.com/documentdb/pricing/ (DCU, almacenamiento, I/O) y tarifas
publicas de EC2/EBS/IPv4/Secrets Manager. Verifique cada precio para us-east-2 en la AWS Pricing Calculator.
"""

PRECIOS = {
    "dcu_hora": 0.0822,            # DocumentDB Serverless, Standard (por DCU-hora). Pagina oficial, N. Virginia
    "t4g_medium_hora": 0.076,      # DocumentDB db.t4g.medium  <- NO verificado: confirmar en la calculadora
    "ec2_t4g_nano_hora": 0.0042,   # EC2 t4g.nano Linux
    "ipv4_publica_hora": 0.005,    # IPv4 publica
    "ebs_gp3_gb_mes": 0.08,        # EBS gp3
    "docdb_gb_mes": 0.10,          # almacenamiento DocumentDB Standard
    "docdb_millon_io": 0.20,       # I/O DocumentDB Standard
    "secreto_mes": 0.40,           # Secrets Manager, por secreto
}
MES = 730
DCU_MIN = 0.5
EBS_GB = 8
DOCDB_GB = 1        # datos de la practica
MILLONES_IO = 0.01  # I/O estimadas de la practica (~10 000)


def por_hora(compute_hora: float) -> dict:
    d = {
        "DocumentDB computo": compute_hora,
        "DocumentDB almacenamiento": PRECIOS["docdb_gb_mes"] * DOCDB_GB / MES,
        "Secreto de DocumentDB": PRECIOS["secreto_mes"] / MES,
        "EC2 t4g.nano (tunel)": PRECIOS["ec2_t4g_nano_hora"],
        "IPv4 publica de la EC2": PRECIOS["ipv4_publica_hora"],
        "EBS 8 GB de la EC2": PRECIOS["ebs_gp3_gb_mes"] * EBS_GB / MES,
    }
    return d


def imprimir(nombre: str, compute_hora: float) -> None:
    d = por_hora(compute_hora)
    total_h = sum(d.values())
    io = PRECIOS["docdb_millon_io"] * MILLONES_IO
    print(f"\n## {nombre}")
    for k, v in d.items():
        print(f"  {k:28s} USD/h {v:8.5f}   1 h: {v:8.4f}   168 h: {v*168:8.3f}   730 h: {v*MES:8.2f}")
    print(f"  {'TOTAL':28s} USD/h {total_h:8.5f}   1 h: {total_h + io:8.4f}   168 h: {total_h*168 + io:8.3f}   730 h: {total_h*MES + io:8.2f}")
    ec2 = d["EC2 t4g.nano (tunel)"] + d["IPv4 publica de la EC2"] + d["EBS 8 GB de la EC2"]
    print(f"  Solo el tunel (EC2+IPv4+EBS): USD/h {ec2:.5f}  1 h: {ec2:.4f}  168 h: {ec2*168:.3f}  730 h: {ec2*MES:.2f}")


if __name__ == "__main__":
    serverless = PRECIOS["dcu_hora"] * DCU_MIN
    imprimir(f"DocumentDB Serverless ({DCU_MIN} DCU minimo)", serverless)
    imprimir("DocumentDB aprovisionado (db.t4g.medium)", PRECIOS["t4g_medium_hora"])
    print(f"\nPunto de equilibrio: serverless cuesta menos mientras la capacidad media sea < "
          f"{PRECIOS['t4g_medium_hora'] / PRECIOS['dcu_hora']:.2f} DCU "
          f"(t4g.medium tiene 4 GiB de RAM, equivalente a ~2 DCU)")
    print(f"Serverless cubierto a 24x7 al minimo: USD {serverless*MES:.2f}/mes vs aprovisionado USD {PRECIOS['t4g_medium_hora']*MES:.2f}/mes")
