# Referencia de la conexión de corte

Esta página se genera desde `src/openconex/help.py`. Cada entrada responde qué es, cómo se usa y cómo afecta al cálculo. Si añade un campo o una acción, actualice la fuente y vuelva a generar la página.

**Tipos:** DA: doble ángulo; PS: placa simple; PSE: placa simple extendida; PE: placa de extremo; AS: asiento; AR: asiento rigidizado; PD: placa doblada; PB: placa base; todas: cualquier tipo.

## Campos del proyecto y de la conexión

### Proyecto

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `project.name` | Nombre del proyecto. | Escríbalo en Datos del proyecto; se imprime en la memoria. | No interviene en el cálculo; identifica el documento. | — | todas |
| `project.number` | Número o código del proyecto. | Escríbalo en Datos del proyecto. | No interviene en el cálculo. | — | todas |
| `project.client` | Cliente del proyecto. | Escríbalo en Datos del proyecto. | No interviene en el cálculo. | — | todas |
| `project.engineer` | Profesional responsable. | Escríbalo en Datos del proyecto. | No interviene en el cálculo. | — | todas |
| `project.revision` | Revisión del documento. | Escríbala en Datos del proyecto. | No interviene en el cálculo. | 0 | todas |
| `project.date` | Fecha del documento. | Escríbala en Datos del proyecto. | No interviene en el cálculo. | — | todas |
| `ui.language` | Idioma de la memoria y del plano. | Seleccione español o inglés en Datos del proyecto. | No cambia las fórmulas; cambia los textos y las unidades de presentación. | es | todas |
| `ui.units` | Sistema de unidades del proyecto (US, SI, MKS…). | Seleccione un preset o escriba valores con su unidad. | Convierte los valores guardados; el cálculo interno es siempre el mismo. | SI_kN_m | todas |

### Conexión

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `type` | Tipología resistente que se va a calcular. | Seleccione el tipo en el desplegable; la ventana muestra solo los campos aplicables. | Determina qué comprobaciones se ejecutan y qué campos son obligatorios. | single_plate | todas |
| `beam` | Sección de la viga que llega a la conexión. | Elija una etiqueta del catálogo AISC o escriba una sección W genérica. | Aporta tw, d, tf, bf y el material; afecta pernos, placa, destaje y viga. | — | todas |
| `beam_grade` | Grado del acero de la viga del catálogo. | Escríbalo o elija uno de la biblioteca de materiales. | Define Fy y Fu de la viga para las comprobaciones del alma y del destaje. | ASTM A992 | todas |
| `support` | Columna o viga principal que recibe la conexión. | Elija una etiqueta del catálogo o una sección W genérica. | Aporta el espesor del ala o del alma y su Fu para aplastamiento y soldadura. | — | todas |
| `support_grade` | Grado del acero del apoyo del catálogo. | Escríbalo o elija uno de la biblioteca. | Define Fy y Fu del apoyo para aplastamiento, desgarro y soldadura. | ASTM A992 | todas |
| `support_element` | Parte del apoyo a la que se conecta la placa o el ángulo. | Seleccione Ala o Alma. | Elige el espesor del apoyo: tf para ala, tw para alma. | flange | todas |
| `grade` | Acero de la placa, los ángulos o el rigidizador. | Escríbalo o elija uno de la biblioteca. | Define Fy y Fu de la placa o ángulo en todas sus comprobaciones. | ASTM A572 Gr. 50 | todas |
| `electrode` | Clasificación del electrodo de las soldaduras. | Escríbalo o elija uno de la biblioteca (E60XX, E70XX…). | Define FEXX y el coeficiente C1 de la Tabla 8-3; afecta la capacidad de soldadura. | E70XX | todas |
| `deformation_considered` | Indica si se considera la deformación en servicio en el aplastamiento. | Marque la casilla para usar 2,4 d t Fu; desmárquela para 3,0 d t Fu. | Cambia la capacidad de aplastamiento de la placa y del alma. | true | todas |

