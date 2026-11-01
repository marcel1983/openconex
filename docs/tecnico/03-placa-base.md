# 3. Placa base: el algoritmo

Código: `connections/base_plate/check.py` (`check_base_plate`) con los modelos de `plate.py` y `transfer.py`. Referencias: AISC Design Guide 1, 3ª ed. (DG1), AISC 360-22 y ACI 318-19 Capítulo 17.

Para cada combinación se calculan las fuerzas P, V = √(V2² + V3²), M = |M3| y M2 = |M2|, y se siguen estos pasos.

Si el proyecto define `connection_type = "embedded"`, la verificación es la de una base empotrada tipo I (DG1 Capítulo 5) y no se ejecutan los pasos 0 a 6 de la placa base expuesta.

## 0. Llave de corte (si la hay)

La llave toma la componente del corte de su orientación: |V2| con `strong`, |V3| con `weak`, ambas con `both`. Su momento V·e, con e = espesor del mortero + h_sl/2, se suma al momento de la placa en el mismo eje, como en DG1 Ejemplo 4.7-5. El corte que queda (√ de las componentes no tomadas) pasa a fricción o a los anclajes.

## 1. Aplastamiento y espesor, eje fuerte

**Presión máxima** (AISC 360-22 §J8): f_p(max) = φ_c 0,85 f'c √(A2/A1) ≤ φ_c 1,7 f'c, con φ_c = 0,65 (Ω_c = 2,31). La carga por unidad de largo es q_max = f_p(max) B.

**Voladizos** (DG1 Ec. 4-10 y 4-11):
- Perfil I: m = (N − 0,95d)/2 y n = (B − 0,8b_f)/2.
- HSS rectangular: m = (N - 0,95d)/2 y n = (B - 0,95b)/2.
- HSS circular: m = n = (N - 0,8D)/2.
- En HSS con momento, estos cantilevers y el modelo rectangular son una aproximación: no hay un ejemplo publicado que valide el conjunto.

Por defecto se usa la distribución rectangular (`plate.rectangular_bending`). La opción `pressure_model = "triangular"` usa `plate.triangular_bending` (DG1 Apéndice B.2) en el eje fuerte; en esta versión no se aplica al eje débil ni a levantamiento. La opción `bearing_area_model = "effective"` usa `plate.effective_area` (DG1 Apéndice B.3) para la capacidad de aplastamiento en compresión concéntrica de perfiles I.

Según la excentricidad e = M/P se clasifica el caso (`plate.rectangular_bending`):

| Caso | Condición | Modelo |
|---|---|---|
| Compresión pura | M = 0 | DG1 §4.3.1: P ≤ φ_c P_p; espesor con l = máx(m, n, λn′). Para perfiles I, λn′ = λ√(d b_f)/4 (Ec. 4-12 a 4-14); en HSS no se usa λn′. |
| Momento pequeño | e ≤ e_crit = N/2 − P/(2 q_max) | DG1 §4.3.3: Y = N − 2e, q = P/Y ≤ q_max; espesor con f_p = q/B (Ec. 4-47 a 4-51). |
| Momento grande | e > e_crit | DG1 §4.3.4, momentos respecto de la fila traccionada: Y = (f + N/2) − √[(f + N/2)² − 2(Pf + M)/q_max] (Ec. 4-58); T = q_max Y − P (Ec. 4-55). Espesor en compresión con f_p(max) y Y; espesor en tracción t_p = 2,11√(T x/(B F_y)) con x = f − d/2 + t_f/2 (Ec. 4-61 y 4-62). |
| Levantamiento con momento pequeño | P < 0 y M ≤ −P f | Sin aplastamiento: todas las barras en tracción, r = −P/n ± M/(n f) (DG1 Ejemplo 4.7-13). |
| Imposible | el radicando es negativo | La placa no puede equilibrar P y M: la verificación `base_plate.bearing` da NG. |

**Espesor en la interfaz de compresión** (DG1 Ec. 4-47 a 4-52): M_pl = f_p l²/2 si Y ≥ l, o M_pl = f_p Y (l − Y/2) si Y < l, con l = máx(m, n). Luego t_p,req = √(4 M_pl/(φ_b F_y)), con φ_b = 0,90 (√(4 Ω_b M_pl/F_y) en ASD).

## 2. Eje débil y flexión biaxial (si M2 ≠ 0)

Se repite el paso 1 con la placa girada:
- N y B intercambiados, junto con el peralte y el ancho de la columna: m se mide contra b_f y n contra d.
- f = `rod_spacing`/2, con dos barras por cara (la barra extrema de cada fila).
- En la interfaz de tracción, x = rod_spacing/2 − b_f/2 en perfiles I (punta de las alas) y x = rod_spacing/2 − b/2 + t/2 en HSS.

Sin barras fuera del eje (una por fila o `rod_spacing` = 0), el momento débil solo puede resistirse por aplastamiento: M2 ≤ P (B/2 − P/(2 q_max)).

