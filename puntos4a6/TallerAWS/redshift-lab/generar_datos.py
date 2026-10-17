import csv, random
from datetime import date, timedelta

random.seed(42)
ciudades = [("Medellin","Colombia"),("Bogota","Colombia"),("Cali","Colombia"),
            ("Lima","Peru"),("Quito","Ecuador"),("Ciudad de Mexico","Mexico"),("Santiago","Chile")]
nombres = ["Ana","Luis","Marta","Carlos","Sofia","Juan","Laura","Pedro","Camila","Andres"]
apellidos = ["Gomez","Perez","Rios","Lopez","Torres","Diaz","Vargas","Mora"]
productos = [("Portatil","Electronica",900),("Telefono","Electronica",500),("Auriculares","Electronica",60),
             ("Silla","Muebles",150),("Escritorio","Muebles",220),
             ("Libro","Papeleria",20),("Cuaderno","Papeleria",5),("Mouse","Electronica",25)]

N_CLIENTES, N_PEDIDOS = 60, 600

with open("datos/clientes.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["cliente_id","nombre","ciudad","pais","fecha_registro"])
    for i in range(1, N_CLIENTES + 1):
        ciudad, pais = random.choice(ciudades)
        w.writerow([i, f"{random.choice(nombres)} {random.choice(apellidos)}", ciudad, pais,
                    date(2023,1,1) + timedelta(days=random.randint(0, 700))])

with open("datos/pedidos.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["pedido_id","cliente_id","fecha_pedido","producto","categoria","cantidad","precio_unitario"])
    for i in range(1, N_PEDIDOS + 1):
        prod, cat, precio = random.choice(productos)
        w.writerow([i, random.randint(1, N_CLIENTES),
                    date(2025,1,1) + timedelta(days=random.randint(0, 450)),
                    prod, cat, random.randint(1, 5), precio])
print("Listo: datos/clientes.csv y datos/pedidos.csv")
