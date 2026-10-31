# 4. Comandos

Todo se usa con el comando `openconex`. `openconex --help` y `openconex <comando> --help` muestran la ayuda; `openconex --version` muestra la versión.

## `openconex baseplate`: calcular una placa base

```bash
openconex baseplate proyecto.ocnx [opciones]
```

Calcula todas las combinaciones del proyecto, imprime la verificación que gobierna de cada tipo y escribe las salidas pedidas. Devuelve 0 si todo cumple y 1 si algo no cumple.

| Opción | Efecto |
|---|---|
| `-o`, `--output RUTA` | Ruta de las salidas, sin extensión (por defecto, la del proyecto). |
| `--lang es\|en` | Idioma de la memoria y los planos (por defecto, `info.language`). |
| `--units SISTEMA` | Sistema de unidades de las salidas: `SI_kN_m`, `SI_N_mm`, `MKS` o `US` (por defecto, `info.units`). |
| `--html` | Memoria HTML. |
| `--docx` | Memoria Word. |
| `--pdf` | Memoria PDF (requiere el extra `pdf`). |
| `--dxf` | Plano DXF. |
| `--step` | Modelo 3D STEP (requiere el extra `3d`). |
| `--stl` | Modelo 3D STL (requiere el extra `3d`). |

## `openconex supports`: apoyos de SAP2000 / ETABS

```bash
openconex supports modelo.xlsx [opciones]
```

Lee las tablas exportadas a Excel y lista cada apoyo con su columna y las reacciones que gobiernan. Con `--create`, escribe además los proyectos de placa base. Detalles en [Importar desde SAP2000 / ETABS](05-importar-sap2000.md).

| Opción | Efecto |
|---|---|
| `--units SISTEMA` | Unidades del listado (por defecto `SI_kN_m`). |
| `--all-cases` | Incluye en el listado los casos de carga sin mayorar (por defecto, solo combinaciones y envolventes). |
| `--create CARPETA` | Escribe los proyectos `.ocnx` en la carpeta. |
| `--template ARCHIVO` | Proyecto plantilla con placa, concreto, anclajes y opciones (obligatorio con `--create`). |
| `--loads cases\|combinations` | `cases` (por defecto): casos de carga, y OpenConex genera las combinaciones. `combinations`: las combinaciones del programa, ya mayoradas. |
| `--include REGEX` | Solo los casos o combinaciones cuyo nombre coincide con la expresión regular, por ejemplo `"^CU"`. |
| `--envelopes` | Con `--loads combinations`, usa también las envolventes Max/Min. |
| `--group joint\|column` | `joint` (por defecto): un proyecto por apoyo. `column`: un proyecto por sección de columna. |
| `--method LRFD\|ASD` | Método de las combinaciones importadas (por defecto, el primero de la plantilla). |

## `openconex convert`: convertir unidades

```bash
openconex convert "3/4 in" thickness --to mm
```
```bash
openconex convert "250 kN*m" moment --system US
```

El primer argumento es la cantidad con su unidad y el segundo la magnitud (`length`, `thickness`, `force`, `moment`, `stress`, `area`, `force_per_length`, `section_modulus`, `moment_of_inertia`, `dimensionless`).

| Opción | Efecto |
|---|---|
| `--to UNIDAD` | Unidad de destino. |
| `--system SISTEMA` | Sistema de destino (en lugar de `--to`). |
| `--precision N` | Cifras significativas (por defecto 4). |

## `openconex units`: unidades disponibles

```bash
openconex units
```

Lista las unidades que admite cada magnitud.
