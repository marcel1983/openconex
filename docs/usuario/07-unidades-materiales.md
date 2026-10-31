# 7. Unidades y materiales

## Escribir cantidades

Cada valor del proyecto puede llevar su propia unidad, sin importar el sistema del proyecto:

| Escrito | Interpretado |
|---|---|
| `"25 mm"`, `"2.5 cm"`, `"0.025 m"` | 25 mm |
| `"3/4 in"`, `"3/4\""` | 19,05 mm |
| `"1-1/2 in"` | 38,1 mm |
| `"120 kN*m"`, `"12.2 tf*m"`, `"1062 kip*in"` | momento |
| `"28 MPa"`, `"280 kgf/cm**2"`, `"4 ksi"` | esfuerzo |

Un número sin unidad (`450`) se interpreta en la unidad del sistema de `info.units` para esa magnitud.

## Sistemas de unidades

| Sistema | Longitud | Espesor | Fuerza | Momento | Esfuerzo |
|---|---|---|---|---|---|
| `SI_kN_m` | m | mm | kN | kN·m | MPa |
| `SI_N_mm` | mm | mm | N | N·mm | MPa |
| `MKS` | m | mm | tf | tf·m | kgf/cm² |
| `US` | in | in | kip | kip·ft | ksi |

También puede elegirse la unidad de cada magnitud por separado:

```json
"units": {"length": "mm", "thickness": "mm", "force": "kN", "moment": "kN*m", "stress": "MPa",
          "area": "mm**2", "force_per_length": "kN/m", "section_modulus": "mm**3",
          "moment_of_inertia": "mm**4"}
```

`openconex units` lista las unidades disponibles para cada magnitud.

## Materiales disponibles

**Acero estructural** (`column_grade`, `plate_grade`, `grade` de secciones genéricas y llave de corte):

| Nombre | Fy | Fu |
|---|---|---|
| `ASTM A36` | 36 ksi | 58 ksi |
| `ASTM A53 Gr. B` | 35 ksi | 60 ksi |
| `ASTM A500 Gr. B (rectangular)` | 46 ksi | 58 ksi |
| `ASTM A500 Gr. B (round)` | 42 ksi | 58 ksi |
| `ASTM A500 Gr. C (rectangular)` | 50 ksi | 62 ksi |
| `ASTM A500 Gr. C (round)` | 46 ksi | 62 ksi |
| `ASTM A501 Gr. A` | 36 ksi | 58 ksi |
| `ASTM A501 Gr. B` | 50 ksi | 70 ksi |
| `ASTM A529 Gr. 50` | 50 ksi | 65 ksi |
| `ASTM A529 Gr. 55` | 55 ksi | 70 ksi |
| `ASTM A572 Gr. 42` | 42 ksi | 60 ksi |
| `ASTM A572 Gr. 50` | 50 ksi | 65 ksi |
| `ASTM A572 Gr. 55` | 55 ksi | 70 ksi |
| `ASTM A572 Gr. 60` | 60 ksi | 75 ksi |
| `ASTM A572 Gr. 65` | 65 ksi | 80 ksi |
| `ASTM A588` | 50 ksi | 70 ksi |
| `ASTM A709 Gr. 36` | 36 ksi | 58 ksi |
| `ASTM A709 Gr. 50` | 50 ksi | 65 ksi |
| `ASTM A709 Gr. 50W` | 50 ksi | 70 ksi |
| `ASTM A847` | 50 ksi | 70 ksi |
| `ASTM A913 Gr. 50` | 50 ksi | 65 ksi |
| `ASTM A913 Gr. 60` | 60 ksi | 75 ksi |
| `ASTM A913 Gr. 65` | 65 ksi | 80 ksi |
| `ASTM A913 Gr. 70` | 70 ksi | 90 ksi |
| `ASTM A992` | 50 ksi | 65 ksi |
| `ASTM A1043 Gr. 36` | 36 ksi | 58 ksi |
| `ASTM A1043 Gr. 50` | 50 ksi | 65 ksi |
| `ASTM A1065 Gr. 50` | 50 ksi | 60 ksi |
| `ASTM A1065 Gr. 50W` | 50 ksi | 70 ksi |
| `ASTM A1085` | 50 ksi | 65 ksi |

**Barras de anclaje y pernos** (`rod_grade`):

| Nombre | Uso |
|---|---|
| `ASTM F1554 Gr. 36` | barras de anclaje |
| `ASTM F1554 Gr. 55` | barras de anclaje |
| `ASTM F1554 Gr. 105` | barras de anclaje |
| `ASTM F3125 Gr. A325` | pernos estructurales |
| `ASTM F3125 Gr. A490` | pernos estructurales |

**Electrodos:** `E70XX` y `E80XX`. Las soldaduras de la placa base usan E70XX.

**Perfiles:** la base de datos AISC Shapes v16.0 (2 299 perfiles) viene incluida. Sus datos son de AISC y no están bajo la GPL (ver `NOTICE.md`).
