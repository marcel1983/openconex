# 9. Interfaz gráfica

> **Estado: inicial (F4.1 ampliada).** Cubre el flujo individual de una placa base expuesta. La edición completa de bases empotradas, bases débiles e importación por lotes desde la interfaz queda para las siguientes fases.

## Instalación

La interfaz usa PySide6:

```bash
pip install -e ".[gui]"
```

## Abrir

```bash
openconex-gui
```

o directamente con un proyecto:

```bash
openconex-gui examples/base_plate_dg1_4_7_11.ocnx
```

## Flujo de trabajo

1. **Archivo > Abrir** para cargar un `.ocnx`.
2. Elegir la **columna** en el desplegable. El campo es editable: se puede escribir una etiqueta AISC (`W12X96`) y el autocompletado filtra el catálogo.
3. Elegir los materiales en los desplegables:
   - **Grado de columna** y **Acero de la placa**: aceros de AISC o materiales propios del proyecto.
   - **Grado de anclaje**: grados de pernos y barras de anclaje de AISC 360-22.
4. Editar las dimensiones y los datos del concreto. Cada valor muestra su unidad a la derecha; las unidades se cambian desde **Unidades**.
5. Añadir, modificar o eliminar casos de carga en la tabla.
6. Pulsar **Calcular** o `F5`.
7. Revisar:
   - la pestaña **Resumen**, con demanda, capacidad, relación y estado;
   - la pestaña **Verificaciones**, con la traza y la cláusula;
   - la pestaña **Figuras**, con planta, elevación e isométrico.
8. **Archivo > Guardar** o **Guardar como** para conservar los cambios.
9. **Exportar** para generar HTML, DOCX, PDF, DXF, STEP o STL.

El botón **Optimizar** reduce N, B y tp con el mismo criterio que `openconex baseplate --optimize`.

## Unidades

El menú **Unidades** ofrece los presets `SI (kN, m)`, `SI (N, mm)`, `MKS (tf, m)` y `US (kip, in)`.

Al cambiar de preset:

- se convierten los valores del formulario y de la tabla de casos;
- se actualizan las etiquetas de unidad junto a cada campo y en las cabeceras de la tabla;
- se convierten las dimensiones de las secciones personalizadas y los bloques que todavía no tienen formulario propio, para que el proyecto guardado siga siendo coherente;
- se invalida el resultado anterior hasta volver a calcular.

Los números se pueden escribir con su unidad (`"3/4 in"`, `"25 mm"`, `"120 kN*m"`); si se omite, se usa el preset activo.

## Biblioteca de secciones

**Bibliotecas > Secciones…** abre el catálogo AISC incluido (perfiles W, M, S y HP) con búsqueda por etiqueta y filtro por tipo. La tabla muestra las dimensiones en las unidades activas. **Usar sección** la lleva al formulario principal.

**Nueva sección…** crea una sección genérica:

- tipo W, HSS rectangular, HSS cuadrada o HSS redonda;
- nombre propio;
- dimensiones y material.

Las secciones creadas se guardan en el bloque `sections` del proyecto y aparecen en el desplegable de columna, también al volver a abrir el archivo. El motor admite secciones W genéricas y HSS genéricas; las etiquetas del catálogo se limitan a W, M, S y HP.

## Biblioteca de materiales

**Bibliotecas > Materiales…** muestra tres pestañas:

- **Columnas y placas**: aceros de AISC 360-22 y materiales propios del proyecto. **Nuevo material…** crea un acero con nombre, Fy, Fu y E; queda disponible para columnas, placas y llaves de corte.
- **Pernos y anclajes**: grados de AISC 360-22 Tabla J3.2 (solo lectura por ahora).
- **Soldadura**: electrodos E70XX y E80XX (solo lectura por ahora; el cálculo usa E70XX por defecto).

## Alcance actual

- Edición de los datos generales y de la placa base expuesta.
- Selección de secciones del catálogo y creación de secciones W/HSS genéricas.
- Selección de materiales de columna, placa y anclaje; creación de aceros propios.
- Cambio de unidades con conversión del formulario.
- Edición de casos de carga.
- Cálculo, resumen, traza y figuras.
- Exportación a los formatos disponibles.
- Los bloques `weak_base`, `embedded_base`, `shear_lug` y `reinforcement` se conservan al abrir y guardar, pero todavía no tienen formulario propio.

## Limitaciones

- No hay edición gráfica de la geometría.
- No hay importación de SAP2000/ETABS desde la interfaz; se sigue usando `openconex supports`.
- No hay proceso por lotes ni agrupación por tipo desde la interfaz.
- Los grados de pernos y electrodos son de solo lectura; añadir grados propios requiere ampliar el motor de cálculo.
- La interfaz no sustituye la revisión del profesional responsable.