### Pernos

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `bolt` | Grupo de pernos de la conexión. | Abra el bloque de pernos y defina diámetro, grado, roscas y agujero. | Afecta corte, aplastamiento, desgarro y bloque de corte. | — | todas |
| `bolt.diameter` | Diámetro nominal del perno. | Escriba el diámetro (por ejemplo, 3/4 in). | Afecta el área, el corte, el aplastamiento y las distancias mínimas. | 3/4 in | todas |
| `bolt.grade` | Especificación del perno (A325, A490, F1852…). | Elija un grado de la biblioteca de pernos. | Define Fnv, Fnt y Fu; afecta corte, tracción y aplastamiento. | ASTM F3125 Gr. A325 | todas |
| `bolt.threads` | Condición de roscas en el plano de corte. | Seleccione N (incluidas) o X (excluidas). | Cambia Fnv y por tanto la capacidad a corte del perno. | N | todas |
| `bolt.hole` | Tipo de agujero: estándar, sobredimensionado o alargado. | Seleccione el tipo; el programa usa sus dimensiones para aplastamiento y áreas netas. | Afecta aplastamiento, desgarro y áreas netas de placa y alma. | STD | todas |

### Geometría

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `rows` | Número de pernos por línea vertical. | Escriba un entero positivo; en la placa de extremo son filas de dos pernos. Debe cumplirse 2 l_ev + (filas - 1) s ≤ largo. | Afecta el grupo de pernos, el área neta y el bloque de corte. | — | todas |
| `lines` | Número de líneas verticales de la placa simple extendida. | Use 1 o 2; con 2 debe definir el gramil. | Duplica el grupo de pernos y cambia el bloque de corte. | 1 | PSE |
| `spacing` | Distancia vertical entre pernos. | Escriba la separación; el mínimo es 2⅔d y el grupo debe caber en el largo. | Afecta aplastamiento interior, desgarro y bloque de corte. | — | todas |
| `gage` | Separación entre líneas de pernos o gramil de los ángulos. | En placa extendida con dos líneas, escriba la separación; en doble ángulo con tracción, el gramil de las alas. | Cambia el grupo de pernos y el brazo de palanca de la tracción. | — | PSE, DA |
| `length` | Largo de la placa, ángulo, asiento o rigidizador. | Escriba el largo; debe alojar el grupo de pernos: largo ≥ 2 l_ev + (filas - 1) s. | Afecta corte, bloque de corte, soldadura y peso. | — | todas |
| `thickness` | Espesor de la placa, ángulo, asiento o rigidizador. | Escriba el espesor; debe ser positivo. | Afecta todas las capacidades de la placa y el tamaño máximo de soldadura. | — | todas |
| `lev` | Distancia vertical del perno extremo al borde. | Escriba la distancia al borde superior o inferior; el mínimo es la Tabla J3.4. | Afecta el desgarro del perno de borde y el espacio disponible. | — | todas |
| `leh` | Distancia horizontal al borde de la placa. | En el doble ángulo, es la distancia en el ala sobre el alma de la viga; el mínimo es la Tabla J3.4. | Afecta el desgarro y el bloque de corte. | — | todas |
| `leh_support` | Distancia horizontal al borde en las alas salientes del ángulo. | Escriba l_eh del lado del apoyo; el mínimo es la Tabla J3.4. | Afecta el desgarro del ángulo en el apoyo. | — | DA |
| `a` | Distancia de la soldadura a la primera línea de pernos. | Escriba a; debe ser positiva. | Genera el momento excéntrico V·a y cambia el grupo de pernos. | — | PS, PSE |
| `weld` | Tamaño del filete de soldadura. | Escriba el tamaño; debe ser positivo. | Afecta la capacidad de soldadura y el espesor mínimo del apoyo. | — | todas |
| `support_weld` | Soldadura de los ángulos o del asiento al apoyo. | Escriba el tamaño; si existe, reemplaza los pernos del apoyo. | Activa la comprobación de soldadura y desactiva los pernos del apoyo. | — | DA, AS |
| `beam_weld` | Soldadura de los ángulos al alma de la viga. | Escriba el tamaño; requiere el ala sobre el alma. | Reemplaza los pernos del lado de la viga por soldadura. | — | DA |
| `beam_leg` | Ancho del ala del ángulo soldada al alma de la viga. | Escriba el ancho; se usa con beam_weld. | Define la geometría del grupo de soldadura en C. | — | DA |
| `outstanding_leg` | Ancho del ala saliente del ángulo. | Escriba el ancho; se usa con soldadura al apoyo o tracción. | Define el brazo de palanca de la soldadura y la tracción. | — | DA |
| `beam_leh` | Distancia del extremo de la viga a la línea de pernos. | Escriba la distancia; se usa en el desgarro del alma con tracción. | Afecta el desgarro del alma de la viga bajo carga axial. | — | DA, PS, PSE |
| `offset` | Separación entre los ejes de dos vigas back-to-back. | Escriba el desplazamiento; active la fila de pernos compartida. | Añade la comprobación de la fila compartida para 2R. | 0 | DA |

