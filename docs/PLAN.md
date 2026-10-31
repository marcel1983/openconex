# OpenConex — Plan de desarrollo

Aplicación libre (GPL-3.0) para el diseño de conexiones metálicas según AISC

Versión 2.1 · 2026-10-30

## 0. Decisiones fijadas

| Tema | Decisión |
|---|---|
| Nombre | **OpenConex** (ver §0.1) |
| Alcance | Conexiones metálicas: placas base, viga–columna, viga–viga, empalmes (y arriostramientos en fase posterior) |
| Plataforma | Escritorio multiplataforma: Windows, macOS y Linux con el mismo nivel de soporte |
| Licencia | GPL-3.0 (ver §2.3 por la compatibilidad con Osdag) |
| Normas | AISC 360-22 · AISC Steel Construction Manual 16ª ed. · Design Guides (§4) · ACI 318-19 Cap. 17 · ASCE 7-22 |
| Sísmico (opcional en el MVP) | AISC 341-22 · AISC 358-22 · ACI 318-19 §17.10 · ASCE 7-22 §12.4.3 |
| Unidades | SI, MKS e imperiales; cada magnitud se configura por separado (§6) |
| Idioma | Interfaz y memoria en español e inglés, elegidos por separado |
| Entrada de lotes | ETABS, SAP2000, Excel, CSV |
| Salidas | Memoria (PDF/DOCX/HTML), planos DXF, modelo 3D (STEP/IFC), resumen de lote (Excel) |

### 0.1 Nombre e identidad

| Elemento | Valor |
|---|---|
| Nombre comercial | OpenConex |
| Paquete Python / PyPI | `openconex` (libre en PyPI al 2026-10-30) |
| Importación | `import openconex` |
| Línea de comandos | `openconex` (p. ej. `openconex run proyecto.ocnx --report pdf --dxf`) |
| Extensión de proyecto | `.ocnx` (JSON). Se evita `.ocx`, que Windows usa para controles ActiveX |
| Repositorio GitHub | `github.com/marcel1983/openconex` (creado); organización `openconex` opcional más adelante |
| Identificador de la aplicación | `org.openconex.OpenConex` (Flatpak, macOS bundle ID, Windows AppUserModelID) |
| Dominios | `openconex.org` (principal), `.com`, `.io`, `.dev`, `.app`: todos libres al 2026-10-30 según RDAP |
| Marca | Buscar en EUIPO, WIPO Global Brand Database, USPTO y la oficina nacional; valorar registrarla |

Nombres descartados: **openXsteel** (choca con la marca Xsteel de Tekla/Trimble), **SteelJoint** (se confunde con Dlubal "Steel Joints"), **Junctura** (dominios ocupados), **SteelNode** (.com y .io ocupados).

---

## 1. Programas existentes

### 1.1 Comerciales (conexiones en general, AISC)

| Programa | Tipos de conexión | Método | Lotes | Planos |
|---|---|---|---|---|
| IDEA StatiCa Connection | Cualquier geometría | CBFEM (elementos finitos de componentes) | Sí (API, BIM) | Exporta a Tekla/Advance; no genera DXF de fabricación propio |
| RISAConnection | Corte, momento, arriostramientos, empalmes, bases | Manual AISC | Desde RISA-3D | Croquis |
| RAM Connection (Bentley) | Corte, momento, arriostramientos, empalmes, bases, sísmico AISC 341/358 | Manual AISC | Desde RAM/STAAD | Croquis DXF |
| Qnect (Bentley) | Corte, momento, arriostramientos | Manual AISC | Automático sobre modelos Tekla/Revit | En el modelo BIM |
| Tekla Tedds / Tekla Structural Designer | Bases, algunas de corte | Manual AISC | Limitado | No |
| SkyCiv Connection / Base Plate | Corte, momento, empalmes, bases | Manual AISC / DG1 | API | No |
| ASDIP STEEL, ENERCALC | Bases, corte, algunas de momento | Manual AISC | No | Croquis |
| Dlubal RFEM 6 Steel Joints | Conexiones en el modelo | Elementos finitos | Desde el modelo | No |
| Hilti PROFIS Engineering | Placas base y anclajes | CBFEM + DG1 | Limitado | No |

