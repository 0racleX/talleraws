# Estimación de costos (us-east-2)

## Configuración elegida (la más barata que cumple el ejercicio)

| Recurso | Elección | Motivo |
|---|---|---|
| EC2 | `t3.micro`, 8 GB gp3, **sin IPv4 pública** | Evita el cargo por IP pública |
| RDS | PostgreSQL 16, `db.t4g.micro`, Single-AZ, 20 GB gp3, **sin backups** (`retention=0`) | Instancia Graviton más barata; sin snapshots |
| S3 | Bucket vacío | Se cobra por almacenamiento y solicitudes |
| Red | VPC, 3 subredes, IGW, route table, 2 SG, **sin NAT Gateway** | Todo esto es gratuito salvo NAT/IP |
| Secreto | Secreto administrado por RDS | Ver abajo |

## Costo por recurso

| Recurso | Tarifa | 1 hora | 1 semana |
|---|---|---|---|
| EC2 t3.micro | ~USD 0.0104 / h | 0.0104 | 1.75 |
| EBS gp3 8 GB | ~USD 0.08 / GB-mes | 0.0009 | 0.15 |
| RDS db.t4g.micro (Single-AZ) | ~USD 0.016 / h | 0.0160 | 2.69 |
| RDS gp3 20 GB | ~USD 0.115 / GB-mes | 0.0032 | 0.54 |
| Secreto de RDS | USD 0.40 / secreto-mes (prorrateado) | 0.0005 | 0.09 |
| S3 vacío | ~0 | 0.00 | 0.00 |
| VPC, subredes, IGW, SG, rutas | gratis | 0.00 | 0.00 |
| **Total** | | **≈ USD 0.03** | **≈ USD 5.2** |

Las pruebas reales (3 despliegues de ~30 min cada uno) cuestan algo así como **USD 0.05 – 0.10**
en total, sobre todo por el tiempo de RDS. Para el reporte, calcula con tus horas reales:
`horas × (0.0104 + 0.0009 + 0.016 + 0.0032 + 0.0005)`.

## ¿Qué componentes siguen generando cargos sin recibir tráfico?

- **EC2 en ejecución**: se cobra por segundo, haya o no tráfico. Detenida deja de cobrar cómputo
  pero **el volumen EBS sigue cobrando**.
- **Volumen EBS** huérfano o de una instancia detenida.
- **RDS**: instancia encendida y su almacenamiento. Si se detiene, el almacenamiento sigue
  cobrando y AWS la **reinicia automáticamente a los 7 días**.
- **Snapshots y backups automáticos**: persisten tras borrar la instancia si no se usa
  `skip_final_snapshot` / `delete_automated_backups`. Aquí se evitan.
- **Secreto en Secrets Manager**: cobra mensualmente mientras exista.
- **IPv4 pública / Elastic IP** (~USD 0.005/h) aunque no haya tráfico.
- **NAT Gateway** (~USD 0.045/h + datos): no se usa a propósito.
- **S3**: solo cobra por los objetos almacenados; un bucket vacío cuesta cero.
- Gratis: VPC, subredes, IGW, tablas de rutas, security groups.

## ¿Qué costo añade el secreto de RDS?

Aproximadamente **USD 0.40 por mes por secreto** (≈ USD 0.0005/h, ≈ USD 0.09 por semana), más
USD 0.05 por cada 10 000 llamadas a la API. Para una prueba de una hora es prácticamente cero
(< USD 0.001). Al **borrar la instancia, RDS elimina el secreto administrado**, así que el cargo
termina. El secreto no es opcional por barato que sea: es lo que evita contraseñas en el
código y en el estado.

## Verificación posterior

Ejecuta `scripts/check_leftovers.sh` y guarda su salida vacía como evidencia. Además, revisa
**Billing → Cost Explorer** al día siguiente: puede tardar hasta 24 h en reflejar el uso.
