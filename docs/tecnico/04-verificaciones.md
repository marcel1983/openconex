# 4. Catálogo de verificaciones

Cada verificación tiene un identificador estable (`id`), que aparece en la traza y en los archivos de resultados. Su título en español e inglés está en `i18n/*.toml` bajo `check.<id>`. Esta lista debe contener todos los identificadores; la prueba `tests/test_docs.py` lo comprueba.

Columna **Placa base**: ✔ la usa `check_base_plate`; — solo existe en la biblioteca (para las conexiones en desarrollo o para uso directo desde Python).

## Placa base (`connections/base_plate`)

| `id` | Verificación | Norma | Placa base |
|---|---|---|---|
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
| `base_plate.lug_anchor_embedment` | Empotramiento de anclajes con llave (h_ef ≥ 2,5 h_sl) | ACI 318-19 §17.11.1 | ✔ |
| `base_plate.plate_bending_rods` | Flexión de la placa por los anclajes en tracción | DG1 Ej. 4.7-3, 4.7-7 | — |
| `base_plate.embedded_moment` | Momento resistente de la base empotrada | DG1 §5.2 | ✔ con `embedded_base` |
| `base_plate.face_plate_bearing` | Aplastamiento del concreto en las placas de cara | DG1 §5.3 | ✔ con `embedded_base` |
| `base_plate.face_plate_thickness` | Espesor de las placas de cara | DG1 §5.3 | ✔ con `embedded_base` |
| `base_plate.face_plate_seismic` | Espesor sísmico mínimo de las placas de cara, máx(0,75 t_w, 3/8 in) | AISC 341-22 §F3.5b.4 | ✔ con `embedded_base` |

## Anclajes (`kernel/anchors.py`, ACI 318-19 Cap. 17, solo LRFD)

| `id` | Verificación | Norma | Placa base |
|---|---|---|---|
| `anchor.steel_tension` | Acero del anclaje a tracción | §17.6.1.2 | ✔ |
| `anchor.concrete_breakout_tension` | Arrancamiento del concreto a tracción (grupo) | §17.6.2 | ✔ si `hef` > 0 |
| `anchor.pullout` | Extracción (tuerca o gancho) | §17.6.3 | ✔ |
| `anchor.side_face_blowout` | Desprendimiento lateral del concreto | §17.6.4 | — |
| `anchor.steel_shear` | Acero del anclaje a corte (×0,8 con mortero) | §17.7.1 | ✔ sin fricción |
| `anchor.concrete_breakout_shear` | Arrancamiento del concreto a corte | §17.7.2 | — |
| `anchor.pryout` | Desprendimiento por palanca | §17.7.3 | — |
| `anchor.interaction` | Interacción tracción–corte | §17.8 | — |
| `anchor.shear_lug_bearing` | Aplastamiento del concreto en la llave de corte | §17.11.2 | ✔ con llave |
| `anchor.shear_lug_breakout` | Arrancamiento del concreto por la llave | §17.11.3 | ✔ con llave y `ca1` |
| `anchor.reinforcement` | Refuerzo de anclaje en tracción | §17.5.2.1 | con refuerzo LRFD |
| `anchor.reinforcement_development` | Desarrollo del refuerzo de anclaje | §25.4.3.1 | con refuerzo LRFD |
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
