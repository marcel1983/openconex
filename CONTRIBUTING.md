# Contribuir a OpenConex / Contributing to OpenConex

*English below.*

## Español

¡Gracias por tu interés! OpenConex es software libre bajo **GPL-3.0-or-later**.

### Certificado de origen del desarrollador (DCO)
No pedimos ceder derechos (CLA). Cada commit debe llevar la línea `Signed-off-by`, que certifica que tienes derecho a aportar ese código según el [Developer Certificate of Origin 1.1](https://developercertificate.org/):

```bash
git commit -s -m "mensaje"
```

### Reglas
- **Encabezado de licencia** en cada archivo Python:
  ```python
  # SPDX-License-Identifier: GPL-3.0-or-later
  # Copyright (C) 2026 The OpenConex contributors
  ```
  El código derivado de otros proyectos conserva su aviso de copyright original.
- **Código de terceros:** solo con licencia compatible con GPL-3.0 (MIT, BSD, Apache-2.0, LGPL, GPL-3, MPL-2.0). No copies código sin licencia clara.
- **Material protegido:** no copies texto, tablas ni figuras de normas o manuales (AISC, ACI, ASCE). En las pruebas usa solo datos numéricos de los ejemplos resueltos y cita la fuente.
- **Unidades:** dentro del motor todo es `float` en N, mm y MPa. Convierte solo en los bordes con `openconex.units`.
- **Verificaciones:** cada una devuelve un `CheckResult` con su traza y la cláusula de la norma.
- **Pruebas:** `python -m pytest`. Toda verificación nueva necesita al menos un ejemplo de referencia.
- **Estilo:** `ruff check .`

### Entorno
```bash
python -m venv .venv
```
```bash
.venv/bin/pip install -e ".[dev]"
```

## English

Thanks for your interest! OpenConex is free software under **GPL-3.0-or-later**.

- **DCO, no CLA:** sign off every commit (`git commit -s`) to certify the [Developer Certificate of Origin 1.1](https://developercertificate.org/).
- **SPDX header** in every Python file (see above); derived code keeps its original copyright notice.
- **Third-party code** only under GPL-3.0-compatible licenses.
- **Do not copy** text, tables or figures from AISC/ACI/ASCE publications; tests may use numeric data from worked examples, with a citation.
- **Units:** the engine works in N, mm and MPa floats; convert only at the boundaries via `openconex.units`.
- **Checks** return a `CheckResult` with a full trace and code clause.
- Run `python -m pytest` and `ruff check .` before opening a pull request.
