# Referencia de la placa base

Esta página se genera desde `src/openconex/help_base.py`. Cada entrada responde qué es, cómo se usa y cómo afecta al cálculo. Si añade un campo o una acción, actualice la fuente y vuelva a generar la página.

**Tipos:** DA: doble ángulo; PS: placa simple; PSE: placa simple extendida; PE: placa de extremo; AS: asiento; AR: asiento rigidizado; PD: placa doblada; PB: placa base; todas: cualquier tipo.

## Campos

### Conexión

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `connection_type` | Tipo de base: placa base expuesta o base empotrada. | Seleccione Placa base expuesta o Base empotrada Tipo I. | Determina qué comprobaciones se ejecutan y qué campos son obligatorios. | exposed | PB |
| `column` | Columna que apoya en la placa. | Elija una etiqueta AISC (W, M, S, HP, HSS o PIPE) o escriba una sección genérica W/HSS. | Aporta d, bf, tf, tw y el material; afecta presiones, anclajes y rigidizadores. | — | PB |
| `column_grade` | Acero de la columna del catálogo. | Elija un acero de la biblioteca. Para HSS y PIPE use ASTM A500 Gr. C (rectangular) o (round). | Define Fy y Fu de la columna para las comprobaciones de placa y soldadura. | ASTM A992 | PB |

### Placa base

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `N` | Largo de la placa en la dirección del eje fuerte. | Escriba N; debe ser positivo. | Afecta el área de apoyo, la presión, la flexión de la placa y el brazo de los anclajes. | — | PB |
| `B` | Ancho de la placa en la dirección perpendicular. | Escriba B; debe ser positivo. | Afecta el área de apoyo, la presión y la flexión en el eje débil. | — | PB |
| `tp` | Espesor de la placa base. | Escriba tp; debe ser positivo. | Afecta la flexión de la placa, el aplastamiento y la soldadura. | — | PB |
| `plate_grade` | Acero de la placa base. | Elija un acero de la biblioteca. | Define Fy y Fu de la placa para flexión, corte y soldadura. | ASTM A572 Gr. 50 | PB |
| `grout` | Espesor del mortero de nivelación. | Escriba el espesor; por defecto 1,5 in. | Se usa en planos, en el brazo de la llave de corte y en la geometría 3D. | 1.5 in | PB |
| `flange_weld` | Filete de soldadura en las alas de la columna. | Déjelo vacío si no se comprueba. | Se verifica para el momento de la columna. | — | PB |
| `grout_pad` | Indica si hay mortero bajo la placa. | Marque la casilla si existe mortero. | Reduce la resistencia a corte del acero del anclaje (ACI 17.7.1.2.1). | true | PB |
| `friction_mu` | Coeficiente para el corte transmitido por fricción. | Escriba μ; por defecto 0,4. | Afecta la fracción de corte tomada por fricción. | 0.4 | PB |

### Anclajes

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `bearing_area` | Área de la tuerca o placa embebida para la extracción. | Déjela vacía para usar la tuerca hexagonal pesada. | Afecta la resistencia a la extracción del concreto. | — | PB |
| `rod_diameter` | Diámetro de las barras de anclaje. | Escriba el diámetro; debe ser positivo. | Afecta tracción, corte, flexión y capacidad del concreto. | — | PB |
| `rod_grade` | Material de las barras de anclaje. | Elija un grado de la biblioteca de pernos. | Define Fy, Fu y Fnt/Fnv de las barras. | ASTM F1554 Gr. 36 | PB |
| `rods_per_side` | Número de barras en cada fila. | Escriba un entero; normalmente 2 o 4. | Afecta la tracción total, el cortante y la geometría. | 2 | PB |
| `f` | Distancia del eje de la columna a cada fila de anclajes. | Escriba la distancia; debe ser positiva. | Define el brazo del momento y la tracción de los anclajes. | — | PB |
| `rod_spacing` | Distancia entre las barras extremas de una fila. | Escriba la separación; 0 si hay una barra por fila. | Afecta el eje débil y la distribución de tracción. | 0 | PB |
| `rod_bending_lever` | Distancia del anclaje al alma o ala que sirve de apoyo. | Déjelo vacío para no verificar la flexión de la placa por anclajes. | Activa la comprobación de flexión de la placa por los anclajes. | — | PB |
| `hef` | Empotramiento efectivo de los anclajes. | Escriba hef; 0 desactiva arrancamiento y empotramiento mínimo. | Afecta arrancamiento del concreto, extracción y llave de corte. | 0 | PB |
| `washer_thickness` | Espesor de arandelas de placa soldadas. | Déjelo vacío si no hay arandelas soldadas. | Con arandelas soldadas, el corte se reparte entre todas las barras. | — | PB |

