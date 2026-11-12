# 7. Validación

Cada parte del cálculo se compara con ejemplos resueltos o tablas publicadas. Las pruebas están en `tests/` y corren en cada pull request, en Windows, macOS y Linux. El [manual de verificación](../verificacion/README.md) ([English](../verificacion/README.en.md)) resume la evidencia y el protocolo de comparación cruzada.

## AISC Design Guide 1 (3ª ed.)

`tests/reference/dg1/*.toml` guarda los datos y resultados de 20 ejemplos, y `tests/base_plate/test_dg1_acceptance.py` compara 369 valores publicados con una tolerancia del 1 %. Hay tolerancias mayores en algunos valores, con su motivo escrito en cada archivo, porque la guía redondea pasos intermedios.

| Ejemplo | Tema |
|---|---|
| 4.7-1, 4.7-2 | compresión axial, sin y con confinamiento del concreto |
| 4.7-3 | tracción axial (levantamiento neto) |
| 4.7-4 | corte resistido por anclajes, limitado por el borde (también `tests/base_plate/test_pedestal_concrete.py`, con la verificación completa: φV_cbg = 18,4 kip) |
| 4.7-5 | llave de corte (también `tests/base_plate/test_shear_lug.py`, con la verificación completa) |
| 4.7-6 | anclajes con tracción, corte y flexión de la barra |
| 4.7-7, 4.7-8 | bases de arriostramiento: tracción y corte; compresión, corte y fricción |
| 4.7-9 | flexión pura con placa extendida |
| 4.7-10, 4.7-11 | compresión con momento pequeño y grande |
| 4.7-12, 4.7-13 | levantamiento con momento grande y pequeño |
| 4.7-14 | flexión biaxial (también `tests/base_plate/test_biaxial.py`: interacción 0,988) |
| 4.7-15 | refuerzo de anclaje (gancho l_dh = 9,71 in; recto l_d = 17,1 in; l_e = 15,2 in) |
| 5.3-1 | base empotrada tipo I (también `tests/base_plate/test_embedded_base.py`, con la verificación completa) |
| 6.4-1 | base débil con anclajes dúctiles (sísmica) |
| B.2-1, B.2-2, B.3-1 | distribución triangular y área efectiva (Apéndice B) |

## Steel Tube Institute (2024)

El artículo *HSS Base Plate Design for Axial Compression and Bending Moment* (M. Manor, septiembre de 2024) adapta la DG1 a columnas HSS e incluye dos ejemplos resueltos. Se comparan con `tests/base_plate/test_hss_moment.py`:

| Ejemplo | Tema | Valores comprobados |
|---|---|---|
| 1 | HSS circular 12x0.375, Pu = 500 kip, placa 18x18x1¼ in, f'c = 3 ksi | t_p,req = 1,10 in |
| 2 | HSS rectangular 16x12x½, Pu = 376 kip, Mu = 300 kip·ft, placa 24x20x1½ in, f'c = 4 ksi | Y = 9,71 in, T = 53,3 kip, t_p,compresión = 1,38 in, t_p,tracción = 0,73 in, 13,3 kip/anclaje |

El artículo no incluye un ejemplo de HSS circular con momento; por eso OpenConex rechaza ese caso en lugar de presentar una aproximación no validada.

## Manual AISC (16ª ed.)

| Tabla | Contenido | Valores | Prueba |
|---|---|---|---|
| 7-6 | grupos de pernos excéntricos, una fila | 242 + 22 de C' | `tests/kernel/test_bolt_group_manual.py` |
| 7-7, 7-8 | dos filas (gramil 3 y 5½ in) | 1 776 | `tests/kernel/test_bolt_group_manual_two_rows.py` |
| 8-3 | coeficiente C1 del electrodo | 6 | `tests/kernel/test_weld_group.py` |
| 8-4, 8-5 | soldaduras en dos líneas | 496 | `tests/kernel/test_weld_group_manual.py` |
| 8-7, 8-8, 8-9 | soldaduras en caja y en C | 1 760 | `tests/kernel/test_weld_group_manual_shapes.py` |
| 8-6, 8-10, 8-11 | soldaduras en caja y en L | 1 760 | `tests/kernel/test_weld_group_manual_angles.py` |
| 14-2 | agujeros y arandelas de placa base | todas las filas | `tests/test_bolting_and_model.py` |

