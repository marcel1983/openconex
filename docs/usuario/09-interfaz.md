# 9. Interfaz gráfica

> **Estado: edición completa, geometría, visor 3D, importación y cálculo por lotes (F4.1).** La interfaz permite editar todos los bloques de una placa base: expuesta, base débil, base empotrada Tipo I, llave de corte, refuerzo de anclaje, opciones avanzadas y combinaciones. También incluye un editor gráfico de planta y elevación, un visor 3D interactivo, importa apoyos de SAP2000/ETABS o de una tabla Excel/CSV, crea un proyecto por apoyo o por sección de columna, calcula una carpeta completa con sus reportes y exporta el resumen del lote a Excel.

## Instalación

La interfaz usa PySide6; el visor 3D usa OpenCASCADE:

```bash
pip install -e ".[gui,3d]"
```

Sin el extra `3d`, el resto de la interfaz funciona y la pestaña 3D muestra un aviso.

## Abrir

```bash
openconex-gui
```

o directamente con un proyecto:

```bash
openconex-gui examples/base_plate_dg1_4_7_11.ocnx
```

## Flujo de trabajo

1. **Archivo > Abrir** para cargar un `.ocnx`.
2. Elegir el **tipo de conexión**:
   - **Placa base expuesta**, con sus dimensiones, anclajes y bloques opcionales.
   - **Base empotrada Tipo I**, con el empotramiento, el pedestal y el refuerzo horizontal.
3. Elegir la **columna** en el desplegable. El campo es editable: se puede escribir una etiqueta AISC (`W12X96`) y el autocompletado filtra el catálogo.
4. Elegir los materiales en los desplegables:
   - **Grado de columna** y **Acero de la placa**: aceros de AISC o materiales propios del proyecto.
   - **Grado de anclaje**: grados de pernos y barras de anclaje de AISC 360-22.
5. Editar las dimensiones y los datos del concreto. Cada valor muestra su unidad a la derecha; las unidades se cambian desde **Unidades**.
6. Completar, si hace falta:
   - **Opciones de cálculo**;
   - **Llave de corte**;
   - **Refuerzo de anclaje**;
   - **Base débil sísmica**;
   - **Barras del pedestal**.
7. Añadir, modificar o eliminar casos de carga en la tabla.
8. Revisar **Combinaciones**: métodos LRFD/ASD, generación ASCE 7-22, `SDS`, `ρ` y `Ω0`.
9. Pulsar **Calcular** o `F5`.
10. Revisar:
    - la pestaña **Resumen**, con demanda, capacidad, relación y estado;
    - la pestaña **Verificaciones**, con la traza y la cláusula;
    - la pestaña **Figuras**, con planta, elevación e isométrico.
11. **Archivo > Guardar** o **Guardar como** para conservar los cambios.
12. **Exportar** para generar HTML, DOCX, PDF, DXF, STEP o STL.

El botón **Optimizar** reduce N, B y tp con el mismo criterio que `openconex baseplate --optimize`. Se desactiva en las bases empotradas.

## Geometría

La pestaña **Geometría** muestra la planta y la elevación de la placa y permite cambiar las dimensiones arrastrando:

- los **bordes de la placa** para ajustar `N` y `B`;
- los **anclajes exteriores** para ajustar `f` y la separación entre barras;
- los **bordes del pedestal**, si está definido, para ajustar `pedestal_N` y `pedestal_B`;
- en elevación, los hitos de **espesor de placa**, **mortero** y **empotramiento `hef`**.

Los cambios se reflejan inmediatamente en el formulario y en las etiquetas de unidad. **Deshacer** (`Ctrl+Z`) y **Rehacer** (`Ctrl+Y`) revierten los cambios gráficos. Los controles impiden reducir la placa por debajo de la columna, cruzar los anclajes o dejar espesores no positivos; la validación completa se ejecuta al calcular o guardar.

La columna se elige en el desplegable **Columna**; su huella en planta se actualiza con la sección seleccionada.

## Visor 3D

La pestaña **3D** muestra el modelo de sólidos generado con OpenCASCADE:

- **Arrastrar** con el botón izquierdo para girar.
- **Rueda** para acercar o alejar.
- **Arrastrar con el botón central o derecho** para desplazar la vista.
- **Doble clic** o **Ajustar vista** para volver a la vista isométrica.
- La lista **Piezas** permite ocultar o mostrar cada sólido y resaltar una pieza al seleccionarla.

