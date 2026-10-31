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

### Combinaciones personalizadas
Cada proyecto puede definir su propio conjunto de combinaciones en `combinations.custom`:

```json
"combinations": {
  "include_code": false,
  "custom": [
    {"name": "C-1", "method": "LRFD", "factors": {"D": 1.2, "L": 1.6}, "source": "Criterio del proyecto"},
    {"name": "C-2", "method": "ASD", "factors": {"D": 1.0, "W": -0.6}, "source": "Criterio del proyecto"}
  ]
}
```

- `include_code` (por defecto `true`) genera además las combinaciones ASCE 7-22 de `methods`; con `false` se usan solo las personalizadas.
- `factors` aplica un factor a cada caso de carga por su `name`; un valor negativo invierte el signo. Todos los casos referenciados deben existir.
- `method` (`LRFD` o `ASD`, por defecto `LRFD`) selecciona las verificaciones aplicables; `seismic`, `overstrength`, `allowable_increase` y `source` son opcionales.
- Los nombres de las combinaciones y de los casos deben ser únicos.

Ver `examples/base_plate_custom_combinations.ocnx`.

### Secciones de columna genéricas
Además de las etiquetas del catálogo AISC (por ejemplo `"column": "W12X96"`), la columna puede definirse por dimensiones.

**Perfil W (I genérico):**

```json
"column": {
  "type": "W",
  "name": "W genérica 20×12",
  "d": "20 in",
  "bf": "12 in",
  "tf": "1 in",
  "tw": "0.5 in",
  "k_des": "1.5 in",
  "grade": "ASTM A992"
}
```

**HSS rectangular o cuadrada:**

```json
"column": {
  "type": "HSS",
  "shape": "rectangular",
  "d": "12 in",
  "bf": "8 in",
  "t": "0.5 in",
  "grade": "ASTM A500 Gr. C (rectangular)"
}
```

Para una sección cuadrada use `"shape": "square"` y puede omitirse `bf` (se toma igual a `d`). Para una sección circular:

```json
"column": {
  "type": "HSS",
  "shape": "round",
  "d": "12.75 in",
  "t": "0.5 in",
  "grade": "ASTM A500 Gr. C (round)"
}
```

En HSS circular, `d` es el diámetro exterior y no se admite `bf`. El área desprecia los radios de esquina. `column_grade` solo se usa con etiquetas del catálogo; las secciones genéricas llevan su propio `grade`. En compresión, las líneas de fluencia de la placa siguen DG1 §4.3.3: 0.95 de las dimensiones exteriores para HSS rectangular/cuadrada y 0.8 del diámetro para HSS circular, sin λn'.

Ver `examples/base_plate_generic_w.ocnx`, `examples/base_plate_hss_square.ocnx` y `examples/base_plate_hss_round.ocnx`.

Ver [CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia
[GPL-3.0-or-later](LICENSE). Las memorias de cálculo, planos y modelos que generes con OpenConex son tuyos y no quedan sujetos a la GPL.

**Aviso:** OpenConex es una herramienta de apoyo. La responsabilidad del diseño corresponde al profesional que lo firma, que debe verificar los resultados.