Lo que el mercado cubre mal: lotes importados de ETABS/SAP con agrupación en tipos, memoria con cada ecuación y su cláusula, planos DXF de fabricación, y todo eso en software libre.

### 1.2 Osdag (https://github.com/osdag-admin/Osdag) — revisión del código

**Qué es:** software libre del IIT Bombay (proyecto FOSSEE) para diseño de conexiones y miembros de acero según la norma india **IS 800:2007**. Interfaz PyQt5, modelo 3D con pythonOCC (OpenCASCADE) y memoria en LaTeX. Revisé el último commit de la rama principal (9 ene 2025).

**Conexiones que implementa** (`src/osdag/design_type/connection/`):
- Corte: placa simple (*fin plate*), ángulo doble (*cleat angle*), placa de extremo de corte, ángulo de asiento (*seated angle*).
- Momento viga–columna: placa de extremo (*end plate*).
- Empalmes: viga con cubreplacas apernadas y soldadas, viga con placa de extremo, columna con cubreplacas apernadas y soldadas, columna con placa de extremo.
- Placa base: articulada, con cartelas, para perfiles tubulares.
- Conexiones de armaduras.

**Hallazgos técnicos:**

| Aspecto | Situación | Impacto para nosotros |
|---|---|---|
| Norma | Las clases heredan directamente de `IS800_2007` (p. ej. `class BasePlateConnection(MomentConnection, IS800_2007, IS_5624_1993, …)`) | La norma está fusionada con la jerarquía de clases; cambiarla a AISC es reescribir casi todo |
| Separación cálculo/interfaz | Los módulos mezclan cálculo, validación de la interfaz, claves de diccionario de entrada, mensajes de log y llamadas a PyQt5/OCC (14 de 18 módulos importan PyQt5 u OCC) | El cálculo no se puede usar sin interfaz ni en lotes |
| Tamaño | `base_plate_connection.py`: 8 686 líneas, 70 métodos; un solo método `bp_analyses` de ≈ 2 000 líneas. 47 000 líneas en conexiones | Difícil de mantener y de verificar |
| Unidades | Fijas en mm, N, kN | No sirve el requisito de unidades configurables |
| Pruebas | Sin suite de pruebas unitarias (solo scripts sueltos como `Module_test.py`) | No hay red de seguridad para modificar |
| DXF | No genera DXF; el 2D es SVG experimental a partir del modelo 3D | Hay que construirlo de todos modos |
| Base de perfiles | SQL con perfiles indios (IS 808) | Hay que reemplazarla por perfiles AISC |
| Memoria | LaTeX (pylatex + TeX Live incluido) | Pesado de empaquetar; nosotros usamos HTML → PDF |
| Interfaz | PyQt5 (Qt 5, sin soporte desde mayo 2025) | Habría que migrar a Qt 6 |
| 3D | pythonOCC, que se instala con conda, no con pip | Empaquetado multiplataforma complicado |
| Licencia | El README y el encabezado dicen LGPL-3.0, pero el texto del archivo `LICENSE` es el de la GPL "versión 3" | Compatible con nuestro proyecto (§2.3) |
| Marca | "Osdag" y su logo son marcas registradas del IIT Bombay | Un derivado no puede llamarse Osdag |

### 1.3 Otras piezas libres reutilizables
- **ezdxf** (MIT): DXF.
- **OCP / build123d** (Apache-2.0): OpenCASCADE con paquetes pip para todas las plataformas, sustituto de pythonOCC.
- **ifcopenshell** (LGPL-3.0): exportación IFC.
- **pint**, **shapely**, **numpy/scipy**, **pydantic**, **PySide6**.
- **efficalc / handcalcs** (MIT): ideas para el formato de memoria.
- **civilpy** (licencia por verificar): solo para comparar resultados de ACI 17.

---

## 2. Estrategia: ¿fork de Osdag o proyecto propio?

