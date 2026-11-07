# Informe de validación — borrador para 0.6.0

**Estado:** borrador de trabajo, 2026-11-07. No cierra la release 0.6.0: faltan la comparación externa y el cálculo independiente de varias familias. Su objetivo es dejar por escrito qué está validado, con qué evidencia y qué queda abierto.

## 1. Alcance

Se revisan las verificaciones implementadas en OpenConex 0.5.5:

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
| `validado` | 174 | Contraste con ejemplo o tabla publicada, dentro de tolerancia |
| `diferencia aceptada` | 3 | Diferencia documentada y conservadora o despreciable |
| `parcial` | 7 | Solo una parte de los casos tiene evidencia |
| `no aplica` | 2 | Función no implementada; se informa como no cumple |

Las 3 diferencias aceptadas son:

- **II.A-17A/17B:** el centro instantáneo da C = 3,556 y 4,06 frente a 3,54 y 4,07 interpolados (≈0,5 %).
- **II.A-1B:** la interacción del bloque de corte usa la forma U (0,054) en vez de la forma L (0,0531); es algo más conservadora.
- **II.A-19A:** `Z_net` calculado 12,75 in³ frente a 12,8 in³ de la Tabla 15-2.

Las 7 verificaciones parciales son las cinco de `kernel/local.py` (solo biblioteca, sin integración en las rutas actuales) y las dos de viga destajada con λ > 2λ_p y doble destaje de II.A-18.

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

Hoy existe un cálculo independiente completo para asientos. Reproduce:

| Caso | OpenConex / cálculo | Publicado |
|---|---:|---:|
| II.A-12A flexión, LRFD | 90,0 kip | 90,0 kip |
| II.A-12A flexión, ASD | 59,9 kip | 59,9 kip |
| II.A-13 soldadura, LRFD | 66,7 kip | 66,7 kip |
| II.A-13 soldadura, ASD | 44,5 kip | 44,5 kip |
| II.A-14 soldadura, LRFD | 139,4 kip | 139 kip |
| II.A-14 soldadura, ASD | 92,9 kip | 93,0 kip |

Las demás familias se apoyan por ahora en los ejemplos publicados y en las pruebas de regresión; falta un segundo cálculo independiente para placa base, doble ángulo, placa simple, placa extendida, viga destajada y anclajes.

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
- [ ] Cálculo independiente de placa base, doble ángulo, placa simple, placa extendida y viga destajada.
- [ ] Comparación externa de los 26 casos de `casos.csv`.
- [ ] Cierre de las 7 verificaciones parciales o declaración de impacto.
- [ ] Revisión manual de DXF/STEP/PDF en CAD/visor independiente.
- [ ] Revisión por un ingeniero independiente.
- [ ] Informe final sin el carácter de borrador.
