# 10. Publicar una release

OpenConex se publica en GitHub Releases con tres paquetes portables, tres instaladores nativos (`.msi`, `.dmg`, `.AppImage`), el wheel y el sdist; el wheel y el sdist también pueden subirse a PyPI. Todo lo hace `.github/workflows/release.yml` al empujar una etiqueta `v*`. La configuración que necesita credenciales (PyPI, certificados de firma) se hace una sola vez y se describe en la [sección 5](#5-configuración-única-credenciales).

## 1. Preparar la versión

1. Actualizar `__version__` en `src/openconex/__init__.py`. El formato es `X.Y.Z` o, para una versión previa, `X.Y.ZaN`, `X.Y.ZbN` o `X.Y.ZrcN` (PEP 440).
2. Actualizar las notas o la documentación que mencione la versión anterior.
3. Ejecutar las comprobaciones locales:

```bash
ruff check .
python -m mypy
python -m pytest --cov=openconex --cov-fail-under=88   # con los extras dev,pdf,3d,gui-test
python -m pytest tests/outputs -ra
python tools/check_licenses.py
python tools/check_release_version.py v0.5.21   # la etiqueta que se va a crear
```

`tests/outputs` requiere los extras `pdf` y `3d`. En Linux también hacen falta las bibliotecas de sistema de Qt WebEngine (ver `docs/usuario/01-instalacion.md`).

## 2. Etiqueta y workflow

1. Fusionar el PR en `main` y esperar a que el CI esté en verde.
2. Crear y empujar la etiqueta, que debe coincidir con `__version__` (con una `v` delante):

```bash
git tag v0.5.21
git push origin v0.5.21
```

El workflow tiene estos trabajos:

| Trabajo | Qué hace |
|---|---|
| `version` | `tools/check_release_version.py <tag>`: falla si la etiqueta no tiene el formato `vX.Y.Z[aN\|bN\|rcN]` o si no coincide con `__version__`. Todo lo demás depende de este trabajo, así que una etiqueta equivocada no publica nada. |
| `dist` | Construye el wheel y el sdist (`python -m build`), los revisa con `twine check --strict`, instala el wheel en un entorno limpio y calcula un ejemplo con HTML, DOCX y DXF. |
| `build` | En Windows x64, macOS ARM64 y Linux x86_64: paquete portable (`packaging/build_portable.py`) y después el instalador (`packaging/build_installer.py`). |
| `publish` | Reúne los artefactos, escribe y comprueba `SHA256SUMS.txt` y crea o actualiza el release de GitHub. Las versiones `a`, `b` o `rc` se marcan como *pre-release*. |
| `pypi` | Sube el wheel y el sdist a PyPI con Trusted Publishing. Solo corre si la variable del repositorio `PYPI_PUBLISH` vale `true`, o a mano. |
| `testpypi` | Igual, contra TestPyPI. Solo corre si `TESTPYPI_PUBLISH` vale `true`, o a mano. |

### Paquete portable

- Instala las dependencias con las versiones exactas de `packaging/constraints-portable.txt` (`pip install -c …`), así dos construcciones de la misma etiqueta llevan las mismas bibliotecas. Para actualizarlas: instalar `.[gui,pdf,3d]` y `pyinstaller` en un entorno virtual limpio con Python 3.12, copiar `pip freeze --exclude-editable` (sin `setuptools`) al archivo, correr la suite completa y comprobar que existen wheels para Windows x64, macOS ARM64 y Linux x86_64.
- Construye la GUI (`OpenConex`) y la CLI (`openconex-cli/openconex`) con PyInstaller `--onedir`.
- Ejecuta la prueba de humo sobre las carpetas de `dist`: versión, assets, conversión de unidades, placa base, conexión de corte, conexión de momento, placa de extremo de momento y columna rigidizada.
- Empaqueta el ZIP, extrae ese mismo ZIP y vuelve a probar la GUI, los assets, la CLI, la exportación PDF y el modelo STEP desde el paquete extraído. Así se detectan symlinks rotos o bibliotecas que falten.

### Instaladores

`packaging/build_installer.py <plataforma>` parte de la carpeta `build/portable/OpenConex-<versión>-<plataforma>` que deja el paso anterior, de modo que el instalador lleva exactamente los archivos que ya pasaron la prueba de humo.

| Plataforma | Herramienta | Contenido | Prueba en el workflow |
|---|---|---|---|
| Windows | WiX Toolset 5 (`dotnet tool install --global wix`) | MSI por máquina en `Program Files\OpenConex`, acceso en el menú Inicio, CLI en el `PATH` del sistema, icono y enlaces en *Aplicaciones instaladas*. `UpgradeCode` fijo: una versión nueva reemplaza a la anterior (`MajorUpgrade`). | Instala en silencio (`msiexec /qn`), ejecuta la CLI y `--check-assets` de la GUI desde la carpeta instalada, desinstala y falla si queda algo en `Program Files\OpenConex`. |
| macOS | `hdiutil` | `.dmg` UDZO con `OpenConex.app`, la carpeta `openconex-cli`, las licencias y un enlace a `/Applications`. | Monta la imagen en solo lectura y ejecuta la GUI y la CLI desde ella. |
| Linux | `appimagetool` 1.9.1 | AppImage con las dos carpetas en `usr/lib/openconex`, `AppRun`, `openconex.desktop` e icono. `AppRun` abre la GUI, o la CLI con `--cli` o si se llama por un enlace `openconex`. Los symlinks del portable se conservan (squashfs). | Ejecuta la GUI (`--version`, `--check-assets`) y la CLI, y calcula la placa base con PDF y STEP desde el AppImage. |

El MSI necesita un número de versión numérico: para `0.6.0rc1` usa `0.6.0`. La desinstalación de Windows no borra las preferencias de la interfaz (`QSettings` en el registro del usuario), igual que la mayoría de los programas; es deliberado para no perderlas al actualizar.

Después de construir el instalador, el script reescribe `SHA256SUMS-<plataforma>.txt` con el ZIP, el instalador y, en Linux, la firma `.asc`.

### Firma

La firma depende solo de que existan los secretos de la sección 5. Sin ellos el workflow funciona igual y publica binarios sin firmar (los forks y las ejecuciones de prueba no tienen acceso a los secretos).

- **Windows:** `signtool` firma todos los `.exe` del paquete y después el `.msi`, con SHA-256 y sello de tiempo RFC 3161 (`WINDOWS_TIMESTAMP_URL`, por defecto DigiCert). Como la firma cambia los `.exe`, el ZIP portable se vuelve a construir con los archivos firmados.
- **macOS:** `codesign` con *hardened runtime* y `packaging/macos/entitlements.plist` (JIT y memoria ejecutable para Qt WebEngine, sin validación de bibliotecas para los módulos de Python), de dentro hacia fuera: primero cada binario Mach-O, después los `.framework` y la `.app`. Luego firma el `.dmg`, lo envía a notarizar con `notarytool --wait`, le grapa el ticket (`stapler`) y comprueba el resultado con `spctl`. El ZIP portable también se reconstruye con la app firmada; el ticket de notarización solo se grapa al `.dmg`, así que el ZIP necesita conexión la primera vez que se abre para que Gatekeeper consulte el ticket.
- **Linux:** firma GPG separada y en ASCII (`OpenConex-<versión>-linux-x86_64.AppImage.asc`), comprobada en el mismo paso. La clave pública debe publicarse (por ejemplo, en el README o en un servidor de claves) para que los usuarios puedan verificarla.

La firma de macOS y Windows se escribió siguiendo la documentación de Apple y Microsoft, pero no se ha podido probar sin certificados reales. La primera release firmada debe revisarse a mano (sección 3).

### Ejecución manual

`workflow_dispatch` permite construir una rama sin publicar:

- `tag` vacío, `publish` desactivado y `pypi` en `none`: compila, prueba y sube los artefactos del workflow (ZIP, instaladores y `python-dist`). Sirve para probar el empaquetado desde un PR.
- `tag` con una etiqueta existente y `publish` activado: publica esa etiqueta en GitHub.
- `pypi` en `testpypi`: sube el wheel y el sdist del ref construido a TestPyPI (las versiones ya subidas se omiten).
- `pypi` en `pypi`: sube a PyPI; exige `tag`.
- `publish` o `pypi: pypi` sin `tag`: falla al inicio con un mensaje claro y no publica nada.

## 3. Comprobar la release

1. Descargar los ZIP, los instaladores y `SHA256SUMS.txt`.
2. Verificar los checksums:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing
```

En Windows se puede usar `Get-FileHash` y comparar con el archivo.

3. En una máquina limpia de cada plataforma: instalar, abrir la GUI, ejecutar la CLI, desinstalar y comprobar que no quedan archivos del programa. El workflow ya lo hace en los runners, pero los runners tienen herramientas que un equipo normal no tiene.
4. Si la release va firmada:
   - Windows: *Propiedades → Firmas digitales* del `.msi` y de `OpenConex.exe`, o `signtool verify /pa archivo`.
   - macOS: `spctl --assess --type open --context context:primary-signature -v OpenConex-*.dmg` y `spctl --assess -v /Applications/OpenConex.app`; la app debe abrir sin aviso de Gatekeeper.
   - Linux: `gpg --verify OpenConex-*.AppImage.asc OpenConex-*.AppImage`.
5. En Linux, extraer el ZIP con `unzip`, `tar` o el gestor de archivos del escritorio. El ZIP contiene enlaces simbólicos para no repetir las bibliotecas de Qt y OpenCASCADE; hay que conservarlos y mantener juntas las carpetas `OpenConex` y `openconex-cli`.
6. Comprobar que el paquete incluye `LICENSE`, `NOTICE-AISC.md`, `LEEME.txt` y la carpeta `licenses/`.
7. Si se publicó en PyPI: `pip install openconex==<versión>` en un entorno limpio y `openconex --version`; con `pip install "openconex[gui,pdf,3d]"`, abrir `openconex-gui` y exportar un PDF y un STEP.

## 4. Empaquetado

- La GUI y la CLI se compilan por separado para evitar el choque de nombres entre `OpenConex.exe` y `openconex.exe` en Windows.
- En Linux, `packaging/build_portable.py` sustituye por symlinks los archivos idénticos de más de 1 MiB antes de comprimir. Esto elimina las copias repetidas de Qt, OpenCASCADE y NumPy que PyInstaller deja en varias rutas. En 0.4.3 pasó de 1.071 MiB a 438 MiB.
- Los textos de licencia de PySide6/Qt, OpenCASCADE, PyInstaller y Python están en `packaging/licenses/` y se copian a `licenses/` dentro de cada paquete y de cada instalador.
- La distribución `--onedir` deja las bibliotecas como archivos separados, de modo que se pueden reemplazar por versiones compiladas por el usuario para cumplir las obligaciones de relinking de la LGPL. Los instaladores conservan esa estructura.
- El README que ve PyPI se genera desde `README.md` con `hatch-fancy-pypi-readme`: los enlaces e imágenes relativos se reescriben a URL absolutas de GitHub (`pyproject.toml`, `[tool.hatch.metadata.hooks.fancy-pypi-readme]`). `tests/test_packaging.py` comprueba que no quede ningún enlace relativo.
- El trabajo `package` del CI construye el wheel y el sdist en cada PR, los revisa con `twine check` e instala el wheel en un entorno limpio.

## 5. Configuración única (credenciales)

Nada de esto se guarda en el repositorio. Los secretos se cargan en *Settings → Secrets and variables → Actions* de GitHub; los entornos, en *Settings → Environments*.

### PyPI y TestPyPI (Trusted Publishing)

No hace falta token: PyPI confía en el workflow por OIDC. El nombre `openconex` estaba libre en PyPI y TestPyPI el 2026-11-23.

1. Crear cuentas en <https://pypi.org> y <https://test.pypi.org> (con 2FA).
2. En cada índice: *Your account → Publishing → Add a new pending publisher* con:
   - PyPI project name: `openconex`
   - Owner: `marcel1983`, Repository: `openconex`
   - Workflow name: `release.yml`
   - Environment name: `pypi` (en TestPyPI: `testpypi`)
3. En GitHub, crear los entornos `pypi` y `testpypi`. En `pypi` conviene activar *Required reviewers* (el propio mantenedor) y limitar *Deployment branches and tags* a `v*`, para que cada subida a PyPI pida una aprobación.
4. Probar con TestPyPI: *Actions → Release → Run workflow*, `pypi: testpypi`. Después:

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ openconex
```

5. Cuando funcione, crear la variable del repositorio `PYPI_PUBLISH` = `true` para que cada etiqueta suba también a PyPI. Una versión subida a PyPI no se puede reemplazar: si sale mal, se publica la siguiente.

### Windows (Authenticode)

| Secreto | Contenido |
|---|---|
| `WINDOWS_CERTIFICATE` | Certificado de firma de código en PFX, en base64 (`base64 -w0 cert.pfx`, o `[Convert]::ToBase64String([IO.File]::ReadAllBytes("cert.pfx"))` en PowerShell). |
| `WINDOWS_CERTIFICATE_PASSWORD` | Contraseña del PFX. |
| `WINDOWS_TIMESTAMP_URL` | Opcional. Servidor de sello de tiempo de la autoridad del certificado. |

Desde 2023 las autoridades entregan los certificados nuevos en un token físico o en un HSM en la nube, no como PFX. Para un proyecto libre hay dos opciones prácticas: [SignPath Foundation](https://signpath.org), gratuita para proyectos de código abierto, o Azure Trusted Signing. Ambas firman con su propia acción de GitHub en lugar del PFX; si se elige una, se reemplaza `windows_sign` en `packaging/build_installer.py` por esa acción, antes y después de `wix build`.

### macOS (Developer ID y notarización)

Requiere una cuenta del Apple Developer Program (de pago).

| Secreto | Contenido |
|---|---|
| `MACOS_CERTIFICATE` | Certificado *Developer ID Application* con su clave privada, exportado desde Llaveros como `.p12` y codificado en base64. |
| `MACOS_CERTIFICATE_PASSWORD` | Contraseña del `.p12`. |
| `MACOS_SIGN_IDENTITY` | Nombre de la identidad, p. ej. `Developer ID Application: Nombre (TEAMID)` (`security find-identity -v -p codesigning`). |
| `APPLE_ID` | Correo de la cuenta de desarrollador. |
| `APPLE_TEAM_ID` | Team ID de 10 caracteres. |
| `APPLE_APP_PASSWORD` | Contraseña específica de app creada en <https://account.apple.com> para `notarytool`. |

El workflow crea un llavero temporal en el runner, importa el certificado y lo borra al terminar el trabajo.

### Linux (GPG)

| Secreto | Contenido |
|---|---|
| `LINUX_GPG_KEY` | Clave privada GPG en ASCII (`gpg --armor --export-secret-keys <id>`). Conviene una subclave solo de firma, dedicada a las releases. |
| `LINUX_GPG_PASSPHRASE` | Frase de paso de la clave (vacía si no tiene). |

Publicar la clave pública (`gpg --armor --export <id>`) junto con su huella en el README.

## 6. Historial de versiones

Los commits `release: 0.5.16`, `0.5.17` y `0.5.18` están en `main` sin etiqueta ni release propios: esas versiones no se publicaron por separado y sus cambios están agrupados en las notas de la release 0.5.19. La etiqueta `v0.5.21` existe pero no tiene release: se creó sin que corriera el workflow, y sus cambios se publicaron en la 0.5.22. No se rellenan las etiquetas, porque crear ahora un release para ellas publicaría binarios que nadie probó en su momento. Desde la incorporación de `tools/check_release_version.py`, cada `release: X.Y.Z` debe ir seguido de su etiqueta `vX.Y.Z`.