La tolerancia es del 1 % (o 0,005 en valores pequeños), porque las tablas redondean a tres cifras.

## AISC Design Examples (v16.0 y v16.1)

| Ejemplo | Tema | Prueba |
|---|---|---|
| II.A-1A, Parte B | doble ángulo apernado: transferencia de corte en los agujeros (282/187 kip), fluencia (441/294) y rotura (302/201) por corte, bloque de corte (315/210), LRFD/ASD | `tests/connections/test_double_angle.py` |
| II.A-2A, Parte B | doble ángulo apernado a la viga y soldado al apoyo: agujeros (286/190 kip), fluencia (528/352) y rotura (363/242) por corte, bloque de corte (380/253), soldaduras B (318/212) y t_min = 0,238 in | `tests/connections/test_double_angle.py` |
| II.A-1B | doble ángulo con corte y tracción: pernos en el alma (182/122 kip), pernos a tracción con efecto palanca (98,1/65,4), ángulos a corte y tracción, bloques de corte (368/245, 542/362, 379/253) e interacción, y viga (192/128, 662/440, 256/171, 159/106). La interacción usa el menor bloque axial (forma U), algo más conservador que el ejemplo | `tests/connections/test_double_angle_axial.py` |
| II.A-3 | doble ángulo totalmente soldado: soldaduras A (257/171 kip) y B (260/173), fluencia (450/300) y rotura (439/293) por corte, t_w,min = 0,286 in y t_f,min = 0,190 in | `tests/connections/test_double_angle.py` |
| II.A-17A | placa simple convencional: agujeros (58,5/38,9 kip; el centro instantáneo da C = 3,556 frente a 3,54 interpolado, 0,5 %), fluencia (86,4/57,6) y rotura (58,5/39,0) por corte, bloque de corte (65,3/43,6), límites dimensionales | `tests/connections/test_single_plate.py` |
| II.A-17B | placa simple con corte y tracción axial: pernos (98,9/65,9 kip con C a 30°), fluencia y rotura por corte, tracción y flexión, pandeo lateral-torsional, interacciones (0,181 y 0,500), bloques de corte en ambas direcciones e interacción (0,241), corte del ala de la columna | `tests/connections/test_single_plate_axial.py` |
| II.A-18 | placa simple en viga con destaje superior: pernos (58,5/38,9 kip), bloque de corte de la placa (65,3/43,6) y bloque de corte de la viga destajada (88,2/58,7) | `tests/connections/test_shear_project.py` |
| II.A-4, II.A-6 (A y B), II.A-7 | viga con destaje: flexión de la sección destajada con destaje superior (374/249, 116/77,2, 150/100 kip) y en ambas alas (37,9/25,2), corte del alma, bloque de corte del alma (68,6/45,8) y S_c, Z_c de la Tabla 9-2 | `tests/connections/test_coped_beam.py` |
| II.A-9 | doble ángulo desplazado: fila de pernos compartida por dos vigas, doble cortante (35,8 kip/perno) y aplastamiento en el alma del apoyo (31,2 kip/perno) para 2R | `tests/connections/test_double_angle.py` |
| II.A-10 | conexión sesgada de doble placa doblada: pernos 7/8 in (grupo 61,4/40,9 kip con t = 5/16 in), fluencia por corte (57,5/38,3), rotura por corte (44,9/30,0 con 5/16; 53,8/35,9 con 3/8), bloque de corte (56,1/37,5), soldadura en C (C = 2,52; D_req = 3,11/16), t_w,min = 0,296 in y t_p,min = 5/16 in | `tests/connections/test_bent_plate.py` |
| II.A-6 C/D | refuerzo del destaje: placa doble 1/4 × 6,5 in (S_net = 25,5 in³, Z_net = 44,8 in³; R_n = 183/110 kip) y rigidizador 4 × 1/4 in (S_xc = 28,6 in³; R_n = 151/90,4 kip), más esbelteces y soldaduras | `tests/connections/test_cope_reinforcement.py` |
| II.A-19A | placa simple extendida con dos líneas de pernos: grupo (41,7/27,7 kip), t_max = 0,575 in, corte, bloque de corte (145/96,5), flexión y pandeo lateral-torsional (810/539 kip·in), interacción (0,200), rotura por flexión (624/416; Z_net = 12,75 in³ contra 12,8 de la Tabla 15-2) | `tests/connections/test_extended_single_plate.py` |
| II.A-19B | placa simple extendida con tracción axial (PL ¾ × 15 in, l_ev = 1½ in, l_eh = 2 in, l_eh de la viga 2 in): grupo (112/74,8 kip con la Tabla 7-7 a 30°; el ICR a 38,7° da 120), fluencia (339/226) y rotura (199/133) por corte, fluencia (509/338) y rotura (332/221) por tracción, flexión (1 900/1 260 kip·in) y rotura por flexión (1 260/840), bloques de corte (237/158 y 369/246 kip), interacciones (0,246, 0,592 y 0,127), t_max = 0,971 in y corte del alma de la columna (386/258). Comentarios: compresión de la placa con K = 1,2 (410/272 kip). Hasta 0.5.15 el ejemplo y la prueba usaban una geometría distinta (placa de 14½ in, l_ev = 1¼ in, l_eh = 1¾ in) y valores que no son los publicados | `tests/connections/test_extended_single_plate_axial.py` |
| II.A-1B, II.A-17B | corte del alma de la viga W18×50 sin destaje: 192/128 kip (`shear_connection.beam_shear_yielding`) | `tests/connections/test_beam_web_shear.py` |
| II.A-11A, Parte B | placa de extremo de corte: agujeros (96,4/64,1 kip), fluencia (128/85,3) y rotura (86,3/57,5) por corte, bloque de corte (93,8/62,5), soldaduras (67,9/45,3) y t_w,min = 0,286 in | `tests/connections/test_end_plate.py` |
| II.A-12A | asiento no rigidizado apernado: longitud de apoyo por fluencia (0,309/0,307 in) y aplastamiento local (negativo, gobierna k_des = 1,03 in), fluencia por corte del ala A36 (108/72 kip) y flexión del ala con l_b = 1 1/16 in (90,0/59,9, Tabla 10-5); el programa usa k_des por defecto (95,5/63,6) y admite el valor tabulado; 4 pernos, 71,6/47,7 kip; ángulo superior estándar L4×4×1/4 con dos pernos por ala | `tests/connections/test_seated.py`, `tests/connections/test_shear_project.py` |
| II.A-13, II.A-16 | asiento soldado: soldaduras (66,7/44,5 y 53,4/35,6 kip, Tabla 10-6); ángulo superior soldado con filete de 3/16 in | `tests/connections/test_seated.py` |
| II.A-14, II.A-15 | asiento rigidizado: W_min por aplastamiento (6,93/6,96 in) y fluencia (3,59/3,61 in), soldaduras (139/93,0 kip, Tabla 10-8), espesor del rigidizador (0,469 in) y del apoyo (0,238 in; 0,476 in con asientos a ambos lados, que no cumple); placa de asiento PL 3/8×7×8 con aplastamiento sobre el rigidizador (295/197 kip) y soldadura de longitud mínima 0,2 l = 3 in | `tests/connections/test_stiffened_seat.py` |
| II.B-1 | placas de ala apernadas: rotura de la viga (318/211 kip·ft), placa del alma (pernos 71,2/47,5, fluencia 101/67,3, rotura 65,9/43,9, bloque 82,2/54,9, soldadura 100/66,8, ala de la columna 410/273), pernos de ala (194/130), placa a tracción (237/157 y 183/122), bloques de corte (300/200 y 294/197), soldadura a la columna (D_min = 5,51), compresión (237/157) y columna (171/114, 186/124, 233/155 kip) | `tests/moment/test_fr_moment.py` |
| II.B-2 | placas de ala soldadas: tracción (270/180), soldadura superior a la viga (169/113, Ec. J2-6), t_min = 0,238 in, soldaduras a la columna (D_min = 6,39 y 4,38), compresión (295/196), soldadura inferior (l_min = 12,1 in) y rotura del ala de la viga (419/279 kip) | `tests/moment/test_fr_moment.py` |
| II.B-3 | alas soldadas con penetración completa: solo la placa del alma y la columna (el ejemplo no da valores propios) | `tests/moment/test_fr_moment.py` |

