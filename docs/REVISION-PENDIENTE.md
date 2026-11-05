# Revisión pendiente

Estado al 2026-11-04, sobre `main` (`19e68d6`, versión 0.4.2). Cada tarea indica qué hay que hacer y los puntos a verificar antes de cerrarla. Prioridad: **A** (corregir pronto), **B** (siguiente iteración), **C** (cuando se pueda).

## 0. Completado en 0.4.2

- [x] Identidad visual AISC: banner, iconos, splash y assets de marca.
- [x] Icono en los ejecutables de Windows y macOS.
- [x] Comprobación `--check-assets` en la GUI y en el smoke test portable.
- [x] Conversión automática de unidades en la ventana de corte.
- [x] Lista de materiales y cuadro de soldaduras AWS A2.4 en el DXF de corte.
- [x] Ejemplo y validación de placa simple con destaje superior contra II.A-18.
- [x] Release 0.4.2 publicada y verificada en las tres plataformas.

## 1. Empaquetado y releases (PR #101 a #105)

### 1.1 Zip de Linux duplicado — A

**Confirmado en 0.4.2.** El zip de Linux pesa 1.071 MiB y contiene 9.377 entradas. Al descomprimirlo ocupa 3.484 MiB. `libQt6WebEngineCore.so.6` aparece cuatro veces con 194,47 MiB cada una: en `OpenConex/_internal/PySide6/Qt/lib`, en `OpenConex/_internal`, y las mismas dos rutas en `openconex-cli`.

`packaging/build_portable.py` arma el zip con `zipfile` recorriendo `rglob`; `ZipFile.write` sigue los symlinks de las bibliotecas Qt/OCP y guarda el contenido completo en cada ruta.

Puntos a verificar:
- [ ] Guardar los symlinks como tales (por ejemplo, `zip -y` en Linux) en lugar de duplicar el contenido.
- [ ] Comparar el tamaño: debería quedar cerca de 550 MiB.
- [ ] Descomprimir el zip nuevo en un Linux limpio y comprobar que la GUI y la CLI arrancan.
- [ ] Revisar que los permisos de ejecución se conservan.

### 1.2 Qt y OpenCASCADE duplicados entre GUI y CLI — B

La GUI y la CLI se compilan como dos `--onedir` independientes, cada uno con su copia de Qt y OCP. Aunque se corrijan los symlinks, sigue habiendo dos copias completas.

Puntos a verificar:
- [ ] Medir cuánto ocupa cada carpeta dentro del zip.
- [ ] Probar un `.spec` con `MERGE`, o un solo ejecutable con modo CLI, y comparar el tamaño.
- [ ] Repetir la prueba de humo de `build_portable.py` (versión, assets, conversión, placa base y conexión de corte) en las tres plataformas.
- [ ] En Windows, confirmar que no vuelve el choque de nombres entre `OpenConex.exe` y `openconex.exe` que corrigió el #103.

### 1.3 Licencias de las bibliotecas incluidas — A

El paquete portable solo trae `LICENSE` de OpenConex y `NOTICE-AISC.md`. No hay una carpeta `licenses/` con los textos de PySide6/Qt ni de OpenCASCADE, que se redistribuyen bajo LGPL. Los `dist-info` de algunos paquetes Python incluyen sus licencias, pero no cubren esas bibliotecas nativas.

Puntos a verificar:
- [ ] Listar las bibliotecas que PyInstaller incluye en cada paquete.
- [ ] Copiar sus licencias a una carpeta `licenses/` dentro del zip.
- [ ] Comprobar que `tools/check_licenses.py` cubre también las dependencias del paquete portable (PyInstaller, PySide6, OCP).
- [ ] Confirmar que la distribución `--onedir` permite reemplazar las bibliotecas LGPL (relinking) y documentarlo.

### 1.4 Documentación del empaquetado — B

Puntos a verificar:
- [ ] `docs/usuario/01-instalacion.md`: cambiar los nombres con versión fija (`OpenConex-0.4.2-…`) por `OpenConex-X.Y.Z-…` o por el nombre del release actual.
- [ ] `packaging/README-portable.txt` y el manual: indicar las bibliotecas del sistema que necesita Linux (`libxcb-cursor0`, `libegl1`, `libnss3`…).
- [ ] Documentar en `docs/tecnico/` cómo se hace una release (etiqueta `v*`, workflow, prueba de humo, checksums).
- [ ] Registrar en `docs/PLAN.md` el avance de la F8 (instaladores portables).

### 1.5 Workflow de release — C

Puntos a verificar:
- [ ] Dar `contents: write` solo al trabajo `publish`; los trabajos de compilación pueden quedar en `read`.
- [ ] Fijar las acciones (`actions/checkout`, `setup-python`, `upload-artifact`, `download-artifact`) por commit.
- [ ] Probar `workflow_dispatch` sin etiqueta y con `publish` activado: debe fallar con un mensaje claro y no publicar nada.
- [ ] Agregar la línea de copyright a los archivos de `packaging/`, como en el resto del repositorio.

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
- [ ] Refuerzo de destajes: placa doble y rigidizadores longitudinales (II.A-6 C y D).
- [ ] Placa simple extendida con carga axial (II.A-19B).
- [ ] Reparto de la carga por excentricidad del asiento (II.A-16).
- [ ] Ángulo superior de los asientos y placa de asiento del asiento rigidizado.
- [ ] Doble destaje viga-viga con placa simple y conexiones desplazadas o en ángulo (II.A-9, II.A-10).
- [ ] Importar reacciones de vigas desde SAP2000/ETABS para crear proyectos de corte.
- [ ] Editor gráfico 2D de la ventana de corte.

### 2.4 Completado en F5

- [x] Conversión automática de unidades en la ventana de corte.
- [x] Lista de materiales y cuadro de soldaduras AWS A2.4 en el DXF.
- [x] Placa simple con destaje superior validada contra II.A-18.

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
