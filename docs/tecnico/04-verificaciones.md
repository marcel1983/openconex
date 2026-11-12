# 4. Catálogo de verificaciones

Cada verificación tiene un identificador estable (`id`), que aparece en la traza y en los archivos de resultados. Su título en español e inglés está en `i18n/*.toml` bajo `check.<id>`. Esta lista debe contener todos los identificadores; la prueba `tests/test_docs.py` lo comprueba.

Columna **Placa base**: ✔ la usa `check_base_plate`; — solo existe en la biblioteca (para las conexiones en desarrollo o para uso directo desde Python).

## Placa base (`connections/base_plate`)

| `id` | Verificación | Norma | Placa base |
|---|---|---|---|
| `base_plate.a2_over_a1` | A2/A1 admisible por el tamaño del pedestal | AISC 360-22 §J8 | ✔ con pedestal |
| `base_plate.bearing` | Aplastamiento del concreto bajo la placa (P ≤ φP_p, o q ≤ q_max) | AISC 360-22 §J8; DG1 §4.3 | ✔ |
| `base_plate.thickness_compression` | Espesor de placa en la interfaz de compresión | DG1 Ec. 4-15, 4-47 a 4-52 | ✔ |
| `base_plate.thickness_tension` | Espesor de placa en la interfaz de tracción | DG1 Ec. 4-61, 4-62 | ✔ |
| `base_plate.bearing_weak` | Aplastamiento, eje débil (o momento débil sin anclajes fuera del eje) | DG1 §4.3 | ✔ |
| `base_plate.thickness_compression_weak` | Espesor en compresión, eje débil | DG1 Ec. 4-47 a 4-52 | ✔ |
| `base_plate.thickness_tension_weak` | Espesor en tracción, eje débil | DG1 Ec. 4-62 | ✔ |
| `base_plate.biaxial` | Interacción de flexión biaxial (M/M_cap)² + (M2/M2_cap)² ≤ 1 | DG1 §4.3.7, Ec. 4-69 | ✔ |
| `base_plate.weak_base_area` | Sección reducida de la barra dúctil | DG1 §6.4.2 | ✔ |
| `base_plate.weak_base_stretch` | Longitud de estiramiento de la barra dúctil | DG1 §6.4.2 | ✔ |
| `base_plate.anchor_column_clearance` | Separación de los anclajes a la columna | DG1 §4.2 | ✔ con placa expuesta |
| `base_plate.anchor_plate_edge` | Distancia de los anclajes al borde de la placa | AISC 360-22 §J3.4 | ✔ con placa expuesta |
| `base_plate.anchor_lug_clearance` | Separación de los anclajes a la llave de corte | DG1 §4.5 | ✔ con `shear_lug` |
| `base_plate.anchor_rebar_clearance` | Separación de los anclajes a las barras del pedestal | AISC 360-22 §J3.3 | ✔ con `pedestal_rebars` |
| `base_plate.friction` | Corte por fricción | DG1 §4.3.5, Ec. 4-30 | ✔ |
| `base_plate.rod_combined` | Barra con tracción, corte y flexión (arandelas soldadas) | AISC 360-22 §J3.8; DG1 Ej. 4.7-6 | ✔ |
| `base_plate.lug_shear_yielding` | Llave de corte: fluencia por corte | AISC 360-22 §J4.2(a) | ✔ |
| `base_plate.lug_shear_rupture` | Llave de corte: rotura por corte | AISC 360-22 §J4.2(b) | ✔ |
| `base_plate.lug_flexural_yielding` | Llave de corte: fluencia por flexión | AISC 360-22 §J4.5 | ✔ |
| `base_plate.lug_flexural_rupture` | Llave de corte: rotura por flexión | AISC 360-22 §J4.5 | ✔ |
| `base_plate.lug_weld` | Llave de corte: soldadura a la placa | AISC 360-22 §J2.4; DG1 Ej. 4.7-5 | ✔ |
| `base_plate.lug_plate_bending` | Llave de corte: flexión local de la placa base | AISC 360-22 §J4.5; DG1 Ej. 4.7-5 | ✔ |
| `base_plate.lug_anchor_embedment` | Empotramiento de anclajes con llave (h_ef ≥ 2,5 h_sl) | ACI 318-19 §17.11.1 | ✔ |
| `base_plate.plate_bending_rods` | Flexión de la placa por los anclajes en tracción | DG1 Ej. 4.7-3, 4.7-7 | ✔ con `rod_bending_lever` |
| `base_plate.embedded_moment` | Momento resistente de la base empotrada | DG1 §5.2 | ✔ con `embedded_base` |
| `base_plate.face_plate_bearing` | Aplastamiento del concreto en las placas de cara | DG1 §5.3 | ✔ con `embedded_base` |
| `base_plate.face_plate_thickness` | Espesor de las placas de cara | DG1 §5.3 | ✔ con `embedded_base` |
| `base_plate.face_plate_seismic` | Espesor sísmico mínimo de las placas de cara, máx(0,75 t_w, 3/8 in) | AISC 341-22 §F3.5b.4 | ✔ con `embedded_base` |

## Doble ángulo apernado (`connections/shear/double_angle.py`)

Primera conexión de corte de la F5 (Manual AISC Parte 10). Integrada en el proyecto (`shear_connection`), el comando `openconex shear`, la memoria, el DXF, el modelo 3D y la GUI; validada contra II.A-1A/1B, II.A-2A y II.A-3.