## AISC Design Guide 16 (2002, revisión 2016)

`tests/moment/test_end_plate_dg16.py` comprueba los nueve ejemplos de placas de extremo de momento (capítulos 3 y 4), con la placa y los pernos del procedimiento de diseño 1 (placa gruesa) y del 2 (placa delgada), contra la resistencia φM_n que da la Guía con el diagrama del Apéndice B (LRFD): Y, la clasificación gruesa/delgada y φM_n con tolerancia del 1 %; además φM_q, Q_max,i y Q_max,o del perno de prueba del procedimiento 2 y la carga axial del ejemplo 4.2.3 (16,9 kip de tracción suman 200 k-in).

| Ejemplo | Configuración | φM_n (procedimientos 1 / 2, k-in) |
|---|---|---|
| 3.2.1 | enrasada de dos pernos | 673 / 693 |
| 3.2.2 | enrasada de cuatro pernos | 783 / 643 |
| 3.2.3 | enrasada de cuatro pernos, rigidizador entre filas | 1045 / 1069 |
| 3.2.4 | enrasada de cuatro pernos, rigidizador bajo las filas | 1045 / (ver hallazgos) |
| 4.2.1 | extendida 4E | 1987 / 2108 |
| 4.2.2 | extendida 4ES | 1987 / 1824 |
| 4.2.3 | extendida multifila 1/2, con tracción axial | (ver hallazgos) / 2431 |
| 4.2.4 | extendida multifila 1/3 | 5460 / 5415 |
| 4.2.5 | extendida multifila 1/3 rigidizada | 5460 / 4935 |

