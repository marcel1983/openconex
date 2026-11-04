# Propuesta de identidad visual — OpenConex en azul AISC

## Concepto

**«El árbol que conecta»**

La estructura real de conexiones de acero sigue siendo el centro de la identidad. El render 3D se recorta y se lleva a una gama de azules inspirada en la referencia de AISC: azul noche, azul profundo, azul medio, azul claro y blanco.

El icono sintetiza la misma estructura: columna azul, vigas de acero claro y nodos blancos. La jerarquía se construye con profundidad, contraste y luz, no con muchos acentos.

- **Azul noche:** fondo, profundidad, software técnico.
- **Azul AISC:** estructura principal y vínculo con la referencia.
- **Azul claro:** iluminación, datos técnicos y enlaces.
- **Blanco:** nodos, texto principal y superficies de acero.

## Paleta

| Uso | Color | Hex |
|---|---|---|
| Fondo principal | Azul noche | `#071824` |
| Fondo secundario | Azul profundo | `#0D334A` |
| Estructura | Azul AISC | `#1D6F9F` |
| Estructura iluminada | Azul medio | `#2E86B8` |
| Acento | Azul claro | `#5AA3CE` |
| Luz | Azul hielo | `#8CC8E8` |
| Superficies | Blanco azulado | `#D6E8F2` |
| Texto principal | Blanco | `#F5FAFD` |
| Texto secundario | Azul grisáceo | `#8FB4C9` |

## Tipografía

- **Wordmark y titulares:** Segoe UI Light + Segoe UI Bold.
- **Datos técnicos y versión:** Consolas.
- En otros sistemas: `Segoe UI, Helvetica Neue, Arial, sans-serif` y `Consolas, monospace`.

## Archivos

| Archivo | Formato | Uso |
|---|---|---|
| `render-blue.png` | 629 × 638, fondo transparente | Render recortado y coloreado en azul |
| `banner-github.png` | 1600 × 600 | Cabecera de README o página del proyecto |
| `github-social-preview.png` | 1280 × 640 | Social preview del repositorio en GitHub |
| `splash.png` | 1000 × 700 | Pantalla de inicio de la aplicación |
| `icon.svg` | Vectorial | Icono principal, 256–1024 px |
| `icon-compact.svg` | Vectorial | Variante para 48–256 px |
| `icon-micro.svg` | Vectorial | Variante para 16–32 px |
| `icon.ico` | Windows ICO | 16, 24, 32, 48, 64, 128 y 256 px |
| `icon-1024.png` | PNG 1024 × 1024 | Uso general y documentación |
| `mark.svg` / `mark-1024.png` | Vectorial / PNG | Símbolo sin fondo para composiciones |

## Uso

### GitHub

- Subir `github-social-preview.png` en **Settings → Social preview**.
- Usar `banner-github.png` al inicio del `README.md`.
- El banner no incluye número de versión para no quedar obsoleto.

### Splash screen

- `splash.png` está preparado para una ventana de 1000 × 700.
- La barra inferior deja espacio para que la aplicación muestre el progreso y la versión real.
- En Qt se puede cargar con `QSplashScreen` y superponer el texto de carga.

### Icono

- Windows: usar `icon.ico` en PyInstaller (`--icon`).
- macOS: exportar `icon-1024.png` a `.icns` al firmar/empaquetar.
- Linux: usar `icon-256.png` o `icon-512.png` en el `.desktop`.

## Integración recomendada

1. Añadir `banner-github.png` al inicio del `README.md`.
2. Subir `github-social-preview.png` en **Settings → Social preview**.
3. Pasar `icon.ico` a PyInstaller con `--icon`.
4. Cargar `splash.png` con `QSplashScreen` antes de crear la ventana principal.
5. Sustituir en el splash el texto `v0.4.1` por `openconex.__version__`.

## Nota sobre la imagen

El render fue aportado por el mantenedor del proyecto como referencia visual. Antes de redistribuirlo fuera de OpenConex, conviene confirmar su autoría y derechos de uso.

La paleta se inspira en una referencia visual de AISC, sin utilizar su logotipo ni reproducir su composición.

## Estado

Propuesta cromática, pendiente de aprobación. No está integrada todavía en la aplicación ni en el empaquetado.
