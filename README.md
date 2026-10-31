# OpenConex

Aplicación libre (GPL-3.0) para el diseño de conexiones metálicas según AISC.
*Free (GPL-3.0) software for the design of steel connections to AISC.*

> **Estado: alfa.** Calcula placas base (AISC DG1 3ª ed., AISC 360-22, ACI 318-19) y genera memoria, planos DXF y modelo 3D desde la línea de comandos o desde una interfaz gráfica inicial. Ver el [plan de desarrollo](docs/PLAN.md).

## Alcance previsto
- **Conexiones:** placas base, viga–columna y viga–viga (corte y momento), empalmes de viga y columna.
- **Normas:** AISC 360-22, AISC Design Guide 1 (3ª ed.), ACI 318-19 Cap. 17, ASCE 7-22; opción sísmica AISC 341-22 / 358-22.
- **Cálculo individual o en lote**, con importación desde ETABS, SAP2000, Excel y CSV.
- **Salidas:** memoria de cálculo en español e inglés (PDF/DOCX), planos DXF y modelo 3D.
- **Unidades** SI, MKS e imperiales, configurables por magnitud.
- **Multiplataforma:** Windows, macOS y Linux.

## Documentación

- **[Manual de usuario](docs/usuario/README.md):** instalación, inicio rápido, archivo de proyecto, comandos, importación desde SAP2000, resultados, unidades y limitaciones.
- **[Documentación técnica](docs/tecnico/README.md):** arquitectura, convenciones, algoritmo de la placa base, catálogo de verificaciones, combinaciones, importación y validación.
- **[Plan de desarrollo](docs/PLAN.md)**

## Uso en 30 segundos

```bash
pip install -e .
```
```bash
openconex baseplate examples/base_plate_dg1_4_7_11.ocnx --html --docx --dxf
```

Calcula una placa base del Ejemplo 4.7-11 de la Guía de Diseño 1 y escribe la memoria y el plano. La interfaz gráfica se instala con `pip install -e ".[gui]"` y se abre con `openconex-gui`. Para importar un modelo de SAP2000 o ETABS, ver [Importar desde SAP2000 / ETABS](docs/usuario/05-importar-sap2000.md).

## Desarrollo

```bash
pip install -e ".[dev]"
```
```bash
python -m pytest
```

Ver [CONTRIBUTING.md](CONTRIBUTING.md). La documentación se actualiza en el mismo pull request que cada cambio.

## Licencia
[GPL-3.0-or-later](LICENSE). Las memorias de cálculo, planos y modelos que generes con OpenConex son tuyos y no quedan sujetos a la GPL.

**Aviso:** OpenConex es una herramienta de apoyo. La responsabilidad del diseño corresponde al profesional que lo firma, que debe verificar los resultados.