### Destaje

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `cope` | Recorte del extremo de la viga. | Active el bloque de destaje y defina sus dimensiones. | Activa las comprobaciones de la sección destajada y del bloque de corte del alma. | — | todas |
| `cope.c` | Longitud del destaje medida desde el apoyo. | Escriba c; debe ser mayor que cero. | Afecta la esbeltez, la flexión y el bloque de corte de la viga destajada. | — | todas |
| `cope.dc` | Profundidad del destaje en el ala superior. | Escriba dc; use 0 si no hay destaje superior. | Reduce el canto útil y cambia S, Z y la resistencia a flexión. | — | todas |
| `cope.dc_bottom` | Profundidad del destaje en el ala inferior. | Escriba dc,inf; use 0 para destaje solo superior. | Cambia la sección destajada y las comprobaciones de flexión. | 0 | todas |
| `cope.setback` | Separación entre el apoyo y el extremo de la viga. | Escriba la holgura; por defecto 1/2 in. | La reacción se aplica a e = c + holgura; afecta el momento del destaje. | 0.5 in | todas |
| `cope.lev` | Distancia vertical desde el borde del destaje al primer perno. | Escriba l_ev si comprueba el bloque de corte del alma. | Se usa en el bloque de corte del alma destajada. | — | todas |
| `cope.leh` | Distancia horizontal desde el extremo de la viga a la línea de pernos. | Escriba l_eh; el programa resta la tolerancia de longitud. | Se usa en el bloque de corte del alma destajada. | — | todas |
| `cope.doubler` | Placa soldada al alma destajada para reforzarla. | Active la placa doble y defina espesor, profundidad, separación y soldadura. | Aumenta la sección y la resistencia a flexión y corte del destaje. | — | todas |
| `cope.doubler.thickness` | Espesor de la placa doble. | Escriba el espesor; debe ser positivo. | Aumenta A, I, S y Z de la sección reforzada. | — | todas |
| `cope.doubler.depth` | Altura de la placa doble. | Escriba la profundidad; debe ser positiva. | Aumenta la sección reforzada y la resistencia a flexión. | — | todas |
| `cope.doubler.gap` | Distancia desde la línea del destaje a la cara de la placa. | Escriba la separación; por defecto 1/2 in. | Cambia la posición del centro de gravedad y el flujo de soldadura. | 0.5 in | todas |
| `cope.doubler.weld` | Filete de soldadura en cada lado de la placa doble. | Escriba el tamaño; debe ser positivo. | Se comprueba el flujo de corte Q/I y la capacidad del filete. | 3/16 in | todas |
| `cope.stiffener` | Rigidizador soldado a lo largo de la línea del destaje. | Active el rigidizador y defina ancho, espesor, soldadura y longitud. | Aumenta la sección y estabiliza el ala comprimida. | — | todas |
| `cope.stiffener.width` | Ancho del rigidizador. | Escriba el ancho; debe ser positivo. | Aumenta la sección reforzada y el momento plástico. | — | todas |
| `cope.stiffener.thickness` | Espesor del rigidizador. | Escriba el espesor; debe ser positivo. | Afecta la esbeltez y la sección reforzada. | — | todas |
| `cope.stiffener.weld` | Filete del rigidizador a la línea del destaje. | Escriba el tamaño; debe ser positivo. | Se comprueba el flujo de corte y la capacidad del filete. | 1/4 in | todas |
| `cope.stiffener.length` | Longitud del rigidizador a lo largo de la viga. | Déjela vacía para usar c + dc. | Cambia la longitud de soldadura y el peso, no la sección resistente. | c + dc | todas |

