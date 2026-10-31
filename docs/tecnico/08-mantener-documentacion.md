# 8. Mantener la documentación

**Regla:** todo cambio que modifique lo que el programa hace, cómo se usa o cómo calcula actualiza la documentación **en el mismo pull request**. No se deja para después.

## Qué actualizar según el cambio

| Si el cambio… | Actualice |
|---|---|
| agrega o cambia un campo del `.ocnx` | `docs/usuario/03-proyecto.md` (y un ejemplo en `examples/` si es una función nueva) |
| agrega o cambia un comando u opción | `docs/usuario/04-comandos.md` |
| agrega o cambia una verificación | `docs/tecnico/04-verificaciones.md`, `docs/tecnico/03-placa-base.md` (si la usa la placa base) y los títulos en `i18n/es.toml` y `en.toml` |
| cambia una fórmula, hipótesis o criterio | `docs/tecnico/03-placa-base.md` o el documento técnico del tema |
| agrega una validación (ejemplo o tabla) | `docs/tecnico/07-validacion.md` |
| cambia la importación | `docs/usuario/05-importar-sap2000.md` y `docs/tecnico/06-importacion-csi.md` |
| cambia las salidas | `docs/usuario/06-resultados.md` |
| quita o agrega una limitación | `docs/usuario/08-limitaciones.md` |
| agrega un módulo o cambia el flujo | `docs/tecnico/01-arquitectura.md` |
| avanza una fase | estado en `docs/PLAN.md` |

## Qué comprueba la integración continua

`tests/test_docs.py` falla si:

- un identificador de verificación con título en `i18n` (`check.*`) no aparece en `docs/tecnico/04-verificaciones.md`;
- un comando u opción de `openconex` no aparece en `docs/usuario/04-comandos.md`;
- un campo de los modelos del proyecto (`info`, `base_plate`, secciones, llave de corte, casos, combinaciones) no aparece en `docs/usuario/03-proyecto.md`;
- un ejemplo de `examples/` no está citado en el manual de usuario;
- un material disponible no aparece en `docs/usuario/07-unidades-materiales.md`;
- un enlace relativo entre documentos apunta a un archivo que no existe.

Estas pruebas atrapan lo que se olvida con facilidad, pero no comprueban que el texto sea correcto. Eso queda en la revisión del pull request, que tiene una casilla para ello en `.github/pull_request_template.md`.

## Estilo

- Español claro, frases cortas; los términos de la norma como los usa la norma (f'c, φ, Ω, h_ef).
- Cada fórmula con su cláusula.
- Nada de texto, tablas ni figuras copiados de AISC, ACI o ASCE: se describen y se citan.