Diferencias de redondeo de la Guía: en 4.2.2 redondea a_i = 0,375 a 0,38 in (Q_max 1 % menor, φM_q 1824 frente a 1809 k-in) y en 4.2.4 usa d_3 = 28,6875 in en lugar de h_3 = 28,875 in en Y (380,3 frente a 381,1 in).

## AISC Design Guide 4 (2ª ed., 2004)

`tests/moment/test_end_plate_dg4.py` compara los ejemplos del capítulo 4 (viga W21×55 a columna W14×109, LRFD):

| Ejemplo | Valores comprobados |
|---|---|
| 4E A (sísmico, 1¼ in A490) | Y_c = 170,1 in, t_fc,req = 1,10 in; con placas de continuidad de ½ in, Y_c = 309,1 in y 0,82 in; ala sin rigidizar 279 kip, fluencia del alma 326 kip (N = 1,15 in), pandeo 330 kip, aplastamiento 284 kip; pernos de compresión en la placa 508 kip con el agujero de la Guía |
| 4E B (viento, 1 in A325, filete de ⅜ in) | t_fc,req = 0,790 in, aplastamiento del alma 275 kip (N = 0,787 in) |
| 8ES (1 in A325) | Y_p = 277,6 in, M_np = 11 470 k-in, Y_c = 224,6 in y t_fc,req = 0,97 in; rigidizada, 377,7 in y 0,75 in; ala 369 kip, fluencia 306 kip, pandeo 330 kip, aplastamiento 284 kip |

Diferencias documentadas:

