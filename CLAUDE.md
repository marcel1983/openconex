# Instrucciones para Claude en este repositorio

## Documentación: siempre al día

Todo cambio que modifique lo que el programa hace, cómo se usa o cómo calcula **actualiza la documentación en el mismo pull request**:

- `docs/usuario/`: manual de uso (proyecto `.ocnx`, comandos, importación, resultados, unidades, limitaciones).
- `docs/tecnico/`: cómo funciona (arquitectura, convenciones, algoritmos, catálogo de verificaciones, validación).
- `docs/PLAN.md`: estado de la fase.

La tabla de qué actualizar según el tipo de cambio está en `docs/tecnico/08-mantener-documentacion.md`. `tests/test_docs.py` falla si una verificación, opción de comando, campo del proyecto, ejemplo o material no está documentado, pero no comprueba que el texto sea correcto: revise el texto que corresponde al cambio.

## Convenciones del proyecto

- Rama nueva y pull request para cada cambio; no hacer merge sin que lo pida el usuario.
- Commits con `git commit -s` (DCO).
- Encabezado SPDX en cada archivo Python.
- Motor en N, mm y MPa; convertir solo en los bordes con `openconex.units`.
- Cada verificación devuelve un `CheckResult` con traza y cláusula, y tiene título en `i18n/es.toml` y `en.toml`.
- Toda verificación nueva se valida contra un ejemplo publicado o una tabla (`tests/reference/`, `tests/kernel/test_*_manual*.py`).
- No copiar texto, tablas ni figuras de AISC, ACI o ASCE; usar solo datos numéricos con su cita.
- Antes de subir: `ruff check src tests` y `python -m pytest`.
