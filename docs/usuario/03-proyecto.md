# 3. El archivo de proyecto `.ocnx`

Un proyecto es un archivo JSON con los bloques `info`, `materials` (opcional), `bolts` (opcional), `electrodes` (opcional), `sections` (opcional), `base_plate`, `shear_connection` o `moment_connection` (uno de los tres), `cases` y `combinations`. Las cantidades se escriben como texto con su unidad (`"25 mm"`, `"3/4 in"`, `"1-1/2 in"`, `"120 kN*m"`). Un número sin unidad se interpreta en el sistema de `info.units`. Los campos opcionales pueden omitirse.

Ejemplos completos en `examples/`:

| Archivo | Muestra |
|---|---|
| `examples/base_plate_dg1_4_7_11.ocnx` | columna del catálogo AISC, combinaciones ASCE 7-22 (DG1 Ejemplo 4.7-11) |
| `examples/base_plate_custom_combinations.ocnx` | combinaciones propias en lugar de las del código |
| `examples/base_plate_generic_w.ocnx` | columna W definida por dimensiones |
| `examples/base_plate_custom_material.ocnx` | material propio para la columna y la placa |
| `examples/base_plate_triangular.ocnx` | distribución triangular de presiones (DG1 B.2-1) |
| `examples/base_plate_effective_area.ocnx` | área efectiva en compresión (DG1 B.3-1) |
| `examples/base_plate_rod_bending.ocnx` | flexión de placa por los anclajes (DG1 4.7-3) |
| `examples/base_plate_anchor_reinforcement.ocnx` | refuerzo de anclaje (DG1 4.7-15) |
| `examples/base_plate_weak_base.ocnx` | base sísmica débil (DG1 6.4-1) |
| `examples/base_plate_embedded_base.ocnx` | base empotrada tipo I (DG1 5.3-1) |
| `examples/base_plate_hss_square.ocnx` | columna HSS cuadrada |
| `examples/base_plate_hss_round.ocnx` | columna HSS circular |
| `examples/base_plate_shear_lug.ocnx` | llave de corte (DG1 Ejemplo 4.7-5) |
| `examples/base_plate_template_sap2000.ocnx` | plantilla para importar de SAP2000 / ETABS |
| `examples/moment_bolted_flange_plate.ocnx` | conexión de momento: placas de ala apernadas (AISC II.B-1) |
| `examples/moment_welded_flange_plate.ocnx` | conexión de momento: placas de ala soldadas (AISC II.B-2) |
| `examples/moment_end_plate_extended.ocnx` | placa de extremo extendida de cuatro pernos 4E (AISC DG16, Ej. 4.2.1) |
| `examples/moment_end_plate_flush.ocnx` | placa de extremo enrasada de cuatro pernos (AISC DG16, Ej. 3.2.2) |
| `examples/moment_end_plate_8es.ocnx` | placa de extremo 8ES con placas de continuidad (AISC DG4, Ej. 4.4) |
| `examples/moment_welded_flange_stiffened.ocnx` | alas soldadas con rigidizadores de altura parcial, doble placa y zona de panel (AISC DG13, Ej. 6-3) |
| `examples/shear_single_plate.ocnx` | conexión de corte: placa simple convencional (AISC II.A-17A) |
| `examples/shear_extended_single_plate_axial.ocnx` | conexión de corte: placa simple extendida con tracción axial (AISC II.A-19B) |
| `examples/shear_double_angle_coped.ocnx` | conexión de corte: doble ángulo apernado en viga destajada (AISC II.A-4) |
| `examples/shear_seated_ii_a_12a.ocnx` | conexión de corte: asiento no rigidizado apernado (AISC II.A-12A) |
| `examples/shear_skewed_bent_plate.ocnx` | conexión de corte: doble placa doblada en esviaje (AISC II.A-10) |

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

Los materiales propios se usan en todo el cálculo: secciones de columna, placa base y llave de corte. Las barras de anclaje y los electrodos se definen en los bloques `bolts` y `electrodes`.

## Pernos y electrodos propios (`bolts`, `electrodes`)

La librería integrada contiene los grados de perno y anclaje de AISC 360-22 Tabla J3.2 y los electrodos E70XX/E80XX. Para añadir un grado propio:

```json
"bolts": [
  {"name": "Perno del proyecto", "Fnt": "100 ksi", "Fnv_N": "60 ksi",
   "Fnv_X": "75 ksi", "Fu": "125 ksi", "Fy": "100 ksi"}
],
"electrodes": [
  {"name": "E90XX", "FEXX": "90 ksi"}
]
```

Después se referencian desde `rod_grade`, `base_plate.electrode` y `shear_lug.electrode`. Los nombres no pueden coincidir con los de la librería integrada.

## Secciones propias (`sections`)