| `id` | Verificación | Norma |
|---|---|---|
| `double_angle.bolts_beam` | Transferencia de corte en los agujeros, lado de la viga: Σ mín(2 r_n,perno, 2 r_n,ángulo, r_n,alma) | §J3.7 (nota), §J3.11 |
| `double_angle.bolts_support` | Transferencia de corte en los agujeros, lado del apoyo: Σ mín(2 r_n,perno, 2 r_n,ángulo, 2 r_n,apoyo) | §J3.7 (nota), §J3.11 |
| `double_angle.bolts_support_shared` | Fila de pernos compartida por dos vigas desplazadas: doble cortante y aplastamiento en el alma del apoyo para 2R | §J3.7, §J3.11; Manual II.A-9 |
| `double_angle.angle_shear_yielding` | Fluencia por corte de los ángulos, A_gv = 2 l t | §J4.2(a) |
| `double_angle.angle_shear_rupture` | Rotura por corte de los ángulos, A_nv = 2 (l − n(d_h + 1/16 in)) t | §J4.2(b), §B4.3b |
| `double_angle.block_shear_beam` | Bloque de corte de los ángulos, lado de la viga (U_bs = 1) | §J4.3 |
| `double_angle.block_shear_support` | Bloque de corte de los ángulos, lado del apoyo (U_bs = 1) | §J4.3 |
| `double_angle.weld_support` | Con `support_weld` > 0 (ángulos soldados al apoyo, "soldaduras B"): dos líneas de soldadura excéntricas, e = ancho del ala soldada, por el centro instantáneo con el C1 de la Tabla 8-3. Reemplaza `bolts_support` y `block_shear_support` | §J2.4; Manual Tabla 10-2 |
| `double_angle.weld_max_size` | w ≤ t − 1/16 in (t ≥ ¼ in) | §J2.2b |
| `double_angle.support_thickness` | t_min = 3,09 D/F_u del apoyo | Manual Ec. 9-6 |
| `double_angle.weld_beam` | Con `beam_weld` > 0 (ángulos soldados al alma, "soldaduras A"): soldadura en C por ángulo (línea vertical en la punta y dos retornos de `beam_leg` − ½ in), cargada en el talón, por el centro instantáneo. Reemplaza `bolts_beam` y `block_shear_beam`; con los dos lados soldados los ángulos no tienen agujeros | §J2.4; Manual Tabla 10-3 |
| `double_angle.beam_web_thickness` | t_w ≥ 6,19 D/F_u | Manual Ec. 9-3 |

### Doble ángulo con carga axial (`connections/shear/double_angle_axial.py`)

`check_double_angle_axial(da, V, N, gage=..., outstanding_leg=..., beam=...)` agrega la tracción axial N al doble ángulo apernado. Con N = 0 equivale a `check_double_angle`. Usa además `bolts_beam` (con las distancias de desgarro a lo largo de la fuerza: l_ev/cos θ en el perno de borde y l_eh/cos β en los demás y en el alma, esta menos la tolerancia de longitud), `bolts_support` (solo corte), `angle_shear_yielding`, `angle_shear_rupture`, `block_shear_beam` y `block_shear_support`.

| `id` | Verificación | Norma |
|---|---|---|
| `double_angle.bolts_tension` | n · F'_nt A_b · Q: tracción con corte y efecto palanca de los ángulos, p = l/n | §J3.8; Manual Parte 9 |
| `double_angle.angle_tension_yielding` | Fluencia por tracción de los ángulos | §J4.1(a) |
| `double_angle.angle_tension_rupture` | Rotura por tracción, A_e = A_n (U = 1) | §J4.1(b) |
| `double_angle.block_shear_axial` | Bloque de corte axial en el lado de la viga, mínimo entre forma L y U | §J4.3 |
| `double_angle.block_shear_interaction` | (V/R_v)² + (N/R_t)² ≤ 1 | como Manual Ec. 12-1 |
| `double_angle.beam_shear_yielding` | Con `beam`: fluencia por corte del alma, d t_w | §J4.2(a) |
| `double_angle.beam_tension_yielding` | Con `beam`: fluencia por tracción de la viga | §J4.1(a) |
| `double_angle.beam_tension_rupture` | Con `beam`: rotura por tracción, U = (d − 2t_f) t_w / A_g | §J4.1(b), §D3 |
| `double_angle.beam_block_shear` | Con `beam`: bloque de corte axial del alma (forma U) | §J4.3 |

## Conexión sesgada de doble placa doblada (`connections/shear/bent_plate.py`)

Manual AISC Parte 10, ejemplo II.A-10. Dos placas dobladas soldadas al alma de la viga y apernadas al alma del apoyo; el reparto de la reacción entre las placas A y B se hace por estática simple. Integrada en el proyecto, el comando `openconex shear` y la memoria; el DXF, el 3D y la GUI quedan para la fase 2.

| `id` | Verificación | Norma |
|---|---|---|
| `skewed_bent_plate.plate_a.bolts` | Pernos de la placa A: corte simple, aplastamiento y desgarro en la placa y aplastamiento en el alma del apoyo | §J3.7, §J3.11 |
| `skewed_bent_plate.plate_a.shear_yielding` | Fluencia por corte de la placa A, A_gv = l t | §J4.2(a) |
| `skewed_bent_plate.plate_a.shear_rupture` | Rotura por corte de la placa A, A_nv = (l − n d_h) t | §J4.2(b), §B4.3b |
| `skewed_bent_plate.plate_a.block_shear` | Bloque de corte de la placa A con U_bs = 1 | §J4.3 |
| `skewed_bent_plate.plate_a.weld` | Soldadura en C de la placa A al alma de la viga, centro instantáneo; C de la Tabla 8-8 | §J2.4(c); Manual Parte 8 |
| `skewed_bent_plate.plate_b.bolts` | Pernos de la placa B: corte simple, aplastamiento y desgarro en la placa y aplastamiento en el alma del apoyo | §J3.7, §J3.11 |
| `skewed_bent_plate.plate_b.shear_yielding` | Fluencia por corte de la placa B, A_gv = l t | §J4.2(a) |
| `skewed_bent_plate.plate_b.shear_rupture` | Rotura por corte de la placa B, A_nv = (l − n d_h) t | §J4.2(b), §B4.3b |
| `skewed_bent_plate.plate_b.block_shear` | Bloque de corte de la placa B con U_bs = 1 | §J4.3 |
| `skewed_bent_plate.plate_b.weld` | Soldadura en C de la placa B al alma de la viga, centro instantáneo; C de la Tabla 8-8 | §J2.4(c); Manual Parte 8 |
| `skewed_bent_plate.beam_web_thickness` | t_w ≥ 6,19 D/F_u del alma de la viga | Manual Ec. 9-3 |
| `skewed_bent_plate.plate_thickness` | t_p ≥ w + 1/16 in para el tamaño máximo de soldadura | §J2.2b |

