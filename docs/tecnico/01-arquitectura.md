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
| `connections/base_plate/` | Placa base: `plate` (modelos de presiones de la DG1), `transfer` (corte, llave, soldaduras), `seismic` (DG1 Cap. 5 y 6), `pedestal` (pedestal como columna corta, ACI 318-19), `interference` (revisor en planta), `check` (verificación completa por combinación), `optimize` (optimización local y global compartida por la CLI y la GUI). |
| `connections/shear/` | Conexiones de corte de extremo de viga: una biblioteca por tipo (`double_angle`, `double_angle_axial`, `single_plate`, `single_plate_axial`, `extended_single_plate`, `end_plate`, `seated`, `stiffened_seat`, `coped_beam`) y `check` (`ShearConnection`, `check_shear_connection`, `check_shear_envelope`), la interfaz común que usan el proyecto, el comando, la memoria y la interfaz gráfica. |
| `connections/moment/` | Conexiones de momento (F6): `fr_moment` (placas de ala apernadas o soldadas y alas soldadas, placa del alma y columna bajo las fuerzas de ala; `check_moment_connection`, `check_moment_envelope`) y `end_plate` (placas de extremo de AISC Design Guides 16 y 4: líneas de fluencia, pernos con efecto palanca, demás estados límite y lado de la columna con placas de continuidad), `column_stiffening` (rigidizadores transversales y dobles placas, AISC Design Guide 13) `panel_zone` (zona de panel con la doble placa, §J10.6) y `seismic` (opción sísmica AISC 358-22: RBS, WUF-W, BFP, BUEEP y BSEEP; `seismic_checks` se agrega una vez a `check_moment_envelope` con la combinación `AISC 358`). |
| `io/` | `project` (archivo `.ocnx` con pydantic), `shear_project` (bloque `shear_connection` y su conversión a `ShearConnection`), `csi` (tablas de SAP2000/ETABS), `csi_projects` (proyectos de placa base a partir de la importación), `csi_beams` y `csi_shear_projects` (extremos de viga de SAP2000 y proyectos de conexión de corte). |
| `report/` | `builder` (estructura de la memoria; `build_report` elige entre placa base y conexión de corte), `shear` (memoria de una conexión de corte), `figures` (planta/elevación desde DXF e isométrico desde 3D), `html` (Jinja2 + MathML), `docx` (python-docx), `pdf` (Qt WebEngine). La memoria consume `Report.figures`; cada futuro tipo de conexión debe aportar sus figuras desde su propio dibujo/modelo. |
| `drawing/` | Plano DXF (ezdxf) y vistas independientes para las figuras de la memoria; `shear` dibuja la elevación de las conexiones de corte desde `shear_layout`, que también usa el modelo 3D. |
| `geometry3d/` | Sólidos OpenCASCADE, exportación STEP/STL y vista isométrica con líneas ocultas. |
| `i18n/` | Textos en `es.toml` y `en.toml`. |
| `gui/` | Interfaz PySide6: `app` (ventana principal y placa base), `shear` y `moment` (ventanas de corte y de momento), `start` (galería de inicio) y diálogos. `session` reúne lo común a las tres ventanas: `ProjectSessionMixin` (cambios sin guardar con el marcador `[*]` del título y la pregunta *Guardar / Descartar / Cancelar* al cerrar, abrir o crear; arrastrar y soltar; geometría de la ventana) y las preferencias en `QSettings` (INI de usuario: proyectos recientes, última carpeta y preset de unidades). Las preferencias nunca entran en el proyecto. `watch_changes` conecta las señales de los widgets editables del formulario; lo que cambia el proyecto sin pasar por un widget con señal (arrastre en el lienzo, bibliotecas, combos dentro de las tablas) llama a `_mark_modified` explícitamente. Las pruebas aíslan `QSettings` en una carpeta temporal y responden «Descartar» (`tests/conftest.py`). |
| `cli.py` | Comando `openconex`. |
| `data/shapes/` | `aisc_v16.sql`, base de datos de perfiles en SQL (no GPL; ver `NOTICE.md`). |

## Flujo de un cálculo (`openconex baseplate`)

1. `io.project.load_project` lee el `.ocnx` y lo valida con pydantic: tipos, campos obligatorios, nombres de casos únicos, combinaciones que citan casos existentes.
2. `Project.base_plate_model()` convierte cada cantidad a unidades internas (N, mm, MPa) y arma el `BasePlate`; `Project.case_forces()` arma las `Forces` de cada caso.
3. `Project.load_combinations()` genera las combinaciones ASCE 7-22 y agrega las propias.
4. `check_envelope` combina las fuerzas de cada combinación (`core.loads.combine`) y llama a `check_base_plate`, que devuelve una lista de `CheckResult`.
5. `report.builder` elige, para cada tipo de verificación, el resultado con mayor relación (`governing`) y arma la memoria.
6. `report.html`, `report.docx`, `drawing` y `geometry3d` escriben las salidas.

