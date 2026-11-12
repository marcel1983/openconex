# Propuesta: visor 3D con z-buffer y vista de conexión

**Estado:** aprobada. Fases 1–2 implementadas juntas en 0.5.16; fase 3 pendiente.  
**Fecha:** 2026-11-12.  
**Base:** OpenConex 0.5.15.

## 1. Situación actual

El visor 3D y las miniaturas usan un canvas propio con `QPainter` y un
algoritmo de pintor: se proyectan los triángulos, se ordenan por profundidad
media y se dibujan de lejos a cerca.

En 0.5.15 ya se corrigieron los problemas más visibles:

- orientación uniforme de las caras y ocultación de caras posteriores;
- sin lápiz oscuro por triángulo (ya no se ve la malla);
- subdivisión de caras planas grandes para que el orden por profundidad sea
  local;
- colores semánticos: conexión en naranja, viga/apoyo/columna en gris azulado.

Queda una limitación de fondo: cuando el ala de una viga tapa parcialmente un
ángulo, el borde de oclusión puede verse con dientes de sierra, y las piezas
que se penetran (pernos dentro de placas) no tienen oclusión por píxel. El
algoritmo de pintor no puede resolverlo de forma exacta.

## 2. Objetivos

1. Oclusión exacta por píxel en el visor interactivo.
2. Sin wireframe, sin caras posteriores y sin parpadeo al girar.
3. Bordes limpios (silueta y aristas vivas), no la triangulación.
4. Mantener la interactividad: giro, zoom, desplazamiento, selección y
   ocultación de piezas.
5. Funcionar en Windows, macOS y Linux, con retroceso automático si OpenGL no
   está disponible (escritorio remoto, VM, CI sin GPU).
6. No cambiar el cálculo ni la geometría exportada a STEP/STL.

## 3. Fuera de alcance

- Cálculo, verificaciones y formatos de proyecto.
- Render fotorrealista, sombras reales o materiales.
- Sustituir OpenCASCADE como generador de sólidos.
- Nuevos tipos de conexión.

## 4. Opciones

| Opción | Ventaja | Inconveniente | Decisión |
|---|---|---|---|
| A. Seguir con `QPainter` y heurísticas | Sin dependencias; ya funciona | No hay oclusión exacta; los dientes de sierra y las penetraciones siguen | Solo como respaldo |
| B. Z-buffer por software en Python | Oclusión exacta; sin GPU | Lento para 20k–100k triángulos; complejo; probablemente necesite NumPy | Descartada |
| C. `QOpenGLWidget` con z-buffer | Oclusión exacta, rápido, MSAA, selección, transparencia y clipping | Requiere contexto OpenGL y prueba en cada plataforma | **Recomendada** |
| D. Biblioteca externa (VTK, VisPy, pyqtgraph) | Muchas funciones hechas | Dependencia grande, licencias, empaquetado y estilo difíciles de integrar | Descartada |

## 5. Solución propuesta

### 5.1. Dos backends, una sola escena

Separar la escena de la forma de dibujarla:

```text
Viewer3D
  ├─ MeshScene        piezas, colores, visibilidad, selección
  ├─ Camera           yaw, pitch, zoom, pan, proyección ortográfica
  ├─ PainterCanvas    QPainter; miniaturas, offscreen y respaldo
  └─ OpenGLCanvas     QOpenGLWidget; visor interactivo
```

`PainterCanvas` conserva el render actual y sigue generando las miniaturas de
la galería de forma determinista. `OpenGLCanvas` se usa en la pestaña 3D cuando
hay contexto OpenGL; si no lo hay, se vuelve a `PainterCanvas` sin cambiar la
interfaz.

### 5.2. OpenGL

- Proyección ortográfica equivalente a la cámara actual.
- `glEnable(GL_DEPTH_TEST)` con `GL_LESS` y búfer de profundidad.
- Culling de caras posteriores.
- MSAA 4× y líneas suavizadas.
- Shader sencillo:
  - posición y normal por vértice;
  - color por pieza;
  - luz principal + luz de relleno + ambiente;
  - selección con color más claro y contorno.
- Un `VBO` por pieza o un único buffer con atributo de color; las piezas se
  dibujan por separado para poder ocultarlas y resaltarlas.
- Sin subdivisión para el visor: el z-buffer no la necesita. Las miniaturas
  mantienen la subdivisión de 25 mm.

### 5.3. Aristas y siluetas

En una segunda pasada, dibujar solo:

- bordes de contorno (una cara);
- aristas vivas (cambio de normal mayor que un umbral);
- siluetas (una cara frontal y otra posterior).

Con `glPolygonOffset` o un pequeño sesgo de profundidad para evitar z-fighting.
No se dibuja la triangulación interna.

### 5.4. Vista de conexión

Añadir en la pestaña 3D:

- botón **Separar** (o control 0–100 %) que aplica los mismos desplazamientos
  de la galería: separa la viga del apoyo para ver placas, ángulos y asientos;
- botones de vistas **Isométrica**, **Frontal**, **Superior** y **Lateral**;
- **Ajustar vista** ya existe; se conserva.