### Concreto

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `fc` | Resistencia especificada del concreto. | Escriba f'c; debe ser positiva. | Define la capacidad de aplastamiento y las resistencias de anclaje. | — | PB |
| `A2_over_A1` | Relación entre el área de apoyo del concreto y la de la placa. | Escriba un valor entre 1 y 4. | Aumenta la capacidad de aplastamiento según √(A2/A1) ≤ 2. | 1.0 | PB |
| `cracked` | Indica concreto fisurado. | Marque la casilla si corresponde. | Aplica el factor de ACI 17.6.2.5 a la tracción del concreto. | true | PB |
| `seismic` | Activa el factor sísmico de las resistencias del concreto. | Marque la casilla para diseño sísmico. | Aplica 0,75 a las resistencias de tracción (ACI 17.10.5.4). | false | PB |
| `pressure_model` | Distribución de presiones bajo la placa. | Elija rectangular (DG1 §4.3) o triangular (DG1 Apéndice B.2). | Cambia la presión de contacto y el momento de la placa. | rectangular | PB |
| `bearing_area_model` | Área usada para el aplastamiento. | Elija plate (B×N) o effective (área efectiva bajo la columna). | Cambia la capacidad de aplastamiento en compresión concéntrica. | plate | PB |
| `edges` | Distancias de los anclajes extremos a los bordes. | Defina left, right, bottom y top; las omitidas se toman lejanas. | Afecta arrancamiento, desprendimiento lateral y corte hacia el borde. | {} | PB |
| `edges.left` | Distancia del anclaje izquierdo al borde. | Escriba la distancia; vacío = lejano. | Afecta el concreto en tracción y corte. | — | PB |
| `edges.right` | Distancia del anclaje derecho al borde. | Escriba la distancia; vacío = lejano. | Afecta el concreto en tracción y corte. | — | PB |
| `edges.bottom` | Distancia de la fila traccionada al borde inferior. | Escriba la distancia; vacío = lejano. | Afecta el arrancamiento y el corte hacia el borde. | — | PB |
| `edges.top` | Distancia de la fila comprimida al borde superior. | Escriba la distancia; vacío = lejano. | Afecta el desprendimiento lateral. | — | PB |

### Pedestal

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `pedestal_N` | Largo del pedestal de concreto. | Escriba N del pedestal; déjelo vacío si no hay pedestal. | Se usa para bordes, planos y límite de A2/A1. | — | PB |
| `pedestal_B` | Ancho del pedestal de concreto. | Escriba B del pedestal; déjelo vacío si no hay pedestal. | Se usa para bordes, planos y límite de A2/A1. | — | PB |
| `pedestal_rebars` | Barras longitudinales para el revisor de interferencias. | Agregue filas con x, y y diámetro. | No cambia el cálculo; revisa interferencias geométricas. | [] | PB |
| `pedestal_rebars.x` | Coordenada x de la barra en planta. | Escriba la coordenada respecto al centro. | No cambia el cálculo; se usa en el revisor. | — | PB |
| `pedestal_rebars.y` | Coordenada y de la barra en planta. | Escriba la coordenada respecto al centro. | No cambia el cálculo; se usa en el revisor. | — | PB |
| `pedestal_rebars.diameter` | Diámetro de la barra longitudinal. | Escriba el diámetro. | No cambia el cálculo; se usa en el revisor. | — | PB |