El bloque opcional `sections` guarda las secciones genéricas creadas desde la interfaz para que sigan disponibles al reabrir el proyecto. Cada elemento usa el mismo formato que una columna genérica (`type`, `name`, `d`, `bf`, `tf`, `tw`, `k_des`, `grade` para W; `type`, `shape`, `d`, `bf`, `t`, `grade` para HSS):

```json
"sections": [
  {"type": "W", "name": "COL-1", "d": "14 in", "bf": "10 in",
   "tf": "0.5 in", "tw": "0.3 in", "k_des": "1 in", "grade": "ASTM A992"}
]
```

La columna activa puede ser una etiqueta del catálogo AISC, una sección del bloque `sections` o un objeto de sección escrito directamente en `base_plate.column`.

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
| `connection_type` | `"exposed"` | Tipo de conexión: `exposed` (placa base expuesta) o `embedded` (base empotrada). Si se omite, se deduce de `embedded_base`. |
| `column` | (obligatorio) | Columna: etiqueta del catálogo AISC (`"W12X96"`) o sección genérica (ver más abajo). |
| `column_grade` | `"ASTM A992"` | Acero de la columna cuando `column` es una etiqueta del catálogo. |
| `N` | (obligatorio en `exposed`) | Largo de la placa, en la dirección del eje fuerte. |
| `B` | (obligatorio en `exposed`) | Ancho de la placa. |
| `tp` | (obligatorio en `exposed`) | Espesor de la placa. |
| `plate_grade` | `"ASTM A572 Gr. 50"` | Acero de la placa. |
| `electrode` | `"E70XX"` | Electrodo de la soldadura de ala; nombre de la librería integrada o de `electrodes`. |
| `pressure_model` | `"rectangular"` | Distribución de presiones: `rectangular` (DG1 §4.3) o `triangular` (DG1 Apéndice B.2). |
| `bearing_area_model` | `"plate"` | Área para el aplastamiento: `plate` (B × N) o `effective` (área efectiva bajo la columna, DG1 Apéndice B.3). |
| `fc` | (obligatorio) | Resistencia del concreto f'c. |
| `A2_over_A1` | `1.0` | Relación entre el área de apoyo del concreto y el área de la placa, A2/A1 (1 a 4). Aumenta la resistencia al aplastamiento según √(A2/A1) ≤ 2. |
| `bearing_area` | ninguno | Área de apoyo de la tuerca o placa embebida para la extracción del anclaje; si se omite, se usa la tuerca hexagonal pesada. |
| `pedestal_N`, `pedestal_B` | sin pedestal | Dimensiones del pedestal. Se usan en los planos y el modelo 3D y, si no se da `edges`, para deducir las distancias de los anclajes a los bordes (arrancamiento en tracción y corte, desprendimiento lateral). También limitan `A2_over_A1`: la verificación avisa si supera el valor que permite el pedestal. Sin pedestal ni `edges`, el concreto se toma ilimitado, como en una zapata. |
| `grout` | `"1.5 in"` | Espesor del mortero de nivelación. Se usa en los planos y en el brazo de la llave de corte. |
| `rod_diameter` | (obligatorio en `exposed`) | Diámetro de las barras de anclaje. |
| `rod_grade` | `"ASTM F1554 Gr. 36"` | Material de las barras. |
| `rods_per_side` | `2` | Barras en cada fila. |
| `f` | (obligatorio en `exposed`) | Distancia del eje de la columna a cada fila de anclajes. |
| `rod_spacing` | `0` | Distancia entre las barras extremas de una fila. Con 0 o una sola barra por fila, el eje débil no tiene anclajes que trabajen a tracción. |
| `rod_bending_lever` | ninguno | Distancia desde el anclaje hasta el alma o ala que sirve de apoyo para la flexión de la placa por los anclajes (DG1 Ejemplos 4.7-3 y 4.7-7). Si se omite, no se hace esa verificación. |
| `reinforcement` | ninguno | Refuerzo de anclaje en tracción (ver más abajo). |
| `weak_base` | ninguno | Base sísmica débil con anclajes dúctiles (ver más abajo). |
| `embedded_base` | ninguno | Base empotrada tipo I con placas de cara (ver más abajo). |
| `hef` | `0` | Empotramiento efectivo de los anclajes. Con 0 no se verifican el arrancamiento del concreto ni el empotramiento mínimo con llave de corte. |
| `pedestal_rebars` | `[]` | Barras longitudinales del pedestal para el revisor de interferencias (ver más abajo). |
| `edges` | `{}` | Distancias de los anclajes extremos a los bordes del concreto: `left`, `right` (en la dirección de B), `bottom` (desde la fila traccionada, en la dirección de N) y `top`. Si se da alguna, se usan estas y no las del pedestal; las omitidas se toman como lejanas. |
| `washer_thickness` | ninguno | Espesor de arandelas de placa soldadas a la placa base. Con arandelas soldadas, el corte se reparte entre todas las barras y se verifica la barra a tracción, corte y flexión. |
| `flange_weld` | ninguno | Tamaño de la soldadura de filete en las alas de la columna; si se da, se verifica para el momento. |
| `grout_pad` | `true` | Hay mortero bajo la placa; reduce la resistencia a corte del acero del anclaje (ACI 318-19 §17.7.1.2.1). |
| `friction_mu` | `0.4` | Coeficiente de fricción para el corte transmitido por fricción. |
| `cracked` | `true` | Concreto fisurado (ACI 318-19 §17.6.2.5). |
| `seismic` | `false` | Opción sísmica: factor 0,75 en las resistencias del concreto en tracción (ACI 318-19 §17.10.5.4). |
| `shear_lug` | ninguna | Llave de corte (ver más abajo). |

