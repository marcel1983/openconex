# Benchmark de elemento finito de II.A-10

Modelo lineal elástico, separado del cálculo normativo de OpenConex, para estudiar el reparto de carga entre las placas A y B de la conexión sesgada de doble placa doblada (AISC II.A-10).

No sustituye las comprobaciones de `openconex.connections.shear.bent_plate`. Sirve para responder una pregunta concreta: **¿la analogía de viga simple que reparte 30/50 kip entre las placas A y B es razonable?**

## Modelo

- Viga W16×77: alma de 0.455 in, tramo de 5 in de largo y 12 in de alto.
- Placas dobladas de 3/8 in, altura 8 1/2 in:
  - placa A: ancho 7 1/4 in, ala soldada 4 7/16 in;
  - placa B: ancho 6 3/4 in, ala soldada 3 9/16 in.
- Esviaje 6:12 (26.565°).
- Tres filas de pernos a 3 in, separadas 6.00 in entre las dos placas (el brazo de palanca de II.A-10).
- Pernos representados por parches circulares fijos de radio 3/4 in en la cara de la placa contra el apoyo. No se modelan el alma del apoyo ni el vástago del perno: el grupo de pernos es rígido.
- Carga: 80 kip repartidos como flujo cortante uniforme a lo largo de la interfaz de soldadura de cada placa.
- Material: acero elástico lineal, `E = 29 000 ksi`, `ν = 0.3`.
- La soldadura se modela como una interfaz solidaria; no se modela el filete.

## Ejecución

Dependencias opcionales:

```bash
pip install gmsh meshio numpy
```

CalculiX CrunchiX (`ccx`) debe estar instalado aparte. En Windows se puede usar la distribución oficial de CalculiX.

```bash
python benchmarks/ii_a_10/benchmark.py --ccx /ruta/a/ccx --hmax 0.18 --hmin 0.05
```

Sin CalculiX, el script escribe la malla y el archivo de entrada:

```bash
python benchmarks/ii_a_10/benchmark.py --no-run
```

Los archivos generados van a `benchmarks/ii_a_10/out/` por defecto. El resultado principal es `results.json`.

## Resultados

Malla gruesa y fina, reacción vertical en cada grupo de pernos:

| Malla | `hmax` / `hmin` [in] | Placa A [kip] | Placa B [kip] | Reparto A/B |
|---|---|---|---|---|
| Gruesa | 0.30 / 0.08 | 30.92 | 49.08 | 38.6 / 61.4 % |
| Fina | 0.18 / 0.05 | **30.25** | **49.75** | **37.8 / 62.2 %** |
| Analogía de viga simple | — | 30.00 | 50.00 | 37.5 / 62.5 % |

La malla fina reproduce el reparto de la analogía de viga simple dentro de **0.3 kip** (0.8 % en A, 0.5 % en B). El reparto es estable al refinar.

Tensiones nominales y representativas de la malla fina:

| Magnitud | Placa A | Placa B |
|---|---:|---:|
| Corte nominal `V/(h t)` | 9.49 ksi | 15.61 ksi |
| von Mises en el centro del ala soldada | 9.05 ksi | 18.67 ksi |
| `0.6 F_y` de la placa A36 | 21.6 ksi | 21.6 ksi |

Las tensiones nominales y las del ala soldada quedan por debajo de la fluencia. Los máximos locales aparecen en los bordes de los parches de pernos y en las esquinas agudas del modelo; son singularidades de borde y no se usan como criterio de diseño.

## Interpretación

- El reparto 30/50 kip de II.A-10 queda respaldado para esta geometría y esta posición de pernos.
- La placa B es la crítica, con una tensión nominal de corte de 15.6 ksi frente a 21.6 ksi de fluencia.
- La soldadura media de la placa B recibe `49.75/8.5 = 5.85 kip/in`, prácticamente igual a la demanda de la comprobación normativa (`50/8.5 = 5.88 kip/in`).
- El modelo no incluye contacto, pretensión, holgura de agujeros ni filete de soldadura. No sirve para calcular la tensión local en el pie de soldadura ni para sustituir las comprobaciones AISC.

## Limitaciones y siguiente paso

- Los pernos son parches rígidos; no hay contacto ni pretensión. Un modelo con vástagos y contacto dará una distribución más realista, pero también más sensible a la malla.
- La soldadura es una unión solidaria; para el pie de soldadura hace falta un submodelo con filete, radio de doblez y malla de convergencia.
- La doblez es una esquina aguda; el modelo no evalúa la concentración real del radio de 9/16 in.
- El alma del apoyo no se modela. La sensibilidad a modelar el alma y los vástagos ya se comprobó: el reparto puede moverse varios puntos porcentuales, por lo que la conclusión 30/50 debe tomarse como una validación de la hipótesis global, no como un valor exacto.

Para una fase posterior: modelo con alma del apoyo, vástagos, contacto y pretensión; submodelo del pie de soldadura y de la doblez; comparación con el método de punto caliente o con las fuerzas por línea de soldadura.

## Archivos

- `benchmark.py`: geometría, malla, archivo de CalculiX, ejecución y extracción de reacciones.
- `results/coarse.json`, `results/fine.json`: resultados de las dos mallas.
- `out/`: archivos generados, no versionados.