El modelo se genera en segundo plano al entrar en la pestaña, con las piezas de `geometry3d.base_plate` (`base_plate_parts` o `embedded_base_parts`). Funciona con placa expuesta y base empotrada. La exportación STEP/STL no cambia.

## Tipos de conexión

### Placa base expuesta

Muestra los campos de la placa, el pedestal, el mortero y los anclajes. Admite los bloques opcionales de llave de corte, refuerzo de anclaje y base débil.

### Base empotrada Tipo I

Sustituye el formulario expuesto por los datos de la DG1 Capítulo 5:

- empotramiento de la columna;
- ancho del pedestal;
- espesor de la placa frontal;
- `β1`;
- placa embebida opcional (ancho y espesor, ambos o ninguno);
- límite de daño;
- refuerzo horizontal superior e inferior, cada uno con área, `fy` y profundidad.

El motor exige LRFD, perfiles I y ausencia de momento débil, llave de corte o base débil. La interfaz desactiva los bloques incompatibles y muestra el error del proyecto si alguna combinación no cumple.

## Opciones de cálculo

- **Modelo de presión:** rectangular (DG1 §4.3) o triangular (DG1 Ap. B.2).
- **Área de apoyo:** placa completa o área efectiva (DG1 Ap. B.3).
- **Brazo de flexión de placa:** distancia del anclaje al alma o ala.
- **Área de apoyo del anclaje:** área de la tuerca o placa embebida para la extracción.
- **Arandela soldada:** espesor de la arandela; activa el reparto del corte entre todas las barras.
- **Soldadura de ala:** tamaño de la soldadura de filete de la columna y electrodo.
- **Coeficiente de fricción** placa-concreto.
- **Bordes del concreto:** izquierdo, derecho, inferior y superior; si se omiten, se deducen del pedestal.
- **Barras del pedestal:** tabla de posición `x`, `y` y diámetro para el revisor de interferencias.

Los campos opcionales muestran la palabra «opcional» y se pueden dejar vacíos.

## Bloques especiales

### Llave de corte

Se activa con la casilla del grupo. Incluye ancho `b_sl`, empotramiento `h_sl`, espesor, soldadura, dirección (fuerte, débil o cruz), acero, electrodo y distancias `c_a1`/`c_a2` opcionales.

### Refuerzo de anclaje

Se activa con la casilla del grupo. Incluye la etiqueta de barras, área total, `fy`, diámetro, recubrimiento, distancia anclaje-barra y desarrollo disponible.

### Base débil sísmica

Se activa con la casilla del grupo. Incluye el diámetro reducido, la longitud de estiramiento y `Rt`. Requiere LRFD, presión rectangular y ausencia de momento débil.

## Combinaciones

- **Métodos:** LRFD y/o ASD.
- **Generar combinaciones ASCE 7-22:** activa o desactiva las combinaciones del código.
- **Factor de carga viva**, **`SDS`**, **`ρ`** y **`Ω0`**.
- **Combinaciones propias:** tabla editable con nombre, método, factores, marca sísmica, sobre-resistencia, incremento ASD y fuente. **Añadir**, **Duplicar** y **Eliminar** gestionan las filas.
  - Factores por caso con el formato `D=1.2; L=1.6`.
  - Los nombres de caso deben existir en la tabla de casos.
  - El incremento ASD debe ser mayor o igual que 1.

Si hay casos sísmicos y se generan combinaciones del código, `SDS` es obligatorio. Use `SDS = 0` para omitir el efecto vertical `Ev`.

Las verificaciones de concreto de ACI 318 se ejecutan solo con combinaciones **LRFD**. En **ASD** los anclajes se revisan como pernos según AISC 360-22 §J3.

## Importar SAP2000 / ETABS

**Archivo > Importar SAP2000 / ETABS…** crea proyectos de placa base a partir de la exportación de tablas a Excel. El proyecto abierto actúa como plantilla: aporta la placa, el concreto, los anclajes y las opciones; la columna y las cargas se toman del modelo.

Opciones del diálogo:

