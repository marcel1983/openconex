# 1. Instalación

Hay tres formas de instalar OpenConex: un **instalador** o un **ejecutable portable** de cada release (no hace falta Python), o el paquete de Python desde **PyPI** o desde el código fuente (necesita **Python 3.12 o posterior** en Windows, macOS o Linux).

## Instaladores

Desde la versión 0.5.21, cada release publica también un instalador por plataforma:

| Plataforma | Archivo | Instalación |
|---|---|---|
| Windows x64 | `OpenConex-<versión>-windows-x64.msi` | Doble clic. Instala en `C:\Program Files\OpenConex`, agrega OpenConex al menú Inicio y la carpeta de la CLI al `PATH` del sistema (abra una terminal nueva para usar `openconex`). Una versión nueva reemplaza a la anterior. |
| macOS ARM64 | `OpenConex-<versión>-macos-arm64.dmg` | Abra la imagen y arrastre `OpenConex.app` a *Aplicaciones*. La carpeta `openconex-cli` de la imagen contiene la CLI; cópiela donde prefiera. |
| Linux x86_64 | `OpenConex-<versión>-linux-x86_64.AppImage` | `chmod +x OpenConex-*.AppImage` y ejecútelo. Con `--cli` ejecuta la línea de comandos (`./OpenConex-*.AppImage --cli baseplate proyecto.ocnx`). Un enlace llamado `openconex` al AppImage también abre la CLI. |

**Desinstalar:**

- **Windows:** *Configuración → Aplicaciones → OpenConex → Desinstalar*. Quita los archivos del programa, el acceso del menú Inicio y la entrada del `PATH`. Las preferencias de la interfaz (proyectos recientes, unidades) quedan en el perfil del usuario.
- **macOS:** arrastre `OpenConex.app` a la papelera.
- **Linux:** borre el archivo `.AppImage`.

**Firma:** cuando el proyecto dispone de los certificados, el `.msi` y los `.exe` van firmados (Authenticode), la app y el `.dmg` de macOS van firmados con Developer ID y notarizados por Apple, y el AppImage tiene una firma GPG separada (`.AppImage.asc`). Mientras no haya certificados, los instaladores se publican sin firmar: Windows SmartScreen pide *Más información → Ejecutar de todas formas* y macOS pide abrir la app con clic derecho → *Abrir* la primera vez. En ambos casos `SHA256SUMS.txt` permite comprobar que la descarga está intacta. Para verificar la firma GPG en Linux:

```bash
gpg --verify OpenConex-<versión>-linux-x86_64.AppImage.asc OpenConex-<versión>-linux-x86_64.AppImage
```

El AppImage necesita FUSE 2 (`libfuse2`) en la mayoría de las distribuciones. Si no está disponible, ejecútelo con `--appimage-extract-and-run`.

## Ejecutables portables

Los releases de GitHub incluyen un paquete portable por plataforma:

| Plataforma | Archivo |
|---|---|
| Windows x64 | `OpenConex-<versión>-windows-x64.zip` |
| macOS ARM64 | `OpenConex-<versión>-macos-arm64.zip` |
| Linux x86_64 | `OpenConex-<versión>-linux-x86_64.zip` |

Descomprima el archivo y ejecute:

- **Windows:** `OpenConex\OpenConex.exe` (GUI) o `openconex-cli\openconex.exe` (CLI).
- **macOS:** `OpenConex.app` (GUI) o `openconex-cli/openconex` (CLI).
- **Linux:** `OpenConex/OpenConex` (GUI) o `openconex-cli/openconex` (CLI).

No requieren Python instalado ni permisos de administrador. Incluyen Qt, el visor 3D, la exportación PDF y el catálogo AISC. La firma de los binarios es la misma que la de los instaladores (ver arriba). Cada release publica `SHA256SUMS.txt` para verificar las descargas.

En Linux, el ZIP usa enlaces simbólicos para no repetir las bibliotecas de Qt y OpenCASCADE. Extráigalo con una herramienta que los conserve (`unzip`, `tar` o el gestor de archivos del escritorio) y mantenga juntas las carpetas `OpenConex` y `openconex-cli`.

## Desde PyPI

Cuando el paquete esté publicado en PyPI (ver el estado en el [plan](../PLAN.md)), basta con:

```bash
pip install openconex
```

Conviene hacerlo dentro de un entorno virtual (`python -m venv .venv`). Los extras se instalan igual que desde el código fuente, sin `-e`:

```bash
pip install "openconex[gui,pdf,3d]"
```

Eso instala los comandos `openconex` y `openconex-gui`. El paquete de PyPI no incluye la carpeta `examples/`; descargue los ejemplos del repositorio si quiere probarlos.

## Desde el código fuente

```bash
git clone https://github.com/marcel1983/openconex.git
```
```bash
cd openconex
```
```bash
python -m venv .venv
```

Active el entorno (`.venv\Scripts\activate` en Windows, `source .venv/bin/activate` en macOS y Linux) e instale:

```bash
pip install -e .
```

Eso basta para calcular y generar la memoria HTML y Word, los planos DXF y la importación desde Excel.

## Extras opcionales

| Extra | Para | Instalación |
|---|---|---|
| `gui` | interfaz gráfica (`openconex-gui`, usa PySide6) | `pip install -e ".[gui]"` |
| `pdf` | memoria en PDF (usa Qt WebEngine) | `pip install -e ".[pdf]"` |
| `3d` | modelo 3D STEP y STL (usa OpenCASCADE) | `pip install -e ".[3d]"` |
| `dev` | pruebas y estilo, para quien desarrolla | `pip install -e ".[dev]"` |

Se pueden combinar: `pip install -e ".[gui,pdf,3d]"`. Desde PyPI, la misma lista va sin `-e` y entre comillas: `pip install "openconex[gui,pdf,3d]"`.

En Linux, la GUI y la memoria PDF necesitan bibliotecas de sistema de Qt. En una instalación mínima instale, por ejemplo, `libegl1`, `libgl1`, `libxkbcommon0`, `libnss3`, `libxcb-cursor0`, `libxcomposite1`, `libxdamage1`, `libxrandr2`, `libxtst6`, `libxkbfile1`, `libgbm1` y `libasound2`.

## Comprobar la instalación

```bash
openconex --version
```
```bash
openconex baseplate examples/base_plate_dg1_4_7_11.ocnx
```

El segundo comando calcula un ejemplo de la Guía de Diseño 1 e imprime el resumen de verificaciones.
