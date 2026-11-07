# Manual de verificación

Este manual explica cómo se comprueba OpenConex, qué referencias publicadas se usan y cómo reproducir cada resultado. Está dirigido a quien revisa un diseño o audita el programa; no sustituye la revisión del profesional responsable.

La lista completa de verificaciones, con su ecuación y su cláusula, está en [el catálogo técnico](../tecnico/04-verificaciones.md). Este documento se centra en la **evidencia de validación** y en el **protocolo de comparación**.

## 1. Método

- El motor trabaja en N, mm y MPa; las conversiones se hacen solo en los bordes con `openconex.units`.
- Cada verificación devuelve un `CheckResult` con `id`, demanda, capacidad, relación, cláusula y traza de cálculo.
- Las comprobaciones se ejecutan por combinación; la memoria muestra la combinación que gobierna.
- Las tolerancias de las pruebas son del **1 %** salvo que el archivo de referencia indique otra cosa y su motivo.
- Las pruebas se ejecutan en Windows, macOS y Linux en cada pull request.

## 1.1 Matriz de trazabilidad

`docs/verificacion/matriz-verificacion.csv` contiene una fila por cada verificación publicada en el catálogo (186 identificadores). Columnas:

| Columna | Contenido |
|---|---|
| `check_id` | identificador estable del `CheckResult` |
| `familia` | placa base, doble ángulo, placa simple, asiento, anclajes, pernos… |
| `clausula` | cláusula o tabla de AISC 360-22, ACI 318-19 o del Manual |
| `formula` | descripción de la comprobación |
| `referencia_publicada` | ejemplo o tabla que sirve de contraste |
| `test` | archivo de prueba automatizada |
| `calculo_independiente` | script o hoja que no importa `openconex` |
| `software_externo` | comparación con RAM, RISA, SkyCiv u otro programa |
| `estado` | `validado`, `diferencia aceptada`, `parcial`, `pendiente` o `no aplica` |
| `riesgo` | `alto`, `medio` o `bajo` |

La matriz se genera desde el catálogo con:

```bash
python tools/generate_verification_matrix.py
```

Hoy **181** verificaciones están validadas contra ejemplos, tablas o cálculos manuales, **3** tienen una diferencia aceptada y documentada y **2** no aplican (compresión axial y tracción no soportadas). **No quedan verificaciones parciales.** La comparación con software comercial sigue pendiente para todas. Hay cálculo independiente para **46** verificaciones: asientos (`docs/verificacion/calculos/asientos.py`, seis valores de II.A-12A, II.A-13 y II.A-14), doble ángulo/placa simple (`docs/verificacion/calculos/doble_angulo_placa_simple.py`, 18 valores de II.A-1A y II.A-17A), placa base (`docs/verificacion/calculos/placa_base.py`, 59 valores de DG1 4.7-1, 4.7-10 y 4.7-14), anclajes (`docs/verificacion/calculos/anclajes.py`, 39 valores de DG1 4.7-4, 4.7-9 y 4.7-15), placa extendida/viga destajada (`docs/verificacion/calculos/placa_extendida_viga_destajada.py`, 29 valores de II.A-4/6/7 y II.A-19A) y fuerzas concentradas (`tests/kernel/test_local.py`, cinco valores manuales de §J10). Los cinco scripts tienen `--check`. El estado y el riesgo son una foto honesta, no una declaración de cierre.

## 2. Referencias publicadas

| Referencia | Uso | Prueba |
|---|---|---|
| AISC DG1 3.ª ed. (2024), 20 ejemplos | Placas base, anclajes, pedestal, llave de corte, base débil y base empotrada | `tests/base_plate/test_dg1_acceptance.py`, `tests/reference/dg1/` |
| Steel Tube Institute (2024), Ejemplos 1 y 2 | HSS circular a compresión y HSS rectangular con momento | `tests/base_plate/test_hss_moment.py` |
| AISC Design Examples v16.0/v16.1 | Conexiones de corte | `tests/connections/` |
| AISC Manual 16.ª ed., Tablas 7-6 a 7-14 y 8-3 a 8-11 | Grupos de pernos y soldaduras excéntricos | `tests/kernel/test_*_manual*.py` |
| AISC Manual 16.ª ed., Tabla 14-2 | Agujeros y arandelas de placa base | `tests/test_bolting_and_model.py` |
| ACI 318-19 Cap. 17 y 25 | Anclajes, refuerzo de anclaje, desarrollo recto y gancho | `tests/kernel/test_anchors.py`, `tests/base_plate/test_anchor_reinforcement.py` |

Los datos numéricos de las referencias se usan con su cita; no se copian texto, tablas ni figuras de AISC, ACI ni ASCE.

## 3. Cobertura