**Interacción** (DG1 §4.3.7, Ec. 4-69, Ejemplo 4.7-14). La capacidad a momento de cada eje sale con las barras de la cara traccionada a su resistencia de acero:
- T_cap = n_cara φN_sa (LRFD) o n_cara F_nt A_b/Ω (ASD).
- Y = (T_cap + P)/q_max.
- M_cap = q_max Y (f + N/2 − Y/2) − P f.

Y se exige (M/M_x,cap)² + (M2/M_y,cap)² ≤ 1,0.

## 3. Anclajes en tracción

**Tracción por barra:**
- T/`rods_per_side` del eje fuerte.
- Con M2, la mayor entre la de cada eje (T_débil/2).
- Con levantamiento y momento biaxial, también la distribución elástica sin aplastamiento: r = −P/n + M x/Σx² + M2 y/Σy². Se toma la mayor.

**LRFD** (ACI 318-19):
- acero del anclaje (§17.6.1);
- arrancamiento del concreto del grupo, si se da `hef` (§17.6.2), con concreto fisurado y factor sísmico 0,75 (§17.10.5.4). El grupo es la fila traccionada (`rod_spacing` de ancho); con levantamiento sin aplastamiento son las dos filas (2f de alto);
- extracción con tuerca hexagonal pesada (§17.6.3);
- desprendimiento lateral (§17.6.4) de la barra más cercana a un borde, solo si h_ef > 2,5 c_a1.

**Bordes del concreto.** Si el proyecto da `edges`, se usan tal cual. Si no, y hay `pedestal_N` y `pedestal_B`, se deducen del pedestal (`concrete_edges`): a los lados, (B_ped − rod_spacing)/2; hacia el borde de la fila traccionada, N_ped/2 − f; hacia el borde opuesto, N_ped/2 + f (N_ped/2 − f si traccionan las dos filas). Sin `edges` ni pedestal, el concreto se toma ilimitado (zapata).

**A2/A1.** Con pedestal, `base_plate.a2_over_a1` comprueba que el A2/A1 del proyecto no supere el del mayor rectángulo semejante y concéntrico que cabe en el pedestal: mín[(N_ped/N)², (B_ped/B)², 4] (AISC 360-22 §J8).

**ASD:** tracción en la barra como perno (AISC 360-22 §J3.6).

**Base sísmica débil.** Si el proyecto define `weak_base`, la tracción `T` se usa para dimensionar la sección reducida de la barra dúctil y su longitud de estiramiento. Los estados no dúctiles se comprueban con `n Rt T_red` (DG1 §6.4). Solo LRFD, presión rectangular y sin momento débil.

**Refuerzo de anclaje.** Si el proyecto define `reinforcement`, el arrancamiento del concreto en tracción se sustituye por: capacidad `φ A_s f_y`, desarrollo del gancho `l_dh` (ACI 318-19 §25.4.3.1) y empotramiento requerido `h_ef,req = l_dh + g/1.5 + c_c` (DG1 4.7-15). La longitud disponible es `le`.

**Flexión de placa por los anclajes.** Si el proyecto define `rod_bending_lever`, cada barra en tracción se comprueba con `transfer.plate_bending_at_rods` (DG1 Ejemplos 4.7-3 y 4.7-7): `M_r = r a`, ancho efectivo `b_eff = 2a` y flexión de la placa. Si no se define, la verificación no se ejecuta.

## 4. Corte

Con el corte que no tomó la llave:
- **Fricción** (LRFD, P > 0 y sin arandelas soldadas): φV_n = mín[0,65 μ P, 0,75·0,2 f'c A_c, 0,75·0,8 ksi A_c] (DG1 Ec. 4-30). Es el caso usual.
- **Corte en los anclajes:** si no hay compresión, o en ASD. Con mortero, V_sa se multiplica por 0,8 (ACI §17.7.1.2.1). El corte se reparte entre las barras de una fila, o entre todas si hay arandelas soldadas.
- **Concreto con corte en los anclajes** (LRFD, cuando el corte va a las barras):
  - arrancamiento hacia el borde (§17.7.2) para cada componente del corte, con la fila más cercana al borde tomando todo el corte (ACI Fig. R17.7.2.1b, caso 3; DG1 Ejemplo 4.7-4). Para V2, c_a1 es el borde `bottom` y la fila mide `rod_spacing`; para V3, c_a1 es `left` y la fila mide 2f. El pedestal se toma profundo (h_a ≥ 1,5 c_a1);
  - desprendimiento por palanca (§17.7.3) del grupo completo, si se da `hef`;
  - interacción tracción–corte (§17.8) con la relación más alta de cada uno.
- **Arandelas soldadas (`washer_thickness`):** se verifica la barra con tracción, corte y flexión (DG1 Ejemplo 4.7-6). El brazo es l = (t_p + t_w/2)/2, M_r = (V/n) l y Z = d³/6; f_t = N/(n A_b) + M_r/Z se compara con F′_nt de AISC 360-22 §J3.8.

## 5. Llave de corte

Para cada componente que toma la llave (ver paso 0), con V y M_sl = V e:
- **Aplastamiento del concreto:** V_brg,sl = 1,7 f'c A_ef,sl ψ_brg,sl, con φ = 0,65 (ACI §17.11.2). A_ef,sl = b_sl h_sl. ψ_brg,sl = 1 + 4P/(A_bp f'c) ≤ 2 con compresión, o 1 + P/(n N_sa) ≤ 1 con tracción (§17.11.2.2).
- **Arrancamiento del concreto hacia el borde,** si se da `ca1` (§17.11.3).
- **Acero de la llave** (AISC 360-22 §J4.2 y §J4.5):
  - fluencia y rotura por corte con A = b_sl t_sl;
  - fluencia y rotura por flexión con Z = b_sl t_sl²/4.
