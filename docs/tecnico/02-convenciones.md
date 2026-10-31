# 2. Convenciones

## Unidades

- **Dentro del motor** todo es `float` en **N, mm y MPa**, sin objetos de unidades. Momentos en N·mm, áreas en mm².
- **Conversión solo en los bordes:** al leer el proyecto (`Project.quantity`) y al escribir resultados (`units.format_value`).
- **Ecuaciones empíricas en unidades de origen:** las que la norma da en psi y pulgadas (por ejemplo, el arrancamiento del concreto de ACI 318) se evalúan en esas unidades y se convierten (`kernel/anchors.py`, `_psi`, `_in`, `_lbf`).
- **Cada valor de la traza lleva su magnitud** (`Kind`), así la memoria lo muestra en el sistema que se pida.

## Ejes y signos de la placa base

- **x a lo largo de N:** dirección del momento del eje fuerte (M3) y del corte V2.
- **y a lo largo de B:** dirección del momento del eje débil (M2) y del corte V3.
- **z hacia arriba;** en el modelo 3D, la cara superior del concreto es z = 0.
- **`P` positivo es compresión;** con `P < 0` hay levantamiento.
- **Momentos y cortes:** las verificaciones usan su valor absoluto. Los signos se conservan al combinar casos, para que dos casos de signo contrario se resten.
- **Anclajes:** dos filas paralelas a B, en x = ±f. Cada fila tiene `rods_per_side` barras repartidas en `rod_spacing` a lo largo de y.

## LRFD y ASD

- **Clase `Resistance(phi, omega)`** (`kernel/design.py`). `Calc.available` devuelve φRn (LRFD) o Rn/Ω (ASD) y deja el paso en la traza.
- **El método de cada combinación** decide qué verificaciones se hacen.
- **ACI 318 es solo de resistencia:** las verificaciones de concreto y anclajes de ACI se hacen solo con combinaciones LRFD y dan error si se piden en ASD. En ASD, las barras de anclaje se verifican como pernos según AISC 360-22 §J3.

## Resultado de una verificación

Cada verificación devuelve un `CheckResult` (`core/checks.py`):

| Campo | Contenido |
|---|---|
| `id` | Identificador estable, por ejemplo `base_plate.biaxial`. |
| `text_id` | Clave del título en `i18n` (`check.` + `id`). |
| `clause` | Cláusula de la norma. |
| `demand`, `capacity`, `kind` | Demanda, resistencia disponible y su magnitud. |
| `ratio`, `status` | demanda/capacidad; `ok` si ≤ 1, `ng` si no, `n/a` si no aplica. |
| `combo` | Combinación que la produjo. |
| `steps` | Traza: lista de `TraceStep` con símbolo, expresión en LaTeX, valor, magnitud, cláusula y datos de entrada. |

`governing()` toma, entre varios resultados, el de mayor relación; la memoria muestra uno por `id`.

`Calc` (`kernel/design.py`) acumula la traza: `c.step(símbolo, expresión, valor, magnitud, cláusula)` registra un paso y devuelve el valor, y `c.result(...)` arma el `CheckResult`.

## Idiomas

Los títulos y textos de la memoria y los planos están en `i18n/es.toml` y `i18n/en.toml`. Toda verificación nueva necesita su título en ambos (lo exigen las pruebas). Las ecuaciones son LaTeX, iguales en ambos idiomas.