### Refuerzo

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `reinforcement` | Refuerzo horizontal para la tracción de los anclajes. | Active el bloque y defina barras, área, fy, db, recubrimiento, desarrollo y le. | Añade las comprobaciones de tracción y desarrollo del refuerzo. | — | PB |
| `reinforcement.bars` | Designación o número de barras del refuerzo. | Escriba la designación; se usa en la memoria y los planos. | No cambia las fórmulas; identifica el refuerzo. | — | PB |
| `reinforcement.area` | Área total del refuerzo. | Escriba el área; debe ser positiva. | Afecta la tracción y el desarrollo del refuerzo. | — | PB |
| `reinforcement.fy` | Fluencia del refuerzo. | Escriba fy; debe ser positiva. | Afecta la capacidad de tracción del refuerzo. | — | PB |
| `reinforcement.db` | Diámetro de la barra de refuerzo. | Escriba db; debe ser positivo. | Afecta el desarrollo y la separación. | — | PB |
| `reinforcement.clear_cover` | Recubrimiento libre del refuerzo. | Escriba el recubrimiento; por defecto 2 in. | Afecta el desarrollo y la longitud disponible. | 2 in | PB |
| `reinforcement.anchor_to_bar` | Distancia del anclaje a la barra de refuerzo. | Escriba la distancia; debe ser positiva. | Afecta la transmisión de tracción al refuerzo. | — | PB |
| `reinforcement.le` | Longitud de desarrollo disponible. | Escriba le; debe ser positiva. | Se compara con la longitud requerida. | — | PB |

### Base débil

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `weak_base` | Base con anclajes de sección reducida (upset-thread). | Active el bloque y defina diámetro reducido, longitud y Rt. | Añade las comprobaciones de anclajes dúctiles de la DG1 §6.4. | — | PB |
| `weak_base.reduced_diameter` | Diámetro de la sección reducida del anclaje. | Escriba el diámetro; debe ser positivo. | Define la fluencia del anclaje dúctil. | — | PB |
| `weak_base.stretch_length` | Longitud de la sección reducida. | Escriba la longitud; debe ser positiva. | Afecta la ductilidad y la capacidad de estiramiento. | — | PB |
| `weak_base.Rt` | Relación de resistencia del anclaje. | Escriba Rt; por defecto 1,2. | Afecta la sobrerresistencia usada en la jerarquía. | 1.2 | PB |

### Base empotrada

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `embedded_base` | Base empotrada Tipo I de la DG1 Capítulo 5. | Active el bloque y defina empotramiento, cimiento y placas de cara. | Ejecuta solo las comprobaciones de la base empotrada. | — | PB |
| `embedded_base.embedment` | Profundidad de empotramiento de la columna. | Escriba la profundidad; debe ser positiva. | Afecta el apoyo horizontal y el momento resistente. | — | PB |
| `embedded_base.foundation_width` | Ancho del cimiento de concreto. | Escriba el ancho; debe ser positivo. | Afecta el apoyo horizontal y las presiones. | — | PB |
| `embedded_base.face_plate_thickness` | Espesor de las placas de apoyo frontal. | Escriba el espesor; debe ser positivo. | Afecta el aplastamiento y la flexión de la placa de cara. | — | PB |
| `embedded_base.beta1` | Factor de bloque rectangular del concreto. | Escriba β1; por defecto 0,85. | Afecta la profundidad del bloque de compresión. | 0.85 | PB |
| `embedded_base.base_plate_width` | Ancho de la placa base embebida. | Déjelo vacío para el valor por defecto. | Afecta la geometría y el peso. | — | PB |
| `embedded_base.base_plate_thickness` | Espesor de la placa base embebida. | Déjelo vacío para el valor por defecto. | Afecta la geometría y el peso. | — | PB |
| `embedded_base.damage_limit` | Activa el límite de daño de la base empotrada. | Marque la casilla si corresponde. | Añade la comprobación de daño. | false | PB |
| `embedded_base.rebar_top` | Capa de refuerzo superior del cimiento. | Defina área, fy y profundidad. | Afecta la capacidad de la base empotrada. | — | PB |
| `embedded_base.rebar_bottom` | Capa de refuerzo inferior del cimiento. | Defina área, fy y profundidad. | Afecta la capacidad de la base empotrada. | — | PB |
| `embedded_base.rebar_top.area` | Área de acero de la capa superior. | Escriba el área; debe ser positiva. | Afecta la flexión y el desarrollo. | — | PB |
| `embedded_base.rebar_top.fy` | Fluencia del acero superior. | Escriba fy; debe ser positiva. | Afecta la capacidad de la capa superior. | — | PB |
| `embedded_base.rebar_top.depth` | Profundidad de la capa superior. | Escriba la profundidad; debe ser positiva. | Afecta el brazo útil. | — | PB |
| `embedded_base.rebar_bottom.area` | Área de acero de la capa inferior. | Escriba el área; debe ser positiva. | Afecta la flexión y el desarrollo. | — | PB |
| `embedded_base.rebar_bottom.fy` | Fluencia del acero inferior. | Escriba fy; debe ser positiva. | Afecta la capacidad de la capa inferior. | — | PB |
| `embedded_base.rebar_bottom.depth` | Profundidad de la capa inferior. | Escriba la profundidad; debe ser positiva. | Afecta el brazo útil. | — | PB |

