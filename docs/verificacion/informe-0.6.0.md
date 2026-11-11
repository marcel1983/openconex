# Informe de validación — borrador para 0.6.0

**Estado:** borrador de trabajo, 2026-11-07. No cierra la release 0.6.0: faltan la comparación externa y el cálculo independiente de varias familias. Su objetivo es dejar por escrito qué está validado, con qué evidencia y qué queda abierto.

## 1. Alcance

Se revisan las verificaciones implementadas en OpenConex 0.5.12:

- placa base y anclajes (DG1 3.ª ed., ACI 318-19);
- conexiones de corte de la F5 (Manual AISC Parte 10 y ejemplos II.A-1A a II.A-19B);
- comprobaciones de la biblioteca (pernos, soldaduras, elementos, fuerzas concentradas);
- salidas HTML, DOCX, PDF, DXF, STEP, STL y GUI.

No se revisan las funciones que aún no existen: compresión axial en el extremo de la viga, flexión de la viga, momento viga-columna (F6) ni empalmes (F7).

## 2. Método

La validación sigue cuatro niveles:

1. **Matriz de trazabilidad:** una fila por verificación, con cláusula, fórmula, referencia, prueba y estado.
2. **Cálculo independiente:** script o hoja que no importa `openconex` y reproduce los valores publicados.
3. **Comparación externa:** mismo caso en un programa comercial, con la misma norma, método y unidades.
4. **Validación de salidas:** abrir DXF/STEP/PDF y comprobar que representan el cálculo.

La tolerancia general es del 1 %, salvo que la referencia publique valores redondeados y el archivo de prueba indique otra.

## 3. Matriz de trazabilidad

`docs/verificacion/matriz-verificacion.csv` contiene **186 verificaciones**. Se genera desde el catálogo con `python tools/generate_verification_matrix.py`.

| Estado | N.º | Significado |
|---|---:|---|
| `validado` | 181 | Contraste con ejemplo, tabla o cálculo manual, dentro de tolerancia |
| `diferencia aceptada` | 3 | Diferencia documentada y conservadora o despreciable |
| `parcial` | 0 | Sin verificaciones parciales |
| `no aplica` | 2 | Función no implementada; se informa como no cumple |

Las 3 diferencias aceptadas son:

- **II.A-17A/17B:** el centro instantáneo da C = 3,556 y 4,06 frente a 3,54 y 4,07 interpolados (≈0,5 %).
- **II.A-1B:** la interacción del bloque de corte usa la forma U (0,054) en vez de la forma L (0,0531); es algo más conservadora.
- **II.A-19A:** `Z_net` calculado 12,75 in³ frente a 12,8 in³ de la Tabla 15-2.

No quedan verificaciones parciales: las cinco de `kernel/local.py` se contrastaron con valores manuales de §J10 y la rama λ > 2λ_p de la viga destajada se contrastó con un caso sintético de alma delgada. Las cinco de `local.*` siguen siendo solo biblioteca, sin integración en las rutas de diseño actuales.

## 4. Discrepancias cerradas

### 4.1 II.A-12A

El ejemplo usa **cuatro pernos** (Connection Type B), no seis. La resistencia de 107 kip que aparecía en la revisión es la columna Type C de la Tabla 10-5, no la conexión del ejemplo. La conexión del ejemplo tiene 71,6 kip LRFD y 47,7 kip ASD por corte de pernos.

La Tabla 10-5 se entra con `l_b = 1 1/16 in`, no con 1 1/8 in: el ejemplo redondea `k_des = 1,03 in` al siguiente 1/16. Con el ángulo A36 y `l_b = 1 1/16 in`, la flexión del ala da **90,0/59,9 kip**, que coincide con la tabla. El programa usa por defecto `k_des` (95,5/63,6 kip) y permite fijar `bearing_length` para reproducir el valor tabulado.

La verificación está en `tests/connections/test_seated.py` y en el proyecto de ejemplo `examples/shear_seated_ii_a_12a.ocnx`, probado en `tests/connections/test_shear_project.py`.

### 4.2 Asientos soldados

La Ec. 10-2a/b del Manual AISC confirma la fórmula de la Tabla 10-6:

```text
φR_n = 2 (1,392 D l) / √(1 + 20,25 e²/l²)
R_n/Ω = 2 (0,928 D l) / √(1 + 20,25 e²/l²)
```

que es equivalente a `2 r_w l² / √(l² + 20,25 e²)` usada en el código. La Tabla 10-8 se contrasta con II.A-14/15 (139/93,0 kip). El cálculo independiente `docs/verificacion/calculos/asientos.py --check` reproduce seis valores publicados dentro del 1 %.

## 5. Cálculo independiente

Hay cinco scripts que no importan `openconex` y comparan sus resultados con los ejemplos publicados.

### 5.1 Asientos

