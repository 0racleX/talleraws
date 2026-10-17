¿Qué es? 
AWS Secrets Manager es un servicio para almacenar credenciales, claves de API y otros datos sensibles, cifrados con KMS.

¿Qué guarda? 
Guarda texto o binario (hasta 64 KB). Lo habitual es un JSON como {"username": "...", "password": "..."}.

¿Quién puede leerlo?
Políticas IAM (identity-based) sobre secretsmanager:GetSecretValue, opcionalmente una política de recursos en el secreto, y permisos de KMS si usa una llave propia.

Diferencia entre las tres operaciones(Crear, recuperar y rotar):
Crear: create-secret guarda el valor inicial.
Recuperar: la aplicación llama a GetSecretValue en tiempo de ejecución.
Rotar: cambiar el valor periódicamente, de forma automática (normalmente con una Lambda) o manual con put-secret-value.

aws secretsmanager create-secret \
  --name eia/taller/credenciales-prueba \
  --secret-string '{"username":"user1","password":"holaatodos2026."}' \
  --region us-east-2

Las cifras provienen de la página oficial de precios de AWS Secrets Manager y de la guía del usuario (ver referencias), consultadas en octubre de 2026. Conviene volver a revisarlas antes de una estimación real, porque las tarifas pueden cambiar y la página de precios es la fuente definitiva.
 
¿Cómo se cobran los secretos almacenados y las llamadas a la API?
 
El modelo es de pago por uso, sin cargos mínimos ni de instalación, y tiene dos componentes principales:
 
- **Secretos almacenados: 0,40 USD por secreto al mes**, prorrateado por hora. La propia página de precios lo ilustra: un secreto que existe una sola hora cuesta 0,40 / (30 días × 24 h) ≈ 0,00056 USD.
- **Llamadas a la API: 0,05 USD por cada 10.000 llamadas.**
Puntos finos que la documentación aclara y que vale la pena anotar:
 
- **Crear versiones nuevas no se cobra.** Actualizar o rotar un secreto crea una versión, pero no añade un cargo por versión (solo cuentan las llamadas a la API que se hagan).
- **Los secretos marcados para eliminación no se cobran.**
- **El cifrado con la llave `aws/secretsmanager` es gratis;** si se usa una llave KMS propia, se paga según las tarifas de KMS.
- **La rotación automática con Lambda** tiene un costo adicional: se paga la función Lambda al precio de Lambda (la rotación administrada no lo genera).
- CloudTrail guarda gratis la primera copia de los eventos de administración, pero el almacenamiento de registros en S3 o las notificaciones por SNS sí pueden cobrarse.
- Las cuentas nuevas pueden recibir créditos del nivel gratuito de AWS aplicables a Secrets Manager, según los términos vigentes en la página de precios.
¿Qué ocurre con el costo si el programa consulta el mismo secreto repetidamente?
 
Cada llamada a `GetSecretValue` es una llamada facturable, así que **el costo de la API crece linealmente con el número de consultas** y puede terminar superando al costo de almacenar el secreto. Un ejemplo con las tarifas anteriores, para un solo secreto durante un mes de 30 días:
 
| Patrón de consulta | Llamadas al mes | Costo de API | Costo del secreto | Total aprox. |
|---|---|---|---|---|
| Una vez por hora | 720 | 0,0036 USD | 0,40 USD | ≈ 0,40 USD |
| Una vez por minuto | 43.200 | 0,216 USD | 0,40 USD | ≈ 0,62 USD |
| **Una vez por segundo** | 2.592.000 | **12,96 USD** | 0,40 USD | **≈ 13,36 USD** |
 
Es decir, un programa que lee el mismo secreto cada segundo cuesta unas 33 veces más que el almacenamiento del secreto, para obtener el mismo valor. Además del dinero, consultar sin necesidad añade **latencia** (cada lectura es una llamada de red) y consume cuota de solicitudes del servicio, con el riesgo de *throttling*.
 
¿Cuándo convendría guardar temporalmente el valor en memoria?
 
Cuando el mismo proceso necesita el mismo secreto muchas veces y el valor cambia con poca frecuencia: servicios que atienden muchas peticiones (una API o una función Lambda invocada con frecuencia), trabajos largos de ETL, o aplicaciones que abren conexiones a una base de datos repetidamente. Guardar el valor en memoria con un **tiempo de vida (TTL)** reduce llamadas, costo y latencia. Con el mismo ejemplo, leer cada segundo pero refrescar el caché cada 5 minutos pasa de 2.592.000 a 8.640 llamadas al mes, es decir, de 12,96 USD a unos 0,04 USD. AWS ofrece componentes de caché para varios lenguajes (para Python, la librería `aws-secretsmanager-caching`).
 
El costo de cachear es la **frescura**: tras una actualización o una rotación, la aplicación seguirá usando el valor viejo hasta que el caché expire. Por eso el TTL debe elegirse en función de la frecuencia de rotación y de qué tan grave es usar una credencial desactualizada unos minutos. Cuando la rotación mantiene válidas la versión actual y la anterior, un TTL corto tolera ese desfase. En esta práctica **no se usó caché**, porque el objetivo era justamente comprobar que cada ejecución obtiene la versión vigente.
 