### 2.1 Recomendación: proyecto propio que reutiliza piezas de Osdag
Hacer un fork de Osdag y "agregar AISC" en realidad es reescribir el cálculo de cada conexión, la interfaz (por el acoplamiento), las unidades y la memoria. Además arrastraría PyQt5, pythonOCC y LaTeX. Lo que de verdad aporta Osdag es:

| Pieza de Osdag | Cómo se reutiliza |
|---|---|
| `cad/items/` (perno, tuerca, arandela, placa, perfil I, tubos, ángulo, soldaduras de filete y ranura, rigidizadores, mortero, concreto, anclaje) | Portar a OCP/build123d (misma API de OpenCASCADE) para el visor 3D y la exportación STEP |
| `cad/*Cad/` (ensamblado 3D de cada conexión) | Referencia para la geometría y el posicionamiento de las piezas |
| Catálogo de tipologías y reglas de detallado (distancias a bordes, separación de pernos, tamaños de soldadura) | Referencia de casos que el programa debe cubrir; las reglas se reescriben con AISC J3.3–J3.5 y J2 |
| Flujo de la interfaz (entrada → preferencias de diseño → salida → 3D) | Inspiración de experiencia de usuario |
| Casos de uso y validación de su equipo | Referencia; no son válidos para AISC |

No se reutiliza el cálculo, que es IS 800 y está acoplado a la interfaz.

### 2.2 Alternativa a futuro
Diseñar el motor con normas intercambiables (§3) permitiría, más adelante, añadir IS 800 o Eurocódigo 3, e incluso proponer colaboración al equipo de Osdag.

### 2.3 Licencia
- El código derivado de Osdag (geometría 3D portada) mantiene su aviso de copyright original y se marca como tal en el encabezado.
- La licencia de Osdag dice "GPL versión 3" sin "o posterior". Si se incorpora su código, el proyecto completo se distribuye como **GPL-3.0-only**. Nuestro código propio puede marcarse como `GPL-3.0-or-later`, que es compatible.
- Antes de portar código conviene escribir al equipo de Osdag para aclarar la discrepancia LGPL/GPL y avisar del uso.
- No se usa el nombre ni el logo de Osdag.
- Se mantienen las reglas del plan anterior: revisión automática de licencias de dependencias con `pip-licenses`, DCO para contribuciones, salidas del usuario no sujetas a la GPL, términos de la AISC Shapes Database por confirmar.

---

## 3. Arquitectura

Principio: **un núcleo común de conexiones** (pernos, soldaduras, elementos conectados) sobre el que cada tipo de conexión es un módulo pequeño que combina verificaciones. Sin dependencia de la interfaz.

```
openconex/
├── core/
│   ├── model/          # Member, Plate, Angle, Tee, BoltGroup, WeldGroup, Stiffener, Pedestal…
│   ├── loads.py        # casos, combinaciones, fuerzas en el nudo (P, V2, V3, T, M2, M3)
│   ├── materials.py    # A36, A572, A992, A500, A1085, F3125 (A325/A490), F1554, E70XX, f'c
│   ├── shapes/         # catálogo AISC v16: W, M, S, HP, C, MC, L, WT, HSS, Pipe
│   └── units.py
├── kernel/                # verificaciones comunes a todas las conexiones
│   ├── bolts.py        # J3: tracción, corte, aplastamiento/desgarro, deslizamiento, interacción
│   ├── bolt_group.py   # análisis elástico y centro instantáneo de rotación (Manual Parte 7)
│   ├── welds.py        # J2: filete, ranura PJP/CJP, resistencia direccional
│   ├── weld_group.py   # análisis elástico y centro instantáneo de rotación (Manual Parte 8)
│   ├── elements.py     # J4: fluencia/rotura en tracción y corte, bloque de corte, pandeo de placas
│   ├── prying.py       # acción de palanca (Manual Parte 9)
│   ├── coped_beam.py   # vigas con destaje (Manual Parte 9)
│   ├── flange_web.py   # J10: flexión local del ala, fluencia y aplastamiento del alma, pandeo, zona de panel
│   └── stiffeners.py   # rigidizadores y placas de refuerzo (J10.8, DG13)
├── connections/           # cada tipo = un módulo: geometría + lista de verificaciones + reglas de detallado
│   ├── base_plate/     # placas base (DG1)
│   ├── shear/          # viga–columna y viga–viga de corte
│   ├── moment/         # viga–columna de momento
│   ├── splice/         # empalmes de viga y columna
│   └── bracing/        # fase posterior
├── codes/              # aisc360_22, aisc341_22, aisc358_22, aci318_19, asce7_22, dg1, dg4/16, dg13
├── solver/             # presiones en placa base, distribución de fuerzas en placas de extremo
├── optimize/           # búsqueda de la conexión mínima que cumple
├── io/                 # proyecto .ocnx (JSON), Excel/CSV, tablas de ETABS/SAP, API de CSI (opcional)
├── report/             # memoria a partir de la traza (ES/EN)
├── drawing/            # DXF parametrizado por tipo de conexión
├── geometry3d/         # modelo 3D con OCP (piezas portadas de Osdag), STEP/IFC
├── i18n/
├── cli/
└── gui/                # PySide6
```

