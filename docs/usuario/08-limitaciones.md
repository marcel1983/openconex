# 8. Alcance y limitaciones

## Qué calcula hoy

- **Placa base de columna expuesta** (W, M, S, HP, HSS rectangular, cuadrada o circular, y secciones genéricas), con:
  - compresión axial, flexión en uno o dos ejes y levantamiento;
  - corte por fricción, por los anclajes o por una llave de corte;
  - anclajes según ACI 318-19 Capítulo 17.
- Combinaciones ASCE 7-22 (LRFD y ASD) generadas o propias.
- Importación de apoyos desde SAP2000 y creación de proyectos por apoyo o por tipo de columna.

## Limitaciones conocidas

- **Sismo sin `SDS`:** las combinaciones con sismo solo se generan si se da `combinations.SDS`. Sin él, los casos `E` no entran en las combinaciones generadas.
- **Concreto solo en LRFD:** las verificaciones de ACI 318 (aplastamiento de la llave, arrancamiento, extracción, corte en el anclaje) se hacen solo con combinaciones LRFD. En ASD se verifican los anclajes como pernos según AISC 360-22 §J3.
- **Modelo de presiones:** por defecto, distribución rectangular con placa rígida (DG1 §4.3). La distribución triangular (DG1 Apéndice B.2) está disponible como opción, pero solo para el eje fuerte y combinaciones con compresión; el eje débil sigue usando el modelo rectangular.
- **Área efectiva:** el área efectiva bajo el perfil I (DG1 Apéndice B.3) está disponible para la capacidad de aplastamiento en compresión concéntrica; no se aplica a HSS ni a combinaciones con momento.
- **Flexión biaxial:** cada eje se verifica por separado y se combina con la interacción de la DG1 Ec. 4-69. No es un análisis de presiones biaxial completo.
- **Llave de corte:** no se dibuja en el DXF ni en el modelo 3D. Tampoco se verifica la flexión local de la placa base en la soldadura de la llave.
- **Interferencias:** el revisor usa una huella cuadrada conservadora para la arandela y el rectángulo envolvente de la columna. No comprueba la trayectoria tridimensional de la barra de anclaje, el gancho ni el resto de la armadura del pedestal que no se declare en `pedestal_rebars`.
- **Refuerzo de anclaje:** se comprueba la capacidad, el desarrollo del gancho y el empotramiento requerido. No se comprueba la longitud de desarrollo recta ni el detalle completo de la armadura del pedestal.
- **Bases sísmicas especiales:** la base débil con anclajes dúctiles (`weak_base`, DG1 §6.4) y la base empotrada tipo I (`embedded_base`, DG1 Capítulo 5) están integradas en el proyecto. La base débil exige LRFD, presión rectangular y un grado con `Fy`; la base empotrada exige LRFD, perfiles I y no admite momento débil, levantamiento neto, llave de corte ni base débil. La base empotrada implementada es Tipo I sin refuerzo horizontal ni placa embebida; no incluye los términos de refuerzo de la Ec. 5-6, la placa del fondo, la soldadura de las placas de cara ni el factor 0,8 de limitación de daño. El Tipo II no está implementado.
- **Importación:** solo SAP2000 (ETABS usa otros nombres de tabla); solo columnas verticales que nacen en el apoyo.
- **Otras conexiones:** viga–columna, viga–viga y empalmes están en desarrollo; el núcleo de verificaciones (pernos, soldaduras, grupos, elementos, fuerzas concentradas) ya existe.
- **Sin interfaz gráfica** por ahora.

La responsabilidad del diseño corresponde al profesional que lo firma, que debe verificar los resultados.