- **Soldaduras de filete en las dos caras:** a = t_sl + 2w/3, r = √[(V/2b)² + (M/(a b))²], θ = 90° (DG1 Ejemplo 4.7-5).
- **Flexión local de la placa base:** M_pl = máx[T f, (q_max Y)(N/2 − Y/2)], con ancho efectivo b_sl y Z = b_sl t_bp²/4 (DG1 Ejemplo 4.7-5; AISC 360-22 §J4.5).
- **Empotramiento de los anclajes:** h_ef ≥ 2,5 h_sl.

Las verificaciones de concreto son solo LRFD.

## 6. Soldadura de las alas (si se da `flange_weld`)

Cada ala transmite la fuerza R = M/d como carga transversal (θ = 90°) sobre una soldadura de filete de largo b_f (DG1 Ejemplo 4.7-9; AISC 360-22 §J2.4).

## 7. Base empotrada (si `connection_type = "embedded"`)

La base empotrada tipo I se verifica con `seismic.embedded_base_moment` y `seismic.face_plate_design`:

- **Momento por apoyo horizontal** (DG1 §5.2, Ec. 5-1 y 5-6):
  f_b = 1,54 √f'c (B_f/b_f)^0,66 ≤ 1,7 f'c;
  b_j = b_f si no hay placa embebida, o (b_f + B)/2 si la hay;
  M_HB = (F_r,t − F_r,b − V)d_e/2 − (F_r,b − F_r,t + V)²/(4 b_j f_b)
  − β1 b_j d_e² f_b(β1 − 2)/4 − F_r,t d_r,t + F_r,b d_r,b;
  φM_HB = 0,75 M_HB, o 0,75(0,8 M_HB) si se activa `damage_limit`.
- **Aplastamiento de las placas de cara** (DG1 §5.3, Ec. 5-7):
  A1 = (b_f − t_w)(d − 2t_f); φP_p = 0,65 (1,7 f'c) A1.
- **Espesor de las placas de cara** (DG1 §5.3, Ec. 5-8):
  l = √(d b_f)/4; t_p,min = l √[2P/(0,9 F_y A1)].
- **Detalle sísmico:** t_p ≥ máx(0,75 t_w, 3/8 in) (AISC 341-22 §F3.5b.4).
- Las placas de apoyo frontal se sitúan en la cara superior del cimiento, no en el fondo del empotramiento (DG1 Fig. 5-1 y §5.3).

Se modela el Tipo I con refuerzo horizontal opcional y placa embebida opcional. La placa embebida solo interviene en `b_j` y en las figuras; no se comprueba su flexión por apoyo vertical ni la tracción. No se verifica la soldadura de las placas de apoyo frontal: se supone CJP o un detalle capaz de desarrollar la fluencia de la placa. El Tipo II no está implementado. Se admite únicamente en LRFD, con perfiles I y sin momento débil, levantamiento neto, llave de corte, base débil ni combinaciones ASD.

## 8. Revisor de interferencias en planta

Para la placa base expuesta se comprueba la huella cuadrada de la arandela de placa (Manual AISC Tabla 14-2) frente a:

- el contorno de la columna; en perfiles I se usa el rectángulo envolvente y en HSS circular el diámetro exterior;
- los bordes de la placa: la distancia del eje al borde debe ser al menos la mayor entre la Tabla J3.4 de AISC 360-22 y media arandela, de modo que la arandela quede dentro de la placa;
- la planta de la llave de corte, según su dirección (`strong`, `weak` o `both`);
- las barras longitudinales del pedestal definidas en `pedestal_rebars`, con separación libre entre el eje del anclaje y el de la barra.

Son verificaciones geométricas, no dependen de las cargas y se repiten para cada combinación para que aparezcan en la memoria.

## Lo que no hace la verificación completa

- La base empotrada no comprueba el levantamiento neto, el momento débil ni el Tipo II.
- No se verifica la soldadura de las placas de apoyo frontal ni la flexión de la placa embebida por apoyo vertical.
- La llave de corte ya se dibuja en DXF/3D y se comprueba su flexión local; no se comprueba la interacción completa placa-llave por elementos finitos.