- **Traza de cálculo:** cada verificación devuelve `CheckResult(id, demanda, capacidad, ratio, cláusula, traza, combo)`. Memoria, interfaz y lote solo la muestran.
- **Interfaz de conexión común:** todos los tipos implementan `geometry()`, `checks()`, `detailing_rules()`, `drawing()`, `model3d()` y `optimize()`. La interfaz, los lotes, la memoria y los planos funcionan igual para todas las conexiones.
- **Normas intercambiables:** `codes/` define factores φ/Ω y ecuaciones; el núcleo los recibe, no los hereda.

---

## 4. Catálogo de conexiones y referencias

### Placas base (Manual Parte 14, DG1 3ª ed., ACI 318-19 Cap. 17)
Todo lo del plan anterior: compresión, momento en uno y dos ejes, tracción, corte por fricción, por anclajes o por llave de corte, anclajes ACI 17 completos, soldadura y opción sísmica.

### Viga–columna y viga–viga de corte (Manual Parte 10)
| Conexión | Notas |
|---|---|
| Placa simple (*shear tab*), convencional y extendida | Verificación de la placa, del ala o alma de apoyo, pernos con excentricidad |
| Ángulo doble apernado/soldado | Tablas 10-1 a 10-3 reproducidas por cálculo |
| Placa de extremo de corte | |
| Ángulo simple | |
| Ángulo de asiento sin rigidizar y rigidizado | |
| Conexión en T (*tee*) | |
| Viga con destaje superior, inferior o doble | Bloque de corte y pandeo local del destaje |
| Al alma de columna, al ala de columna, a viga principal (viga–viga) | |

### Viga–columna de momento (Manual Parte 12, DG4, DG16, DG13)
| Conexión | Notas |
|---|---|
| Placas de ala apernadas (*flange-plated*) | |
| Alas soldadas directamente (CJP) | |
| Placa de extremo extendida y al ras, 4E, 4ES, 8ES (DG4/DG16) | Rigidizadores de la placa, acción de palanca |
| Verificación de la columna | Flexión local del ala, alma, zona de panel, rigidizadores, placas de refuerzo (DG13) |
| Sísmicas precalificadas (AISC 358-22, opción) | RBS, BUEEP/BSEEP, BFP, WUF-W |

### Empalmes (Manual Parte 14 para columnas, Partes 12 y 9 para vigas)
| Conexión | Notas |
|---|---|
| Empalme de viga con cubreplacas de ala y alma apernadas | |
| Empalme de viga soldado (CJP o con cubreplacas) | |
| Empalme de viga con placa de extremo | |
| Empalme de columna con cubreplacas apernadas o soldadas, con o sin placa separadora | Cambio de perfil, apoyo directo |
| Empalme de columna con placa de extremo | |
| Requisitos sísmicos de empalmes de columna (AISC 341 D2.5) | Opción |