### Modelos de presión y área efectiva

- `pressure_model: "triangular"` usa la distribución lineal de presiones del Apéndice B.2 de la DG1. Se aplica a cada eje con compresión (`P > 0`); en el eje débil se intercambian las dimensiones de la placa y la columna. Las combinaciones con levantamiento siguen usando el modelo rectangular.
- `bearing_area_model: "effective"` usa el área efectiva bajo el perfil I (Apéndice B.3) para la capacidad de aplastamiento en compresión concéntrica. No se admite en HSS, con el modelo triangular, con momento ni con levantamiento.
- El HSS rectangular o cuadrado con momento usa el modelo rectangular con líneas de fluencia a 0,95 de las dimensiones exteriores; está validado contra el Ejemplo 2 del artículo del Steel Tube Institute (2024). El HSS circular con momento se rechaza porque no hay un ejemplo publicado que lo valide.
- Los valores por defecto son `rectangular` y `plate`, por lo que los proyectos existentes no cambian.

### Columna del catálogo

`"column": "W14X90"` toma las dimensiones de la base de datos de perfiles AISC v16, incluida en el programa. Admite perfiles W, M, S, HP, HSS y PIPE. Para HSS y PIPE, seleccione el grado `ASTM A500 Gr. C (rectangular)` o `ASTM A500 Gr. C (round)` en `column_grade`; el grado por defecto `ASTM A992` es solo para perfiles I.

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

Las líneas de fluencia de la placa en compresión están a 0,95 de las dimensiones exteriores para HSS rectangular o cuadrada, y a 0,8 del diámetro para HSS circular (DG1 §4.3.3). El HSS rectangular o cuadrado con momento está validado contra el Ejemplo 2 del Steel Tube Institute (2024); el HSS circular con momento se rechaza.

### Refuerzo de anclaje (`reinforcement`)

Cuando el arrancamiento del concreto en tracción no alcanza, se puede definir un refuerzo desarrollado a ambos lados de la superficie de falla: gancho arriba y barra recta abajo (ACI 318-19 §17.5.2.1, DG1 4.7-15):

```json
"reinforcement": {
  "bars": "4 #6",
  "area": "1.76 in**2",
  "fy": "60 ksi",
  "db": "0.75 in",
  "clear_cover": "2 in",
  "anchor_to_bar": "2.83 in",
  "le": "15.2 in"
}
```

| Campo | Por defecto | Significado |
|---|---|---|
| `bars` | `""` | Etiqueta para la memoria. |
| `area` | (obligatorio) | Área total de refuerzo. |
| `fy` | (obligatorio) | Fluencia del refuerzo. |
| `db` | (obligatorio) | Diámetro de la barra. |
| `clear_cover` | `"2 in"` | Recubrimiento libre; se usa en el empotramiento y en el desarrollo recto. |
| `anchor_to_bar` | (obligatorio) | Distancia horizontal del anclaje a la barra. |
| `le` | (obligatorio) | Longitud de desarrollo recta disponible bajo el plano de falla. |

Si se define refuerzo, la verificación de arrancamiento del concreto se sustituye por las comprobaciones de capacidad, desarrollo del gancho, desarrollo recto y empotramiento del refuerzo.

### Base sísmica débil (`weak_base`)

Base con barras de anclaje de sección reducida (upset-thread) que fluyen antes que los estados no dúctiles (DG1 §6.4, ejemplo 6.4-1):

```json
"weak_base": {
  "reduced_diameter": "0.75 in",
  "stretch_length": "8 in",
  "Rt": 1.2
}
```

| Campo | Por defecto | Significado |
|---|---|---|
| `reduced_diameter` | (obligatorio) | Diámetro de la sección reducida. |
| `stretch_length` | (obligatorio) | Longitud de estiramiento disponible. |
| `Rt` | `1.2` | Factor de sobrerresistencia del acero. |

La verificación es LRFD, requiere el modelo de presión rectangular, no admite momento débil y exige un grado de barra con `Fy` definido (por ejemplo F1554). La capacidad de los estados no dúctiles se comprueba con `n Rt T_red`.

### Base empotrada (`embedded_base`)