### Llave de corte

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `shear_lug` | Placa soldada bajo la placa base para transmitir corte. | Active el bloque y defina ancho, empotramiento, espesor, soldadura y bordes. | Añade las comprobaciones de aplastamiento, flexión y soldadura. | — | PB |
| `shear_lug.width` | Ancho de la llave de corte. | Escriba el ancho; debe ser positivo. | Afecta el aplastamiento y la flexión. | — | PB |
| `shear_lug.embedment` | Profundidad embebida de la llave. | Escriba la profundidad; debe ser positiva. | Afecta el aplastamiento del concreto. | — | PB |
| `shear_lug.thickness` | Espesor de la placa de la llave. | Escriba el espesor; debe ser positivo. | Afecta flexión y soldadura. | — | PB |
| `shear_lug.weld` | Filete de soldadura de la llave a la placa base. | Escriba el tamaño; debe ser positivo. | Afecta la capacidad de la soldadura. | — | PB |
| `shear_lug.direction` | Orientación de la llave respecto a los ejes. | Elija strong, weak o both. | Cambia la geometría y las comprobaciones de flexión. | strong | PB |
| `shear_lug.grade` | Acero de la llave de corte. | Elija un acero de la biblioteca. | Define Fy y Fu de la llave. | ASTM A572 Gr. 50 | PB |
| `shear_lug.electrode` | Electrodo de la soldadura de la llave. | Elija un electrodo de la biblioteca. | Define FEXX de la soldadura. | E70XX | PB |
| `shear_lug.ca1` | Distancia al borde en la dirección de la llave. | Escriba la distancia; debe ser positiva. | Afecta el corte hacia el borde. | — | PB |
| `shear_lug.ca2` | Distancias laterales al borde. | Escriba una o dos distancias; vacío = lejano. | Afecta el desprendimiento lateral. | — | PB |

