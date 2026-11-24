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

## Signos de una conexión de corte

En el extremo de la viga, `V` (`Forces.V2`) es la reacción vertical y se usa en valor absoluto; `P` es la fuerza axial con la compresión positiva, como en la placa base. Las bibliotecas de corte reciben la tracción como `N = −P ≥ 0`. En el plano y el modelo 3D, x va a lo largo de la viga desde la cara del apoyo, y hacia arriba desde el ala inferior y z perpendicular al alma.

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

## Calidad del código

- **Complejidad:** ruff rechaza funciones con complejidad ciclomática mayor que 25 (`C901`, `[tool.ruff.lint.mccabe]` en `pyproject.toml`). Las cinco que todavía la superan (`check_base_plate`, `build_base_plate_report`, `BasePlateEditor._project_from_form` (`gui/base_plate.py`), `import_beam_ends` y `_draw` de `drawing/splice.py`) llevan `# noqa: C901` hasta que se dividan. `Project._consistent_loads` y `Project._validate_shear` ya se dividieron en pasos con nombre. No se agregan excepciones nuevas: una función nueva que pase el límite se divide en pasos con nombre.
- **Tipos:** la CI corre `python -m mypy` sobre `units.py`, `core/`, `kernel/`, `connections/` e `io/` con `check_untyped_defs`. En esas carpetas toda función lleva anotaciones (`disallow_untyped_defs`). Un bloque opcional del modelo que la verificación necesita (`end_plate`, `top`, `shear_lug`, `embedded_base`…) se toma con `required(valor, "nombre")` (`core/model.py`), que da `ValueError` si falta; un bloque del proyecto, con `Project.require_<familia>()` (`require_base_plate()`, `require_moment_connection()`…). mypy no acepta `required` cuando el tipo es una unión con `str` (por ejemplo, `str | WSectionInput | None`): ahí se usa un `if … is None: raise ValueError(…)`. La GUI queda fuera por ahora.
- **Cobertura:** la CI mide la cobertura con los extras `dev,pdf,3d,gui-test` y exige 88 %. Sin esos extras se omiten las pruebas de la GUI y del 3D y el número baja.
- **Resultados de los ejemplos:** una refactorización no cambia ningún resultado de `examples/` (`tests/test_examples_snapshot.py`, ver [validación](07-validacion.md)).

## Versiones del formato `.ocnx`

`FORMAT_VERSION` (`io/project.py`) sube cada vez que cambia el esquema del proyecto, y cada versión se anota en `CHANGES` de `io/migrations.py` (lo exige `tests/outputs/test_project.py`). `load_project` llama a `migrate` antes de validar con pydantic:

- **Cambio aditivo** (un campo nuevo con valor por defecto): basta con la entrada en `CHANGES`; los archivos viejos toman el valor por defecto.
- **Cambio no aditivo** (renombrar o quitar un campo, cambiar su significado o su unidad por defecto): además se registra `STEPS[n]`, una función que reescribe el JSON de la versión `n − 1` como versión `n`, y se agrega a `examples/` o a las pruebas un archivo de la versión anterior que compruebe el resultado.
- `examples/` conserva archivos de las versiones 9 a 14, así que la prueba de caracterización (`tests/test_examples_snapshot.py`) comprueba que los archivos viejos siguen dando los mismos resultados. No se actualiza el `format_version` de un ejemplo sin motivo.
- Dos ramas que suben la versión en paralelo deben resolverlo al fusionar: la segunda toma el número siguiente y su propia entrada en `CHANGES` (pasó con la 13 y la 14).
