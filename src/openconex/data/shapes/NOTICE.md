# Catálogo de perfiles / Shape catalog

`aisc_v16.sql` contiene los valores de la **AISC Shapes Database v16.0**, publicada por el American Institute of Steel Construction (AISC), https://www.aisc.org. Los valores se copian tal como los publica AISC, en unidades de EE. UU.; OpenConex los convierte a unidades internas al cargarlos.

- El archivo se genera con `tools/build_shapes_db.py` a partir de la hoja de cálculo oficial. No se edita a mano.
- Estos datos **no** son obra de los colaboradores de OpenConex y **no** se distribuyen bajo la GPL. Los derechos que correspondan pertenecen a AISC.
- Versión de origen: *AISC Shapes Database v16.0*, hoja de agosto de 2023 (2 299 perfiles). Su hoja "Readme" incluye un descargo de responsabilidad, que se aplica también aquí: los datos no deben usarse sin la verificación de un profesional habilitado. No incluye condiciones de redistribución.
- Los términos de redistribución de AISC están pendientes de confirmar. Si AISC lo pide, el archivo se retirará del repositorio y se generará en la instalación a partir de la hoja descargada por el usuario.
- Comprueba siempre las propiedades críticas contra el Manual de AISC vigente.

*English:* `aisc_v16.sql` holds the values of the AISC Shapes Database v16.0, published by the American Institute of Steel Construction, copied as published (U.S. customary units) and generated with `tools/build_shapes_db.py`. The data is not authored by the OpenConex contributors and is not licensed under the GPL; any rights belong to AISC. Redistribution terms are pending confirmation with AISC.