### Placa doblada

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `skew` | Ángulo entre la viga y el apoyo, escrito como 6:12, grados o radianes. | Escriba el esviaje; se usa en el plano y el 3D. | No cambia las fórmulas resistentes; cambia la geometría dibujada. | — | PD |
| `row_distance` | Distancia entre las dos filas verticales de pernos. | Escriba la distancia; junto con load_offset define el reparto. | Define el reparto A/B por estática simple. | — | PD |
| `load_offset` | Distancia de la línea de carga a la fila de pernos B. | Escriba la distancia; debe ser menor que row_distance. | Define share_a = load_offset/row_distance y por tanto la demanda de cada placa. | — | PD |
| `share_a` | Fracción de la reacción que toma la placa A. | Escriba un valor entre 0 y 1; sustituye al reparto geométrico. | Cambia la demanda de la placa A y, por diferencia, la de B. | — | PD |
| `share_b` | Fracción de la reacción que toma la placa B. | Escriba un valor entre 0 y 1; alternativa a share_a. | Cambia la demanda de la placa B; la memoria avisa si es menor que 0,66. | — | PD |
| `plate_a_width` | Ancho de la placa A a lo largo del apoyo. | Escriba el ancho; se usa en el plano, el 3D y la lista de materiales. | No cambia las fórmulas; cambia la geometría y el peso. | — | PD |
| `plate_b_width` | Ancho de la placa B a lo largo del apoyo. | Escriba el ancho; se usa en el plano, el 3D y la lista de materiales. | No cambia las fórmulas; cambia la geometría y el peso. | — | PD |
| `plate_a_leg` | Longitud del ala de la placa A soldada al alma de la viga. | Escriba la longitud; se usa en el plano y el 3D. | No cambia las fórmulas; cambia la geometría y el peso. | — | PD |
| `plate_b_leg` | Longitud del ala de la placa B soldada al alma de la viga. | Escriba la longitud; se usa en el plano y el 3D. | No cambia las fórmulas; cambia la geometría y el peso. | — | PD |
| `bend_radius` | Radio interior de la doblez. | Escriba el radio; se guarda para el plano y el 3D. | No se usa en las fórmulas; el 3D lo representa con esquina aguda. | — | PD |
| `weld_return` | Longitud de los retornos superior e inferior de la soldadura en C. | Escriba la longitud; debe ser positiva. | Cambia el coeficiente C y la capacidad del grupo de soldadura. | — | PD |
| `weld_offset` | Distancia de la soldadura vertical a la línea de carga. | Escriba la distancia; debe ser positiva. | Define la excentricidad del grupo de soldadura en C. | — | PD |

### Asiento

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `leg` | Ancho del ala horizontal del asiento. | Escriba el ancho; debe ser positivo. | Afecta la longitud de apoyo y la flexión del ala. | — | AS, AR |
| `vertical_leg` | Altura del ala vertical del asiento soldado. | Escriba la altura; se usa con soldadura al apoyo. | Afecta el grupo de soldadura y la geometría del asiento. | — | AS |
| `bolts` | Número de pernos del ala vertical. | Escriba un entero positivo. | Afecta la capacidad de los pernos del asiento. | 4 | AS |
| `bearing_length` | Longitud de apoyo usada en la flexión del ala. | Déjela vacía para usar la mínima requerida. | Cambia el momento del ala del asiento. | — | AS |
| `width` | Ancho W del rigidizador del asiento rigidizado. | Escriba el ancho; debe ser positivo. | Afecta el aplastamiento y la flexión del asiento. | — | AR |
| `two_sided` | Indica si hay un asiento a cada lado del alma. | Marque la casilla si corresponde. | Duplica la capacidad del asiento y cambia el espesor mínimo del apoyo. | false | AR |
| `seat_plate_width` | Ancho de la placa de asiento del asiento rigidizado. | Déjelo vacío para usar W + 1 in. | Cambia el peso y la geometría; la comprobación de aplastamiento usa W. | W + 1 in | AR |
| `seat_plate_thickness` | Espesor de la placa de asiento. | Déjelo vacío para usar 3/8 in. | Cambia el peso y la geometría de la placa. | 3/8 in | AR |
| `seat_plate_weld` | Filete de la placa de asiento al rigidizador. | Déjelo vacío para usar 5/16 in. | Cambia la longitud y capacidad de la soldadura. | 5/16 in | AR |
| `top_angle_leg` | Ala del ángulo de estabilidad superior. | Déjela vacía para usar 4 in. | Detalle estándar; no toma carga. | 4 in | AS, AR |
| `top_angle_thickness` | Espesor del ángulo de estabilidad. | Déjelo vacío para usar 1/4 in. | Detalle estándar; no toma carga. | 1/4 in | AS, AR |
| `top_angle_length` | Longitud del ángulo de estabilidad a lo largo de la viga. | Déjela vacía para usar 4 in. | Detalle estándar; no toma carga. | 4 in | AS, AR |
| `top_angle_bolts` | Pernos por ala del ángulo de estabilidad apernado. | Use 2 o más. | Detalle estándar; no toma carga. | 2 | AS |
| `top_angle_weld` | Filete del ángulo de estabilidad al apoyo. | Déjelo vacío para usar 3/16 in. | Detalle estándar; no toma carga. | 3/16 in | AS, AR |