## Flujo de una conexión de momento (`openconex moment`)

Igual que el de corte: `io/moment_project.py` valida y convierte `moment_connection` en un `MomentConnection`, `check_moment_envelope` combina `V2` y `M3` (y `P`, que solo usa la placa de extremo) de cada combinación, `report/moment.py` arma la memoria y `drawing/moment.py` y `geometry3d/moment.py` el plano y el modelo. La ventana es `gui/moment.py`.

## Flujo de una conexión de corte (`openconex shear`)

1. `load_project` valida el bloque `shear_connection`: los campos que necesita cada tipo (`io.shear_project.REQUIRED`), materiales y pernos conocidos, y casos con solo `V` y `P`.
2. `Project.shear_model()` arma un `ShearConnection`: el elemento de la biblioteca (`DoubleAngle`, `SinglePlate`…), la viga y el apoyo como `IShape`, el destaje (`CopedBeam`) y los datos para la tracción.
3. `check_shear_envelope` combina las fuerzas de cada combinación y llama a `check_shear_connection`. Con `P` < 0 (tracción) usa la variante axial de la placa simple o del doble ángulo; la compresión, o la tracción en otro tipo, devuelven un resultado `shear_connection.*` que no cumple. Si hay destaje, agrega las verificaciones de `coped_beam`.
4. `report.shear.build_shear_report` arma la memoria con el mismo `Report` que la placa base; `drawing.shear` y `geometry3d.shear` escriben el plano y el modelo.

## Flujo del visor 3D (`gui.viewer3d`)

1. Cada ventana conecta todos los campos de su formulario (`session.watch_changes`) a `Viewer3D.schedule_update`, que reinicia un temporizador de 300 ms (`AUTO_DELAY_MS`).
2. Al vencer, si la pestaña está visible, `update_model` lee el proyecto del formulario en el hilo de la interfaz (`snapshot`: `project_from_form` en corte y momento, `_viewer_project` en placa base, sin diálogos). Si la pestaña está oculta, el modelo queda pendiente y se genera al mostrarla.
3. La clave de caché es el JSON del proyecto sin casos, combinaciones ni generador. Si coincide con el modelo en pantalla no se hace nada; si está entre los ocho últimos (`CACHE_SIZE`), se muestra al instante.
4. Si no, un único `_MeshWorker` en `QThreadPool` llama a `parts_3d` y a `geometry3d.mesh.tessellate_parts(max_edge=None, edges=True)`: triángulos de OpenCASCADE (deflexión 0,35 mm y 0,3 rad) y aristas vivas (`feature_edges`, ángulo entre caras > 35°). Los cambios que llegan mientras trabaja se agrupan en una sola actualización posterior, que vuelve a leer el formulario.
5. El canvas OpenGL dibuja esos triángulos con z-buffer y, en una segunda pasada, las aristas (`GL_LINES`, con `glPolygonOffset` en las caras). El canvas `QPainter` de respaldo recibe la malla subdividida a 40 mm (`subdivide_meshes`) que necesita el algoritmo del pintor; las normales se calculan una vez por modelo, no en cada cuadro.
6. Las conexiones de corte (eje y vertical) se giran con `geometry3d.mesh.y_up_to_z_up`, (x, y, z) → (x, −z, y), una rotación sin reflexión; las vistas estándar se reflejan en el giro (`180° − yaw`) para mirar desde el lado de la placa. Los desplazamientos de **Separar** (`EXPLODE_BY_TYPE`) están en los ejes del modelo y se aplican antes del giro.
7. La lista de piezas conserva las ocultas y la seleccionada; la cámara solo se reencuadra si el modelo nuevo no cabe en la vista o es mucho más pequeño (`geometry3d.mesh.keeps_framing`).

Las miniaturas de la galería (`render_parts`) siguen usando el canvas `QPainter` con su propia convención de ejes.

## Flujo de una importación (`openconex supports`)

1. `io.csi.read_tables` lee cada hoja del Excel como tabla (título, campos, unidades, filas).
2. `io.csi.import_supports` arma los `Support`: nodo, coordenadas, columna y fuerzas por caso de salida, en los ejes locales de la columna.
3. `io.csi_projects.base_plate_projects` copia la plantilla, pone la columna y las cargas, y agrupa por nodo o por sección.

`openconex beams` sigue el mismo flujo para las conexiones de corte: `io.csi_beams.import_beam_ends` lee los extremos de viga articulados, su apoyo y sus fuerzas de `Element Forces - Frames`, e `io.csi_shear_projects.shear_projects` crea los proyectos desde una plantilla de corte.

## Dependencias

Todas son compatibles con GPL-3.0 (lo comprueba `tools/check_licenses.py` en la integración continua): pint, pydantic, Jinja2, latex2mathml, python-docx, ezdxf y openpyxl; opcionales PySide6 (PDF) y cadquery-ocp-novtk (3D).
