#!/usr/bin/env python3
"""Crea base y coleccion, inserta 12 documentos y ejecuta busqueda con filtro, ordenacion y agregacion."""
import json
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, get_client

DB_NAME = "lab_tienda"
COLLECTION = "productos"
OUT = ROOT / "results" / "docdb_demo_resultados.txt"
lines: list[str] = []


def emit(text: str = "") -> None:
    print(text)
    lines.append(text)


def show(title: str, docs) -> None:
    emit(f"\n=== {title} ===")
    for doc in docs:
        emit(json.dumps(doc, ensure_ascii=False, default=str))


def sample_documents() -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = [
        ("Portatil 14 pulgadas", "electronica", 1250.00, 8, ["computo", "oficina"]),
        ("Auriculares inalambricos", "electronica", 89.90, 40, ["audio"]),
        ("Monitor 27 pulgadas", "electronica", 310.50, 15, ["computo", "video"]),
        ("Teclado mecanico", "electronica", 74.00, 0, ["computo"]),
        ("Silla ergonomica", "hogar", 220.00, 12, ["oficina"]),
        ("Lampara de escritorio", "hogar", 35.75, 60, ["oficina", "iluminacion"]),
        ("Cafetera de goteo", "hogar", 58.20, 25, ["cocina"]),
        ("Mochila urbana", "accesorios", 45.00, 80, ["viaje"]),
        ("Botella termica", "accesorios", 18.50, 150, ["viaje", "cocina"]),
        ("Libro: Bases de datos", "libros", 39.99, 30, ["estudio"]),
        ("Libro: Python avanzado", "libros", 49.50, 22, ["estudio", "computo"]),
        ("Cuaderno A5 (pack 3)", "libros", 12.00, 200, ["estudio", "oficina"]),
    ]
    return [
        {"nombre": n, "categoria": c, "precio": p, "stock": s, "etiquetas": t, "creado": now}
        for n, c, p, s, t in rows
    ]


def main() -> None:
    client = get_client()
    col = client[DB_NAME][COLLECTION]  # la base y la coleccion se crean con la primera insercion

    col.delete_many({})  # permite repetir el script sin duplicar
    res = col.insert_many(sample_documents())
    emit(f"Insertados {len(res.inserted_ids)} documentos en {DB_NAME}.{COLLECTION}")
    emit(f"Total en la coleccion: {col.count_documents({})}")
    emit(f"Bases de datos: {client.list_database_names()}")
    emit(f"Colecciones en {DB_NAME}: {client[DB_NAME].list_collection_names()}")

    # 1) Busqueda con filtro: electronica con precio >= 100
    show(
        "BUSQUEDA CON FILTRO: categoria = electronica y precio >= 100",
        col.find({"categoria": "electronica", "precio": {"$gte": 100}}, {"_id": 0, "nombre": 1, "precio": 1, "stock": 1}),
    )

    # 2) Ordenacion: los 5 productos con stock mas caros
    show(
        "ORDENACION: stock > 0, precio descendente, top 5",
        col.find({"stock": {"$gt": 0}}, {"_id": 0, "nombre": 1, "categoria": 1, "precio": 1}).sort("precio", -1).limit(5),
    )

    # 3) Agregacion: resumen por categoria ($sort al final para que se conserve el orden)
    pipeline = [
        {"$group": {
            "_id": "$categoria",
            "productos": {"$sum": 1},
            "precio_promedio": {"$avg": "$precio"},
            "unidades": {"$sum": "$stock"},
            "valor_inventario": {"$sum": {"$multiply": ["$precio", "$stock"]}},
        }},
        {"$sort": {"valor_inventario": -1}},
    ]
    show("AGREGACION: resumen por categoria", col.aggregate(pipeline))

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nResultados guardados en {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
