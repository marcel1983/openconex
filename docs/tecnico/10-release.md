# 10. Publicar una release

OpenConex se publica con tres paquetes portables y los paquetes de Python. El flujo es automático al empujar una etiqueta `v*`, pero conviene revisar los pasos manuales antes y después.

## 1. Preparar la versión

1. Actualizar `__version__` en `src/openconex/__init__.py`.
2. Actualizar las notas o la documentación que mencione la versión anterior.
3. Ejecutar las comprobaciones locales:

```bash
ruff check .
python -m pytest
python -m pytest tests/outputs -ra
python tools/check_licenses.py
```

`tests/outputs` requiere los extras `pdf` y `3d`. En Linux también hacen falta las bibliotecas de sistema de Qt WebEngine (ver `docs/usuario/01-instalacion.md`).

## 2. Etiqueta y workflow

1. Fusionar el PR en `main` y esperar a que el CI esté en verde.
2. Crear y empujar la etiqueta:

```bash
git tag v0.4.3
git push origin v0.4.3
```

El workflow `.github/workflows/release.yml` compila en Windows x64, macOS ARM64 y Linux x86_64:

- Ejecuta `packaging/build_portable.py <plataforma>`.
- Construye la GUI (`OpenConex`) y la CLI (`openconex-cli/openconex`) con PyInstaller `--onedir`.
- Ejecuta la prueba de humo sobre las carpetas de `dist`: versión, assets, conversión de unidades, placa base y conexión de corte.
- Empaqueta el ZIP, extrae ese mismo ZIP y vuelve a probar la GUI, los assets, la CLI, la exportación PDF y el modelo STEP desde el paquete extraído. Así se detectan symlinks rotos o bibliotecas que falten.
- Genera `SHA256SUMS-<plataforma>.txt`.

El trabajo `publish` crea el wheel y el sdist, reúne los tres ZIP, escribe `SHA256SUMS.txt` y crea o actualiza el release de GitHub.

### Ejecución manual

`workflow_dispatch` permite construir una rama sin publicar:

- `tag` vacío y `publish` desactivado: compila y sube los artefactos del workflow.
- `tag` con una etiqueta existente y `publish` activado: publica esa etiqueta.
- `publish` activado sin `tag`: falla al inicio con un mensaje claro y no publica nada.

## 3. Comprobar la release

1. Descargar los tres ZIP y `SHA256SUMS.txt`.
2. Verificar los checksums:

```bash
sha256sum -c SHA256SUMS.txt
```

En Windows se puede usar `Get-FileHash` y comparar con el archivo.

3. Abrir la GUI y ejecutar la CLI desde el paquete descomprimido en cada plataforma.
4. En Linux, extraer con `unzip`, `tar` o el gestor de archivos del escritorio. El ZIP contiene enlaces simbólicos para no repetir las bibliotecas de Qt y OpenCASCADE; hay que conservarlos y mantener juntas las carpetas `OpenConex` y `openconex-cli`.
5. Comprobar que el paquete incluye `LICENSE`, `NOTICE-AISC.md`, `LEEME.txt` y la carpeta `licenses/`.

## 4. Empaquetado

- La GUI y la CLI se compilan por separado para evitar el choque de nombres entre `OpenConex.exe` y `openconex.exe` en Windows.
- En Linux, `packaging/build_portable.py` sustituye por symlinks los archivos idénticos de más de 1 MiB antes de comprimir. Esto elimina las copias repetidas de Qt, OpenCASCADE y NumPy que PyInstaller deja en varias rutas. En 0.4.3 pasó de 1.071 MiB a 438 MiB.
- Los textos de licencia de PySide6/Qt, OpenCASCADE, PyInstaller y Python están en `packaging/licenses/` y se copian a `licenses/` dentro de cada paquete.
- La distribución `--onedir` deja las bibliotecas como archivos separados, de modo que se pueden reemplazar por versiones compiladas por el usuario para cumplir las obligaciones de relinking de la LGPL.
- Los binarios no están firmados en esta fase. Windows SmartScreen y macOS Gatekeeper pueden pedir confirmación.