`docs/verificacion/calculos/asientos.py --check` reproduce seis valores:

| Caso | Cálculo independiente | Publicado |
|---|---:|---:|
| II.A-12A flexión, LRFD | 90,0 kip | 90,0 kip |
| II.A-12A flexión, ASD | 59,9 kip | 59,9 kip |
| II.A-13 soldadura, LRFD | 66,7 kip | 66,7 kip |
| II.A-13 soldadura, ASD | 44,5 kip | 44,5 kip |
| II.A-14 soldadura, LRFD | 139,4 kip | 139 kip |
| II.A-14 soldadura, ASD | 92,9 kip | 93,0 kip |

### 5.2 Doble ángulo y placa simple

`docs/verificacion/calculos/doble_angulo_placa_simple.py --check` reproduce 18 valores de II.A-1A y II.A-17A:

| Caso | Cálculo independiente | Publicado |
|---|---:|---:|
| II.A-1A pernos, lado viga, LRFD/ASD | 281,3 / 187,6 kip | 282 / 187 kip |
| II.A-1A fluencia por corte, LRFD/ASD | 440,6 / 293,8 kip | 441 / 294 kip |
| II.A-1A rotura por corte, LRFD/ASD | 301,6 / 201,1 kip | 302 / 201 kip |
| II.A-1A bloque de corte, LRFD/ASD | 315,4 / 210,2 kip | 315 / 210 kip |
| II.A-17A pernos, LRFD/ASD | 58,7 / 39,1 kip | 58,5 / 38,9 kip |
| II.A-17A fluencia por corte, LRFD/ASD | 86,3 / 57,5 kip | 86,4 / 57,6 kip |
| II.A-17A rotura por corte, LRFD/ASD | 58,5 / 39,0 kip | 58,5 / 39,0 kip |
| II.A-17A bloque de corte, LRFD/ASD | 65,5 / 43,7 kip | 65,3 / 43,6 kip |

El coeficiente de centro instantáneo de II.A-17A se resuelve por bisección independiente y da C = 3,556, frente a 3,54 interpolado de la Tabla 10-9 (0,5 %).

### 5.3 Placa base

`docs/verificacion/calculos/placa_base.py --check` reproduce 59 valores de DG1:

| Caso | Cálculo independiente | Publicado |
|---|---:|---:|
| 4.7-1 compresión, φPp / Pp/Ω | 729 / 486 kip | 729 / 486 kip |
| 4.7-1 X, λ, t_p,req | 0,959 / 1,000 / 1,361 in | 0,960 / 1,000 / 1,36 in |
| 4.7-10 Y, q, t_p,req | 14,0 in, 26,9 kip/in, 1,16 in | 14,0 in, 26,9 kip/in, 1,16 in |
| 4.7-10 f_p,max / q_max | 2,21 ksi / 42,0 kip/in | 2,21 ksi / 42,0 kip/in |
| 4.7-14 Y / T | 1,65 in / 12,4 kip | 1,70 in / 15,2 kip |
| 4.7-14 interacción | 0,981 | 0,988 |

Las diferencias de 4.7-14 son las que la propia DG1 documenta al redondear Y; el script usa 5 % en Y, 25 % en T y 12 % en el espesor de tracción, y 1 % en el resto.

### 5.4 Anclajes

`docs/verificacion/calculos/anclajes.py --check` reproduce 39 valores de DG1:

| Caso | Cálculo independiente | Publicado |
|---|---:|---:|
| 4.7-4 A_Vc / A_Vco / V_b | 720 / 648 in² / 23,7 kip | 720 / 648 / 23,7 |
| 4.7-4 V_cbg / φV_cbg | 26,3 / 18,4 kip | 26,3 / 18,4 |
| 4.7-4 perno AISC, φR_nv / grupo | 8,63 / 17,3 kip | 8,63 / 17,3 |
| 4.7-9 N_sa / φN_sa | 35,1 / 26,3 kip | 35,1 / 26,3 |
| 4.7-9 A_Nc / A_Nco / N_b | 1512 / 1296 in² / 63,6 kip | 1510 / 1300 / 63,6 |
| 4.7-9 N_cbg / φN_cbg | 74,3 / 52,0 kip | 73,9 / 51,7 |
| 4.7-9 N_p / φN_pn | 48,0 / 33,6 kip | 48,0 / 33,6 |
| 4.7-15 h_ef' / A_Nc / N_cbg | 5,33 in / 400 in² / 29,2 kip | 5,33 / 400 / 29,2 |
| 4.7-15 l_dh / l_d / h_ef,req | 9,71 / 17,1 / 13,6 in | 9,71 / 17,1 / 13,6 |

El ejemplo 4.7-4 usa el corte del perno de AISC 360 (φ = 0,75) para el acero del anclaje; la comprobación ACI §17.7.1 (`anchor.steel_shear`, φ = 0,65) es un estado límite distinto y no se contabiliza en este ejemplo. Se deja constancia para no mezclar ambas resistencias.

