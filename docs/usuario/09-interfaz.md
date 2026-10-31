# 9. Interfaz gráfica

> **Estado: inicial (F4.1).** Cubre el flujo individual de una placa base. La edición completa de bases empotradas, bases débiles e importación por lotes desde la interfaz queda para las siguientes fases.

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
2. Editar los datos del proyecto y de la placa base en el panel izquierdo.
3. Añadir, modificar o eliminar casos de carga en la tabla.
4. Pulsar **Calcular** o `F5`.
5. Revisar:
   - la pestaña **Resumen**, con demanda, capacidad, relación y estado;
   - la pestaña **Verificaciones**, con la traza y la cláusula;
   - la pestaña **Figuras**, con planta, elevación e isométrico.
6. **Archivo > Guardar** o **Guardar como** para conservar los cambios.
7. **Exportar** para generar HTML, DOCX, PDF, DXF, STEP o STL.

El botón **Optimizar** reduce N, B y tp con el mismo criterio que `openconex baseplate --optimize`.

## Alcance actual

- Edición de los datos generales y de la placa base expuesta.
- Edición de casos de carga.
- Cálculo, resumen, traza y figuras.
- Exportación a los formatos disponibles.
- Los bloques `weak_base`, `embedded_base`, `shear_lug` y `reinforcement` se conservan al abrir y guardar, pero todavía no tienen formulario propio.

## Limitaciones

- No hay edición gráfica de la geometría.
- No hay importación de SAP2000/ETABS desde la interfaz; se sigue usando `openconex supports`.
- No hay proceso por lotes ni agrupación por tipo desde la interfaz.
- La interfaz no sustituye la revisión del profesional responsable.
