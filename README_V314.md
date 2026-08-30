# Westcon Iberia Business Intelligence v3.14.0

Production Candidate construida sobre **v3.13.0**.

## Objetivo de la release

v3.14 mejora la utilidad ejecutiva de las vistas: los encabezados explican de forma directa qué información ofrece cada sección y para qué sirve al usuario; además, la ausencia de cualquier señal secundaria deja de presentarse automáticamente como un gap de investigación, evitando demasiados “En investigación”.

## Cambios principales

### 1. Encabezados descriptivos y orientados al usuario
Los encabezados de Fabricantes, Mayoristas, Integradores, Clientes, Tendencias y Arquitecturas explican qué información encontrará el usuario en cada vista y qué utilidad tiene, dejando las reglas internas, cautelas metodológicas y criterios de clasificación para las ayudas y la capa de trazabilidad.

### 2. Mayoristas orientados a inteligencia competitiva
La tabla conserva solo distribuidores/mayoristas validados y añade como columnas de decisión:
- Facturación / escala pública.
- Fabricantes / linecard público.
- Fabricantes coincidentes con Westcon.
- Fabricantes competidores de Westcon presentes en el linecard.
- Capacidades diferenciales.

Comstor continúa excluido como competidor por ser la unidad especializada en Cisco de Westcon. Los fabricantes no entran en esta tabla aunque tengan venta directa.

### 3. Facturación y capacidades con trazabilidad
Se incorporan cifras 2025 publicadas para 14 mayoristas españoles del Ranking del Canal 2026 y capacidades oficiales de distribuidores cuando existe fuente pública. La cifra conserva año y geografía; una cifra global no se presenta como Iberia.

### 4. Fabricantes: menos huecos obvios
Se amplía el panorama competitivo mediante fuentes públicas de mercado/Peer Insights. Los fabricantes sin competidores públicos en el snapshot pasan de 17 a 6. Las alternativas se etiquetan como peers/alternativas, no como equivalencia funcional absoluta.

### 5. Gap engine v3.14
Se separan:
- **gaps decisionales**: ausencia que impide una lectura de negocio relevante;
- **enriquecimiento opcional**: empleo, casos, verticales, ventanas de renovación u otras señales que pueden no existir públicamente para todas las entidades.

La UI muestra **Pendiente de evidencia** solo para campos decisionales. En un campo opcional sin evidencia suficiente muestra `—` o la columna se oculta si la cobertura es demasiado baja.

## Métricas v3.13 → v3.14

| Métrica | v3.13 | v3.14 |
|---|---:|---:|
| Fabricantes | 36 | 36 |
| Mayoristas validados | 60 | 60 |
| Integradores | 130 | 130 |
| Clientes | 81 | 81 |
| Clientes públicos | 30 | 30 |
| Clientes privados | 51 | 51 |
| Fuentes / familias | 278 | 294 |
| Campos trazables | 1.881 | 1.921 |
| Gaps críticos | 1.554 | 600 |
| Gaps críticos mayoristas | 428 | 114 |
| Gaps críticos integradores | 738 | 249 |
| Fabricantes sin competidores | 17 | 6 |

La reducción de gaps no se logra borrando carencias: los faltantes opcionales se conservan en `optional_missing_by_field` para investigación progresiva.

## Cobertura estructural preservada
- IBEX 35 completo: 35 cuentas.
- PSI Portugal: 16 cuentas.
- 30 oportunidades públicas con identificador/enlace exacto.
- 237 relaciones fabricante↔integrador.
- Forescout fuera del portfolio Westcon activo.
- Comstor fuera de Mayoristas de la competencia.

## Validación

```powershell
python -m unittest tests/test_v314.py -v
python scripts/v314/validate_v314.py
node --check assets/v314/intelligence.js
node tests/ui_smoke_v314.js
```

Prueba del supervisor sin lanzar la fase larga heredada:

```powershell
python scripts/research_supervisor_v314.py --profile daily --max-runtime 90 --fallback-runtime 0 --skip-v33
```

Prueba daily real:

```powershell
python scripts/research_supervisor_v314.py --profile daily --max-runtime 720 --fallback-runtime 0
```

Prueba weekly real:

```powershell
python scripts/research_supervisor_v314.py --profile weekly --max-runtime 1200 --fallback-runtime 0
```

## Probar la aplicación localmente

Desde la raíz:

```powershell
python -m http.server 8000
```

Abrir `http://localhost:8000/`.

## Actualización periódica
Los workflows diaria, semanal y mensual apuntan a `research_supervisor_v314.py`, validan v3.14 antes de publicar y GitHub Pages sirve `data/v314`.
