OpenConex portable
==================

Este paquete no requiere Python instalado.

Windows
-------
Ejecute OpenConex\OpenConex.exe para abrir la interfaz.
Ejecute openconex-cli\openconex.exe para la línea de comandos.

macOS
-----
Abra OpenConex.app para la interfaz.
El ejecutable de línea de comandos está en openconex-cli/openconex.

Linux
-----
Ejecute OpenConex/OpenConex para la interfaz.
Ejecute openconex-cli/openconex para la línea de comandos.

Si la GUI no arranca en una instalación mínima, instale las bibliotecas de
sistema de Qt: libegl1 libgl1 libxkbcommon0 libnss3 libxcb-cursor0
libxcomposite1 libxdamage1 libxrandr2 libxtst6 libxkbfile1 libgbm1
libasound2.

La primera vez, macOS puede pedir confirmación porque el binario no está
firmado. En Windows, SmartScreen puede mostrar una advertencia.

El paquete incluye las licencias de terceros en la carpeta licenses/.

El ZIP de Linux contiene enlaces simbólicos para no duplicar las bibliotecas
de Qt y OpenCASCADE. Extráigalo con unzip, tar o el gestor de archivos del
escritorio, y mantenga juntas las carpetas OpenConex y openconex-cli.

Documentación: https://github.com/marcel1983/openconex
