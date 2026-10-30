# OpenConex

Aplicación libre (GPL-3.0) para el diseño de conexiones metálicas según AISC.
*Free (GPL-3.0) software for the design of steel connections to AISC.*

> **Estado: alfa.** Calcula placas base (AISC DG1 3ª ed., AISC 360-22, ACI 318-19) y genera memoria, planos DXF y modelo 3D desde la línea de comandos. La interfaz gráfica está en desarrollo. Ver el [plan de desarrollo](docs/PLAN.md).

## Alcance previsto
- **Conexiones:** placas base, viga–columna y viga–viga (corte y momento), empalmes de viga y columna.
- **Normas:** AISC 360-22, AISC Design Guide 1 (3ª ed.), ACI 318-19 Cap. 17, ASCE 7-22; opción sísmica AISC 341-22 / 358-22.
- **Cálculo individual o en lote**, con importación desde ETABS, SAP2000, Excel y CSV.
- **Salidas:** memoria de cálculo en español e inglés (PDF/DOCX), planos DXF y modelo 3D.
- **Unidades** SI, MKS e imperiales, configurables por magnitud.
- **Multiplataforma:** Windows, macOS y Linux.

## Desarrollo
```bash
pip install -e ".[dev]"
```
```bash
python -m pytest
```
```bash
openconex convert "3/4 in" thickness --to mm
```

### Calcular una placa base
```bash
pip install -e ".[pdf,3d]"
```
```bash
openconex baseplate examples/base_plate_dg1_4_7_11.ocnx --html --docx --pdf --dxf --step
```
El comando calcula todas las combinaciones de ASCE 7-22, imprime el resumen y devuelve 1 si alguna verificación no cumple. `--lang en` y `--units SI_kN_m` cambian el idioma y las unidades de las salidas.

Ver [CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia
[GPL-3.0-or-later](LICENSE). Las memorias de cálculo, planos y modelos que generes con OpenConex son tuyos y no quedan sujetos a la GPL.

**Aviso:** OpenConex es una herramienta de apoyo. La responsabilidad del diseño corresponde al profesional que lo firma, que debe verificar los resultados.