- **Archivo CSI:** exportación `.xlsx` de SAP2000 o ETABS.
- **Salida:** carpeta donde se escriben los `.ocnx`.
- **Agrupación:** un proyecto por apoyo o uno por sección de columna.
- **Cargas:** casos de carga (OpenConex genera las combinaciones) o combinaciones del programa ya factorizadas.
- **Incluir:** expresión regular opcional para filtrar casos o combinaciones.
- **Envolventes:** incluye Max/Min cuando se importan combinaciones.
- **Método:** LRFD, ASD o el de la plantilla.

Los proyectos creados se pueden abrir uno a uno para revisar, calcular y exportar. Los avisos de la importación (apoyos sin columna, secciones no admitidas, casos omitidos) se muestran al terminar.

## Importar Excel / CSV

**Archivo > Importar Excel / CSV…** crea proyectos de placa base desde una tabla propia. La primera fila es la cabecera y cada fila es un caso de un apoyo:

| Columna | Uso |
|---|---|
| `support` | Nombre del apoyo o proyecto (obligatorio). |
| `case` | Nombre del caso de carga (obligatorio). |
| `type` | Tipo ASCE 7-22: `D`, `L`, `Lr`, `S`, `R`, `W`, `WT` o `E`; por defecto `D`. |
| `column` | Etiqueta AISC o sección propia; si se omite, se usa la columna de la plantilla. |
| `P` | Fuerza axial, compresión positiva. |
| `V` | Corte en el eje fuerte. |
| `M` | Momento en el eje fuerte. |
| `V_weak` | Corte en el eje débil. |
| `M_weak` | Momento en el eje débil. |

Los números sin unidad usan el sistema elegido en el diálogo; también se puede escribir la unidad en la celda (`"25 kN"`). El proyecto abierto actúa como plantilla (placa, concreto, anclajes y opciones) y se genera un `.ocnx` por apoyo. Las combinaciones se generan con ASCE 7-22; si hay casos sísmicos, la plantilla debe tener `SDS`.

## Ayuda y tooltips

Cada campo de las ventanas de placa base y conexión de corte tiene un **tooltip** con tres datos: qué es, cómo se usa y cómo afecta al cálculo. El menú **Ayuda** incluye:

- **Guía rápida** (`F1`): flujo de trabajo.
- **Referencia de campos**: lista buscable de todos los campos.
- **Menús y acciones**: qué hace cada acción.
- **Verificaciones**: cómo leer demanda, capacidad, relación y estado.
- **Acerca de**: versión y licencia.

La misma información está en [Referencia de la conexión de corte](10-referencia-conexion-corte.md) y [Referencia de la placa base](11-referencia-placa-base.md), generadas desde la fuente de ayuda del programa. La referencia de placa base incluye además los diálogos auxiliares (importación, unidades, bibliotecas y lote).

## Conexiones de corte

**Archivo > Nueva conexión de corte…** abre una ventana propia para las conexiones de extremo de viga. Al abrir un `.ocnx` con `shear_connection` desde la ventana principal, se abre también en esa ventana.

1. Elegir el **tipo**: doble ángulo, placa simple, placa extendida, placa de extremo, asiento o asiento rigidizado. Solo se muestran los campos de ese tipo; los obligatorios llevan `*`.
2. Elegir la **viga** y el **apoyo** (catálogo W, editable) y si la conexión va al **ala** o al **alma** del apoyo.
3. Escribir el material, el electrodo, los pernos y la geometría. Las cantidades se escriben con su unidad (`3 in`, `75 mm`); un número sin unidad usa las unidades del proyecto.
4. Marcar **Destaje de la viga** si la viga está destajada. Dentro del mismo grupo se puede activar la **placa doble** o el **rigidizador longitudinal** y editar sus dimensiones y soldadura.
5. Completar los casos de carga con `V` y `P` (tracción negativa) y los métodos LRFD/ASD.
6. **Calcular** (`F5`): pestañas **Resumen**, **Verificaciones**, **Figuras** (elevación e isométrico) y **3D**.
7. **Archivo > Guardar** y **Exportar** a HTML, Word, PDF, DXF, STEP o STL.

El cálculo por lotes también admite proyectos de conexión de corte; en el resumen, la columna muestra la viga.

## Cálculo por lotes

**Cálculo > Calcular lote…** calcula una carpeta completa de proyectos `.ocnx` sin abrirlos uno a uno.

