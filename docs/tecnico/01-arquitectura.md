# 1. Arquitectura

El cálculo está separado de la entrada, las salidas y la interfaz. Cada capa usa solo las de abajo:

```
cli.py ─────────────► io/ (proyecto, importación) ─► connections/ ─► kernel/ ─► core/
   │                                                     ▲              ▲
   └──► report/  drawing/  geometry3d/ ──────────────────┘              │
                                                    units.py, i18n/ ────┘
```

## Paquetes (`src/openconex/`)

| Paquete | Contenido |
|---|---|
| `units.py` | Magnitudes (`Kind`), sistemas de unidades (`UnitSystem`, `PRESETS`), conversión con pint, lectura de fracciones (`3/4 in`) y formato. |
| `core/` | Datos sin cálculo: `checks.py` (`CheckResult`, `TraceStep`, `Status`), `materials.py` (aceros, pernos, electrodos), `bolting.py` (Tablas J3.1, J3.3, J3.4 y 14-2), `model.py` (perfiles I, HSS, pernos, soldaduras), `loads.py` (casos, combinaciones, ASCE 7-22), `shapes.py` (base de datos AISC en SQLite). |
| `kernel/` | Verificaciones reutilizables por cualquier conexión: `bolts` (§J3), `welds` (§J2), `elements` (§J4), `prying` (Manual Parte 9), `bolt_group` y `weld_group` (método elástico y centro instantáneo), `local` (§J10), `anchors` (ACI 318-19 Cap. 17), `design` (`Calc`, φ/Ω). |
| `connections/base_plate/` | Placa base: `plate` (modelos de presiones de la DG1), `transfer` (corte, llave, soldaduras), `seismic` (DG1 Cap. 5 y 6), `check` (verificación completa por combinación). |
| `io/` | `project` (archivo `.ocnx` con pydantic), `csi` (tablas de SAP2000/ETABS), `csi_projects` (proyectos a partir de la importación). |
| `report/` | `builder` (estructura de la memoria), `html` (Jinja2 + MathML), `docx` (python-docx), `pdf` (Qt WebEngine). |
| `drawing/` | Plano DXF (ezdxf). |
| `geometry3d/` | Sólidos OpenCASCADE y exportación STEP/STL. |
| `i18n/` | Textos en `es.toml` y `en.toml`. |
| `cli.py` | Comando `openconex`. |
| `data/shapes/` | `aisc_v16.sql`, base de datos de perfiles en SQL (no GPL; ver `NOTICE.md`). |

## Flujo de un cálculo (`openconex baseplate`)

1. `io.project.load_project` lee el `.ocnx` y lo valida con pydantic: tipos, campos obligatorios, nombres de casos únicos, combinaciones que citan casos existentes.
2. `Project.base_plate_model()` convierte cada cantidad a unidades internas (N, mm, MPa) y arma el `BasePlate`; `Project.case_forces()` arma las `Forces` de cada caso.
3. `Project.load_combinations()` genera las combinaciones ASCE 7-22 y agrega las propias.
4. `check_envelope` combina las fuerzas de cada combinación (`core.loads.combine`) y llama a `check_base_plate`, que devuelve una lista de `CheckResult`.
5. `report.builder` elige, para cada tipo de verificación, el resultado con mayor relación (`governing`) y arma la memoria.
6. `report.html`, `report.docx`, `drawing` y `geometry3d` escriben las salidas.

## Flujo de una importación (`openconex supports`)

1. `io.csi.read_tables` lee cada hoja del Excel como tabla (título, campos, unidades, filas).
2. `io.csi.import_supports` arma los `Support`: nodo, coordenadas, columna y fuerzas por caso de salida, en los ejes locales de la columna.
3. `io.csi_projects.base_plate_projects` copia la plantilla, pone la columna y las cargas, y agrupa por nodo o por sección.

## Dependencias

Todas son compatibles con GPL-3.0 (lo comprueba `tools/check_licenses.py` en la integración continua): pint, pydantic, Jinja2, latex2mathml, python-docx, ezdxf y openpyxl; opcionales PySide6 (PDF) y cadquery-ocp-novtk (3D).