### Arriostramientos (fase posterior, Manual Parte 13)
Cartela con Whitmore, método de la fuerza uniforme (UFM), riostras HSS y de ángulos.

---

## 5. Lotes e importación
- **Plantilla Excel/CSV:** una hoja por tipo de conexión con las piezas conectadas, más una hoja de fuerzas por combinación.
- **ETABS/SAP2000 por tablas** (funciona en los tres sistemas):

| Tabla | Uso |
|---|---|
| `Joint Reactions` | Placas base |
| `Element Forces – Frames` (en los extremos I/J) | Viga–columna, viga–viga |
| Fuerzas en la estación del empalme | Empalmes |
| Conectividad, secciones, ejes locales, *releases* | Asignar la tipología automáticamente: articulado → corte, continuo → momento |
| Definición de combinaciones | Marcar las sísmicas |

- **Transformación de ejes** de global o local del elemento a los ejes de la conexión, con vista previa.
- **Agrupación** de conexiones iguales en tipos (BP-1, SC-3, MC-2…), con optimización y uniformidad por tipo.
- **API de CSI en vivo:** fase posterior, solo Windows.

**Estado (2026-10-31):** primer paso de la F4 hecho. `openconex.io.csi` lee las tablas exportadas a Excel por SAP2000 (probado con una exportación real de SAP2000 v27, en kgf y m): nodos con apoyo, reacciones por caso, combinación o envolvente (Max/Min), tipo de cada caso (D, L, Lr, S, W, E), columna conectada a cada apoyo con su sección y dimensiones, y giro de sus ejes locales. Las reacciones se pasan a los ejes locales de la columna. El comando `openconex supports archivo.xlsx` lista los apoyos y las reacciones que gobiernan, y con `--create carpeta --template plantilla.ocnx` escribe un proyecto de placa base por apoyo, con la columna importada y las cargas: los casos de carga (OpenConex genera las combinaciones ASCE 7-22) o las combinaciones del programa (ya factorizadas, con filtro por nombre y marca sísmica deducida de los patrones Quake). La placa base se verifica a flexión biaxial (DG1 §4.3.7): cada eje por separado y la interacción de la Ec. 4-69, validada contra el Ejemplo 4.7-14; el proyecto guarda V y M de ambos ejes (`V_weak`, `M_weak`). Con `--group column` se crea un proyecto por sección de columna con los casos de todos sus apoyos (prefijados con el nodo y combinados nodo por nodo); `--group joint` (por defecto) crea uno por apoyo. La placa base admite una llave de corte (DG1 §4.5, Ejemplo 4.7-5; ACI 318-19 §17.11) en una dirección o en cruz. ETABS 23.2 está soportado mediante tablas de objetos y unión por `UniqueName`. La llave de corte ya se dibuja en DXF, se modela en 3D y se comprueba la flexión local de la placa con ancho efectivo igual al ancho de la llave.

## 6. Unidades e idiomas
Sin cambios respecto a la versión 1.2: cada magnitud se configura por separado, internamente todo se guarda en SI, las ecuaciones empíricas se evalúan en sus unidades originales, y la invariancia de unidades se prueba automáticamente. Interfaz y memoria en ES/EN por separado, con glosario controlado.

## 7. Salidas
- **Memoria:** HTML → PDF (Qt WebEngine) y DOCX, con ecuaciones y cláusulas, figura de la conexión y tabla resumen.
- **DXF:** generadores parametrizados por tipo de conexión. Vistas en planta, elevación y cortes, cotas de gramil y separación de pernos, símbolos de soldadura AWS A2.4, lista de materiales y cajetín. Capas estándar.
- **3D:** visor en la aplicación (OCP, pyvista) y exportación STEP. IFC en fase posterior para BIM.
- **Opción futura:** obtener las líneas de las vistas del DXF a partir del modelo 3D (eliminación de líneas ocultas de OpenCASCADE) y añadir las cotas paramétricas encima. Así 3D y 2D nunca discrepan.

