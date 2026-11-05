# 1. Instalación

Se necesita **Python 3.12 o posterior** en Windows, macOS o Linux, o se puede usar un **ejecutable portable** publicado en cada release.

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

No requieren Python instalado. Incluyen Qt, el visor 3D, la exportación PDF y el catálogo AISC. Los binarios no están firmados en esta fase: Windows SmartScreen y macOS Gatekeeper pueden pedir confirmación. Cada release publica `SHA256SUMS.txt` para verificar las descargas.

En Linux, el ZIP usa enlaces simbólicos para no repetir las bibliotecas de Qt y OpenCASCADE. Extráigalo con una herramienta que los conserve (`unzip`, `tar` o el gestor de archivos del escritorio) y mantenga juntas las carpetas `OpenConex` y `openconex-cli`.

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
| `pdf` | memoria en PDF (usa Qt WebEngine) | `pip install -e ".[pdf]"` |
| `3d` | modelo 3D STEP y STL (usa OpenCASCADE) | `pip install -e ".[3d]"` |
| `dev` | pruebas y estilo, para quien desarrolla | `pip install -e ".[dev]"` |

Se pueden combinar: `pip install -e ".[pdf,3d]"`.

En Linux, la GUI y la memoria PDF necesitan bibliotecas de sistema de Qt. En una instalación mínima instale, por ejemplo, `libegl1`, `libgl1`, `libxkbcommon0`, `libnss3`, `libxcb-cursor0`, `libxcomposite1`, `libxdamage1`, `libxrandr2`, `libxtst6`, `libxkbfile1`, `libgbm1` y `libasound2`.

## Comprobar la instalación

```bash
openconex --version
```
```bash
openconex baseplate examples/base_plate_dg1_4_7_11.ocnx
```

El segundo comando calcula un ejemplo de la Guía de Diseño 1 e imprime el resumen de verificaciones.
