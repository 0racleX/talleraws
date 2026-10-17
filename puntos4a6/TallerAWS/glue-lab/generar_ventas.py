import csv, random, os
from datetime import date

random.seed(7)
ciudades = [("Medellin","050001"),("Bogota","110111"),("Cali","760001"),
            ("Barranquilla","080001"),("Cartagena","130001"),("Bucaramanga","680001")]
productos = [("Portatil","Electronica",899.90),("Telefono","Electronica",499.50),
             ("Audifonos","Electronica",59.90),("Silla","Muebles",149.00),
             ("Libro","Papeleria",19.99),("Cuaderno","Papeleria",4.50)]

def generar(carpeta, archivo, anio, mes, n, id_inicial):
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, archivo), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["venta_id","fecha_venta","ciudad","codigo_postal","producto",
                    "categoria","cantidad","precio_unitario","cliente_vip"])
        for i in range(n):
            ciudad, cp = random.choice(ciudades)
            prod, cat, precio = random.choice(productos)
            w.writerow([id_inicial + i, date(anio, mes, random.randint(1, 28)).isoformat(),
                        ciudad, cp, prod, cat, random.randint(1, 5), precio,
                        random.choice(["true", "false"])])

generar("datos/mes=2026-01", "ventas_2026-01.csv", 2026, 1, 24, 1)         # carga inicial: 24 registros
generar("datos_nuevos/mes=2026-02", "ventas_2026-02.csv", 2026, 2, 12, 25) # registros nuevos (Fase 7)
print("Listo")