### Avanzado

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `beam_area` | Área bruta de una viga genérica. | Úsela solo con secciones genéricas y carga axial. | Se usa en las comprobaciones de tracción de la viga. | — | DA, PS, PSE |

## Menús, botones y controles

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `menu.file.new` | Crea un proyecto nuevo con la plantilla de placa simple. | Archivo → Nuevo (Ctrl+N). | Descarta el proyecto actual y carga la plantilla. | — | todas |
| `menu.file.open` | Abre un proyecto .ocnx existente. | Archivo → Abrir (Ctrl+O) y elija el archivo. | Carga todos los datos y recalcula la ventana. | — | todas |
| `menu.file.save` | Guarda el proyecto en el archivo actual. | Archivo → Guardar (Ctrl+S). | Escribe el .ocnx con los valores del formulario. | — | todas |
| `menu.file.save_as` | Guarda el proyecto con otro nombre. | Archivo → Guardar como y elija la ruta. | Crea un archivo nuevo; no modifica el original. | — | todas |
| `menu.calc.run` | Ejecuta todas las comprobaciones del proyecto. | Cálculo → Calcular o F5. | Actualiza el resumen, las verificaciones y las figuras. | — | todas |
| `menu.export.html` | Genera la memoria de cálculo en HTML. | Exportar → Memoria HTML y elija el archivo. | Incluye datos, combinaciones, verificaciones y figuras. | — | todas |
| `menu.export.docx` | Genera la memoria de cálculo en DOCX. | Exportar → Memoria Word y elija el archivo. | Incluye textos, tablas y figuras rasterizadas. | — | todas |
| `menu.export.pdf` | Genera la memoria de cálculo en PDF. | Exportar → Memoria PDF y elija el archivo. | Requiere el extra de PDF; produce el documento imprimible. | — | todas |
| `menu.export.dxf` | Genera el plano de la conexión. | Exportar → Plano DXF y elija el archivo. | En II.A-10 produce la planta; en el resto, la elevación. | — | todas |
| `menu.export.step` | Exporta el modelo 3D en STEP. | Exportar → Modelo STEP y elija el archivo. | Requiere el extra 3D; el archivo se abre en CAD. | — | todas |
| `menu.export.stl` | Exporta el modelo 3D en STL. | Exportar → Modelo STL y elija el archivo. | Requiere el extra 3D; el archivo se usa para impresión o visores. | — | todas |
| `menu.help.guide` | Resumen del flujo de trabajo de la ventana. | Ayuda → Guía rápida o F1. | No calcula; explica cómo introducir datos y calcular. | — | todas |
| `menu.help.fields` | Lista buscable de todos los campos. | Ayuda → Referencia de campos. | Muestra qué es, cómo se usa y cómo afecta cada campo. | — | todas |
| `menu.help.menus` | Lista de menús, botones y acciones. | Ayuda → Menús y acciones. | Explica qué hace cada acción y cuándo se usa. | — | todas |
| `menu.help.checks` | Guía para leer la tabla de verificaciones. | Ayuda → Verificaciones. | Explica demanda, capacidad, relación, estado y referencia. | — | todas |
| `menu.help.about` | Versión, licencia y aviso de responsabilidad. | Ayuda → Acerca de. | No calcula; muestra información del programa. | — | todas |
| `action.calculate` | Ejecuta el cálculo con los datos del formulario. | Pulse Calcular o F5. | Valida el proyecto, calcula y llena el resumen. | — | todas |
| `tab.summary` | Tabla de verificaciones gobernantes. | Revise la pestaña Resumen después de calcular. | Muestra demanda, capacidad, relación y estado por combinación. | — | todas |
| `tab.details` | Traza de cálculo de cada verificación. | Seleccione una fila del resumen y revise esta pestaña. | Muestra fórmulas, valores intermedios y cláusulas. | — | todas |
| `tab.figures` | Plano y figuras de la conexión. | Revise la pestaña Figuras después de calcular. | Muestra el DXF convertido a imagen y el isométrico si está disponible. | — | todas |
| `tab.viewer` | Visor 3D interactivo con caras ocultas y superficies sombreadas. | Gire, haga zoom o seleccione piezas; los elementos de conexión se resaltan en naranja y los pernos en gris oscuro. | Muestra el modelo 3D; no cambia el cálculo. | — | todas |
| `ui.type` | Elige la tipología de conexión. | Seleccione un tipo en el desplegable. | Muestra solo los campos aplicables y activa sus comprobaciones. | — | todas |
| `ui.methods` | Métodos de diseño que se van a calcular. | Marque LRFD, ASD o ambos. | Genera las combinaciones y verifica con los factores correspondientes. | LRFD | todas |
| `ui.cases` | Cargas D, L, S, W o combinaciones propias. | Agregue filas con nombre, tipo, V y P. | Las cargas se combinan y producen la demanda de cada verificación. | — | todas |
| `ui.combinations` | Combinaciones ASCE 7 o personalizadas. | Active las combinaciones de código o defina factores propios. | Cada combinación se calcula por separado y se reporta la gobernante. | — | todas |