Base empotrada tipo I de la DG1 Capítulo 5: la columna se empotra en el concreto y el momento se resiste por apoyo horizontal. Las placas de apoyo frontal se apoyan en la cara superior del cimiento y transmiten la compresión axial (ejemplo 5.3-1):

```json
"connection_type": "embedded",
"embedded_base": {
  "embedment": "22 in",
  "foundation_width": "60 in",
  "face_plate_thickness": "1 in",
  "beta1": 0.85,
  "base_plate_width": "30 in",
  "base_plate_thickness": "1 in",
  "rebar_top": {"area": "1.0 in**2", "fy": "60 ksi", "depth": "5 in"},
  "rebar_bottom": {"area": "0.8 in**2", "fy": "60 ksi", "depth": "18 in"},
  "damage_limit": false
}
```

| Campo | Por defecto | Significado |
|---|---|---|
| `embedment` | (obligatorio) | Profundidad de empotramiento de la columna en el concreto. |
| `foundation_width` | (obligatorio) | Ancho del cimiento en la dirección del momento. |
| `face_plate_thickness` | (obligatorio) | Espesor de las placas de apoyo frontal. |
| `beta1` | `0.85` | Factor del bloque de compresión del concreto, β1. |
| `base_plate_width` | ninguno | Ancho B de la placa embebida del fondo. Si se define, `b_j = (b_f + B)/2`. |
| `base_plate_thickness` | ninguno | Espesor de la placa embebida; obligatorio junto con `base_plate_width`. |
| `rebar_top` | ninguno | Refuerzo horizontal superior: `area`, `fy` y `depth`. |
| `rebar_bottom` | ninguno | Refuerzo horizontal inferior: `area`, `fy` y `depth`. |
| `damage_limit` | `false` | Aplica el factor adicional 0,8 sobre `M_HB` para limitar el daño. |

Cada capa de refuerzo horizontal se define con:

| Campo | Significado |
|---|---|
| `area` | Área total de la capa. |
| `fy` | Fluencia del refuerzo. |
| `depth` | Profundidad bajo la cara superior del cimiento. |

Cuando se define `connection_type: "embedded"`, no son necesarios `N`, `B`, `tp`, `rod_diameter` ni `f`: la verificación ejecuta solo los estados de la base empotrada y no los de la placa base expuesta.

Alcance implementado:

- Tipo I con o sin placa embebida y con refuerzo horizontal superior e inferior opcional.
- Solo LRFD, perfiles I y eje fuerte.
- No admite levantamiento neto, momento débil, llave de corte, base débil ni combinaciones ASD.
- El espesor sísmico mínimo de las placas de cara es `máx(0,75 t_w, 3/8 in)`.
- La soldadura de las placas de apoyo frontal no se verifica; se supone CJP o un detalle capaz de desarrollar la fluencia de la placa.
- El Tipo II no está implementado.

### Barras del pedestal (`pedestal_rebars`)

Posiciones en planta de las barras longitudinales del pedestal, respecto al eje de la columna. `x` va en la dirección de `N` y `y` en la de `B`:

```json
"pedestal_rebars": [
  {"x": "-7 in", "y": "7 in", "diameter": "0.75 in"},
  {"x": "7 in", "y": "-7 in", "diameter": "0.75 in"}
]
```

| Campo | Significado |
|---|---|
| `x` | Posición en la dirección de `N`. |
| `y` | Posición en la dirección de `B`. |
| `diameter` | Diámetro de la barra. |

El revisor comprueba que las barras de anclaje no choquen con estas barras. Si la lista está vacía, no se ejecuta esa comprobación.

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
| `electrode` | `"E70XX"` | Electrodo de la soldadura de la llave. |
| `ca1` | sin verificar | Distancia al borde del concreto en la dirección del corte; si se da, se verifica el arrancamiento del concreto hacia ese borde. |
| `ca2` | `[null, null]` | Distancias a los bordes a cada lado de la llave (`null`: lejano). |