| Familia | Qué se valida | Evidencia |
|---|---|---|
| Placa base | Compresión, momento, levantamiento, biaxial, modelos de presión, área efectiva | DG1 4.7-1 a 4.7-14, B.2 y B.3 |
| Anclajes | Acero, arrancamiento, extracción, desprendimiento lateral, corte, interacción, refuerzo | DG1 4.7-3 a 4.7-6 y 4.7-15 |
| Llave de corte | Aplastamiento, arrancamiento, flexión local de la placa y soldadura | DG1 4.7-5 |
| Base sísmica débil | Anclajes dúctiles, capacidad y longitud de estiramiento | DG1 6.4-1 |
| Base empotrada Tipo I | Momento por apoyo horizontal, placas de cara y refuerzo horizontal | DG1 5.3-1 |
| Conexiones de corte | Pernos, placas, ángulos, soldaduras, destajes y asientos | AISC II.A-1A a II.A-19A |
| Grupos de pernos y soldaduras | Método elástico y centro instantáneo | Tablas 7-6 a 7-14 y 8-3 a 8-11 |
| Unidades e idiomas | Invariancia, conversión y catálogos ES/EN | `tests/test_units.py`, `tests/test_i18n.py` |
| Salidas | HTML, DOCX, PDF, DXF, STEP y STL | `tests/outputs/` |

## 4. Comparación cruzada

La comparación con un programa comercial (RAM Connection, RISAConnection o SkyCiv) se documenta en `casos.csv`. El archivo contiene 20 casos de placa base y 6 de conexiones de corte, con su archivo de entrada. La columna `resultado_openconex` ya está rellena para los 6 casos de corte; la columna `resultado_externo` sigue vacía porque no hay licencia de software comercial en el entorno de pruebas.

Protocolo:

1. Calcular el caso con OpenConex y anotar la verificación gobernante, su demanda, su capacidad y la relación.
2. Introducir los mismos datos en el programa de referencia, con la misma norma, método (LRFD/ASD), unidades y combinaciones.
3. Anotar el resultado externo y la diferencia relativa.
4. Si la diferencia supera el 1 %, documentar la causa (redondeo, hipótesis de presión, área efectiva, longitud de desarrollo, etc.).
5. Adjuntar la versión del programa externo y la fecha.

La comparación **todavía no se ha ejecutado**; el archivo es la plantilla reproducible. Hasta completarla, la validación numérica de OpenConex es la de las referencias publicadas de la sección 2.

## 5. Diferencias conocidas

Las diferencias aceptadas de la validación están en [Revisión pendiente](../REVISION-PENDIENTE.md), sección 2.2. Las más relevantes:

- Centro instantáneo de II.A-17A/17B: 3,556 y 4,06 frente a 3,54 y 4,07 interpolados.
- II.A-1B: bloque de corte con forma U en lugar de L.
- II.A-19A: `Z_net` calculado 12,75 in³ frente a 12,8 in³ de la Tabla 15-2.
- Viga destajada con λ > 2λ_p: Ec. 9-12/9-13 sin ejemplo publicado.
- II.A-18: doble destaje y conexiones desplazadas o en ángulo pendientes.

II.A-12A quedó aclarado: el ejemplo usa cuatro pernos y entra a la Tabla 10-5 con `l_b = 1 1/16 in` (redondeo de `k_des = 1,03 in`); con A36 la flexión da 90,0/59,9 kip. Las fórmulas de asientos se confirmaron con la Ec. 10-2a/b del Manual (Tabla 10-6) y con II.A-14/15 (Tabla 10-8).

## 6. Limitaciones declaradas

Las limitaciones de alcance están en [Alcance y limitaciones](../usuario/08-limitaciones.md). En particular:

- El HSS circular con momento se rechaza; el rectangular/cuadrado está validado contra STI.
- El área efectiva solo aplica a compresión concéntrica de perfiles I.
- La base empotrada Tipo II no se implementa porque la DG1 no presenta un método definitivo.
- El pedestal no se diseña como columna ni se comprueba su corte como elemento.
- La interacción placa–llave de corte usa un ancho efectivo, sin validación con elementos finitos.

## 7. Reproducción

```bash
pip install -e ".[dev]"
python -m pytest
ruff check .
python docs/verificacion/calculos/asientos.py --check
python docs/verificacion/calculos/doble_angulo_placa_simple.py --check
python docs/verificacion/calculos/placa_base.py --check
python docs/verificacion/calculos/anclajes.py --check
python docs/verificacion/calculos/placa_extendida_viga_destajada.py --check
```

Para las salidas completas:

```bash
pip install -e ".[dev,pdf,3d,gui-test]"
python -m pytest tests/outputs -ra
```

Cada archivo de `tests/` indica en su docstring la referencia y el rango de tolerancia. Los casos de `tests/reference/dg1/` guardan los datos de entrada y los valores publicados.
