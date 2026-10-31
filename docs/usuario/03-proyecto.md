# 3. El archivo de proyecto `.ocnx`

Un proyecto es un archivo JSON con cinco bloques: `info`, `materials` (opcional), `base_plate`, `cases` y `combinations`. Las cantidades se escriben como texto con su unidad (`"25 mm"`, `"3/4 in"`, `"1-1/2 in"`, `"120 kN*m"`). Un número sin unidad se interpreta en el sistema de `info.units`. Los campos opcionales pueden omitirse.

Ejemplos completos en `examples/`:

| Archivo | Muestra |
|---|---|
| `examples/base_plate_dg1_4_7_11.ocnx` | columna del catálogo AISC, combinaciones ASCE 7-22 (DG1 Ejemplo 4.7-11) |
| `examples/base_plate_custom_combinations.ocnx` | combinaciones propias en lugar de las del código |
| `examples/base_plate_generic_w.ocnx` | columna W definida por dimensiones |
| `examples/base_plate_custom_material.ocnx` | material propio para la columna y la placa |
| `examples/base_plate_triangular.ocnx` | distribución triangular de presiones (DG1 B.2-1) |
| `examples/base_plate_effective_area.ocnx` | área efectiva en compresión (DG1 B.3-1) |
| `examples/base_plate_hss_square.ocnx` | columna HSS cuadrada |
| `examples/base_plate_hss_round.ocnx` | columna HSS circular |
| `examples/base_plate_shear_lug.ocnx` | llave de corte (DG1 Ejemplo 4.7-5) |
| `examples/base_plate_template_sap2000.ocnx` | plantilla para importar de SAP2000 / ETABS |

## Datos generales (`info`)

| Campo | Por defecto | Significado |
|---|---|---|
| `name` | `""` | Nombre del proyecto o de la conexión; aparece en la memoria y el cajetín. |
| `number` | `""` | Número de proyecto o de plano. |
| `client` | `""` | Cliente. |
| `engineer` | `""` | Responsable del cálculo. |
| `revision` | `"0"` | Revisión. |
| `date` | `""` | Fecha (texto libre). |
| `language` | `"es"` | Idioma de la memoria y los planos: `es` o `en`. |
| `units` | `"SI_kN_m"` | Sistema de unidades de las salidas y de los números sin unidad. Puede ser `SI_kN_m`, `SI_N_mm`, `MKS` o `US`, o un objeto con la unidad de cada magnitud (ver [Unidades](07-unidades-materiales.md)). |

## Materiales propios (`materials`)

La librería integrada contiene los aceros típicos de AISC 360-22. Para usar un acero que no esté en ella, defínalo en `materials`; después puede referenciarlo desde `column_grade`, `plate_grade`, el `grade` de una sección genérica o `shear_lug.grade`:

```json
"materials": [
  {"name": "Acero del proyecto", "Fy": "355 MPa", "Fu": "490 MPa", "E": "200 GPa"}
]
```

| Campo | Por defecto | Significado |
|---|---|---|
| `name` | (obligatorio) | Nombre único del material; no puede coincidir con uno de la librería integrada. |
| `Fy` | (obligatorio) | Límite de fluencia mínimo especificado. |
| `Fu` | (obligatorio) | Resistencia última mínima especificada; debe ser mayor o igual que `Fy`. |
| `E` | `"29000 ksi"` | Módulo de elasticidad. |

Los materiales propios se usan en todo el cálculo: secciones de columna, placa base y llave de corte. Las barras de anclaje y los electrodos mantienen sus librerías propias (`rod_grade` y el electrodo de la soldadura).

## Placa base (`base_plate`)

La placa es rectangular. `N` va en la dirección del momento del eje fuerte (a lo largo del peralte de la columna) y `B` en la dirección perpendicular. Los anclajes forman dos filas paralelas a `B`, a ±`f` del eje de la columna.

```
            B
   ┌─────────────────┐
   │  o     o     o  │   ← fila de anclajes (rods_per_side), a +f
   │      ┌───┐      │
 N │      │col│      │   → momento del eje fuerte (M) a lo largo de N
   │      └───┘      │
   │  o     o     o  │   ← fila a −f
   └─────────────────┘
      └─rod_spacing─┘
```

