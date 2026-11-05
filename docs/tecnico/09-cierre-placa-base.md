# 9. Cierre de la placa base

Objetivo: completar la placa base para la versión 1.0 sin reescribir las ecuaciones ya validadas contra AISC DG1 3ª ed.

## Estado

- Modelo rectangular: implementado y usado por defecto.
- Modelo triangular: integrado en ambos ejes (`pressure_model = "triangular"`).
- Área efectiva: integrada para compresión concéntrica de perfiles I (`bearing_area_model = "effective"`).
- Refuerzo de anclaje: integrado con capacidad, desarrollo y empotramiento (`reinforcement`).
- Base sísmica débil: integrada con anclajes dúctiles y diseño por capacidad (`weak_base`).
- Base empotrada tipo I: tipo de conexión propio (`connection_type = "embedded"`), con refuerzo horizontal y placa embebida opcionales, entradas, revisión y figuras específicas.
- El resto de funciones de la DG1 existe en la biblioteca y está validado a nivel de función, pero todavía no se usa desde el proyecto.

## Matriz de cierre

| Funcionalidad | Función existente | Ejemplos DG1 | Estado |
|---|---|---|---|
| Presión triangular | `plate.triangular_bending` | B.2-1, B.2-2 | Integrada en ambos ejes con compresión |
| Área efectiva | `plate.effective_area` | B.3-1 | Integrada en compresión concéntrica de perfiles I |
| Flexión de placa por anclajes | `transfer.plate_bending_at_rods` | 4.7-3, 4.7-7 | Integrada con brazo explícito |
| Refuerzo de anclaje | `anchors.anchor_reinforcement` | 4.7-15 | Integrado con capacidad, gancho, desarrollo recto y empotramiento |
| Base sísmica débil | `seismic.ductile_anchors` | 6.4-1 | Integrada en el proyecto y la memoria |
| Base empotrada | `seismic.embedded_base_moment`, `seismic.face_plate_design` | 5.3-1 | Tipo I con refuerzo horizontal y placa embebida opcionales |
| Llave de corte en DXF/3D | - | 4.7-5 | Integrada en DXF y 3D |
| Flexión local de placa por llave | `transfer.lug_plate_bending` | 4.7-5 | Integrada con ancho efectivo b_sl |
| HSS con momento | `plate.rectangular_bending` | STI Ejemplo 2 | Validado en HSS rectangular/cuadrado; circular rechazado |
| Optimización N/B/tp | `plate.optimize_plan`, `check.optimize_base_plate` | — | Integrada en `baseplate --optimize` |
| Figuras de memoria | `report/figures.py`, `drawing`, `geometry3d` | — | Planta, elevación e isométrico integrados |
| Revisor de interferencias | `connections/base_plate/interference.py` | - | Columna, borde, llave y barras del pedestal |

## Decisiones de la fase 1

- Los valores por defecto siguen siendo `pressure_model = "rectangular"` y `bearing_area_model = "plate"`; los proyectos existentes no cambian.
- `pressure_model = "triangular"` se aplica a cada eje con `P > 0`, incluido el eje débil con las dimensiones giradas. Las combinaciones con levantamiento usan el modelo rectangular.
- `bearing_area_model = "effective"` solo se aplica a compresión concéntrica de perfiles I. No se admite en HSS, con momento, con levantamiento ni junto con el modelo triangular.
- La base empotrada es LRFD, solo para perfiles I, sin momento débil, levantamiento neto, llave de corte ni base débil. No se verifica la soldadura de las placas de apoyo frontal ni el Tipo II.
- La optimización de N/B/tp es local y determinista; parte de la placa actual y reduce dimensiones mientras todas las combinaciones sigan cumpliendo.
- La memoria muestra una hipótesis específica cuando se usa cualquiera de los dos modelos.

## Orden de implementación

1. **Fase 1 (hecha):** presión triangular en ambos ejes y área efectiva en compresión concéntrica.
2. **Fase 2:** flexión de placa por anclajes; decidir si `a` se deriva o se pide explícitamente.
3. **Fase 3 (hecha):** refuerzo de anclaje; capacidad, gancho, desarrollo recto y empotramiento.
4. **Fase 4 (parcial):** llave de corte integrada en DXF/3D; falta la flexión local si hay método validado.
5. **Fase 5 (hecha):** bases sísmicas débiles y empotradas, en dos PRs separados.
6. **Fase 6 (hecha):** HSS rectangular/cuadrado con momento validado contra STI; HSS circular con momento rechazado.
7. **Fase 7 (hecha):** optimización de N, B y tp en la CLI.

## Criterio de aceptación

- Cada ejemplo DG1 afectado se prueba de extremo a extremo, no solo la función aislada.
- Cada nueva verificación aparece en la memoria con traza, demanda, capacidad y cláusula.
- Los proyectos existentes conservan sus resultados con la configuración por defecto.
- La documentación y los ejemplos se actualizan en el mismo PR.
- `python -m pytest` y `ruff check .` pasan antes de cada merge.

## Riesgos

- La interacción del modelo triangular con biaxial y levantamiento puede requerir un tratamiento específico; por eso se aplica por eje solo con compresión y el levantamiento usa el rectangular.
- Las bases sísmicas no son solo una conexión de funciones: requieren diseño por capacidad y nuevos estados límite.
- El HSS circular con momento no tiene una referencia de aceptación; se rechaza. El HSS rectangular/cuadrado está validado contra el Ejemplo 2 del Steel Tube Institute (2024).