## 8. Pila tecnológica
Python 3.12+, PySide6 (Qt 6), pydantic, pint, shapely, numpy/scipy, OCP/build123d (3D, en lugar de pythonOCC), ezdxf, Jinja2 + Qt WebEngine, python-docx, openpyxl/pandas, platformdirs, pytest/hypothesis/pytest-qt, PyInstaller. CI en Windows, macOS y Linux. Paquetes MSI/MSIX, `.dmg`, AppImage/Flatpak y pip (sin cambios respecto a la versión 1.2).

---

**Documentación (2026-10-31):** manual de usuario en `docs/usuario/` y documentación técnica en `docs/tecnico/`. Se actualizan en el mismo pull request que cada cambio; `tests/test_docs.py` comprueba que verificaciones, comandos, campos del proyecto, ejemplos y materiales estén documentados.

## 9. Hoja de ruta

**Estado (2026-10-30):** F0 terminada. F1 (núcleo de verificaciones) implementada en `src/openconex/kernel/`: pernos (§J3), soldaduras (§J2), elementos (§J4), efecto palanca (Manual Parte 9), grupos de pernos y de soldaduras por los métodos elástico y del centro instantáneo, y fuerzas concentradas (§J10). Grupos de pernos excéntricos validados contra la Tabla 7-6 del Manual (ángulos 0° a 60°, s = 3 y 6 in, n = 2 a 12, y C'); y contra las Tablas 7-7 y 7-8 (dos filas verticales con gramil de 3 y 5½ in; ángulos 0°, 30° y 60°; s = 3 y 6 in; n = 1 a 12; ex = 2 a 36 in; y C'): 1 776 valores dentro del 1 %, sin cambios en el cálculo. Grupos de soldaduras validados contra las Tablas 8-4 (ángulos 0°, 45° y 75°) y 8-5 (0° y 60°), k = 0 a 2,0 y a = 0 a 3,0: 496 valores dentro del 0,6 %; y contra las Tablas 8-7 (caja; 0° y 60°), 8-8 (C con la carga hacia el lado abierto; 0° y 60°) y 8-9 (C con la carga del lado del alma; 60°), a = 0 a 3,0: otros 1 760 valores dentro del 0,6 %. Y contra las Tablas 8-6 (caja; 15° y 60°), 8-10 (L con la carga del lado del ala; 0° y 60°) y 8-11 (L con la carga del lado del alma; 60°): otros 1 760 valores dentro del 1 %. En total, 4 016 valores de las Tablas 8-4 a 8-11. El método ICR aplica el coeficiente C1 de la Tabla 8-3 para electrodos distintos de E70.

**F2 (placas base)** implementada en `src/openconex/connections/base_plate/` y `src/openconex/kernel/anchors.py` (ACI 318-19 Cap. 17): compresión, flexión rectangular y triangular, levantamiento, flexión biaxial, corte (fricción, llave de corte, anclajes con flexión), tracción, soldaduras, base débil sísmica y base empotrada, con verificación completa por combinación. Los 20 ejemplos de la DG1 son pruebas de aceptación (369 valores publicados comparados).

**F3 (salidas)** implementada para placas base: archivo de proyecto `.ocnx` (JSON), memoria de cálculo ES/EN en HTML (ecuaciones MathML), DOCX y PDF (Qt WebEngine, extra `pdf`), plano DXF R2013 (planta, elevación, lista de materiales, notas y cajetín) y modelo 3D STEP/STL (OpenCASCADE, extra `3d`), todo desde `openconex baseplate`. La memoria PDF se genera con Qt WebEngine en lugar de WeasyPrint, como estaba previsto.

