# 2. Inicio rápido

## Paso 1: describir la placa

Copie un ejemplo y edítelo con cualquier editor de texto. El archivo es JSON:

```json
{
  "info": {"name": "Galpón — columna C-1", "number": "P-001", "language": "es", "units": "SI_kN_m"},
  "base_plate": {
    "column": "W12X96",
    "N": "450 mm", "B": "400 mm", "tp": "32 mm",
    "fc": "28 MPa", "A2_over_A1": 1.0,
    "rod_diameter": "1-1/4 in", "rod_grade": "ASTM F1554 Gr. 55", "rods_per_side": 2,
    "f": "175 mm", "rod_spacing": "250 mm", "hef": "400 mm"
  },
  "cases": [
    {"name": "D", "type": "D", "P": "400 kN", "M": "30 kN*m"},
    {"name": "L", "type": "L", "P": "250 kN", "M": "20 kN*m"},
    {"name": "E", "type": "E", "P": "-50 kN", "V": "60 kN", "M": "120 kN*m"}
  ],
  "combinations": {"methods": ["LRFD"], "SDS": 0.8}
}
```

- Cada valor lleva su unidad (`"450 mm"`, `"3/4 in"`, `"30 kN*m"`). Sin unidad, se toma la del sistema de `info.units`.
- `P` positivo es compresión.
- `V` y `M` corresponden al eje fuerte de la columna. Para el eje débil use `V_weak` y `M_weak`.

Todos los campos están en [El archivo de proyecto](03-proyecto.md).

## Paso 2: calcular

```bash
openconex baseplate columna.ocnx --html --docx --dxf
```

En pantalla aparece una línea por verificación, con la relación demanda/capacidad de la combinación que gobierna:

```
OK     0.481  Aplastamiento en el concreto bajo la placa (LRFD-2)
OK     0.750  Espesor de placa en la interfaz de compresión (LRFD-3 +E)
OK     0.463  Espesor de placa en la interfaz de tracción (LRFD-5 +E)
OK     0.559  Resistencia del acero del anclaje a tracción (LRFD-5 +E)
OK     0.714  Arrancamiento del concreto a tracción (LRFD-5 +E)
OK     0.599  Extracción del anclaje (LRFD-5 +E)
OK     0.938  Corte por fricción (LRFD-5 +E)
```

`LRFD-5 +E` es la quinta combinación LRFD generada, con el sismo E positivo; la memoria indica su cláusula de ASCE 7-22. El comando devuelve **0** si todo cumple y **1** si alguna verificación no cumple, lo que sirve en procesos automáticos.

## Paso 3: revisar los resultados

Junto al proyecto quedan `columna.html` y `columna.docx` (la memoria, con cada ecuación y su cláusula) y `columna.dxf` (planta, elevación y lista de materiales). Ver [Resultados](06-resultados.md).

## ¿Algo no cumple?

Cambie el dato que corresponda y vuelva a calcular. Para el corte por fricción, por ejemplo, agregue una llave de corte (ver [`shear_lug`](03-proyecto.md#llave-de-corte-shear_lug)) o arandelas soldadas (`washer_thickness`), que hacen que todos los anclajes trabajen a corte.
