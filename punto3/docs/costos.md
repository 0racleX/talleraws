# Estimación de costos – Punto 3 (us-east-2)

Cálculo reproducible con `python scripts/calc_costos.py`. Mes = 730 h, semana = 168 h.

## Precios usados

| Componente | Tarifa | Fuente |
|---|---|---|
| DocumentDB Serverless (Standard) | USD 0,0822 por DCU-hora, mínimo 0,5 DCU, facturado por segundo | [Precios de DocumentDB](https://aws.amazon.com/documentdb/pricing/) * |
| DocumentDB `db.t4g.medium` | USD 0,076 por hora | Tarifa pública recordada, **no verificada** |
| Almacenamiento DocumentDB (Standard) | USD 0,10 por GB-mes | Precios de DocumentDB * |
| I/O DocumentDB (Standard) | USD 0,20 por millón | Precios de DocumentDB * |
| EC2 `t4g.nano` | USD 0,0042 por hora | Tarifa pública de EC2 |
| IPv4 pública | USD 0,005 por hora | Tarifa pública de AWS |
| EBS gp3 | USD 0,08 por GB-mes (8 GB) | Tarifa pública de EBS |
| Secreto de Secrets Manager | USD 0,40 por secreto-mes | Tarifa pública |

Datos de la práctica: 1 GB almacenado y unas 10 000 I/O (≈ USD 0,002).

## Resultado

| Concepto | 1 hora | 1 semana | 1 mes (730 h) |
|---|---|---|---|
| **Serverless (0,5 DCU)** – total con EC2 y secreto | **USD 0,054** | **USD 8,72** | USD 37,86 |
| **Aprovisionado (`db.t4g.medium`)** – total con EC2 y secreto | USD 0,089 | USD 14,58 | USD 63,34 |
| Solo cómputo serverless | 0,041 | 6,90 | 30,00 |
| Solo cómputo aprovisionado | 0,076 | 12,77 | 55,48 |
| **EC2 del túnel** (instancia + IPv4 + EBS) | **USD 0,010** | **USD 1,69** | USD 7,36 |
| Secreto de DocumentDB | 0,0005 | 0,09 | 0,40 |

## Preguntas de costos

**¿Qué opción cuesta menos para esta práctica?** DocumentDB Serverless al mínimo de 0,5 DCU.

- Serverless: 0,5 × USD 0,0822 = **USD 0,041/h**. Aprovisionado: **USD 0,076/h**. Ahorro de ~46 %.
- El punto de equilibrio es 0,076 / 0,0822 ≈ **0,92 DCU** de capacidad media. Mientras la carga no supere
  ese promedio, serverless gana. Una práctica con 12 documentos casi no usa capacidad, así que se queda en 0,5 DCU.
- Aprovisionado solo compensa con carga **constante y alta** (un `t4g.medium` equivale a ~2 DCU de memoria)
  o con instancias reservadas.
- Serverless **no escala a cero**: seguiría cobrando 0,5 DCU mientras exista. La condición para que gane es
  borrar el cluster al terminar, igual que en la opción aprovisionada.
- Si la cuenta es nueva, el Free Tier de DocumentDB incluye 750 h de `db.t3.medium` durante un mes; ese caso
  haría gratis la opción aprovisionada con esa clase, pero no con `t4g.medium`.

**¿Cuánto agrega la EC2 del túnel?** Unos **USD 0,010 por hora** (≈ USD 1,69 por semana): la instancia
`t4g.nano` pone USD 0,0042, la IPv4 pública USD 0,005 (la mitad del total) y el disco de 8 GB USD 0,0009.
Equivale a ~19 % del costo total de la opción serverless. La IPv4 pública es necesaria para que SSH llegue
desde su equipo.

## ¿Qué sigue cobrando sin tráfico?

- La capacidad mínima de serverless (0,5 DCU) o la instancia aprovisionada completa.
- El almacenamiento del cluster y los backups por encima del 100 % del tamaño de los datos.
- El secreto (USD 0,40/mes mientras exista; DocumentDB lo elimina con el cluster).
- La EC2 en ejecución, su disco EBS y la IPv4 pública (detenida deja de cobrar cómputo, pero IPv4 y EBS siguen).

## Costo real de la práctica

Tiempo medido de cada despliegue (rellene con los `date` del inicio y fin) × tarifa horaria de la tabla.
Una prueba de ~1 hora cuesta menos de USD 0,10. Contraste con Cost Explorer (us-east-2) al día siguiente.
