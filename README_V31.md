# Westcon Iberia · Decision Intelligence v3.1

**Upgrade no destructivo para la v3.0 · España + Portugal · información pública/verificable · GitHub Pages + GitHub Actions**

La v3.1 mantiene la interfaz ejecutiva de la versión existente y refuerza el motor de inteligencia. No introduce CRM, pipeline, margen, objetivos, personas ni otros datos internos.

## Qué incorpora

1. **Corrección estructural de `Awards → procurement`**. La palabra *award(s)* no puede activar contratación pública sin anclas positivas de procurement (buyer/contracting authority, notice/tender, CPV, expediente, TED/PLACSP/BASE, contract award, adjudicación...). Los premios de cliente/fabricante/partner/industria se clasifican por separado. Una etiqueta antigua de procurement sin anclas suficientes se pone en `pending_classification`.
2. **Rollback atómico de todo `data/`**. Antes de cada ciclo se crea un snapshot completo; si falla cualquier validación v3.1 se restaura el árbol entero, no solo el JSON principal.
3. **Fabricantes / Mayoristas / Integradores como entidades equivalentes**. Se genera `data/v31/entity_intelligence.json` y el frontend añade un selector con tablas y ficha profunda para mayoristas e integradores.
4. **Source Intelligence Registry dinámico** con fuentes oficiales, open data, contratación, analistas públicos, medios de canal, fabricantes, mayoristas, integradores, seguridad, repositorios y fuentes históricas. Incluye fuentes de España, Portugal, UE y globales.
5. **Adaptive discovery con aprendizaje**. Cada fuente acumula utilidad, fiabilidad, falsos positivos, duplicados, autoridad y latencia. El presupuesto se mueve hacia las fuentes/queries que dan más inteligencia sin abandonar exploración.
6. **Deuda de investigación**. Las tareas no terminadas o fallidas se guardan en `data/v31/research_debt.json`; la ausencia de resultado no elimina relaciones históricas.
7. **Confianza explicable**. Autoridad, corroboración, geografía, frescura, relación directa, diversidad y especificidad; penalizaciones por contradicción/inferencia. Umbrales: alta ≥85%, sólida ≥70%, indicativa ≥55%, débil ≥40%.
8. **Recomendaciones con gates más exigentes**. Decisiones estratégicas requieren ≥85%; acciones de inversión/capacidad/canal ≥78%; pilotos/vigilancia ≥62%. Cada recomendación incluye oportunidad, monetización, KPI, contraevidencia y condición de cambio.

## Instalación sobre tu repo v3.0

La forma más sencilla es la misma que estás usando con las versiones anteriores:

1. **Deja `.git/` intacto** en tu carpeta `estrategia`.
2. Descomprime el ZIP v3.1 y copia su contenido sobre la raíz de `estrategia`. No incluye `index.html`, por lo que no pisa tu frontend v3.0.
3. Desde la raíz de `estrategia` ejecuta:

```powershell
python tools/aplicar_v31.py
```

También puedes ejecutar el instalador desde una carpeta externa; detecta ambos modos.

El instalador:

- copia `scripts/v31`, `config/v31` y `assets/v31`;
- añade el frontend v3.1 sin reemplazar tu UI;
- guarda backup de `index.html`;
- cambia los workflows existentes para llamar a `scripts/research_supervisor_v31.py`;
- **no elimina** `scripts/research_supervisor.py`: la v3.1 lo usa como fase legacy y añade control/descubrimiento/validación encima.

### Prueba corta antes de hacer push

```powershell
python scripts/research_supervisor_v31.py --profile daily --max-runtime 180 --skip-legacy
python -m pytest tests/test_v31.py -q
```

Si no tienes `pytest`, el primer comando es suficiente para generar las tablas; los tests son opcionales.

### Publicación

```powershell
git status
git add .
git commit -m "Westcon Iberia Decision Intelligence v3.1"
git push
```

## Comportamiento de runtime

La v3.1 reparte el presupuesto de ejecución entre la investigación ya existente y la nueva capa de descubrimiento adaptativo:

- diaria: ~76% legacy / 24% v3.1;
- semanal: ~66% / 34%;
- mensual: ~58% / 42%.

Se puede variar con `--v31-share 0.30`. El nuevo motor trabaja por presupuesto temporal, con timeouts y deuda; nunca espera indefinidamente a completar todas las búsquedas.

## Ficheros nuevos importantes

- `scripts/research_supervisor_v31.py` — orquestador y rollback de snapshot completo.
- `scripts/v31/taxonomy.py` — taxonomía y guard anti-Awards.
- `scripts/v31/discovery.py` — Google News RSS, GDELT y Brave opcional.
- `scripts/v31/source_learning.py` — aprendizaje de fuentes.
- `scripts/v31/confidence.py` — scoring y umbrales.
- `scripts/v31/entity_views.py` — agregación fabricantes/mayoristas/integradores.
- `scripts/v31/recommendations.py` — inteligencia de negocio explicable.
- `config/v31/source_registry.json` — registro ampliable de fuentes.
- `assets/v31/entity-intelligence.*` — tablas/ficha profunda sin romper el frontend existente.

## Regla de publicación

`discover → checkpoint → classify → corroborate → score → validate → publish`

En v3.1, *publish* significa que **el árbol de datos ha pasado validación semántica**. Si aparece otra vez un `Awards` de AttackIQ clasificado como procurement sin anclas reales, la validación lo rechaza y el snapshot completo se restaura.

## Nota sobre fuentes de analistas

Solo se utiliza contenido públicamente accesible. La aplicación no intenta reconstruir contenido licenciado de Gartner, IDC, Forrester u otros analistas.