| Campo | Por defecto | Significado |
|---|---|---|
| `column` | (obligatorio) | Columna: etiqueta del catálogo AISC (`"W12X96"`) o sección genérica (ver más abajo). |
| `column_grade` | `"ASTM A992"` | Acero de la columna cuando `column` es una etiqueta del catálogo. |
| `N` | (obligatorio) | Largo de la placa, en la dirección del eje fuerte. |
| `B` | (obligatorio) | Ancho de la placa. |
| `tp` | (obligatorio) | Espesor de la placa. |
| `plate_grade` | `"ASTM A572 Gr. 50"` | Acero de la placa. |
| `pressure_model` | `"rectangular"` | Distribución de presiones: `rectangular` (DG1 §4.3) o `triangular` (DG1 Apéndice B.2). |
| `bearing_area_model` | `"plate"` | Área para el aplastamiento: `plate` (B × N) o `effective` (área efectiva bajo la columna, DG1 Apéndice B.3). |
| `fc` | (obligatorio) | Resistencia del concreto f'c. |
| `A2_over_A1` | `1.0` | Relación entre el área de apoyo del concreto y el área de la placa, A2/A1 (1 a 4). Aumenta la resistencia al aplastamiento según √(A2/A1) ≤ 2. |
| `pedestal_N`, `pedestal_B` | sin pedestal | Dimensiones del pedestal; solo se usan en los planos y el modelo 3D. |
| `grout` | `"1.5 in"` | Espesor del mortero de nivelación. Se usa en los planos y en el brazo de la llave de corte. |
| `rod_diameter` | (obligatorio) | Diámetro de las barras de anclaje. |
| `rod_grade` | `"ASTM F1554 Gr. 36"` | Material de las barras. |
| `rods_per_side` | `2` | Barras en cada fila. |
| `f` | (obligatorio) | Distancia del eje de la columna a cada fila de anclajes. |
| `rod_spacing` | `0` | Distancia entre las barras extremas de una fila. Con 0 o una sola barra por fila, el eje débil no tiene anclajes que trabajen a tracción. |
| `hef` | `0` | Empotramiento efectivo de los anclajes. Con 0 no se verifican el arrancamiento del concreto ni el empotramiento mínimo con llave de corte. |
| `edges` | `{}` | Distancias de los anclajes extremos a los bordes del concreto: `left`, `right`, `bottom`, `top`. Si se omite una, se toma ese borde como lejano. |
| `washer_thickness` | ninguno | Espesor de arandelas de placa soldadas a la placa base. Con arandelas soldadas, el corte se reparte entre todas las barras y se verifica la barra a tracción, corte y flexión. |
| `flange_weld` | ninguno | Tamaño de la soldadura de filete en las alas de la columna; si se da, se verifica para el momento. |
| `grout_pad` | `true` | Hay mortero bajo la placa; reduce la resistencia a corte del acero del anclaje (ACI 318-19 §17.7.1.2.1). |
| `friction_mu` | `0.4` | Coeficiente de fricción para el corte transmitido por fricción. |
| `cracked` | `true` | Concreto fisurado (ACI 318-19 §17.6.2.5). |
| `seismic` | `false` | Opción sísmica: factor 0,75 en las resistencias del concreto en tracción (ACI 318-19 §17.10.5.4). |
| `shear_lug` | ninguna | Llave de corte (ver más abajo). |

### Modelos de presión y área efectiva

- `pressure_model: "triangular"` usa la distribución lineal de presiones del Apéndice B.2 de la DG1. En esta versión solo se aplica al eje fuerte y a combinaciones con compresión (`P > 0`); las combinaciones con levantamiento siguen usando el modelo rectangular, y el momento débil requiere el modelo rectangular.
- `bearing_area_model: "effective"` usa el área efectiva bajo el perfil I (Apéndice B.3) para la capacidad de aplastamiento en compresión concéntrica. No se admite en HSS ni junto con el modelo triangular.
- Los valores por defecto son `rectangular` y `plate`, por lo que los proyectos existentes no cambian.

### Columna del catálogo

`"column": "W14X90"` toma las dimensiones de la base de datos de perfiles AISC v16, incluida en el programa. Admite perfiles W, M, S y HP.

### Columna W genérica

```json
"column": {"type": "W", "name": "COL-1", "d": "450 mm", "bf": "300 mm",
           "tf": "9.65 mm", "tw": "6.35 mm", "k_des": "20 mm", "grade": "ASTM A572 Gr. 50"}
```

`type` (`"W"`), `name`, `d`, `bf`, `tf`, `tw`, `k_des` (por defecto 0) y `grade` (obligatorio). El material debe ser un nombre de la librería integrada o de `materials`.

### Columna HSS genérica

```json
"column": {"type": "HSS", "shape": "rectangular", "d": "12 in", "bf": "8 in", "t": "0.5 in",
           "grade": "ASTM A500 Gr. C (rectangular)"}
```

| Campo | Significado |
|---|---|
| `type` | `"HSS"`. |
| `name` | Nombre para la memoria (opcional). |
| `shape` | `rectangular` (por defecto), `square` o `round`. |
| `d` | Peralte exterior, o diámetro exterior si es `round`. |
| `bf` | Ancho exterior; obligatorio en `rectangular`, se omite en `square` y no se admite en `round`. |
| `t` | Espesor de pared. |
| `grade` | Acero; obligatorio. Nombre de la librería integrada o de `materials`. |

Las líneas de fluencia de la placa en compresión están a 0,95 de las dimensiones exteriores para HSS rectangular o cuadrada, y a 0,8 del diámetro para HSS circular (DG1 §4.3.3).

### Llave de corte (`shear_lug`)

Una placa soldada bajo la placa base que transmite el corte al concreto por aplastamiento.