| Fase | Contenido | Duración (1 desarrollador) |
|---|---|---|
| F0 | Repositorio, CI multiplataforma, licencias, modelos, unidades, catálogo AISC, traza y estructura de las verificaciones | 4 sem |
| F1 | **Núcleo de conexiones:** pernos, grupos de pernos (elástico y centro instantáneo), soldaduras y grupos, elementos J4, acción de palanca, J10 | 8 sem |
| F2 | **Placas base** completas, con opción sísmica | 8 sem |
| F3 | Memoria ES/EN, DXF y visor 3D genéricos (sobre la interfaz común de conexión), con placa base como primer caso | 6 sem |
| F4 | Interfaz: individual y por lotes; importación de Excel, CSV, ETABS y SAP | 7 sem |
| — | **Versión 1.0: placas base completas sobre la plataforma final** | **≈ 33 sem (≈ 8 meses)** |
| F5 | **Corte viga–columna y viga–viga** (Parte 10, destajes) | 8 sem |
| F6 | **Momento viga–columna** (Parte 12, DG4/16, DG13), con AISC 358 como opción sísmica | 10 sem |
| F7 | **Empalmes** de viga y columna | 6 sem |
| F8 | Validación cruzada, manual de verificación, instaladores | 4 sem |
| — | **Versión 2.0: todos los tipos pedidos** | **≈ 61 sem (≈ 14 meses)** |
| Posterior | Arriostramientos, perfiles tubulares (DG24), IFC, API de CSI en vivo, placa flexible por elementos finitos | — |

Con dos desarrolladores (uno en el motor y las conexiones, otro en interfaz, memoria, DXF y 3D) la versión 2.0 baja a unos 9–10 meses.

**Por qué el núcleo va primero:** las placas base usan pernos, soldaduras y elementos que después reutilizan todas las demás conexiones. Programarlo bien una vez acelera F5–F7.

## 10. Validación
- Ejemplos resueltos de AISC (Companion to the Manual, ejemplos de diseño v16), DG1, DG4/DG16 y DG13 como pruebas automáticas, usando solo datos numéricos.
- Tablas del Manual (pernos con excentricidad, Tabla 7-6 a 7-14; soldaduras, Tabla 8-4 a 8-11; Parte 10) recalculadas y comparadas, con tolerancia ≤ 1 %.
- Invariancia de unidades.
- Comparación con RAM Connection, RISAConnection o SkyCiv en 20 casos por tipo.
- Pruebas de regresión en CI y manual de verificación ES/EN.

## 11. Riesgos

| Riesgo | Mitigación |
|---|---|
| El alcance crece demasiado | Versión 1.0 solo con placas base sobre la plataforma completa; cada familia de conexiones es una versión aparte |
| Centro instantáneo de rotación (grupos de pernos y soldaduras) | Algoritmo iterativo validado contra las tablas del Manual |
| Variedad de tipologías y reglas de detallado | Interfaz común de conexión y reglas de detallado declarativas |
| Precalificadas sísmicas (AISC 358) | Opción en F6, con límites de precalificación verificados explícitamente |
| Licencia de Osdag ambigua | Consultar al equipo; distribuir como GPL-3.0-only si se incorpora su código |
| Portar el 3D de pythonOCC a OCP | API casi idéntica; empezar por las piezas sencillas |
| AISC Shapes Database y ejemplos del Manual | **Decisión:** el catálogo se incluye como SQL de texto (`data/shapes/aisc_v16.sql`, generado con `tools/build_shapes_db.py`) con aviso de atribución (`NOTICE.md`) y fuera de la GPL. Pedir permiso a AISC; si lo niega, se retira y se genera en la instalación. En las pruebas, solo datos numéricos |
| Compatibilidad del DXF y firma de instaladores | Ver versión 1.2 del plan |

## 12. Próximos pasos
1. **Reservar la identidad:**
   - ~~Crear el repositorio en GitHub~~ (hecho: `marcel1983/openconex`); opcionalmente crear la organización `openconex` y transferirlo.
   - Registrar `openconex.org` (y opcionalmente `.com`).
   - Publicar un paquete mínimo `openconex` 0.0.1 en PyPI para reservar el nombre.
   - Buscar la marca en EUIPO, WIPO, USPTO y la oficina nacional.
2. F0: estructura `openconex/`, `LICENSE`, encabezados SPDX, CI, `units.py`, modelos y catálogo de perfiles.
3. Escribir al equipo de Osdag sobre la licencia y el uso del código 3D.
4. Transcribir los ejemplos de AISC y DG1 como pruebas antes de implementar el núcleo.
