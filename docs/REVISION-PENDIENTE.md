# Revisión pendiente

Estado al 2026-11-05, sobre `main` (`d937ff3`, versión 0.4.4). Cada tarea indica qué hay que hacer y los puntos a verificar antes de cerrarla. Prioridad: **A** (corregir pronto), **B** (siguiente iteración), **C** (cuando se pueda).

## 0. Completado en 0.4.2

- [x] Identidad visual AISC: banner, iconos, splash y assets de marca.
- [x] Icono en los ejecutables de Windows y macOS.
- [x] Comprobación `--check-assets` en la GUI y en el smoke test portable.
- [x] Conversión automática de unidades en la ventana de corte.
- [x] Lista de materiales y cuadro de soldaduras AWS A2.4 en el DXF de corte.
- [x] Ejemplo y validación de placa simple con destaje superior contra II.A-18.
- [x] Release 0.4.2 publicada y verificada en las tres plataformas.

## 0 bis. Completado en 0.4.3 y 0.4.4

- [x] Release 0.4.3 y 0.4.4 publicadas con checksums y prueba de humo en las tres plataformas.
- [x] Zip de Linux deduplicado con symlinks (438 MiB) y licencias de PySide6, OpenCASCADE, PyInstaller y Python.
- [x] Workflow de release para etiquetas `v*`, con wheel, sdist y checksums.
- [x] Ángulo superior de los asientos y placa de asiento del asiento rigidizado.

## 1. Empaquetado y releases (PR #101 a #105)

### 1.1 Zip de Linux duplicado — A (resuelto en 0.4.3)

**Confirmado en 0.4.2 y corregido en 0.4.3.** El zip de 0.4.2 pesaba 1.071 MiB y ocupaba 3.484 MiB descomprimido. `libQt6WebEngineCore.so.6` aparecía cuatro veces con 194,47 MiB cada una: en `OpenConex/_internal/PySide6/Qt/lib`, en `OpenConex/_internal`, y las mismas dos rutas en `openconex-cli`.

`packaging/build_portable.py` ahora sustituye por symlinks relativos los archivos idénticos de más de 1 MiB antes de comprimir. En 0.4.3 reemplazó 330 archivos y evitó 2.137 MiB de copias; el zip quedó en **438 MiB**.

Puntos verificados:
- [x] Guardar los symlinks como tales en el ZIP en lugar de duplicar el contenido.
- [x] Comparar el tamaño: 438 MiB.
- [x] Descomprimir el zip en un runner Linux limpio y ejecutar la GUI, la CLI, la exportación PDF y el modelo STEP desde el paquete extraído.
- [x] Conservar los permisos de ejecución al extraer con `unzip`.

### 1.2 Qt y OpenCASCADE duplicados entre GUI y CLI — B

En Linux, la deduplicación por contenido también elimina la copia que la CLI tiene de Qt y OCP: los symlinks cruzan de `openconex-cli` a `OpenConex`. En Windows y macOS siguen siendo dos `--onedir` completos, con 589 MiB y 538 MiB respectivamente.

Puntos a verificar:
- [ ] Medir cuánto ocupa cada carpeta dentro del zip en Windows y macOS.
- [ ] Probar un `.spec` con `MERGE`, o un solo ejecutable con modo CLI, y comparar el tamaño.
- [x] Repetir la prueba de humo de `build_portable.py` (versión, assets, conversión, placa base y conexión de corte) en las tres plataformas.
- [x] Confirmar que no vuelve el choque de nombres entre `OpenConex.exe` y `openconex.exe` que corrigió el #103.

### 1.3 Licencias de las bibliotecas incluidas — A (resuelto en 0.4.3)

El paquete ahora incluye `licenses/` con los textos de PySide6/Qt (LGPL-3.0), OpenCASCADE (LGPL-2.1 y excepción OCCT), PyInstaller y Python, además de `LICENSE` y `NOTICE-AISC.md`.

Puntos verificados:
- [x] Copiar las licencias de las bibliotecas nativas a una carpeta `licenses/` dentro del zip.
- [x] `tools/check_licenses.py` ya revisa PySide6 y OCP porque el trabajo `licenses` instala los extras `pdf` y `3d`; PyInstaller es una herramienta de compilación y se incluye su texto.
- [x] Documentar que la distribución `--onedir` permite reemplazar las bibliotecas LGPL (relinking) en `docs/tecnico/10-release.md`.
- [x] Comprobar en el ZIP extraído que `LICENSE` y las licencias de PySide6/OpenCASCADE están presentes.

### 1.4 Documentación del empaquetado — B (resuelto en 0.4.3)

Puntos verificados:
- [x] `docs/usuario/01-instalacion.md` usa nombres genéricos `OpenConex-<versión>-…`.
- [x] `packaging/README-portable.txt` y el manual indican las bibliotecas de sistema de Linux y cómo extraer los symlinks.
- [x] `docs/tecnico/10-release.md` documenta la etiqueta `v*`, el workflow, las pruebas de humo y los checksums.
- [x] `docs/PLAN.md` registra el avance de la F8.

### 1.5 Workflow de release — C (resuelto en 0.4.3)

Puntos verificados:
- [x] `contents: write` solo en el trabajo `publish`; el resto usa `contents: read`.
- [x] Acciones fijadas por commit (`checkout`, `setup-python`, `upload-artifact`, `download-artifact`).
- [x] `workflow_dispatch` con `publish` activado y sin `tag` falla al inicio con un mensaje claro y no publica nada.
- [x] Línea de copyright en los archivos Python de `packaging/`.