La componente del corte que no toma la llave sigue yendo a fricción o a los anclajes. Ver la [documentación técnica](../tecnico/03-placa-base.md#llave-de-corte).

## Conexión de corte (`shear_connection`)

Conexión del extremo de una viga a una columna o a una viga principal (Manual AISC Partes 9, 10 y 12). Un proyecto tiene `shear_connection` **o** `base_plate`, nunca los dos. Se calcula con `openconex shear` o en la ventana de conexiones de corte de la interfaz.

```json
"shear_connection": {
  "type": "single_plate",
  "beam": "W16X50",
  "support": "W14X90",
  "support_element": "flange",
  "bolt": {"diameter": "3/4 in"},
  "rows": 4, "spacing": "3 in", "length": "11.5 in", "thickness": "1/4 in",
  "lev": "1.25 in", "leh": "1.5 in", "a": "3 in", "weld": "3/16 in"
}
```

| Campo | Por defecto | Significado |
|---|---|---|
| `type` | (obligatorio) | `double_angle`, `single_plate`, `extended_single_plate`, `end_plate`, `seated`, `stiffened_seat` o `skewed_bent_plate`. |
| `beam` | (obligatorio) | Viga: etiqueta W del catálogo AISC o sección W genérica (como la columna W genérica). |
| `beam_grade` | `ASTM A992` | Acero de la viga del catálogo. |
| `support` | (obligatorio) | Columna o viga principal: etiqueta del catálogo o sección W genérica. |
| `support_grade` | `ASTM A992` | Acero del apoyo del catálogo. |
| `support_element` | `flange` | Parte del apoyo a la que se une: `flange` (ala) o `web` (alma); define el espesor del apoyo. |
| `grade` | `ASTM A572 Gr. 50` | Acero de la placa, los ángulos o el rigidizador. |
| `electrode` | `E70XX` | Electrodo de las soldaduras. |
| `bolt` | ¾ in A325-N, agujero estándar | Pernos: `diameter`, `grade`, `threads` (`N` incluidas, `X` excluidas) y `hole` (`STD`, `OVS`, `SSL`, `LSL`). |
| `deformation_considered` | `true` | Aplastamiento con deformación en servicio considerada (2,4 d t F_u); `false` usa 3,0 d t F_u. |
| `cope` | — | Destaje de la viga (ver abajo). |
| `rows` | — | Pernos por línea vertical; en la placa de extremo, filas de dos pernos. |
| `lines` | `1` | Placa extendida: líneas verticales de pernos (1 o 2). |
| `spacing` | — | Separación vertical entre pernos. |
| `gage` | — | Placa extendida: separación entre líneas. Doble ángulo con tracción: gramil entre las alas salientes. |
| `length` | — | Largo de la placa, los ángulos, el asiento o el rigidizador. |
| `thickness` | — | Espesor de la placa, los ángulos, el asiento o el rigidizador. |
| `lev` | — | Distancia vertical del perno extremo al borde. |
| `leh` | — | Distancia horizontal al borde de la placa; en el doble ángulo, en el ala sobre el alma de la viga. |
| `leh_support` | — | Doble ángulo: distancia horizontal al borde en las alas salientes. |
| `a` | — | Placa simple: distancia de la soldadura a la (primera) línea de pernos. |
| `weld` | — | Soldadura de la placa, la placa de extremo o el rigidizador. |
| `support_weld` | — | Doble ángulo: soldaduras al apoyo (soldaduras B). Asiento: soldadura del ala vertical. |
| `beam_weld` | — | Doble ángulo: soldaduras al alma de la viga (soldaduras A). |
| `beam_leg` | — | Doble ángulo: ancho del ala sobre el alma de la viga (con `beam_weld`). |
| `outstanding_leg` | — | Doble ángulo: ancho de las alas salientes (soldaduras B y tracción). |
| `beam_leh` | - | Distancia del extremo de la viga a los pernos, para el desgarro del alma con tracción. |
| `offset` | - | Doble ángulo: desplazamiento entre los ejes de dos vigas que comparten la fila de pernos del apoyo (II.A-9). |
| `skew` | - | Placa doblada: esviaje tal como se escribe en el plano (por ejemplo, `6:12`); informativo. |
| `row_distance` | - | Placa doblada: distancia entre las dos filas verticales de pernos. |
| `load_offset` | - | Placa doblada: distancia de la línea de carga a la fila de pernos de la placa B. |
| `share_a` | - | Placa doblada: fracción de carga de la placa A; si se omite, se deduce de `load_offset/row_distance`. |
| `share_b` | - | Placa doblada: fracción de carga de la placa B; alternativa a `share_a`. |
| `plate_a_width` | - | Placa doblada: ancho de la placa A (plano y 3D). |
| `plate_b_width` | - | Placa doblada: ancho de la placa B (plano y 3D). |
| `plate_a_leg` | - | Placa doblada: ala soldada de la placa A a lo largo del alma de la viga. |
| `plate_b_leg` | - | Placa doblada: ala soldada de la placa B a lo largo del alma de la viga. |
| `bend_radius` | - | Placa doblada: radio interior de doblez. |
| `weld_return` | - | Placa doblada: longitud de los retornos superior e inferior de la soldadura en C. |
| `weld_offset` | - | Placa doblada: distancia de la soldadura vertical a la línea de carga. |
| `leg` | — | Asiento: ala horizontal. |
| `vertical_leg` | — | Asiento soldado: ala vertical. |
| `bolts` | `4` | Asiento apernado: pernos del ala vertical. |
| `bearing_length` | — | Asiento: longitud de apoyo usada en la flexión del ala (por defecto, la mínima requerida). |
| `width` | — | Asiento rigidizado: ancho W del rigidizador. |
| `two_sided` | `false` | Asiento rigidizado: asientos a ambos lados del alma del apoyo. |
| `seat_plate_width` | W + 1 in | Asiento rigidizado: ancho de la placa de asiento. |
| `seat_plate_thickness` | `3/8 in` | Asiento rigidizado: espesor de la placa de asiento. |
| `seat_plate_weld` | `5/16 in` | Asiento rigidizado: soldadura de la placa de asiento al rigidizador. |
| `top_angle_leg` | `4 in` | Asiento: ala del ángulo superior de estabilidad. |
| `top_angle_thickness` | `1/4 in` | Asiento: espesor del ángulo superior. |
| `top_angle_length` | `4 in` | Asiento: largo del ángulo superior a lo largo de la viga. |
| `top_angle_bolts` | `2` | Asiento apernado: pernos por ala del ángulo superior. |
| `top_angle_weld` | `3/16 in` | Asiento soldado: soldadura del ángulo superior al apoyo. |
| `beam_area` | — | Área bruta de una viga genérica, para las verificaciones de la viga con tracción. |

Campos que necesita cada tipo:

| `type` | Campos obligatorios |
|---|---|
| `double_angle` | `rows`, `spacing`, `length`, `thickness`, `lev`; `leh` o `beam_weld` + `beam_leg`; `leh_support` o `support_weld` + `outstanding_leg` |
| `single_plate` | `rows`, `spacing`, `length`, `thickness`, `lev`, `leh`, `a`, `weld` |
| `extended_single_plate` | los de `single_plate`; con `lines: 2`, también `gage` |
| `end_plate` | `rows`, `spacing`, `length`, `thickness`, `lev`, `leh`, `weld` |
| `seated` | `length`, `thickness`, `leg`; con `support_weld`, también `vertical_leg` |
| `stiffened_seat` | `width`, `length`, `thickness`, `weld` |
| `skewed_bent_plate` | `rows`, `spacing`, `length`, `thickness`, `lev`, `leh`, `weld`, `weld_return`, `weld_offset`, y `share_a` o (`row_distance` + `load_offset`) |

### Destaje de la viga (`cope`)

| Campo | Por defecto | Significado |
|---|---|---|
| `c` | (obligatorio) | Largo del destaje. |
| `dc` | (obligatorio) | Profundidad del destaje del ala superior. |
| `dc_bottom` | `0` | Profundidad del destaje del ala inferior. |
| `setback` | `0.5 in` | Holgura entre el apoyo y el extremo de la viga; la reacción actúa a e = c + holgura. |
| `lev` | - | Del borde del destaje al primer perno; con `leh` activa el bloque de corte del alma. |
| `leh` | - | Del extremo de la viga a la línea de pernos (sin descontar la tolerancia de ¼ in, que se resta sola). |
| `doubler` | - | Placa doble de refuerzo (AISC II.A-6 C): `thickness`, `depth`, `gap`, `weld`. |
| `stiffener` | - | Rigidizador longitudinal (AISC II.A-6 D): `width`, `thickness`, `weld`, `length`. |

El refuerzo solo se admite en un destaje superior (`dc_bottom = 0`). La placa doble se coloca a `gap` de la línea del destaje; el rigidizador se suelda a lo largo de esa línea. La memoria incluye las comprobaciones de flexión, corte, esbeltez y soldadura.

### Cargas de una conexión de corte

Cada caso lleva solo `V` (reacción vertical) y `P` (fuerza axial, **tracción negativa**, como en la placa base). `M`, `V_weak` y `M_weak` no se admiten. La tracción se verifica en la placa simple, la placa simple extendida y el doble ángulo apernado. La compresión (`P` > 0) se verifica en la placa simple y la placa extendida: la placa se comprueba a pandeo como voladizo desde la soldadura (K = 1,2, L = `a`) en lugar de la tracción. En los demás tipos aparecen como verificaciones que no cumplen (`shear_connection.axial_unsupported`, `shear_connection.axial_compression`).

## Conexión de momento (`moment_connection`)

Conexión de momento totalmente restringida de una viga al ala de una columna (Manual AISC Partes 9 a 12, ejemplos II.B-1 a II.B-3) o placa de extremo de momento enrasada o extendida (AISC Design Guide 16). Se calcula con `openconex moment` o en la ventana de conexiones de momento de la interfaz. Cada caso de carga lleva `V` (corte del extremo de la viga) y `M` (momento del extremo de la viga); la placa de extremo admite además `P` (axial de la viga, positiva en compresión).

| Campo | Por defecto | Significado |
|---|---|---|
| `type` | (obligatorio) | `bolted_flange_plate` (placas de ala apernadas), `welded_flange_plate` (placas de ala soldadas), `welded_flange` (alas soldadas con penetración completa) o `end_plate` (placa de extremo de momento). |
| `beam` | (obligatorio) | Viga: etiqueta W del catálogo o W genérica. |
| `beam_grade` | `ASTM A992` | Acero de la viga del catálogo. |
| `column` | (obligatorio) | Columna: etiqueta W del catálogo o W genérica; la conexión va a su ala. |
| `column_grade` | `ASTM A992` | Acero de la columna del catálogo. |
| `grade` | `ASTM A572 Gr. 50` | Acero de las placas. |
| `electrode` | `E70XX` | Electrodo. |
| `web` | — | Placa del alma (ver abajo); obligatoria salvo en `end_plate`. |
| `end_plate` | — | `end_plate`: la placa de extremo (ver abajo). |
| `top` | — | Placa de ala. Apernadas: ambas placas (salvo que se dé `bottom`). Soldadas: la superior (de tracción). |
| `bottom` | — | Soldadas: la placa inferior (de compresión). Apernadas: opcional. |
| `bolt` | — | Apernadas: pernos de ala (`diameter`, `grade`, `threads`, `hole`). |
| `rows` | `0` | Apernadas: pernos en cada una de las dos líneas. |
| `spacing` | — | Apernadas: separación de los pernos de ala. |
| `gage` | — | Apernadas: gramil entre las dos líneas. |
| `plate_lev` | — | Apernadas: del extremo de la placa al primer perno. |
| `beam_lev` | — | Apernadas: del extremo de la viga al primer perno (sin descontar la tolerancia). |
| `underrun` | `0.25 in` | Tolerancia de longitud de la viga. |
| `deformation_considered` | `true` | Aplastamiento con deformación en servicio considerada. |
| `column_near_end` | `false` | Fuerza de ala cerca del extremo de la columna (§J10, resistencias reducidas). |
| `two_sided` | `false` | Vigas a ambos lados de la columna (pandeo del alma, §J10.5). |
| `panel_zone` | `false` | Verifica la zona de panel de la columna (§J10.6) con `column_V` y `column_P` de los casos. La demanda es la fuerza de ala (de las dos vigas con `two_sided`) menos el corte de piso. |
| `panel_zone_inelastic` | `false` | El análisis de estabilidad considera la deformación de la zona de panel (Ec. J10-11 y J10-12). |
| `doubler_plate` | — | Espesor total de las dobles placas del alma en la zona de panel (acero `grade`): suma 0,60 F_y d_c t_d a la resistencia. |
| `continuity_plate` | — | Espesor de los rigidizadores transversales (placas de continuidad) de la columna, un par a la altura de cada ala de la viga, del acero `grade`. Con ellos las verificaciones locales de la columna pasan a no aplicables y se verifican los rigidizadores (AISC DG13); en placas de extremo, el ala de la columna se verifica rigidizada (DG4). |
| `continuity_plate_width` | (b_fc − t_wc)/2 | Ancho b_s de cada rigidizador. |
| `continuity_plate_clip` | `3/4 in` | Recorte de esquina de los rigidizadores. |
| `continuity_plate_full_depth` | `true` | Rigidizadores de altura completa; con `false`, de altura parcial. |
| `continuity_plate_length` | — | Largo de los rigidizadores; si no se da, la altura libre del alma (completa) o su mitad (parcial). |
| `continuity_plate_weld` | — | Filete doble de los rigidizadores a las alas de la columna; sin él, penetración completa. |
| `continuity_plate_web_weld` | — | Filete doble de los rigidizadores al alma; sin él no se verifica esa soldadura. |
| `doubler_weld` | — | Filete de la doble placa a las alas de la columna (bisel igual al espesor); sin él, penetración completa. |

Placa del alma (`web`): `bolt`, `rows`, `spacing`, `length`, `thickness`, `lev` (del borde de la placa al perno inferior), `leh` (de la línea de pernos al borde) y `weld` (filete a cada lado, en la columna).

Placa de ala (`top`, `bottom`): `width`, `thickness`, `weld_to_column` (filete a cada lado, en la columna), `unbraced_length` (longitud para la compresión: la separación entre pernos o la longitud libre hasta las soldaduras), y en las placas soldadas `weld_to_beam`, `weld_length` (largo de cada soldadura longitudinal) y `transverse_weld` (soldadura también en el extremo de la placa).

### Placa de extremo de momento (`end_plate`)

Placa soldada al extremo de la viga y apernada al ala de la columna, con dos pernos por fila (AISC Design Guide 16). El acero de la placa es `grade`.

| Campo | Por defecto | Significado |
|---|---|---|
| `layout` | (obligatorio) | Configuración: `flush_2`, `flush_4`, `flush_4_stiffened_between`, `flush_4_stiffened_inside` (enrasadas, DG16 Tablas 3-2 a 3-5) o `extended_4` (4E), `extended_4_stiffened` (4ES), `extended_1_2`, `extended_1_3`, `extended_1_3_stiffened` (extendidas, Tablas 4-2 a 4-6) o `extended_8_stiffened` (8ES, AISC Design Guide 4, Tabla 3.3: dos filas exteriores separadas `pb`). |
| `bolt` | `3/4 in` A325 | Pernos (`diameter`, `grade`, `threads`, `hole`). |
| `width` | (obligatorio) | Ancho b_p de la placa (la Guía limita el ancho efectivo a b_f + 1 in). |
| `thickness` | (obligatorio) | Espesor t_p. |
| `gage` | (obligatorio) | Gramil g entre las dos líneas de pernos. |
| `pf` | (obligatorio) | p_f (enrasadas) o p_f,i (extendidas): de la primera fila interior a la cara interior del ala de tracción. |
| `pb` | — | Separación entre filas interiores (y entre las exteriores en `extended_8_stiffened`); obligatoria con dos o más filas interiores (`flush_4*`, `extended_1_2`, `extended_1_3*`, `extended_8_stiffened`). |
| `pf_o` | — | Extendidas: de la fila exterior a la cara exterior del ala de tracción. |
| `pext` | — | Extendidas: extensión de la placa más allá de la cara exterior del ala. |
| `ps_o`, `stiffener_thickness` | — | `flush_4_stiffened_between`: de la fila exterior al rigidizador y espesor t_s del rigidizador (p_s,i = p_b − p_s,o − t_s). |
| `ps` | — | `flush_4_stiffened_inside`: de la fila al rigidizador. |
| `snug_tight` | `false` | Pernos con apriete ajustado (solo A325): T_b es el 75 %, 50 %, 37,5 % o 25 % de la pretensión de la Tabla J3.1 según el diámetro (≤ 5/8, 3/4, 7/8, ≥ 1 in). |
| `pretension` | — | Pretensión T_b propia en lugar de la Tabla J3.1 (pernos métricos: si no se da, 0,7 P_t). |
| `web_weld` | — | Filete a cada lado del alma; sin él, penetración completa (no se verifica). |
| `flange_weld` | — | Filete en las alas; sin él, penetración completa que desarrolla el ala. |
| `weld_reinforcement` | — | Soldadura de penetración completa en las alas: lado del filete de refuerzo, para N = t_f + 2w en el alma de la columna (DG4 paso 16). Con `flange_weld`, N = t_f + 0,707 w. |
| `symmetric` | `true` | Misma disposición de pernos en ambas alas (momento reversible); con `false`, dos pernos en el ala de compresión, como en los modelos de fuerzas de la Guía. |

Las dimensiones probadas en los ensayos están en las Tablas 3-6 y 4-7 de la Guía; fuera de ese rango el mecanismo puede cambiar (el programa no las limita).

## Casos de carga (`cases`)

Cada caso es un conjunto de fuerzas sin mayorar en la base de la columna (o en el extremo de la viga, para una conexión de corte):

| Campo | Por defecto | Significado |
|---|---|---|
| `name` | (obligatorio) | Nombre único del caso. |
| `type` | (obligatorio) | Tipo de carga ASCE 7-22: `D` muerta, `L` viva, `Lr` viva de techo, `S` nieve, `R` lluvia, `W` viento, `WT` tornado, `E` sismo horizontal. |
| `P` | `0` | Carga axial; **positiva en compresión**. |
| `V` | `0` | Corte en la dirección de N (eje fuerte). |
| `M` | `0` | Momento del eje fuerte. |
| `V_weak` | `0` | Corte en la dirección de B (eje débil). |
| `M_weak` | `0` | Momento del eje débil; si no es cero, la placa se verifica a flexión biaxial. |
| `column_V` | `0` | Conexiones de momento con `panel_zone`: corte de piso de la columna sobre el nudo, que descuenta la fuerza de ala en la zona de panel. |
| `column_P` | `0` | Conexiones de momento con `panel_zone`: carga axial de la columna (§J10.6). |

Los signos de `V` y `M` se conservan al combinar los casos; las verificaciones usan valores absolutos.

## Combinaciones (`combinations`)

| Campo | Por defecto | Significado |
|---|---|---|
| `methods` | `["LRFD"]` | Métodos con los que se generan las combinaciones ASCE 7-22: `LRFD`, `ASD` o ambos. |
| `include_code` | `true` | Genera las combinaciones de ASCE 7-22 §2.3 (LRFD) y §2.4 (ASD) a partir de los tipos de los casos. |
| `live_factor` | `1.0` | Factor de L en las combinaciones LRFD 3, 4 y 6 de ASCE 7-22 §2.3.1 y en las sísmicas (1,0, o 0,5 donde la norma lo permite). |
| `SDS` | ninguno | Parámetro S_DS. **Obligatorio si hay casos `E` y `include_code` es `true`**: sin él, el proyecto da error en lugar de omitir el sismo. Las combinaciones sísmicas incluyen el sismo vertical E_v = 0,2 S_DS D (ASCE 7-22 §2.3.6 y §2.4.5); use `0` para no considerar E_v. |
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
