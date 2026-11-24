# 13. Agregar una familia de conexiones

Una **familia** es un tipo de bloque del proyecto `.ocnx` con todo lo que el programa hace con él: el comando, la memoria, el plano DXF, el modelo 3D, la etiqueta del cálculo por lotes y la ventana. El registro está en `src/openconex/families.py` (`FAMILIES`). El comando, `report.builder.build_report`, el cálculo por lotes, las exportaciones y la interfaz preguntan `family_of(project)` en lugar de comprobar qué bloque tiene el proyecto, así que una familia nueva se conecta en un solo lugar.

## Familias registradas

| Bloque (`key`) | Comando | Memoria | Ventana |
|---|---|---|---|
| `base_plate` | `openconex baseplate` | `report.builder.build_base_plate_report` | ventana principal (`gui/app.py`, formulario en `gui/base_plate.py`) |
| `shear_connection` | `openconex shear` | `report.shear.build_shear_report` | `gui/shear.py` |
| `moment_connection` | `openconex moment` | `report.moment.build_moment_report` | `gui/moment.py` |
| `splice` | `openconex splice` | `report.splice.build_splice_report` | `gui/splice.py` |

## Pasos

1. **Motor:** `connections/<familia>/` con el modelo, las verificaciones (cada una devuelve un `CheckResult`, con título en `i18n/es.toml` y `en.toml`) y la envolvente por combinación. Reutilice `kernel/` para pernos, soldaduras y elementos.
2. **Proyecto:** `io/<familia>_project.py` con el bloque de entrada (pydantic) y su conversión al modelo del motor; el campo en `Project` (`io/project.py`), el accesor `require_<familia>()`, la validación `_validate_<familia>()` (en el despacho de `_consistent_loads`) y el método `<familia>_model()`. Suba `FORMAT_VERSION` y anote la versión en `CHANGES` de `io/migrations.py` ([convenciones](02-convenciones.md#versiones-del-formato-ocnx)).
3. **Salidas:** `report/<familia>.py` (memoria), `drawing/<familia>.py` (plano DXF y figuras) y `geometry3d/<familia>.py` (piezas 3D).
4. **Registro:** una entrada `ConnectionFamily` en `FAMILIES` con el bloque, el comando, los nombres, la memoria, el plano, las piezas 3D, los miembros que muestra el lote y la ventana. Las fábricas `_dxf` y `_parts` cubren el caso habitual (modelo del proyecto + función de dibujo o de piezas).
5. **Comando:** un subcomando en `cli.build_parser` y una función de dos líneas que llama a `_load` y `_write_outputs` (ver `_moment` o `_splice`). Documéntelo en `docs/usuario/04-comandos.md`.
6. **Interfaz:** `gui/<familia>.py` con la ventana, una subclase de `gui/connection_window.ConnectionWindow` que define `family_key`, `template` y `noun`, arma el formulario en `_build_body` (con `_build_info_group`, `_build_cases_group`, `_end_form` y `_build_results`) e implementa `_fill`, `project_from_form` y `_unit_fields`; menús, archivos, cálculo, exportaciones y unidades vienen de la base. Además, la entrada del menú **Archivo** en `gui/app.py`, y la galería de inicio (`gui/start_data.py`) con sus plantillas. Abrir un archivo, la galería y el arranque ya eligen la ventana por el registro.
7. **Ayuda, ejemplo y documentación:** ayuda de los campos (`i18n/help.es.toml`), un ejemplo en `examples/` citado en el manual, la referencia del bloque en `docs/usuario/03-proyecto.md`, las verificaciones en `docs/tecnico/04-verificaciones.md` y la validación en `docs/tecnico/07-validacion.md`. Regenere la referencia de los ejemplos con `python tools/snapshot_examples.py`.
8. **Esta guía:** agregue la fila de la familia a la tabla de arriba.

`tests/test_families.py` comprueba que cada familia registrada tenga un bloque en `Project`, un subcomando, una memoria importable, un ejemplo en `examples/` que se calcula y da miembros para el lote, la clase de su ventana y su fila en esta tabla.