## 2. Conexiones de corte (F5)

### 2.1 Revisión de la integración — A

Puntos a verificar:
- [ ] Abrir `examples/shear_single_plate.ocnx`, `examples/shear_double_angle_coped.ocnx` y `examples/shear_single_plate_coped.ocnx` en la GUI portable: calcular, ver figuras y 3D, y exportar HTML, DOCX, PDF y DXF.
- [ ] Abrir los DXF en AutoCAD, BricsCAD o LibreCAD: capas `SC-*`, cotas legibles, textos negros, lista de materiales y cuadro de soldaduras.
- [ ] Crear desde la GUI un proyecto de cada uno de los seis tipos y comprobar que los campos visibles y obligatorios son los correctos.
- [ ] Calcular con unidades SI (`SI_kN_m`) y comprobar que la memoria convierte bien las cantidades.
- [ ] Confirmar que la compresión axial y la tracción en tipos sin procedimiento axial aparecen como "no cumple".
- [ ] Cálculo por lotes con una carpeta que mezcle placas base y conexiones de corte.

### 2.2 Valores a contrastar con el Manual — B

Diferencias aceptadas en la validación que conviene revisar con criterio propio:

- [ ] II.A-17A y II.A-17B: C del centro instantáneo (3,556 y 4,06) contra el interpolado de las tablas (3,54 y 4,07).
- [ ] II.A-1B: la interacción del bloque de corte usa la forma U (0,054); el ejemplo usa la forma L (0,0531).
- [ ] II.A-12A: el ejemplo entra a la Tabla 10-5 con l_b = 1⅛ in; el programa usa la mínima requerida (k_des). Con k_des la flexión del ala da unos 133 kip contra 113.
- [ ] II.A-12A: la resistencia de pernos del ejemplo (107/71,6 kip) corresponde a seis pernos, no a los cuatro que indica el ejemplo.
- [ ] II.A-19A: Z_net calculado (12,75 in³) contra el de la Tabla 15-2 (12,8 in³).
- [ ] Asientos (Tablas 10-6 y 10-8): las fórmulas elásticas se reconstruyeron a partir de los valores tabulados; confirmarlas con el texto del Manual Parte 10.
- [ ] Viga destajada con λ > 2λ_p: la Ec. 9-12/9-13 (F_cr = 0,903 E k₁ (t_w/h_c)²) no está validada con un ejemplo.
- [ ] II.A-18: la placa simple con destaje superior está validada; falta contrastar el doble destaje y las conexiones desplazadas/en ángulo.

### 2.3 Funciones que faltan — B

- [ ] Compresión axial en el extremo de la viga.
- [ ] Flexión de la viga y corte del alma sin destaje.

- [ ] II.A-10, fase 2: plano en planta con el esviaje, 3D de las placas dobladas y editor en la GUI.
- [ ] Importar reacciones de vigas desde SAP2000/ETABS para crear proyectos de corte.
- [ ] Editor gráfico 2D de la ventana de corte.

### 2.4 Completado en F5

- [x] Conversión automática de unidades en la ventana de corte.
- [x] Lista de materiales y cuadro de soldaduras AWS A2.4 en el DXF.
- [x] Placa simple con destaje superior validada contra II.A-18.
- [x] Placa simple extendida con carga axial (II.A-19B): pernos, placa, bloque de corte e interacción; sin comprobar la viga ni la línea de fluencia del alma de la columna.
- [x] Refuerzo de destajes (II.A-6 C y D): placa doble y rigidizador longitudinal en el cálculo, el proyecto, la memoria, el DXF, el 3D y la GUI.
- [x] Doble ángulo desplazado con fila de pernos compartida (II.A-9): comprobación de la fila compartida para 2R; el desplazamiento no se dibuja todavía en planta.
- [x] Conexión sesgada de doble placa doblada (II.A-10), fase 1: motor, proyecto, memoria y validación LRFD/ASD; sin DXF, 3D ni GUI.
- [x] Ángulo superior de los asientos: detalle estándar L4×4×1/4, dos pernos por ala o soldadura de 3/16 in, incluido en DXF, BOM y 3D. No se le asigna carga porque el asiento toma toda la reacción.
- [x] Placa de asiento del asiento rigidizado: PL 3/8 in × W × (W + 1 in), soldadura de 5/16 in y longitud mínima 0,2 l; comprobación de aplastamiento sobre el rigidizador.
- [x] II.A-16: el reparto queda aclarado: el asiento toma toda la carga, el ángulo superior solo estabiliza y la soldadura del asiento se verifica con el método elástico de la Tabla 10-6.

## 3. Próximas fases

- [ ] **F6, momento viga–columna** (Parte 12, DG4/DG16, DG13, AISC 358 opcional): elegir los ejemplos de validación antes de empezar.
- [ ] **F7, empalmes** de viga y columna.
- [ ] **F8, validación cruzada:** manual de verificación y comparación con otro programa en un conjunto de casos.

## 4. Antes de cada release

- [ ] `ruff check .` y `python -m pytest` sin errores, también con los extras `gui`, `pdf` y `3d`.
- [ ] CI en verde en Windows, macOS y Linux.
- [ ] Versión actualizada en `src/openconex/__init__.py`.
- [ ] Prueba de humo de los paquetes portables en las tres plataformas.
- [ ] `SHA256SUMS.txt` coincide con los archivos publicados.
- [ ] Notas de la release con novedades y limitaciones.
