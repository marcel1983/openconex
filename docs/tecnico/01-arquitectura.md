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
| `connections/shear/` | Conexiones de corte de extremo de viga: una biblioteca por tipo (`double_angle`, `double_angle_axial`, `single_plate`, `single_plate_axial`, `extended_single_plate`, `end_plate`, `seated`, `stiffened_seat`, `coped_beam`) y `check` (`ShearConnection`, `check_shear_connection`, `check_shear_envelope`), la interfaz común que usan el proyecto, el comando, la memoria y la interfaz gráfica. |
| `io/` | `project` (archivo `.ocnx` con pydantic), `shear_project` (bloque `shear_connection` y su conversión a `ShearConnection`), `csi` (tablas de SAP2000/ETABS), `csi_projects` (proyectos a partir de la importación). |
| `report/` | `builder` (estructura de la memoria; `build_report` elige entre placa base y conexión de corte), `shear` (memoria de una conexión de corte), `figures` (planta/elevación desde DXF e isométrico desde 3D), `html` (Jinja2 + MathML), `docx` (python-docx), `pdf` (Qt WebEngine). La memoria consume `Report.figures`; cada futuro tipo de conexión debe aportar sus figuras desde su propio dibujo/modelo. |
| `drawing/` | Plano DXF (ezdxf) y vistas independientes para las figuras de la memoria; `shear` dibuja la elevación de las conexiones de corte desde `shear_layout`, que también usa el modelo 3D. |
| `geometry3d/` | Sólidos OpenCASCADE, exportación STEP/STL y vista isométrica con líneas ocultas. |
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

## Flujo de una conexión de corte (`openconex shear`)

1. `load_project` valida el bloque `shear_connection`: los campos que necesita cada tipo (`io.shear_project.REQUIRED`), materiales y pernos conocidos, y casos con solo `V` y `P`.
2. `Project.shear_model()` arma un `ShearConnection`: el elemento de la biblioteca (`DoubleAngle`, `SinglePlate`…), la viga y el apoyo como `IShape`, el destaje (`CopedBeam`) y los datos para la tracción.
3. `check_shear_envelope` combina las fuerzas de cada combinación y llama a `check_shear_connection`. Con `P` < 0 (tracción) usa la variante axial de la placa simple o del doble ángulo; la compresión, o la tracción en otro tipo, devuelven un resultado `shear_connection.*` que no cumple. Si hay destaje, agrega las verificaciones de `coped_beam`.
4. `report.shear.build_shear_report` arma la memoria con el mismo `Report` que la placa base; `drawing.shear` y `geometry3d.shear` escriben el plano y el modelo.

## Flujo de una importación (`openconex supports`)

1. `io.csi.read_tables` lee cada hoja del Excel como tabla (título, campos, unidades, filas).
2. `io.csi.import_supports` arma los `Support`: nodo, coordenadas, columna y fuerzas por caso de salida, en los ejes locales de la columna.
3. `io.csi_projects.base_plate_projects` copia la plantilla, pone la columna y las cargas, y agrupa por nodo o por sección.

## Dependencias

Todas son compatibles con GPL-3.0 (lo comprueba `tools/check_licenses.py` en la integración continua): pint, pydantic, Jinja2, latex2mathml, python-docx, ezdxf y openpyxl; opcionales PySide6 (PDF) y cadquery-ocp-novtk (3D).