## Placa simple convencional (`connections/shear/single_plate.py`)

Manual AISC Parte 10, configuración convencional, con pernos en una fila. Integrada en el proyecto, el comando `openconex shear`, la memoria, el DXF, el modelo 3D y la GUI; validada contra II.A-17A y II.A-17B.

| `id` | Verificación | Norma |
|---|---|---|
| `single_plate.bolts` | Transferencia de corte en los agujeros: (C/n) Σ mín(r_n,perno, r_n,placa, r_n,alma), C del centro instantáneo con e = a/2 | §J3.7 (nota), §J3.11; Manual Tabla 10-9 |
| `single_plate.shear_yielding` | Fluencia por corte de la placa | §J4.2(a) |
| `single_plate.shear_rupture` | Rotura por corte de la placa | §J4.2(b), §B4.3b |
| `single_plate.block_shear` | Bloque de corte de la placa (U_bs = 1) | §J4.3 |
| `single_plate.max_thickness` | mín(t_p, t_w) ≤ d/2 + 1/16 in | Manual Parte 10 |
| `single_plate.leh` | l_eh ≥ 2d | Manual Parte 10 |
| `single_plate.lev` | l_ev según la Tabla J3.4 | §J3.4 |
| `single_plate.weld_size` | w ≥ 5t_p/8 | Manual Parte 10 |
| `single_plate.support_thickness` | t_min = 3,09 D/F_u del apoyo | Manual Ec. 9-6 |

### Placa simple con carga axial (`connections/shear/single_plate_axial.py`)

`check_single_plate_axial(sp, V, N, ...)` sigue el método del Manual Parte 12: la placa es un voladizo desde la soldadura con M = V·a. Con N = 0 equivale a `check_single_plate`. Usa además `single_plate.bolts`, `shear_yielding`, `shear_rupture`, `block_shear`, `weld_size` y `support_thickness`.

| `id` | Verificación | Norma |
|---|---|---|
| `single_plate.tension_yielding` | Fluencia por tracción de la placa | §J4.1(a) |
| `single_plate.compression` | Con `P` > 0 (compresión): pandeo de la placa como voladizo desde la soldadura, K = 1,2, L = a, r = t/√12; reemplaza la tracción y los bloques de corte axiales, y su capacidad entra en la interacción de fluencia | §J4.4; Comentario Tabla C-A-7.1(d); II.A-19B (comentarios) |
| `single_plate.tension_rupture` | Rotura por tracción, A_e = A_n | §J4.1(b) |
| `single_plate.flexural_yielding` | M_n = mín(F_y Z, 1,5 F_y S) | §F11.1 |
| `single_plate.flexural_ltb` | Pandeo lateral-torsional con L_b = a y C_b = 1,84 | §F11.2 |
| `single_plate.flexural_rupture` | M_n = F_u Z_net | §J4.5; Manual Ec. 9-8 |
| `single_plate.interaction_yielding` | Interacción N, M, V con resistencias de fluencia | Manual Ec. 12-2, 12-3 |
| `single_plate.interaction_rupture` | Interacción N, M, V con resistencias de rotura | Manual Ec. 12-2, 12-3 |
| `single_plate.block_shear_axial` | Bloque de corte en dirección axial, mínimo entre forma L y U | §J4.3 |
| `single_plate.block_shear_interaction` | (V/R_v)² + (N/R_t)² ≤ 1 en el bloque de corte | Manual Ec. 12-1 |
| `single_plate.support_shear_rupture` | Rotura por corte del apoyo en dos planos, A_nv = 2 l t | §J4.2(b) |

En los pernos, C se calcula con el centro instantáneo para la resultante a θ = atan(N/V) y e = a; el desgarro usa la peor distancia al borde (l_ev o l_eh de la placa, y l_eh de la viga menos la tolerancia de longitud, ¼ in por defecto).

## Viga con destaje (`connections/shear/coped_beam.py`)

Extremo de viga destajado (Manual AISC Parte 9). La reacción actúa a e = c + holgura (½ in por defecto). Las propiedades de la T que deja un destaje superior se calculan sin filetes, como en la Tabla 9-2.

| `id` | Verificación | Norma |
|---|---|---|
| `coped_beam.flexure` | R_n = M_n/e. Destaje superior: fluencia y pandeo local del alma con f, k y k_1. Destaje en ambas alas: pandeo lateral-torsional del alma como barra rectangular, L_b = c y C_b de la Ec. 9-21 | Manual Ec. 9-9 a 9-21; §F11 |
| `coped_beam.shear_yielding` | Fluencia por corte del alma reducida, h_c t_w | §J4.2(a) |
| `coped_beam.shear_rupture` | Rotura por corte, descontando los agujeros si los hay | §J4.2(b) |
| `coped_beam.block_shear` | Bloque de corte del alma apernada; l_eh menos la tolerancia de longitud (¼ in); U_bs = 1 con una línea y 0,5 con dos | §J4.3 |

### Refuerzo del destaje (`connections/shear/cope_reinforcement.py`)

