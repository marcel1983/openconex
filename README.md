# OpenConex

Aplicación libre (GPL-3.0) para el diseño de conexiones metálicas según AISC.
*Free (GPL-3.0) software for the design of steel connections to AISC.*

> **Estado: pre-alfa.** Todavía no calcula conexiones. Ver el [plan de desarrollo](docs/PLAN.md).

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

Ver [CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia
[GPL-3.0-or-later](LICENSE). Las memorias de cálculo, planos y modelos que generes con OpenConex son tuyos y no quedan sujetos a la GPL.

**Aviso:** OpenConex es una herramienta de apoyo. La responsabilidad del diseño corresponde al profesional que lo firma, que debe verificar los resultados.
