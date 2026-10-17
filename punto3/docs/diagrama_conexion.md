# Diagrama de conexión: MongoDB Compass / Python → DocumentDB

```mermaid
flowchart LR
  subgraph PC["Su equipo (Windows + WSL)"]
    C["MongoDB Compass"]
    PY["Python (pymongo + boto3)"]
    L["localhost:27017<br/>extremo local del túnel"]
    K[("llave SSH privada<br/>~/.ssh, solo local")]
  end

  subgraph AWS["AWS us-east-2 · VPC por defecto"]
    subgraph PUB["Subred pública"]
      EC2["EC2 t4g.nano (bastion)<br/>SG: SSH 22 solo desde mi IP/32"]
    end
    subgraph PRIV["Subredes del subnet group (2 AZ)"]
      DB[("DocumentDB<br/>cluster + instancia<br/>SG: 27017 solo desde el SG de la EC2")]
    end
  end

  SM["AWS Secrets Manager<br/>secreto rds!cluster-… (contraseña)"]

  C -->|"TLS + CA global-bundle.pem"| L
  PY -->|"TLS + CA global-bundle.pem"| L
  L ==>|"túnel SSH (puerto 22)"| EC2
  K -.->|"autentica"| EC2
  EC2 -->|"27017 dentro de la VPC"| DB
  PY -->|"HTTPS · credenciales user_cli · get_secret_value"| SM
```

## Lectura paso a paso

```
 Compass / Python                                                 AWS (us-east-2)
┌───────────────┐   TLS (valida con global-bundle.pem)
│ localhost:27017│──────────────┐
└───────────────┘              │   Túnel SSH, puerto 22
                               └────────────────────────▶ ┌───────────────────────┐
  llave SSH (local) ──────── autentica ───────────────▶  │ EC2 bastion t4g.nano  │
                                                          │ SG: 22 solo desde mi IP│
                                                          └──────────┬────────────┘
                                                                     │ 27017 (red interna de la VPC)
                                                                     ▼
                                                          ┌───────────────────────┐
                                                          │ DocumentDB (sin IP    │
                                                          │ pública)              │
                                                          │ SG: 27017 solo desde  │
                                                          │ el SG de la EC2       │
                                                          └───────────────────────┘

  Python ──HTTPS (user_cli)──▶ Secrets Manager ──▶ usuario y contraseña (en memoria, nunca en el código)
```

| Qué | Por qué es necesario |
|---|---|
| Túnel SSH | DocumentDB no tiene endpoint público; la única ruta es desde dentro de la VPC |
| SG de la EC2 (22 desde mi IP/32) | Solo mi equipo puede abrir el túnel |
| SG de DocumentDB (27017 desde el SG de la EC2) | Solo el bastion puede hablar con la base |
| `global-bundle.pem` | DocumentDB usa TLS con certificados de la CA de Amazon |
| `tlsAllowInvalidHostnames` | El cliente conecta a `localhost` y el certificado es del endpoint del cluster |
| `directConnection=true`, `retryWrites=false` | Una sola ruta (el túnel) y motor 5.0.0 sin retryable writes |
| Secrets Manager | La contraseña se recupera en ejecución; no se escribe en código ni en archivos |