Con placa doble o rigidizador longitudinal se sustituye la comprobación de flexión de la sección sin reforzar por la de la sección reforzada (Manual Parte 9, ejemplo II.A-6 C y D). Las propiedades se calculan como la T del destaje más la placa, sin filetes.

| `id` | Verificación | Norma |
|---|---|---|
| `coped_beam.doubler_flexure` | R_n = M_n/e con S_net y Z_net de la sección con placa doble; M_n por la Ec. 9-7 | Manual Ec. 9-7, 9-9 |
| `coped_beam.doubler_shear_yielding` | Fluencia por corte del alma más la placa | §J4.2(a) |
| `coped_beam.doubler_shear_rupture` | Rotura por corte del alma más la placa | §J4.2(b) |
| `coped_beam.doubler_compact` | d_p/t_p ≤ 1,12√(E/F_y) | Tabla B4.1b |
| `coped_beam.doubler_weld` | Flujo de corte RQ/I en dos soldaduras | §J2.4; Manual Ec. 9-6 |
| `coped_beam.stiffener_flexure` | R_n = M_n/e con la sección reforzada; M_n por §F4 con R_pc = 1,0 | §F4; Manual Ec. 9-9 |
| `coped_beam.stiffener_compact` | b/t del rigidizador ≤ 0,38√(E/F_y) | Tabla B4.1b, caso 11 |
| `coped_beam.stiffener_web_compact` | h_c/t_w ≤ 5,70√(E/F_y) | Tabla B4.1b, caso 16 |
| `coped_beam.stiffener_weld` | Flujo de corte y transferencia de fuerza en dos soldaduras | §J2.4 |
| `coped_beam.stiffener_web_shear` | Rotura por corte del alma en la longitud del rigidizador | §J4.2(b) |

## Placa simple extendida (`connections/shear/extended_single_plate.py`)

Placa soldada al apoyo (por ejemplo, al alma de una columna) con una o dos líneas de pernos lejos de la soldadura (Manual AISC Parte 10). Momento M = R·a en la primera línea de pernos. No se verifica el desgarro del alma de la viga, que se supone protegido por el ala superior.

| `id` | Verificación | Norma |
|---|---|---|
| `extended_plate.bolts` | C · mín(corte del perno, aplastamiento en alma y placa, desgarro del perno de borde de la placa); C por el centro instantáneo con e desde el apoyo al centroide | §J3.7, §J3.11; Manual Parte 7 |
| `extended_plate.max_thickness` | t_p ≤ t_max = 6 M_max/(F_y l²), M_max = F_nv A_b C'/0,90 | Manual Ec. 10-6, 10-7 |
| `extended_plate.shear_yielding` | Fluencia por corte de la placa | §J4.2(a) |
| `extended_plate.shear_rupture` | Rotura por corte en la línea de agujeros | §J4.2(b) |
| `extended_plate.block_shear` | Bloque de corte (U_bs = 0,5 con dos líneas) | §J4.3 |
| `extended_plate.flexural_yielding` | M_n = mín(F_y Z, 1,5 F_y S) | §F11.1 |
| `extended_plate.flexural_ltb` | Pandeo lateral-torsional con L_b = a y C_b = 1,84 | §F11.2 |
| `extended_plate.interaction` | (V/V_c)² + (M/M_c)² ≤ 1 | Manual Parte 10 |
| `extended_plate.flexural_rupture` | M_n = F_u Z_net en la primera línea | Manual Ec. 9-8 |
| `extended_plate.weld_size` | w ≥ 5t_p/8 | Manual Parte 10 |
| `extended_plate.support_thickness` | t_min = 3,09 D/F_u | Manual Ec. 9-6 |

### Placa simple extendida con carga axial (`extended_single_plate_axial.py`)

La placa extendida con tracción axial añade los estados límite de la placa y del bloque de corte en la dirección axial (Manual Parte 12, ejemplo II.A-19B). El grupo de pernos usa el centro instantáneo con el ángulo del resultado. No se comprueban la viga ni la línea de fluencia del alma de la columna.