- **Proyectos:** carpeta de entrada; se puede incluir subcarpetas.
- **Salida:** carpeta de los reportes; si se deja vacía, se usa la de entrada.
- **Salidas:** HTML, Word, PDF, DXF, STEP y/o STL; el resumen en pantalla siempre se genera.
- **Progreso y cancelación:** el lote se puede cancelar; el proyecto en curso termina y no se empieza el siguiente.
- **Resumen:** tabla con proyecto, estado (OK/NG/ERROR), relación gobernante, verificación, combinación y error.
- **Exportar Excel…:** guarda el mismo resumen en un libro `.xlsx`, con archivo, columna y salidas generadas.

Cada proyecto se calcula con sus propios datos; el formulario abierto no se modifica. Un proyecto con error no detiene el resto del lote.

## Unidades

El menú **Unidades** ofrece los presets `SI (kN, m)`, `SI (N, mm)`, `MKS (tf, m)` y `US (kip, in)`, y **Configurar por magnitud…** para elegir la unidad de longitud, espesor, fuerza, momento, tensión, área, fuerza por longitud, módulo de sección e inercia.

Al cambiar de unidades:

- se convierten los valores del formulario, los bloques especiales, la tabla de barras del pedestal y la tabla de casos;
- se actualizan las etiquetas de unidad junto a cada campo y en las cabeceras de las tablas;
- se convierten las dimensiones de las secciones personalizadas;
- se invalida el resultado anterior hasta volver a calcular.

Los números se pueden escribir con su unidad (`"3/4 in"`, `"25 mm"`, `"120 kN*m"`); si se omite, se usa el preset activo.

## Biblioteca de secciones

**Bibliotecas > Secciones…** abre el catálogo AISC incluido (perfiles W, M, S y HP) con búsqueda por etiqueta y filtro por tipo. La tabla muestra las dimensiones en las unidades activas. **Usar sección** la lleva al formulario principal.

**Nueva sección…** crea una sección genérica:

- tipo W, HSS rectangular, HSS cuadrada o HSS redonda;
- nombre propio;
- dimensiones y material.

Las secciones creadas se guardan en el bloque `sections` del proyecto y aparecen en el desplegable de columna, también al volver a abrir el archivo. El motor admite secciones W genéricas y HSS genéricas; las etiquetas del catálogo se limitan a W, M, S y HP.

## Biblioteca de materiales

**Bibliotecas > Materiales…** muestra tres pestañas:

- **Columnas y placas**: aceros de AISC 360-22 y materiales propios del proyecto. **Nuevo material…** crea un acero con nombre, Fy, Fu y E; queda disponible para columnas, placas y llaves de corte.
- **Pernos y anclajes**: grados de AISC 360-22 Tabla J3.2 y grados propios del proyecto. **Nuevo perno…** crea un grado con Fnt, Fnv, Fu y Fy.
- **Soldadura**: electrodos E70XX/E80XX y electrodos propios. **Nuevo electrodo…** crea un electrodo con su FEXX.

## Alcance actual

- Edición de los datos generales y de todos los bloques de la placa base.
- Editor gráfico de planta y elevación con deshacer/rehacer.
- Visor 3D interactivo con rotación, zoom, ocultación y resaltado de piezas.
- Selección de secciones del catálogo y creación de secciones W/HSS genéricas.
- Selección de materiales de columna, placa, anclaje y llave de corte; creación de aceros, pernos y electrodos propios.
- Cambio de unidades por preset o por magnitud, con conversión del formulario y de los bloques especiales.
- Edición de casos de carga, opciones de combinaciones y combinaciones propias.
- Importación de SAP2000/ETABS y Excel/CSV, con creación de proyectos por apoyo o por sección.
- Cálculo y reporte por lotes de una carpeta de proyectos.
- Cálculo individual, resumen, traza y figuras.
- Exportación a los formatos disponibles.
- Ventana de conexiones de corte: edición (incluido el refuerzo del destaje), cálculo, figuras, 3D y exportación.

## Limitaciones

- La ventana de conexiones de corte convierte automáticamente las unidades al cambiar el preset. No tiene editor gráfico 2D.
- La huella de la columna se selecciona con el desplegable de sección; no se edita arrastrando en el lienzo.
- El visor 3D requiere el extra `3d` (OpenCASCADE); sin él, la pestaña muestra un aviso.
- La interfaz no sustituye la revisión del profesional responsable.