## Verificaciones

| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |
|---|---|---|---|---|---|
| `checks.summary` | Tabla con la verificación gobernante de cada estado límite. | Lea de izquierda a derecha: verificación, combinación, demanda, capacidad, relación y estado. | Una relación ≤ 1,00 es OK; > 1,00 es NG. | — | todas |
| `checks.ratio` | Cociente entre la demanda y la capacidad disponible. | Compare con 1,00; el valor más alto gobierna el diseño. | Resume el margen; no es un porcentaje de utilización de la sección. | — | todas |
| `checks.status` | Resultado OK, NG o n/a. | OK: cumple; NG: no cumple; n/a: no aplica al tipo o a la combinación. | Determina si la conexión cumple globalmente. | — | todas |
| `checks.clause` | Cláusula o tabla AISC que define la comprobación. | Use la referencia para auditar la fórmula en la memoria o en el código. | No cambia el resultado; permite trazabilidad. | — | todas |
| `checks.details` | Pasos simbólicos con sus valores y unidades. | Seleccione una verificación en el resumen y lea la pestaña Verificaciones. | Muestra cómo se obtuvo la capacidad y qué términos gobernaron. | — | todas |
| `checks.bent_plate` | Pernos, corte, bloque de corte y soldadura de cada placa A/B. | Revise las filas plate_a.* y plate_b.* del resumen. | Cada placa se comprueba con su fracción de la reacción. | — | PD |
| `checks.weld` | Soldadura de filete por centro instantáneo o grupo en C. | Revise las filas weld.* y las referencias J2.4 y Tabla 8-8. | La capacidad depende del tamaño, la longitud, la excentricidad y FEXX. | — | todas |
| `checks.coped` | Flexión, corte y bloque de corte de la viga destajada. | Active el bloque Destaje y revise las filas coped_beam.*. | La sección destajada y el refuerzo cambian la capacidad. | — | todas |

## Cómo leer una verificación

1. **Demanda:** fuerza o momento de la combinación.
2. **Capacidad:** resistencia disponible con φ o Ω.
3. **Relación:** demanda/capacidad; debe ser ≤ 1,00.
4. **Estado:** OK, NG o n/a.
5. **Referencia:** cláusula AISC y, en la pestaña Verificaciones, la traza completa.

Las fórmulas y los valores intermedios de cada verificación están en la memoria y en `docs/tecnico/04-verificaciones.md`.
