# 5. Importar desde SAP2000 / ETABS

OpenConex lee las tablas de base de datos que SAP2000 exporta a Excel. Con ellas encuentra los apoyos, la columna que nace en cada uno y sus reacciones, y crea los proyectos de placa base.

> Probado con SAP2000 v27 y con una exportación real de ETABS 23.2. También se aceptan variantes de nombres de tabla y columna (`Joint Restraints`, `Joint Reaction Forces`, `Load Cases`, `Frame Connectivity`, etc.).

## 1. Exportar desde SAP2000

1. Corra el análisis.
2. **File > Export > SAP2000 MS Excel Spreadsheet .xlsx File**.
3. Marque estas tablas. No use "Selection Only", o seleccione también las columnas además de los apoyos.

| Tabla | Para qué | ¿Necesaria? |
|---|---|---|
| Joint Coordinates | posición de los apoyos | sí |
| Joint Restraint Assignments | qué nodos son apoyos | sí |
| Joint Reactions (Analysis Results) | fuerzas por caso y combinación | sí |
| Load Case Definitions | tipo de cada caso (muerta, viva, sismo…) | recomendada |
| Load Pattern Definitions | patrones sísmicos | recomendada |
| Case - Static 1 - Load Assignments | patrones de cada caso estático | recomendada |
| Combination Definitions | casos de cada combinación | recomendada |
| Connectivity - Frame | columna de cada apoyo | para crear proyectos |
| Frame Section Assignments | sección de cada barra | para crear proyectos |
| Frame Section Properties 01 - General | dimensiones de las secciones | para crear proyectos |
| Frame Local Axes Assignments 1 - Typical | giro de los ejes locales | si alguna columna está girada |

Sin las tablas de barras, los apoyos se importan sin columna y no se pueden crear proyectos. Sin la tabla de ejes locales, se toma un giro de 0°.

ETABS comparte el esquema de base de datos CSI, pero usa tablas de objetos (`Point Object Connectivity`, `Column Object Connectivity`, `Frame Assignments - ...`) y separa los casos en `Load Case Definitions - Linear Static`, `- Nonlinear Static` y `- Response Spectrum`. OpenConex une esas tablas por `UniqueName` y normaliza las variantes de nombre más comunes. Si una versión usa otro nombre, exporte la tabla con el nombre estándar o añada el alias en `io/csi.py`.

## 2. Revisar lo importado

```bash
openconex supports modelo.xlsx
```

```
10 supports, 63 of 69 output cases

joint 50  x=6 m y=8 m  HSS6X6X3/8 (Box/Tube, frame 78, angle 0°)
  max P               23.5 kN  1.2CM+1.6CV-NL (Max)
  min P              -6.99 kN  CS17 0.6CM-0.7SY-0.21SX
  max shear V         3.55 kN  CU8  1.2CM+CV+SY-0.3SX
  max |M3|            8.29 kN⋅m  1.2CM+CV+SX-NL (Max)
  max |M2|            8.79 kN⋅m  CU8  1.2CM+CV+SY-0.3SX
```

`P` negativo es tracción. Los avisos (`warning:`) indican casos omitidos, como los modos del análisis modal o los casos sin tipo.

## 3. Preparar la plantilla

Copie `examples/base_plate_template_sap2000.ocnx` y ajuste lo que el modelo no tiene: placa (`N`, `B`, `tp`), concreto (`fc`, pedestal), anclajes (diámetro, grado, cantidad, separación, `hef`), llave de corte si la hay, y opciones (`seismic`, `SDS`, métodos). La columna y las cargas de la plantilla se reemplazan.

Si el modelo tiene casos sísmicos y se usa `--loads cases`, la plantilla debe tener `combinations.SDS` (puede ser `0`); si no, `--create` termina con un error en lugar de omitir el sismo.

## 4. Crear los proyectos

**Con los casos de carga** (OpenConex genera las combinaciones ASCE 7-22):

```bash
openconex supports modelo.xlsx --create proyectos --template plantilla.ocnx
```

**Con las combinaciones de SAP2000** (ya mayoradas), por ejemplo solo las que empiezan con "CU":

```bash
openconex supports modelo.xlsx --create proyectos --template plantilla.ocnx --loads combinations --include "^CU"
```

**Un proyecto por tipo de columna** en lugar de uno por apoyo:

```bash
openconex supports modelo.xlsx --create proyectos --template plantilla.ocnx --group column
```

Después calcule cada proyecto:

```bash
openconex baseplate proyectos/column-HSS6X6X3_8.ocnx --html --docx --dxf
```

### Qué hace la importación

- **Columna:** si la sección es un perfil W con nombre del catálogo AISC, se usa el catálogo. Si no, se crea una sección genérica (W, HSS rectangular o cuadrada, o tubo) con las dimensiones de SAP2000. El acero se deduce del nombre del material según la librería integrada. Si no se reconoce, se usa `column_grade` de la plantilla y se emite un aviso; revise ese grado antes de calcular.
- **Ejes:** las reacciones se pasan a los ejes locales de la columna. `P` es la reacción vertical (compresión positiva); `V` y `M` son las componentes en el eje fuerte (local 2 y 3) y `V_weak` y `M_weak` las del eje débil.
- **Tipos de caso:** se toman de la definición de cada caso: Dead → `D`, Live → `L`, Roof Live → `Lr`, Snow → `S`, Wind → `W`, Quake → `E`. Los casos con otro tipo (por ejemplo, nocionales) se avisan y no se usan en el modo `cases`.
- **Combinaciones sísmicas:** en el modo `combinations`, una combinación se marca como sísmica si incluye un patrón de tipo Quake, aunque sea a través de casos no lineales o de otras combinaciones.
- **Envolventes:** los casos con resultados Max/Min se importan como "caso (Max)" y "caso (Min)". Sus componentes no ocurren a la vez, así que usarlas es conservador; por eso solo se incluyen con `--envelopes`.
- **Agrupación por columna:** cada caso lleva el nodo como prefijo ("50: DEAD") y las combinaciones se forman nodo por nodo. La memoria indica el nodo y la combinación que gobiernan.

Los archivos se llaman `joint-<nodo>.ocnx` o `column-<sección>.ocnx`.