La vista separada es una ayuda de inspección: al desactivarla, el modelo vuelve
a la posición real. No cambia el proyecto ni la exportación.

### 5.5. Detección de OpenGL y respaldo

- Intentar crear el contexto al abrir la pestaña 3D.
- Si falla (`QOpenGLContext.create()` falso, plataforma `offscreen`, escritorio
  remoto sin aceleración), usar `PainterCanvas` y mostrar una nota discreta:
  “Vista simplificada: OpenGL no disponible”.
- La preferencia se puede recordar por sesión, sin tocar el proyecto.

## 6. Fases y entregables

| Fase | Contenido | Versión propuesta | Estimación |
|---|---|---|---|
| 0 | Render limpio actual: culling, sin wireframe, subdivisión y colores | 0.5.15 (hecho) | — |
| 1 | Vistas estándar, ajustar y botón **Separar** con la vista explosionada | 0.5.16 | 1–2 días |
| 2 | Backend OpenGL con z-buffer, MSAA, selección, ocultación y respaldo | 0.5.17 | 4–6 días |
| 3 | Aristas vivas/siluetas, plano de corte y transparencia opcional | 0.5.18 | 2–3 días |
| 4 (opcional) | Agujeros de pernos, tuercas, arandelas y cordones de soldadura | 0.5.19 / 0.6.0 | 3–5 días |

La fase 1 da una mejora inmediata sin tocar el renderer. La fase 2 es la que
elimina de verdad los dientes de sierra y las penetraciones. En 0.5.16 se
publicaron las fases 1 y 2 juntas; la tabla conserva la estimación original por
fases.

## 7. Criterios de aceptación

- En las vistas estándar no se ve triangulación, caras posteriores ni
  z-fighting.
- El borde entre el ala de la viga y un ángulo es limpio, sin dientes de
  sierra, al girar y hacer zoom.
- El visor mantiene al menos 30 fps a 720p con 100 000 triángulos en un equipo
  de oficina; el primer frame no supera 1 s.
- Selección, ocultación, giro, zoom, pan y ajuste funcionan igual que ahora.
- Sin OpenGL, la pestaña sigue funcionando con el render de respaldo.
- Las miniaturas de la galería no cambian de geometría ni de composición.
- `ruff`, `mypy`, pruebas y CI en verde en Windows, macOS y Linux.
- El cálculo y STEP/STL no cambian en las fases 1–3.

## 8. Pruebas y verificación

- Unitarias: cámara, matrices, culling, extracción de aristas, selección de
  backend.
- Imágenes de referencia: miniaturas `QPainter` en modo offscreen; el render
  OpenGL se compara con tolerancia cuando hay contexto.
- Pruebas de respaldo: `QT_QPA_PLATFORM=offscreen` debe seguir generando la
  vista simplificada sin errores.
- Prueba manual por plataforma: placa base expuesta y empotrada; corte
  viga-columna y viga-viga; doble ángulo, placa simple, extendida, extremo,
  asiento, rigidizado y doblado; ocultar/mostrar y seleccionar.
- Rendimiento: malla de 20k y 100k triángulos; medir tiempo de frame y memoria.
- Empaquetado: añadir `PySide6.QtOpenGLWidgets` a los imports ocultos de
  `packaging/build_portable.py`; probar los tres ZIP portables.

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| OpenGL no disponible en escritorio remoto o VM | Respaldo automático a `QPainter`; nota en la pestaña |
| macOS mantiene OpenGL en desuso | Probar Qt 6.8; si falla, evaluar `QRhiWidget` (Metal/Vulkan/D3D) en una fase posterior |
| Diferencias de color/iluminación entre backends | Paleta y luces compartidas; imágenes de referencia |
| Coste de empaquetado | `QtOpenGLWidgets` ya forma parte de PySide6; solo hay que declararlo en PyInstaller |
| Pérdida de estado al cambiar de backend | Estado centralizado en `MeshScene`; los canvas solo dibujan |
| Z-fighting en aristas | `glPolygonOffset` y bias de profundidad |
| La fase 4 cambia STEP/STL | Decidir antes: solo visualización o geometría exportada |

## 10. Decisiones que necesito

1. ¿Apruebas la opción **C (OpenGL)** y las fases 1–2 para 0.5.16/0.5.17?
2. ¿Prefieres empezar por la fase 1 (vista separada y vistas estándar) o ir
   directamente al backend OpenGL?
3. En la fase 4, ¿los agujeros de pernos deben verse solo en el visor o también
   cambiar STEP/STL?

## 11. Archivos previstos

- `src/openconex/gui/viewer3d.py`: separar escena, cámara y canvas.
- `src/openconex/gui/viewer3d_gl.py` (nuevo): canvas OpenGL, shaders y VBO.
- `src/openconex/geometry3d/mesh.py`: normales y aristas para el pase de
  contorno.
- `packaging/build_portable.py`: `PySide6.QtOpenGLWidgets`.
- `tests/outputs/test_viewer3d.py`: backend, culling, aristas y respaldo.
- `docs/usuario/09-interfaz.md` y `docs/tecnico/01-arquitectura.md`: flujo y
  limitaciones.
- `docs/verificacion/render-3d/`: capturas antes/después por plataforma.