## Menús, botones y controles

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `main.file.new` | Abre la galería para crear una conexión. | Archivo → Nueva conexión (Ctrl+N). | Crea un proyecto de placa base o de corte con valores iniciales. | — | todas |
| `main.file.open` | Abre un proyecto .ocnx. | Archivo → Abrir (Ctrl+O). | Carga el proyecto y actualiza la ventana. | — | todas |
| `main.file.save` | Guarda el proyecto actual. | Archivo → Guardar (Ctrl+S). | Escribe el archivo .ocnx. | — | todas |
| `main.file.save_as` | Guarda con otro nombre. | Archivo → Guardar como. | Crea un archivo nuevo. | — | todas |
| `main.file.shear` | Abre la ventana de conexiones de corte. | Archivo → Nueva conexión de corte. | Abre una ventana independiente; no cambia el proyecto actual. | — | todas |
| `main.file.import_csi` | Importa reacciones de un modelo CSI. | Archivo → Importar SAP2000 / ETABS. | Crea proyectos por apoyo o por sección. | — | todas |
| `main.file.import_table` | Importa una tabla de reacciones. | Archivo → Importar Excel / CSV. | Crea proyectos desde una tabla. | — | todas |
| `main.file.exit` | Cierra la aplicación. | Archivo → Salir. | No guarda automáticamente. | — | todas |
| `main.library.sections` | Abre la biblioteca de secciones. | Bibliotecas → Secciones. | Permite consultar y crear secciones propias. | — | todas |
| `main.library.materials` | Abre la biblioteca de materiales. | Bibliotecas → Materiales. | Permite consultar y crear aceros, pernos y electrodos. | — | todas |
| `main.units.presets` | Cambia el sistema de unidades. | Unidades → SI, MKS o US. | Convierte los valores guardados; no cambia el cálculo interno. | — | todas |
| `main.units.configure` | Configura la unidad de cada magnitud. | Unidades → Configurar por magnitud. | Cambia la presentación y la conversión. | — | todas |
| `main.calc.run` | Calcula el proyecto actual. | Cálculo → Calcular o F5. | Actualiza el resumen y las figuras. | — | todas |
| `main.calc.optimize` | Optimiza N, B y tp. | Cálculo → Optimizar N, B y tp. | Busca dimensiones menores con las mismas comprobaciones. | — | PB |
| `main.calc.batch` | Calcula una carpeta de proyectos. | Cálculo → Calcular lote. | Genera reportes y un resumen Excel. | — | todas |
| `main.export.html` | Memoria en HTML. | Exportar → Memoria HTML. | Incluye datos, verificaciones y figuras. | — | todas |
| `main.export.docx` | Memoria en DOCX. | Exportar → Memoria Word. | Incluye tablas y figuras. | — | todas |
| `main.export.pdf` | Memoria en PDF. | Exportar → Memoria PDF. | Requiere el extra de PDF. | — | todas |
| `main.export.dxf` | Plano en DXF. | Exportar → Plano DXF. | Genera la planta y elevación. | — | todas |
| `main.export.step` | Modelo 3D en STEP. | Exportar → Modelo STEP. | Requiere el extra 3D. | — | todas |
| `main.export.stl` | Modelo 3D en STL. | Exportar → Modelo STL. | Requiere el extra 3D. | — | todas |
| `main.help.guide` | Resumen del flujo de trabajo. | Ayuda → Guía rápida o F1. | No calcula; explica el uso. | — | todas |
| `main.help.fields` | Lista buscable de campos de placa base. | Ayuda → Referencia de campos. | Explica qué es, cómo se usa y cómo afecta cada campo. | — | todas |
| `main.help.menus` | Lista de menús y acciones. | Ayuda → Menús y acciones. | Explica qué hace cada acción. | — | todas |
| `main.help.checks` | Guía para leer las verificaciones. | Ayuda → Verificaciones. | Explica demanda, capacidad, relación y estado. | — | todas |
| `main.help.about` | Versión y licencia. | Ayuda → Acerca de. | No calcula. | — | todas |
| `base.ui.type` | Selector de placa base expuesta o empotrada. | Seleccione el tipo. | Muestra solo los bloques aplicables. | exposed | PB |
| `base.ui.column` | Columna del proyecto. | Elija una sección del catálogo (W, M, S, HP, HSS o PIPE) o escriba una genérica. | Aporta la geometría y el material. | — | PB |
| `base.ui.methods` | Métodos LRFD/ASD. | Marque uno o ambos. | Genera las combinaciones y factores. | LRFD | PB |
| `base.ui.cases` | Cargas del proyecto. | Agregue filas con nombre, tipo, P, V, M. | Producen la demanda de cada verificación. | — | PB |
| `base.ui.combinations` | Combinaciones ASCE 7 o propias. | Active las de código o defina factores. | Cada combinación se calcula por separado. | — | PB |
| `comb.live_factor` | Factor que multiplica el caso L en las combinaciones generadas. | Escriba el factor; por defecto 1,0. | Cambia la demanda de las combinaciones con L. | 1.0 | PB |
| `comb.SDS` | Aceleración espectral de diseño para sismo. | Escriba SDS en g si hay casos sísmicos. | Genera las combinaciones sísmicas y su demanda. | — | PB |
| `comb.rho` | Factor de redundancia sísmica. | Escriba ρ; por defecto 1,0. | Multiplica la demanda sísmica. | 1.0 | PB |
| `comb.omega0` | Factor de sobrerresistencia sísmica. | Escriba Ω0 si aplica. | Afecta las combinaciones sísmicas. | — | PB |
| `base.ui.geometry` | Editor gráfico de planta y elevación. | Arrastre los bordes o edite los campos. | Cambia N, B, tp y la posición de anclajes. | — | PB |
| `base.ui.viewer` | Visor 3D del conjunto. | Gire, haga zoom o seleccione piezas. | No cambia el cálculo. | — | PB |
| `geometry.undo` | Deshace el último cambio del editor gráfico. | Pulse Deshacer o Ctrl+Z. | Restaura la geometría anterior; no cambia el cálculo hasta Calcular. | — | PB |
| `geometry.redo` | Rehace el cambio deshecho. | Pulse Rehacer o Ctrl+Y. | Vuelve a aplicar la geometría; no cambia el cálculo hasta Calcular. | — | PB |
| `viewer.refresh` | Recarga el modelo 3D con el proyecto actual. | Pulse Actualizar en la pestaña 3D. | Regenera la malla; no cambia el cálculo. | — | PB |
| `viewer.reset` | Restablece la cámara del visor 3D. | Pulse Ajustar vista. | Solo cambia la vista; no modifica el modelo. | — | PB |
| `viewer.iso` | Vuelve a la vista isométrica de la conexión. | Pulse Iso en la barra del visor 3D. | Solo cambia la cámara; no modifica el modelo. | — | todas |
| `viewer.front` | Mira la conexión de frente. | Pulse Frente en la barra del visor 3D. | Solo cambia la cámara; no modifica el modelo. | — | todas |
| `viewer.top` | Mira la conexión desde arriba. | Pulse Planta en la barra del visor 3D. | Solo cambia la cámara; no modifica el modelo. | — | todas |
| `viewer.side` | Mira la conexión de lado. | Pulse Lado en la barra del visor 3D. | Solo cambia la cámara; no modifica el modelo. | — | todas |
| `viewer.explode` | Separa la viga del apoyo para ver placas, ángulos y asientos. | Marque Separar en la pestaña 3D. | Solo cambia la vista; no modifica el proyecto ni la exportación. | — | todas |
| `dialog.import_csi.file` | Archivo Excel exportado de SAP2000 o ETABS. | Elija el archivo con Examinar. | Es la fuente de apoyos, reacciones y casos. | — | todas |
| `dialog.import_csi.output` | Carpeta donde se escribirán los proyectos. | Elija la carpeta con Carpeta. | No cambia el cálculo; determina dónde se guardan los .ocnx. | — | todas |
| `dialog.import_csi.group` | Criterio para crear proyectos: por apoyo o por sección de columna. | Seleccione Joint o Column. | Cambia el número de proyectos y su agrupación. | joint | todas |
| `dialog.import_csi.loads` | Usar casos de carga o combinaciones del programa. | Seleccione Casos o Combinaciones. | Cambia qué reacciones se importan y si OpenConex vuelve a combinar. | cases | todas |
| `dialog.import_csi.include` | Expresión regular para filtrar casos o combinaciones. | Escriba un patrón, por ejemplo ^CU. | Limita los casos importados. | — | todas |
| `dialog.import_csi.envelopes` | Incluir envolventes Max/Min al importar combinaciones. | Marque la casilla si existen envolventes. | Añade casos de demanda extrema. | false | todas |
| `dialog.import_csi.method` | Método de las combinaciones importadas. | Elija LRFD, ASD o el del proyecto. | Cambia los factores de las combinaciones importadas. | — | todas |
| `dialog.import_csi.accept` | Acciones del diálogo de importación CSI. | Pulse Importar para escribir los proyectos o Cancelar para salir. | Importar crea los .ocnx; Cancelar no escribe nada. | — | todas |
| `dialog.import_table.file` | Tabla Excel o CSV con reacciones. | Elija el archivo con Examinar. | Es la fuente de los proyectos. | — | todas |
| `dialog.import_table.output` | Carpeta donde se escribirán los proyectos. | Elija la carpeta con Carpeta. | Determina dónde se guardan los .ocnx. | — | todas |
| `dialog.import_table.units` | Unidades de los valores de la tabla. | Seleccione el sistema de la tabla. | Convierte las reacciones importadas. | — | todas |
| `dialog.import_table.accept` | Acciones del diálogo de importación de tabla. | Pulse Importar para escribir los proyectos o Cancelar para salir. | Importar crea los .ocnx; Cancelar no escribe nada. | — | todas |
| `dialog.units.kind` | Unidad de presentación de una magnitud. | Elija la unidad para longitud, fuerza, tensión, etc. | Convierte el formulario y el proyecto; no cambia el cálculo interno. | — | todas |
| `dialog.units.apply` | Acciones del diálogo de unidades. | Pulse Aplicar para convertir o Cancelar para salir. | Aplicar convierte los valores del formulario y del proyecto. | — | todas |
| `dialog.batch.folder` | Carpeta con archivos .ocnx. | Elija la carpeta con Carpeta. | Define los proyectos del lote. | — | todas |
| `dialog.batch.output` | Carpeta de reportes del lote. | Elija la carpeta con Carpeta. | Determina dónde se escriben los reportes. | — | todas |
| `dialog.batch.recursive` | Incluir proyectos en subcarpetas. | Marque la casilla si corresponde. | Amplía el conjunto de proyectos del lote. | false | todas |
| `dialog.batch.formats` | Formatos de reporte que se generan. | Marque HTML, DOCX, PDF, DXF, STEP o STL. | Cada formato añade archivos al lote. | — | todas |
| `dialog.batch.accept` | Acciones del diálogo de lote. | Pulse Calcular para procesar la carpeta o Cancelar para salir. | Calcular escribe los reportes; Cancelar detiene el lote. | — | todas |
| `dialog.library.sections.type` | Filtro por familia de sección. | Elija Todas, Personalizadas o una familia AISC. | Filtra la tabla de secciones. | Todas | todas |
| `dialog.library.sections.search` | Texto de búsqueda por etiqueta. | Escriba parte de la etiqueta, por ejemplo W12. | Filtra la tabla de secciones. | — | todas |
| `dialog.library.sections.new` | Crea una sección genérica para el proyecto. | Pulse Nueva sección y defina tipo, nombre y dimensiones. | Añade la sección a la biblioteca del proyecto. | — | todas |
| `dialog.library.sections.use` | Selecciona la sección para el proyecto. | Elija una fila y pulse Usar sección. | Cambia la columna y sus propiedades. | — | todas |
| `dialog.library.materials.tabs` | Aceros, pernos y electrodos. | Cambie de pestaña para consultar cada biblioteca. | No cambia el cálculo; permite elegir materiales. | — | todas |
| `dialog.library.materials.new` | Crea un acero, perno o electrodo propio. | Pulse Nuevo en la pestaña correspondiente. | Añade el material a la biblioteca del proyecto. | — | todas |

## Cómo leer una verificación

1. **Demanda:** fuerza o momento de la combinación.
2. **Capacidad:** resistencia disponible con φ o Ω.
3. **Relación:** demanda/capacidad; debe ser ≤ 1,00.
4. **Estado:** OK, NG o n/a.
5. **Referencia:** cláusula y traza completa en la pestaña Verificaciones.