```json
"shear_lug": {"width": "200 mm", "embedment": "75 mm", "thickness": "25 mm", "weld": "8 mm",
              "direction": "strong", "grade": "ASTM A572 Gr. 50", "ca1": "400 mm", "ca2": [null, "300 mm"]}
```

| Campo | Por defecto | Significado |
|---|---|---|
| `width` | (obligatorio) | Ancho b_sl, perpendicular al corte. |
| `embedment` | (obligatorio) | Profundidad h_sl que apoya en el concreto, bajo el mortero. |
| `thickness` | (obligatorio) | Espesor de la llave. |
| `weld` | (obligatorio) | Tamaño de las soldaduras de filete, una en cada cara. |
| `direction` | `"strong"` | `strong`: resiste el corte en la dirección de N (V). `weak`: en la dirección de B (V_weak). `both`: llave en cruz, resiste ambos. |
| `grade` | `"ASTM A572 Gr. 50"` | Acero de la llave. |
| `ca1` | sin verificar | Distancia al borde del concreto en la dirección del corte; si se da, se verifica el arrancamiento del concreto hacia ese borde. |
| `ca2` | `[null, null]` | Distancias a los bordes a cada lado de la llave (`null`: lejano). |

La componente del corte que no toma la llave sigue yendo a fricción o a los anclajes. Ver la [documentación técnica](../tecnico/03-placa-base.md#llave-de-corte).

## Casos de carga (`cases`)

Cada caso es un conjunto de fuerzas en la base de la columna, sin mayorar:

| Campo | Por defecto | Significado |
|---|---|---|
| `name` | (obligatorio) | Nombre único del caso. |
| `type` | (obligatorio) | Tipo de carga ASCE 7-22: `D` muerta, `L` viva, `Lr` viva de techo, `S` nieve, `R` lluvia, `W` viento, `WT` tornado, `E` sismo horizontal. |
| `P` | `0` | Carga axial; **positiva en compresión**. |
| `V` | `0` | Corte en la dirección de N (eje fuerte). |
| `M` | `0` | Momento del eje fuerte. |
| `V_weak` | `0` | Corte en la dirección de B (eje débil). |
| `M_weak` | `0` | Momento del eje débil; si no es cero, la placa se verifica a flexión biaxial. |

Los signos de `V` y `M` se conservan al combinar los casos; las verificaciones usan valores absolutos.

## Combinaciones (`combinations`)

| Campo | Por defecto | Significado |
|---|---|---|
| `methods` | `["LRFD"]` | Métodos con los que se generan las combinaciones ASCE 7-22: `LRFD`, `ASD` o ambos. |
| `include_code` | `true` | Genera las combinaciones de ASCE 7-22 §2.3 (LRFD) y §2.4 (ASD) a partir de los tipos de los casos. |
| `live_factor` | `1.0` | Factor de L en las combinaciones LRFD 3, 4 y 6 de ASCE 7-22 §2.3.1 y en las sísmicas (1,0, o 0,5 donde la norma lo permite). |
| `SDS` | ninguno | Parámetro S_DS. **Las combinaciones con sismo solo se generan si se da `SDS`**: incluyen el sismo vertical E_v = 0,2 S_DS D (ASCE 7-22 §2.3.6 y §2.4.5). Sin `SDS`, los casos `E` no entran en las combinaciones generadas. |
| `rho` | `1.0` | Factor de redundancia ρ aplicado a E. |
| `omega0` | ninguno | Factor de sobrerresistencia Ω0; con `SDS`, agrega las combinaciones con E_mh = Ω0 E (en ASD con aumento de 1,2 de las resistencias admisibles). |
| `custom` | `[]` | Combinaciones propias (ver abajo). |

Cada sismo `E` se combina con los dos signos (`+SX`, `-SX`). Las combinaciones generadas se llaman `LRFD-1`, `LRFD-2`, …, `ASD-1`, … y la memoria indica la sección de ASCE 7-22 de cada una.

### Combinaciones propias (`custom`)

```json
"custom": [
  {"name": "C-1", "method": "LRFD", "factors": {"D": 1.2, "L": 1.6}, "source": "Criterio del proyecto"},
  {"name": "C-2", "method": "ASD", "factors": {"D": 0.6, "W": -0.6}}
]
```

| Campo | Por defecto | Significado |
|---|---|---|
| `name` | (obligatorio) | Nombre único. |
| `method` | `"LRFD"` | `LRFD` o `ASD`; decide qué verificaciones se aplican. |
| `factors` | (obligatorio) | Factor de cada caso, por su `name`; un factor negativo invierte el signo. Todos los casos citados deben existir. |
| `seismic` | `false` | Marca la combinación como sísmica. |
| `overstrength` | `false` | El sismo está amplificado por Ω0. |
| `allowable_increase` | `1.0` | Aumento de las resistencias admisibles en ASD (1,2 en las combinaciones con E_m). |
| `source` | `""` | Origen de la combinación, que se muestra en la memoria. |

Con `"include_code": false` se usan solo las combinaciones propias.
