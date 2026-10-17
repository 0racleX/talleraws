import os
import json
import boto3

ENDPOINT = f"https://{os.environ['NEPTUNE_ENDPOINT']}:8182"
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# El cliente firma cada petición con SigV4 usando tus credenciales de AWS CLI (sin contraseñas en el código)
client = boto3.client("neptunedata", region_name=REGION, endpoint_url=ENDPOINT)


def cypher(query):
    return client.execute_open_cypher_query(openCypherQuery=query)["results"]


def mostrar(titulo, filas):
    print(f"\n=== {titulo} ===")
    for fila in filas:
        print("  ", fila)
    print(f"   ({len(filas)} filas)")


# ---------- 1. Limpiar e insertar el grafo ----------
cypher("MATCH (n) DETACH DELETE n")

cypher("""
CREATE
 (co:Company {name:'DataCorp'}),
 (ana:Person {name:'Ana',    role:'Manager'}),
 (luis:Person {name:'Luis',   role:'Engineer'}),
 (marta:Person {name:'Marta',  role:'Analyst'}),
 (carlos:Person {name:'Carlos', role:'Engineer'}),
 (sofia:Person {name:'Sofia',  role:'Analyst'}),
 (alfa:Project {name:'Alfa'}), (beta:Project {name:'Beta'}), (gamma:Project {name:'Gamma'}),
 (py:Skill {name:'Python'}), (sql:Skill {name:'SQL'}), (spark:Skill {name:'Spark'}),
 (ana)-[:WORKS_AT]->(co), (luis)-[:WORKS_AT]->(co), (marta)-[:WORKS_AT]->(co),
 (carlos)-[:WORKS_AT]->(co), (sofia)-[:WORKS_AT]->(co),
 (ana)-[:MANAGES]->(luis), (ana)-[:MANAGES]->(marta),
 (luis)-[:WORKS_ON]->(alfa), (marta)-[:WORKS_ON]->(alfa), (marta)-[:WORKS_ON]->(beta),
 (carlos)-[:WORKS_ON]->(beta), (sofia)-[:WORKS_ON]->(gamma), (carlos)-[:WORKS_ON]->(gamma),
 (ana)-[:HAS_SKILL]->(sql), (luis)-[:HAS_SKILL]->(py), (marta)-[:HAS_SKILL]->(spark),
 (carlos)-[:HAS_SKILL]->(py), (sofia)-[:HAS_SKILL]->(sql)
""")

# ---------- 2. Verificación ----------
mostrar("Total de vértices", cypher("MATCH (n) RETURN count(n) AS vertices"))
mostrar("Total de relaciones", cypher("MATCH ()-[r]->() RETURN count(r) AS relaciones"))
mostrar("Vértices por etiqueta", cypher("MATCH (n) RETURN labels(n) AS etiqueta, count(*) AS total"))
mostrar("Relaciones por tipo", cypher("MATCH ()-[r]->() RETURN type(r) AS tipo, count(*) AS total"))

# ---------- 3. Tres consultas que recorren relaciones ----------
mostrar("Q1: compañeros de proyecto de Marta (Persona->Proyecto<-Persona)", cypher("""
MATCH (m:Person {name:'Marta'})-[:WORKS_ON]->(p:Project)<-[:WORKS_ON]-(c:Person)
WHERE c.name <> 'Marta'
RETURN DISTINCT c.name AS companero, p.name AS proyecto"""))

mostrar("Q2: habilidades de los subordinados de Ana (MANAGES->HAS_SKILL)", cypher("""
MATCH (:Person {name:'Ana'})-[:MANAGES]->(e:Person)-[:HAS_SKILL]->(s:Skill)
RETURN e.name AS empleado, s.name AS habilidad"""))

mostrar("Q3: proyectos donde trabaja el equipo de Ana (MANAGES->WORKS_ON)", cypher("""
MATCH (:Person {name:'Ana'})-[:MANAGES]->(e:Person)-[:WORKS_ON]->(p:Project)
RETURN p.name AS proyecto, collect(e.name) AS equipo_de_ana, count(e) AS personas
ORDER BY personas DESC"""))

# ---------- 4. Extra opcional: misma lógica en Gremlin ----------
try:
    g = client.execute_gremlin_query(
        gremlinQuery="g.V().has('Person','name','Ana').out('MANAGES').out('WORKS_ON').values('name').dedup()")
    print("\n=== Extra Gremlin: proyectos del equipo de Ana ===")
    print("  ", json.dumps(g.get("result"), default=str)[:500])
except Exception as e:
    print("\n(Extra Gremlin omitido:", e, ")")
