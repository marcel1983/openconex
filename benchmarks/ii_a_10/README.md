# Benchmark de elemento finito de II.A-10

Modelo lineal elástico, separado del cálculo normativo de OpenConex, para estudiar el reparto de carga entre las placas A y B de la conexión sesgada de doble placa doblada (AISC II.A-10).

No sustituye las comprobaciones de `openconex.connections.shear.bent_plate`. Sirve para responder una pregunta concreta: **¿la analogía de viga simple que reparte 30/50 kip entre las placas A y B es razonable?**

## Modelo

- Viga W16×77: alma de 0.455 in, tramo de 5 in de largo y 12 in de alto.
- Placas dobladas de 3/8 in, altura 8 1/2 in:
  - placa A: ancho 7 1/4 in, ala soldada 4 7/16 in;
  - placa B: ancho 6 3/4 in, ala soldada 3 9/16 in.
- Esviaje 6:12 (26.565°).
- Tres filas de pernos a 3 in; la fila A está a 3.75 in y la fila B a 2.25 in de la línea de carga, con 6.00 in entre filas (Manual II.A-10). La carga queda entre las dos filas.
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
| Gruesa | 0.30 / 0.08 | 14.62 | 65.38 | 18.3 / 81.7 % |
| Fina | 0.18 / 0.05 | **13.50** | **66.50** | **16.9 / 83.1 %** |
| Analogía de viga simple | — | 30.00 | 50.00 | 37.5 / 62.5 % |

Con las filas en su posición real, el modelo de pernos rígidos **no reproduce** la analogía de viga simple: la placa B toma unos 66.5 kip, un 33 % más que los 50 kip del método normativo.

Tensiones nominales y representativas de la malla fina:

| Magnitud | Placa A | Placa B |
|---|---:|---:|
| Corte nominal `V/(h t)` | 4.24 ksi | 20.86 ksi |
| von Mises en el centro del ala soldada | 7.83 ksi | 11.85 ksi |
| `0.6 F_y` de la placa A36 | 21.6 ksi | 21.6 ksi |

La placa B queda prácticamente en el límite de fluencia por corte (20.86 frente a 21.6 ksi).

## Interpretación

- El reparto 30/50 kip de II.A-10 **no queda confirmado** por este modelo. Con las filas en 2.25/3.75 in, la placa B toma 66.5 kip en el modelo de pernos rígidos, frente a 50 kip.
- La placa B es claramente la crítica: 20.86 ksi de corte nominal frente a 21.6 ksi de fluencia.
- La soldadura media de la placa B recibe `66.5/8.5 = 7.82 kip/in`, por encima de la demanda normativa (`50/8.5 = 5.88 kip/in`).
- Una variante exploratoria con alma del apoyo y vástagos de perno dio B entre 53 y 63 kip, pero no convergió con la malla; el modelo de pernos rígidos es el límite superior de la rigidez de los apoyos.
- El resultado es una **señal de alarma**, no una demostración de fallo: el modelo no tiene contacto, pretensión, holgura de agujeros ni filete de soldadura.

## Limitaciones y siguiente paso

- Los pernos son parches rígidos; no hay contacto ni pretensión. Esto maximiza la diferencia de rigidez entre las placas y probablemente exagera la carga de B.
- La soldadura es una unión solidaria; para el pie de soldadura hace falta un submodelo con filete, radio de doblez y malla de convergencia.
- La doblez es una esquina aguda; el modelo no evalúa la concentración real del radio de 9/16 in.
- El alma del apoyo no se modela en el caso base. La variante con alma y vástagos muestra una sensibilidad grande; hace falta un modelo con contacto, pretensión y malla convergida antes de cambiar el reparto normativo.
- Mientras no exista ese modelo, el cálculo de OpenConex mantiene el reparto 30/50 de II.A-10, pero conviene revisar la placa B con un reparto más conservador o aumentar su margen.

Para una fase posterior: modelo con alma del apoyo, vástagos, contacto y pretensión; submodelo del pie de soldadura y de la doblez; comparación con el método de punto caliente o con las fuerzas por línea de soldadura.

## Archivos

- `benchmark.py`: geometría, malla, archivo de CalculiX, ejecución y extracción de reacciones.
- `results/coarse.json`, `results/fine.json`: resultados de las dos mallas.
- `out/`: archivos generados, no versionados.
