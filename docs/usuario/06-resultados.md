# 6. Resultados

## Resumen en pantalla

`openconex baseplate` imprime, para cada tipo de verificación, la combinación que gobierna:

```
OK     0.465  Espesor de placa en la interfaz de compresión (CU3 1.2CM+CV+SX+0.3SY)
NG     1.243  Corte por fricción (CU18 0.9CM-SY-0.3SX)
```

`OK` o `NG` indica si cumple. El número es la relación demanda/capacidad; cumple si es ≤ 1. Al final aparecen los archivos escritos.

## Memoria de cálculo (`--html`, `--docx`, `--pdf`)

En español o inglés según `--lang`, y en las unidades de `--units`:

- **Encabezado:** datos del proyecto (`info`).
1. **Normas e hipótesis:** normas de referencia e hipótesis (placa rígida, concreto fisurado, opción sísmica, tipo de columna).
2. **Datos:** geometría, materiales, anclajes, soldaduras y llave de corte; casos de carga (P, V, M y, si hay, los del eje débil).
3. **Figuras:** planta, elevación e isométrico del modelo 3D. En la base empotrada muestran la columna, el cimiento y las placas de cara. Son SVG vectoriales en HTML/PDF. En DOCX se rasterizan a PNG con PySide6 (extra `pdf`); sin ese extra se omite con un aviso.
4. **Combinaciones:** factores y origen de cada una.
5. **Resumen:** una fila por verificación con demanda, capacidad, relación y estado.
6. **Verificaciones:** para la combinación que gobierna cada verificación, todas las ecuaciones con sus valores y la cláusula de la norma (AISC 360-22, DG1, ACI 318-19).

El HTML se abre en cualquier navegador y se imprime a PDF desde él. El DOCX se edita en Word o LibreOffice. El PDF directo requiere el extra `pdf`.

## Plano DXF (`--dxf`)

DXF R2013, a escala 1:1 en la unidad de longitud del proyecto (mm o in), legible en AutoCAD, BricsCAD, LibreCAD o QCAD:

- **Planta:** placa, columna, anclajes con agujeros y arandelas, llave de corte en línea oculta y cotas.
- **Elevación:** placa, mortero, pedestal, anclajes con su empotramiento y llave de corte con su profundidad embebida.
- **Lista de materiales:** placa, barras de anclaje, tuercas hexagonales pesadas, arandelas de placa y llave de corte.
- **Notas y cajetín** con los datos de `info`.

Capas: `BP-PLACA`, `BP-COLUMNA`, `BP-ANCLAJE`, `BP-LLAVE` (solo si hay llave), `BP-COTAS`, `BP-TEXTO`, `BP-EJES` y `BP-CONCRETO`.

## Modelo 3D (`--step`, `--stl`)

Sólidos de placa, columna (tramo corto), anclajes, tuercas, arandelas, mortero, pedestal y llave de corte, en mm. Cada pieza es un sólido aparte. STEP sirve para programas de detallado y BIM; STL para visualización.