| `id` | Verificación | Norma |
|---|---|---|
| `extended_plate.tension_yielding` | Fluencia por tracción de la placa, A_g = l t | §J4.1(a) |
| `extended_plate.compression` | Con `P` > 0 (compresión): pandeo de la placa, K = 1,2, L = a, r = t/√12; reemplaza la tracción y los bloques de corte axiales, y su capacidad entra en la interacción de fluencia | §J4.4; Comentario Tabla C-A-7.1(d); II.A-19B (comentarios) |
| `extended_plate.tension_rupture` | Rotura por tracción, A_n = (l − n d_h') t, U = 1 | §J4.1(b) |
| `extended_plate.interaction_yielding` | Interacción axial, flexión y corte (fluencia), Ec. 12-2 o 12-3 | Manual Parte 12 |
| `extended_plate.interaction_rupture` | Interacción axial, flexión y corte (rotura) | Manual Parte 12 |
| `extended_plate.block_shear_axial` | Bloque de corte axial, mínimo de las formas L y U | §J4.3 |
| `extended_plate.block_shear_interaction` | (V/R_v)² + (N/R_t)² ≤ 1 | Manual Ec. 12-1 |
| `extended_plate.support_shear_rupture` | Rotura por corte del apoyo en dos planos | §J4.2(b) |

## Placa de extremo de corte (`connections/shear/end_plate.py`)

Placa soldada al extremo del alma de la viga y apernada al apoyo con dos pernos por fila (Manual AISC Parte 10).

| `id` | Verificación | Norma |
|---|---|---|
| `end_plate.bolts` | Σ por fila mín(2 r_n,perno, 2 r_n,placa, 2 r_n,apoyo); el perno superior es el de borde | §J3.7 (nota), §J3.11 |
| `end_plate.shear_yielding` | Fluencia por corte, A_gv = 2 l t | §J4.2(a) |
| `end_plate.shear_rupture` | Rotura por corte, A_nv = 2 (l − n d_h') t | §J4.2(b) |
| `end_plate.block_shear` | Bloque de corte en las dos líneas (U_bs = 1) | §J4.3 |
| `end_plate.weld` | Dos soldaduras al alma, longitud efectiva l − 2w | §J2.4 |
| `end_plate.beam_web_thickness` | t_w ≥ 6,19 D/F_u | Manual Ec. 9-3 |

## Asiento no rigidizado apernado (`connections/shear/seated.py`)

La viga apoya en el ala horizontal de un ángulo apernado al apoyo (Manual AISC Parte 10). La holgura incluye la tolerancia de longitud (¾ in por defecto). El ángulo superior es el detalle estándar de estabilidad L4×4×1/4 con dos pernos de 3/4 in por ala (o soldadura de 3/16 in); se comprueban sus dimensiones mínimas, no su resistencia, porque no toma parte de la reacción.

| `id` | Verificación | Norma |
|---|---|---|
| `seated.bearing_length` | l_b,min = máx(fluencia local del alma, aplastamiento local del alma, k_des) ≤ ala − holgura | Manual Ec. 10-1 a 10-3; §J10.2, §J10.3 |
| `seated.shear_yielding` | Fluencia por corte del ala, 0,60 F_y L t | §J4.2(a) |
| `seated.flexural_yielding` | R_n = (F_y L t²/4)/e_c, e_c = holgura + l_b/2 − t − 3/8 in | Manual Parte 10 |
| `seated.bolts` | n · mín(corte del perno, aplastamiento en el ángulo y en el apoyo) | §J3.7, §J3.11 |
| `seated.weld` | Con `support_weld` > 0 (asiento soldado): R_n = 2 r_w l_v²/√(l_v² + 20,25 e²), e = holgura + (ala − holgura)/2. Reemplaza `seated.bolts` | Manual Tabla 10-6 |
| `seated.top_angle_leg` | Ala del ángulo superior ≥ 4 in | Manual Parte 10, detalle estándar |
| `seated.top_angle_thickness` | Espesor ≥ 1/4 in | Manual Parte 10, detalle estándar |
| `seated.top_angle_length` | Largo ≥ 4 in | Manual Parte 10, detalle estándar |
| `seated.top_angle_bolts` | Pernos por ala ≥ 2 (asiento apernado) | Manual Parte 10, detalle estándar |
| `seated.top_angle_weld` | Soldadura ≥ 3/16 in (asiento soldado) | Manual Parte 10, detalle estándar |

La Tabla 10-5 entra con `l_b,req` redondeado al siguiente 1/16 in. El programa usa por defecto la `l_b,min` exacta (nunca menor que `k_des`) y permite fijar `bearing_length` para reproducir el valor tabulado. En II.A-12A, `k_des = 1,03 in` se redondea a 1 1/16 in; con el ángulo A36, la flexión da 90,0/59,9 kip frente a 95,5/63,6 kip con la longitud exacta.

## Asiento rigidizado soldado (`connections/shear/stiffened_seat.py`)

Placa de asiento sobre un rigidizador vertical de ancho W y largo l, soldados al apoyo (Manual AISC Parte 10). La placa de asiento es el detalle estándar de 3/8 in de espesor, 1 in más ancha que el rigidizador y soldada con filete de 5/16 in; el ángulo superior es el mismo detalle de estabilidad L4×4×1/4 del asiento no rigidizado.

| `id` | Verificación | Norma |
|---|---|---|
| `stiffened_seat.width` | W ≥ W_min = (R − R_a)/R_b + holgura + tolerancia, por fluencia (R_1, R_2) y aplastamiento local del alma (R_3, R_4 o R_5, R_6 según l_b/d) | Manual Tabla 9-4; §J10.2, §J10.3 |
| `stiffened_seat.weld` | R_n = 2 r_w · 1,2 l²/√(l² + 16 e²), e = 0,8 W | Manual Tabla 10-8 |
| `stiffened_seat.stiffener_thickness` | t ≥ máx(1,5 w, F_y,viga t_w / F_y,rigidizador); 1,5 w vale para placas de 50 ksi y electrodos E70 | Manual Parte 10 |
| `stiffened_seat.support_thickness` | t ≥ 3,09 D/F_u, o 6,19 D/F_u con asientos a ambos lados del alma | Manual Ec. 9-6, 9-7 |
| `stiffened_seat.seat_plate_bearing` | Aplastamiento de la placa de asiento sobre el rigidizador, φ 1,8 F_y W t | §J7.1 |
| `stiffened_seat.seat_plate_width` | Ancho de la placa ≥ W + 1 in | Manual Parte 10, detalle de II.A-14 |
| `stiffened_seat.seat_plate_thickness` | Espesor ≥ 3/8 in | Manual Parte 10, detalle de II.A-14 |
| `stiffened_seat.seat_plate_weld` | Soldadura ≥ 5/16 in | Manual Parte 10, detalle de II.A-14 |
| `stiffened_seat.seat_plate_weld_length` | Largo de soldadura (W) ≥ 0,2 l | Manual Parte 10, detalle de II.A-14 |
| `seated.top_angle_*` | Mínimos del ángulo superior de estabilidad, iguales que en el asiento no rigidizado | Manual Parte 10, detalle estándar |

## Conexión de corte: resultados comunes (`connections/shear/check.py`)

| `id` | Verificación | Norma |
|---|---|---|
| `shear_connection.beam_shear_yielding` | Fluencia por corte del alma de la viga sin destaje, 0,60 F_y d t_w; con destaje la verifica `coped_beam.shear_yielding` sobre el alma reducida | §J4.2(a); II.A-1B, II.A-17B |
| `shear_connection.axial_compression` | Compresión axial en un tipo sin procedimiento de compresión (todos salvo la placa simple y la placa extendida): se informa con capacidad 0 (no cumple) | — |
| `shear_connection.axial_unsupported` | Tracción axial en un tipo sin procedimiento axial (placa extendida, placa de extremo, asientos, doble ángulo soldado): capacidad 0 | — |

## Conexiones de momento (`connections/moment/fr_moment.py`)

Conexiones de momento totalmente restringidas al ala de una columna (F6, Manual AISC Partes 9 a 12): placas de ala apernadas (II.B-1), placas de ala soldadas (II.B-2) y alas soldadas directamente con soldadura de penetración completa (II.B-3). La fuerza de ala es P_f = M/d_m (Manual Ec. 11-1); con alas soldadas, d_m = d − t_f. Integradas en el proyecto (`moment_connection`), el comando `openconex moment`, la memoria, el plano, el 3D y la interfaz.

| `id` | Verificación | Norma |
|---|---|---|
| `moment.beam_flexural_rupture` | Rotura de la viga en los agujeros del ala de tracción, M_n = F_u A_fn S_x / A_fg; aplicable si F_u A_fn < Y_t F_y A_fg | §F13.1, Ec. F13-1 |
| `moment.web_bolts` | Placa del alma: Σ mín(corte, aplastamiento y desgarro en placa y alma); el perno inferior es el de borde | §J3.7, §J3.11 |
| `moment.web_plate_shear_yielding` | Fluencia por corte de la placa del alma | §J4.2(a) |
| `moment.web_plate_shear_rupture` | Rotura por corte de la placa del alma | §J4.2(b) |
| `moment.web_plate_block_shear` | Bloque de corte de la placa del alma (U_bs = 1) | §J4.3 |
| `moment.web_weld` | Dos soldaduras de la placa del alma a la columna, en corte directo | §J2.4; Manual Ec. 8-2 |
| `moment.web_support_rupture` | Rotura por corte del ala de la columna en las soldaduras, 2 l t_f | §J4.2(b) |
| `moment.flange_bolts` | Placas de ala apernadas: 2 Σ mín(corte, placa, ala de la viga) para P_f = M/d | §J3.7, §J3.11; Manual Ec. 11-1 |
| `moment.flange_plate_tension_yielding` | Fluencia por tracción de la placa de ala, P_f = M/(d + t_p) o M/(d + (t_sup + t_inf)/2) | §J4.1(a) |
| `moment.flange_plate_tension_rupture` | Rotura por tracción de la placa de ala apernada, A_n = (b − 2 d_h') t_p | §J4.1(b) |
| `moment.flange_plate_block_shear` | Bloque de corte de la placa de ala: mínimo de los casos 1, 2 y 3 del ejemplo II.B-1 | §J4.3 |
| `moment.beam_flange_block_shear` | Bloque de corte del ala de la viga (l_ev menos la tolerancia de longitud) | §J4.3 |
| `moment.flange_plate_weld` | Soldadura de la placa de ala apernada a la columna, k_ds = 1,5 | §J2.4, Ec. J2-5; Manual Ec. 8-2 |
| `moment.flange_plate_compression` | Compresión de la placa de ala, K = 0,65 y L entre pernos o hasta la soldadura | §J4.4; Comentario Tabla C-A-7.1 |
| `moment.top_plate_weld_to_beam` | Soldaduras longitudinales y transversal de la placa superior al ala, P_f = M/d | §J2.4(b), Ec. J2-6 |
| `moment.weld_base_metal` | Espesor mínimo de ala y placa para la soldadura, 3,09 D/F_u | Manual Ec. 9-6 |
| `moment.top_plate_weld_to_column` | Soldadura de la placa superior a la columna, k_ds = 1,5 | §J2.4, Ec. J2-5 |
| `moment.bottom_plate_weld_to_beam` | Soldaduras longitudinales de la placa inferior al ala | §J2.4; Manual Ec. 8-2 |
| `moment.beam_flange_rupture_at_welds` | Rotura por corte del ala de la viga junto a las soldaduras de la placa inferior | §J4.2(b) |
| `moment.bottom_plate_weld_to_column` | Soldadura de la placa inferior a la columna, k_ds = 1,5 | §J2.4, Ec. J2-5 |
| `moment.column_flange_local_bending` | Flexión local del ala de la columna bajo la fuerza de ala | §J10.1 |
| `moment.column_web_local_yielding` | Fluencia local del alma de la columna, l_b = espesor de la placa o del ala | §J10.2 |
| `moment.column_web_crippling` | Aplastamiento local del alma de la columna | §J10.3 |
| `moment.column_web_compression_buckling` | Pandeo del alma de la columna, con vigas a ambos lados (en placas de extremo, siempre en el ala de compresión, DG4 Ec. 3.26) | §J10.5 |
| `moment.column_panel_zone` | Corte de la zona de panel, con el corte de la columna dado | §J10.6 |

### Placas de extremo de momento (`connections/moment/end_plate.py`)

Placas de extremo enrasadas y extendidas según AISC Design Guide 16 (Murray y Shoemaker, 2002, revisión 2016; `type: end_plate`) y, del lado de la columna y para la 8ES, AISC Design Guide 4, 2ª ed. (Murray y Sumner, 2004). Diez configuraciones (`layout`): `flush_2`, `flush_4`, `flush_4_stiffened_between`, `flush_4_stiffened_inside` (DG16 Tablas 3-2 a 3-5), `extended_4`, `extended_4_stiffened`, `extended_1_2`, `extended_1_3`, `extended_1_3_stiffened` (DG16 Tablas 4-2 a 4-6) y `extended_8_stiffened` (8ES, DG4 Tabla 3.3, con h_1 a h_4 medidos al centro del ala de compresión; solo placa gruesa: con placa delgada la rotura de pernos se informa con capacidad 0, DG4 §3.3). La resistencia sigue el diagrama de revisión del Apéndice B con la errata de 2016: placa gruesa si φM_np ≤ φ_b M_pl/1,11 (rotura de pernos sin palanca), si no placa delgada (rotura con palanca, M_q). Las distancias d_n van al centro del ala de compresión y h_n a su cara exterior. La carga axial se convierte en M_u = |M| − P(h − t_f)/2 (P positiva en compresión; §2.5.3, punto 11). La fuerza de ala para las demás verificaciones es F_fu = M_u/(d − t_f). En ASD se usa Ω = 1,67 (fluencia) y 2,00 (pernos) en lugar de mayorar el momento por 1,5 como la Guía; ambos dan el mismo resultado.

| `id` | Verificación | Norma |
|---|---|---|
| `moment.end_plate_yielding` | Fluencia de la placa: φ_b F_py t_p² Y / γ_r, con Y de la tabla de la configuración y γ_r = 1,25 (enrasada) o 1,0 (extendida); s = ½√(b_p g), p_f ≤ s | DG16 Tablas 3-2 a 4-6, §2.5.3 |
| `moment.end_plate_bolt_rupture` | Rotura de pernos: φM_np = φ 2P_t Σd_n (placa gruesa) o φM_q con Q_max,i y Q_max,o (Ec. 2-11 a 2-19), T_b de la Tabla J3.1 (fracción de la Tabla 2-1 con apriete ajustado) | DG16 Apéndice B |
| `moment.end_plate_shear_yielding` | Placas extendidas sin rigidizador (DG4 paso 8): fluencia por corte de la extensión, F_fu/2 ≤ φ 0,6 F_y b_p t_p | §J4.2(a); DG16 §2.6 |
| `moment.end_plate_shear_rupture` | Placas extendidas sin rigidizador (DG4 paso 9): rotura por corte en los pernos exteriores, A_n = (b_p − 2(d_h + 1/16 in)) t_p | §J4.2(b); DG16 §2.6 |
| `moment.end_plate_bolt_shear` | Corte en los pernos del ala en compresión (todos los de tracción si `symmetric`, si no dos): Σ mín(corte, aplastamiento o desgarro en la placa, aplastamiento en el ala de la columna). El desgarro usa la distancia libre al agujero vecino y, en la fila exterior, también al borde de la placa (el corte puede cambiar de sentido) | §J3.7, §J3.11; DG16 §2.5.3 punto 5; DG4 Ec. 3.17 a 3.19 |
| `moment.end_plate_web_weld_shear` | Soldadura del alma para el corte, en la longitud mín(d/2 − t_f, d − 2t_f − p_f − (n_i − 1)p_b − 2d_b) | §J2.4; DG16 §2.5.3 punto 10 |
| `moment.end_plate_web_weld_tension` | Soldadura del alma junto a los pernos de tracción para desarrollar la fluencia del alma, φF_y t_w ≤ 2 × 1,5 r_w | §J2.4, Ec. J2-5; DG16 §2.5.3 punto 9 |
| `moment.end_plate_flange_weld` | Filete de las alas (si se da `flange_weld`): máx(F_fu, 0,6 F_y b_f t_f) ≤ 1,5 r_w (2b_f − t_w); sin él, penetración completa | §J2.4, Ec. J2-5; DG16 §2.5.3 punto 8 |

Lado de la columna (DG4, pasos 14 a 20), con la fuerza de ala F_fu y N = t_fb + 2 × `weld_reinforcement` (penetración completa) o t_fb + 0,707 w (filete):

| `id` | Verificación | Norma |
|---|---|---|
| `moment.column_flange_bending` | Configuraciones 4E, 4ES y 8ES: espesor requerido del ala, t_fc,req = √(1,11 φM_np / (φ_b F_yc Y_c)) ≤ t_fc, con Y_c sin rigidizar o, con `continuity_plate`, rigidizado (p_so = p_si = (c − t_s)/2) | DG4 Ec. 3.20; Tablas 3.4 y 3.5 |
| `moment.column_flange_strength` | Configuraciones 4E, 4ES y 8ES, ala sin rigidizar: F_fu ≤ φ_b F_yc Y_c t_fc² / (d − t_fb) | DG4 Ec. 3.21, 3.22 |
| `moment.continuity_plates` | Con `continuity_plate`: F_su = F_fu − mín φR_n (ala sin rigidizar, fluencia, pandeo y aplastamiento del alma) ≤ φ F_y (2 b_s t_s), b_s = (b_fc − t_wc)/2; esas cuatro verificaciones pasan a no aplicables | DG4 Ec. 3.32; §J10.8, §J4.4 |

`moment.column_web_local_yielding` usa la Ec. 3.24 de la DG4, R_n = [C_t(6k_c + 2t_p) + N] F_yc t_wc con φ = 1,0 y C_t = 0,5 cerca del extremo de la columna. `moment.column_web_compression_buckling` se verifica siempre en el ala de compresión (DG4 Ec. 3.26 y 3.27, igual que §J10.5) y `moment.column_web_crippling` es §J10.3 con l_b = N (DG4 Ec. 3.29 a 3.31). `moment.column_panel_zone`, como en las demás conexiones de momento. Las configuraciones enrasadas y multifila 1/2 y 1/3 no tienen líneas de fluencia del ala de la columna en las guías: en ellas no se verifica la flexión del ala de la columna.

## Anclajes (`kernel/anchors.py`, ACI 318-19 Cap. 17, solo LRFD)

| `id` | Verificación | Norma | Placa base |
|---|---|---|---|
| `anchor.steel_tension` | Acero del anclaje a tracción | §17.6.1.2 | ✔ |
| `anchor.concrete_breakout_tension` | Arrancamiento del concreto a tracción (grupo) | §17.6.2 | ✔ si `hef` > 0 |
| `anchor.pullout` | Extracción (tuerca o gancho) | §17.6.3 | ✔ |
| `anchor.side_face_blowout` | Desprendimiento lateral del concreto | §17.6.4 | ✔ si h_ef > 2,5 c_a1 |
| `anchor.steel_shear` | Acero del anclaje a corte (×0,8 con mortero) | §17.7.1 | ✔ sin fricción |
| `anchor.concrete_breakout_shear` | Arrancamiento del concreto a corte | §17.7.2 | ✔ corte en anclajes con borde |
| `anchor.pryout` | Desprendimiento por palanca | §17.7.3 | ✔ corte en anclajes |
| `anchor.interaction` | Interacción tracción–corte | §17.8 | ✔ tracción y corte en anclajes |
| `anchor.shear_lug_bearing` | Aplastamiento del concreto en la llave de corte | §17.11.2 | ✔ con llave |
| `anchor.shear_lug_breakout` | Arrancamiento del concreto por la llave | §17.11.3 | ✔ con llave y `ca1` |
| `anchor.reinforcement` | Refuerzo de anclaje en tracción | §17.5.2.1 | con refuerzo LRFD |
| `anchor.reinforcement_development` | Desarrollo del gancho sobre el plano de falla | §25.4.3.1 | con refuerzo LRFD |
| `anchor.reinforcement_straight_development` | Desarrollo recto bajo el plano de falla, con reducción por exceso de área | §25.4.2.4, §25.4.10 | con refuerzo LRFD |
| `anchor.reinforcement_embedment` | Empotramiento requerido para el refuerzo | §17.5.2.1 | con refuerzo LRFD |
| `concrete.bearing` | Aplastamiento en el concreto (título reservado; la placa base usa `base_plate.bearing`) | AISC 360-22 §J8 | — |

## Pernos (`kernel/bolts.py`, AISC 360-22 §J3)

| `id` | Verificación | Norma | Placa base |
|---|---|---|---|
| `bolt.tension` | Tracción (también barras de anclaje en ASD) | §J3.7, Ec. J3-1 | ✔ ASD |
| `bolt.shear` | Corte | §J3.7, Ec. J3-1 | ✔ ASD |
| `bolt.combined` | Interacción tracción y corte | §J3.8 | — |
| `bolt.slip` | Deslizamiento crítico | §J3.9, Ec. J3-4 | — |
| `bolt.bearing` | Aplastamiento en el agujero | §J3.11(a) | — |
| `bolt.tearout` | Desgarro en el agujero | §J3.11(b) | — |
| `bolt.min_spacing` | Separación mínima | §J3.3 | — |
| `bolt.max_spacing` | Separación máxima | §J3.5 | — |
| `bolt.min_edge` | Distancia mínima al borde | §J3.4, Tabla J3.4 | — |
| `bolt.max_edge` | Distancia máxima al borde | §J3.5 | — |
| `bolt_group.eccentric` | Grupo de pernos con carga excéntrica (elástico o centro instantáneo) | Manual AISC Parte 7 | — |
| `prying.tension` | Tracción con efecto palanca | Manual AISC Parte 9 | — |
| `prying.min_thickness` | Espesor mínimo para despreciar el efecto palanca | Manual AISC Parte 9 | — |

## Soldaduras (`kernel/welds.py`, `kernel/weld_group.py`, AISC 360-22 §J2)

| `id` | Verificación | Norma | Placa base |
|---|---|---|---|
| `weld.strength` | Resistencia de soldadura de filete (con aumento direccional) | §J2.4, Ec. J2-4, J2-5 | ✔ con `flange_weld` |
| `weld.min_size` | Tamaño mínimo de filete | §J2.2b, Tabla J2.4 | — |
| `weld.max_size` | Tamaño máximo de filete | §J2.2b(b) | — |
| `weld.min_length` | Longitud mínima de filete | §J2.2b(c) | — |
| `weld.pjp` | Soldadura de penetración parcial | §J2.4, Tabla J2.5 | — |
| `weld_group.eccentric` | Grupo de soldaduras con carga excéntrica (elástico o centro instantáneo, con C1 de la Tabla 8-3) | §J2.4(c); Manual Parte 8 | — |

## Elementos de conexión (`kernel/elements.py`, AISC 360-22 §J4)

| `id` | Verificación | Norma |
|---|---|---|
| `element.tension_yielding` | Fluencia en tracción | §J4.1(a), Ec. J4-1 |
| `element.tension_rupture` | Rotura en tracción | §J4.1(b), Ec. J4-2 |
| `element.shear_yielding` | Fluencia en corte | §J4.2(a), Ec. J4-3 |
| `element.shear_rupture` | Rotura en corte | §J4.2(b), Ec. J4-4 |
| `element.block_shear` | Bloque de corte | §J4.3, Ec. J4-5 |
| `element.compression` | Compresión | §J4.4 |
| `element.flexural_yielding` | Fluencia en flexión | §J4.5 |
| `element.flexural_rupture` | Rotura en flexión | §J4.5 |

En la placa base, las verificaciones de la llave usan estas funciones pero se renombran a `base_plate.lug_*`.

## Fuerzas concentradas (`kernel/local.py`, AISC 360-22 §J10)

| `id` | Verificación | Norma |
|---|---|---|
| `local.flange_bending` | Flexión local del ala | §J10.1, Ec. J10-1 |
| `local.web_yielding` | Fluencia local del alma | §J10.2, Ec. J10-2/J10-3 |
| `local.web_crippling` | Aplastamiento local del alma | §J10.3, Ec. J10-4/J10-5 |
| `local.web_compression_buckling` | Pandeo del alma por compresión | §J10.5, Ec. J10-8 |
| `local.panel_zone` | Corte en la zona de panel | §J10.6, Ec. J10-9 a J10-12 |
