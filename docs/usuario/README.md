# Manual de usuario

OpenConex calcula conexiones metálicas según AISC 360-22, la Guía de Diseño 1 de AISC (3ª ed.) y ACI 318-19. Hoy calcula **placas base de columna** desde la línea de comandos y desde una interfaz gráfica inicial. Genera memoria de cálculo (HTML, Word y PDF), planos DXF y modelo 3D (STEP y STL), y también importa los apoyos de un modelo de SAP2000 o ETABS.

> **Estado: alfa.** La interfaz gráfica cubre el flujo individual de placa base; los demás tipos de conexión están en desarrollo ([plan](../PLAN.md)). La responsabilidad del diseño es del profesional que lo firma, que debe verificar los resultados.

## Contenido

1. [Instalación](01-instalacion.md)
2. [Inicio rápido](02-inicio-rapido.md): calcular una placa base en tres pasos.
3. [El archivo de proyecto `.ocnx`](03-proyecto.md): todos los datos de entrada.
4. [Comandos](04-comandos.md): referencia de `openconex`.
5. [Importar desde SAP2000 / ETABS](05-importar-sap2000.md): de las reacciones del modelo a un proyecto por apoyo o por tipo de columna.
6. [Resultados](06-resultados.md): memoria, planos y modelo 3D.
7. [Unidades y materiales](07-unidades-materiales.md)
8. [Alcance y limitaciones](08-limitaciones.md)
9. [Interfaz gráfica](09-interfaz.md): secciones, materiales, unidades, cálculo y exportación desde el escritorio.

## Flujo de trabajo

```
Modelo SAP2000 ──(exportar tablas a Excel)──► modelo.xlsx
                                                   │
                       openconex supports modelo.xlsx --create ... --template plantilla.ocnx
                                                   ▼
                                    proyectos/*.ocnx  (uno por apoyo o por tipo)
                                                   │
                       openconex baseplate proyecto.ocnx --html --docx --dxf
                                                   ▼
                            memoria + planos + modelo 3D + resumen en pantalla
```

El proyecto también puede escribirse a mano, partiendo de los ejemplos de la carpeta `examples/`.
