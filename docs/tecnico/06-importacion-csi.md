# 6. Importación desde SAP2000 / ETABS

Código: `io/csi.py` (lectura) e `io/csi_projects.py` (proyectos).

## Lectura de tablas

SAP2000 exporta una tabla por hoja de Excel:
- fila 1: `TABLE:  <nombre>`;
- fila 2: nombres de los campos;
- fila 3: unidades;
- desde la fila 4: datos.

`read_tables` usa el título de la fila 1 y no el nombre de la hoja, porque Excel limita los nombres de hoja a 31 caracteres y SAP2000 los abrevia.

Las unidades de cada columna (`Kgf`, `Tonf`, `KN`, `Kip`, `m`, `cm`, `in`, `Kgf-m`, …) se convierten a N y mm. Una unidad desconocida da error.

## Apoyos y columnas

1. **Apoyos:** son los nodos de `Joint Restraint Assignments` con alguna restricción.
2. **Columna de cada apoyo:** es la barra de `Connectivity - Frame` que tiene el apoyo como extremo y cuyo centroide está sobre él (misma x e y, z mayor). Así se descartan las vigas a nivel del apoyo y se aceptan columnas definidas de arriba hacia abajo. Si hay varias, se usa la primera y se avisa.
3. **Sección, forma, material y dimensiones:** salen de `Frame Section Assignments` y `Frame Section Properties 01 - General` (t3, t2, tf, tw).
4. **Giro de los ejes locales:** sale de `Frame Local Axes Assignments 1 - Typical`.

## Fuerzas en ejes de la columna

`Joint Reactions` da F1, F2, F3, M1, M2 y M3 en ejes globales. Con el ángulo θ de los ejes locales (eje 2 = X global y eje 3 = Y global cuando θ = 0, como en SAP2000 para columnas verticales):

```
P  = F3                      (compresión positiva)
V2 =  F1 cos θ + F2 sin θ    V3 = −F1 sin θ + F2 cos θ
M2 =  M1 cos θ + M2 sin θ    M3 = −M1 sin θ + M2 cos θ     T = M3 global
```

En perfiles I, el eje fuerte es el local 3: `M` del proyecto = M3, `M_weak` = M2, `V` = V2 y `V_weak` = V3.

## Casos de salida

| Tipo de salida | Clase | Uso |
|---|---|---|
| LinStatic y otros casos de un paso | `LOAD_CASE` | Con su tipo de carga (de `Load Case Definitions`: Dead, Live, Roof Live, Snow, Rain, Wind, Quake). |
| Combination de un paso | `COMBINATION` | Ya mayorada. |
| StepType `Max` / `Min` | `ENVELOPE` | Se importa como "caso (Max)" y "caso (Min)"; las componentes no son simultáneas. |
| Modos, pasos, historia en el tiempo | — | Se omiten con aviso. |

**Marca sísmica:** se recorre la cadena combinación → casos (`Combination Definitions`) → patrones (`Case - Static 1 - Load Assignments`), hasta encontrar un patrón Quake (`Load Pattern Definitions`) o un caso de tipo Quake. La búsqueda está protegida contra ciclos.

## Proyectos

`base_plate_projects` copia la plantilla y, para cada apoyo con columna:
- **Columna:** si es un perfil I con nombre del catálogo AISC, se usa el catálogo. Si no, se crea una sección genérica (`WSectionInput` o `HSSSectionInput`). El acero se deduce del nombre del material con expresiones regulares.
- **Modo `cases`:** casos con tipo conocido y `include_code = true`, para que OpenConex genere las combinaciones de la plantilla.
- **Modo `combinations`:** cada combinación del programa es un caso de tipo `D` (marcador) con una combinación propia de factor 1,0, el método elegido y la marca sísmica.
- **Agrupación por columna (`Grouping.COLUMN`):** primero se crean los proyectos por apoyo y después se unen por sección. Los casos llevan el prefijo `"<nodo>: "`, y las combinaciones de cada apoyo (ya expandidas con `load_combinations`) se copian como combinaciones propias con los nombres prefijados. Así ninguna combinación mezcla apoyos.
- Las cantidades se escriben en N y N·mm con 10 cifras significativas.
- Los avisos que se repiten en varios nodos se juntan en uno.