- Los agujeros son los de AISC 360-22 Tabla J3.3 (1⅜ in para pernos de 1¼ in y 1⅛ in para 1 in); la Guía usa 1 5/16 y 1 1/16 in. En 4E A el desgarro de los pernos exteriores da 91,4 kip en lugar de 94,5 kip (503 frente a 508 kip en total); la prueba también comprueba los 94,5 kip con el agujero de la Guía.
- La Guía toma el desgarro hacia el borde de la placa en los pernos exteriores de 4E A, pero no en 4E B ni en 8ES (411 y 807 kip). OpenConex lo considera siempre, porque el corte puede cambiar de sentido: 314 y 646 kip.
- En 4E B la Guía usa N = t_fb = 0,522 in para la fluencia del alma (289 kip) y N = 0,787 in para el aplastamiento; OpenConex usa 0,787 in en ambos (296 kip).
- La fuerza de las placas de continuidad (Ec. 3.32) se calcula con las resistencias de los pasos 15 a 18: 396 − 279 = 117 kip en 4E A y 399 − 284 = 115 kip en 8ES. La Guía resta valores que no coinciden con esos pasos (268 kip) y publica 128 y 131 kip.
- El ejemplo 8ES escribe h_2 = 22,24 in en Y_c rigidizado, en lugar de 22,29 in.
- La fluencia por corte de la extensión usa φ = 1,0 (AISC 360-22 §J4.2) en lugar del 0,9 de la Guía (LRFD 1999).

## Hallazgos de la validación

- **DG16, ejemplo 3.2.4, procedimiento 2:** φM_np = 1045 ≤ φ_b M_pl/1,11 = 1064 k-in, así que el diagrama del Apéndice B corregido por la errata de 2016 clasifica la placa como gruesa y da mín(φM_np, φ_b M_pl/γ_r) = 945 k-in (fluencia de la placa). La Guía publica 901 k-in (rotura de pernos con palanca), que corresponde a la rama de placa delgada. La prueba comprueba 945 y 1045 k-in.
- **DG16, ejemplo 4.2.3, procedimiento 1:** φM_np = 2782 k-in supera en 0,4 % a φ_b M_pl/1,11 = 2772 k-in, así que el diagrama toma la rama de placa delgada (palanca con T_b = 19 kip para los pernos de 5/8 in). La Guía publica la resistencia de placa gruesa, 2782 k-in.

- **Soldaduras concéntricas:** si todos los elementos son paralelos se usa §J2.4(b) sin compatibilidad de deformaciones. Si son longitudinales y transversales, se toma la mayor entre la compatibilidad y la Ec. J2-6.
- **Electrodos E80 y superiores:** el método del centro instantáneo usa el C1 de la Tabla 8-3, no FEXX/70 (E80: 1,03 en lugar de 1,14).
- **Grupos en L con la carga cerca del centroide de resistencia:** el centro instantáneo puede quedar del lado opuesto a la estimación elástica. En ese caso la resistencia se limita a la de traslación pura, que es lo que da la Tabla 8-10.
- **Tabla 14-2:** se corrigieron los diámetros de agujero de 1, 1¼, 1½ y 1¾ in.

## Otras pruebas

- **Conexiones de corte en proyecto:** los ejemplos `shear_single_plate.ocnx` y `shear_double_angle_coped.ocnx` reproducen II.A-17A y II.A-4 a través del archivo, las combinaciones y el despachador (`tests/connections/test_shear_project.py`), con memoria, comando, plano y 3D; la ventana de la interfaz se prueba en `tests/outputs/test_gui_shear.py`.

- **Unidades:** pruebas de propiedades (hypothesis) de ida y vuelta entre unidades.
- **Centro instantáneo:** equilibrio de fuerzas y momentos, resistencia decreciente con la excentricidad, límite elástico ≤ ICR.
- **Importación:** un Excel sintético con el formato de SAP2000 (`tests/test_csi_import.py`). Se probó además con una exportación real de SAP2000 v27, que no se incluye en el repositorio.
- **Salidas:** HTML, DOCX, PDF, DXF, STEP y STL se generan y se vuelven a leer (`tests/outputs/`).
- **Licencias de dependencias:** se revisan en la integración continua (`tools/check_licenses.py`).
