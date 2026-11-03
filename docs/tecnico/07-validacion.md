# 7. Validación

Cada parte del cálculo se compara con ejemplos resueltos o tablas publicadas. Las pruebas están en `tests/` y corren en cada pull request, en Windows, macOS y Linux.

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
| 4.7-15 | refuerzo de anclaje |
| 5.3-1 | base empotrada tipo I (también `tests/base_plate/test_embedded_base.py`, con la verificación completa) |
| 6.4-1 | base débil con anclajes dúctiles (sísmica) |
| B.2-1, B.2-2, B.3-1 | distribución triangular y área efectiva (Apéndice B) |

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
| II.A-3 | doble ángulo totalmente soldado: soldaduras A (257/171 kip) y B (260/173), fluencia (450/300) y rotura (439/293) por corte, t_w,min = 0,286 in y t_f,min = 0,190 in | `tests/connections/test_double_angle.py` |
| II.A-17A | placa simple convencional: agujeros (58,5/38,9 kip; el centro instantáneo da C = 3,556 frente a 3,54 interpolado, 0,5 %), fluencia (86,4/57,6) y rotura (58,5/39,0) por corte, bloque de corte (65,3/43,6), límites dimensionales | `tests/connections/test_single_plate.py` |
| II.A-17B | placa simple con corte y tracción axial: pernos (98,9/65,9 kip con C a 30°), fluencia y rotura por corte, tracción y flexión, pandeo lateral-torsional, interacciones (0,181 y 0,500), bloques de corte en ambas direcciones e interacción (0,241), corte del ala de la columna | `tests/connections/test_single_plate_axial.py` |
| II.A-4, II.A-6 (A y B), II.A-7 | viga con destaje: flexión de la sección destajada con destaje superior (374/249, 116/77,2, 150/100 kip) y en ambas alas (37,9/25,2), corte del alma, bloque de corte del alma (68,6/45,8) y S_c, Z_c de la Tabla 9-2 | `tests/connections/test_coped_beam.py` |
| II.A-19A | placa simple extendida con dos líneas de pernos: grupo (41,7/27,7 kip), t_max = 0,575 in, corte, bloque de corte (145/96,5), flexión y pandeo lateral-torsional (810/539 kip·in), interacción (0,200), rotura por flexión (624/416; Z_net = 12,75 in³ contra 12,8 de la Tabla 15-2) | `tests/connections/test_extended_single_plate.py` |
| II.A-11A, Parte B | placa de extremo de corte: agujeros (96,4/64,1 kip), fluencia (128/85,3) y rotura (86,3/57,5) por corte, bloque de corte (93,8/62,5), soldaduras (67,9/45,3) y t_w,min = 0,286 in | `tests/connections/test_end_plate.py` |
| II.A-12A | asiento no rigidizado apernado: longitud de apoyo por fluencia (0,309/0,307 in) y aplastamiento local (negativo, gobierna k_des = 1,03 in), fluencia por corte del ala (150/100 kip) y flexión del ala con l_b = 1⅛ in (113/74,9, Tabla 10-5) | `tests/connections/test_seated.py` |

## Hallazgos de la validación

- **Soldaduras concéntricas:** si todos los elementos son paralelos se usa §J2.4(b) sin compatibilidad de deformaciones. Si son longitudinales y transversales, se toma la mayor entre la compatibilidad y la Ec. J2-6.
- **Electrodos E80 y superiores:** el método del centro instantáneo usa el C1 de la Tabla 8-3, no FEXX/70 (E80: 1,03 en lugar de 1,14).
- **Grupos en L con la carga cerca del centroide de resistencia:** el centro instantáneo puede quedar del lado opuesto a la estimación elástica. En ese caso la resistencia se limita a la de traslación pura, que es lo que da la Tabla 8-10.
- **Tabla 14-2:** se corrigieron los diámetros de agujero de 1, 1¼, 1½ y 1¾ in.

## Otras pruebas

- **Unidades:** pruebas de propiedades (hypothesis) de ida y vuelta entre unidades.
- **Centro instantáneo:** equilibrio de fuerzas y momentos, resistencia decreciente con la excentricidad, límite elástico ≤ ICR.
- **Importación:** un Excel sintético con el formato de SAP2000 (`tests/test_csi_import.py`). Se probó además con una exportación real de SAP2000 v27, que no se incluye en el repositorio.
- **Salidas:** HTML, DOCX, PDF, DXF, STEP y STL se generan y se vuelven a leer (`tests/outputs/`).
- **Licencias de dependencias:** se revisan en la integración continua (`tools/check_licenses.py`).