### 5.5 Placa extendida y viga destajada

`docs/verificacion/calculos/placa_extendida_viga_destajada.py --check` reproduce 29 valores de II.A-4/6/7 y II.A-19A:

| Caso | Cálculo independiente | Publicado |
|---|---:|---:|
| II.A-6 A flexión, LRFD/ASD | 116,8 / 77,7 kip | 116 / 77,2 |
| II.A-6 B flexión, LRFD/ASD | 150,2 / 99,9 kip | 150 / 100 |
| II.A-4 flexión, LRFD/ASD | 373,2 / 248,3 kip | 374 / 249 |
| II.A-7 doble destaje, LRFD/ASD | 37,8 / 25,2 kip | 37,9 / 25,2 |
| II.A-4 bloque de corte, LRFD/ASD | 68,8 / 45,9 kip | 68,6 / 45,8 |
| II.A-19A pernos, C / capacidad | 2,318 / 41,5 kip | 41,7 |
| II.A-19A t_max | 0,575 in | 0,575 |
| II.A-19A flexión / LTB / rotura | 810 / 810 / 621,6 kip·in | 810 / 810 / 624 |
| II.A-19A interacción | 0,200 | 0,200 |

El coeficiente de centro instantáneo de II.A-19A se resuelve por búsqueda en rejilla y refinamiento, independiente del Newton amortiguado del programa, y da C = 2,318.

Todas las familias principales tienen ya un cálculo independiente. Las cinco de `kernel/local.py` se contrastaron con valores manuales de §J10 y la rama λ > 2λ_p con un caso sintético de alma delgada; no quedan verificaciones parciales.

## 6. Comparación externa

`docs/verificacion/casos.csv` contiene 20 casos de placa base y 6 de conexiones de corte. Los 6 casos de corte ya tienen el resultado de OpenConex:

| Caso | Referencia | Resultado OpenConex |
|---|---|---|
| SC-01 | II.A-17A | 0,848 rotura por corte de la placa; 1,000 distancia al borde |
| SC-02 | II.A-4 | 0,872 bloque de corte del alma destajada |
| SC-03 | II.A-18 | 0,757 bloque de corte de la placa; 1,000 distancia al borde |
| SC-04 | II.A-19B | 0,937 tamaño de soldadura |
| SC-05 | II.A-10 | 0,840 rotura por corte de la placa B |
| SC-06 | II.A-12A | 0,766 pernos del asiento; 0,610 flexión del ala (ASD); 1,000 detalle del ángulo superior |

La columna `resultado_externo` sigue vacía. No hay licencia de RAM Connection, RISAConnection ni SkyCiv en el entorno de pruebas, así que la comparación externa **no se ha ejecutado**. Hasta completarla, la validación numérica es la de los ejemplos publicados y el cálculo independiente de asientos.

## 7. Validación de salidas

- `tests/outputs`: 133 pruebas correctas y 1 omitida (pytest-qt no instalado en el entorno local).
- Se genera HTML, DOCX, DXF, STEP y STL y se vuelven a leer en las pruebas.
- El proyecto `shear_seated_ii_a_12a.ocnx` se ejecuta con `openconex shear` y genera la memoria y el plano.
- Falta abrir los DXF en AutoCAD/BricsCAD/LibreCAD y los STEP/STL en un visor independiente; es una revisión manual pendiente.

## 8. Limitaciones declaradas

- El FE de II.A-10 con contacto y pretensión no se ha ejecutado; la sensibilidad de apoyos elásticos acota el reparto entre 0,669 y 0,742.
- La compresión axial en el extremo de la viga no está implementada.
- La flexión de la viga y el corte del alma sin destaje no se comprueban.
- El editor gráfico 2D de la ventana de corte y el desplazamiento en planta de II.A-9 siguen pendientes.
- La comparación con software comercial y la revisión por un ingeniero independiente no se han realizado.

## 9. Checklist para cerrar 0.6.0

- [x] Matriz de trazabilidad completa (186/186).
- [x] II.A-12A aclarado y corregido.
- [x] Fórmulas de asientos confirmadas.
- [x] Cálculo independiente de asientos, doble ángulo (II.A-1A), placa simple (II.A-17A), placa base (DG1 4.7-1/10/14), anclajes (DG1 4.7-4/9/15) y placa extendida/viga destajada (II.A-4/6/7 y II.A-19A).
- [ ] Comparación externa de los 26 casos de `casos.csv`.
- [x] Cierre de las verificaciones parciales: 0 parciales (181 validadas, 3 diferencias aceptadas, 2 no aplican).
- [ ] Revisión manual de DXF/STEP/PDF en CAD/visor independiente.
- [ ] Revisión por un ingeniero independiente.
- [ ] Informe final sin el carácter de borrador.
