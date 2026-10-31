# 5. Combinaciones de carga

Código: `core/loads.py` (`asce7_combinations`, `combine`) y `io/project.py` (`load_combinations`).

## Generación ASCE 7-22

A partir del tipo de cada caso (`D`, `L`, `Lr`, `S`, `R`, `W`, `WT`, `E`) se generan las combinaciones básicas:

- **LRFD:** ASCE 7-22 §2.3.1, más §2.3.6 para sismo.
- **ASD:** §2.4.1, más §2.4.5 para sismo.

Reglas:
- Todos los casos `D` llevan el mismo factor de D, y todos los `L` el de L.
- Se toma una carga de techo a la vez (Lr, S o R).
- Viento y sismo se toman con los dos signos. Tornado (`WT`) puede reemplazar a W donde la norma dice "W o W_T".
- **Nieve con factores de resistencia de ASCE 7-22:** en LRFD, 1,0S en la combinación 3 y 0,3S en las de viento y sismo; en ASD, 0,7S, 0,75·0,7S y 0,1S donde corresponde.
- `live_factor` es el factor de L en las combinaciones LRFD 3, 4 y 6 y en las sísmicas.
- Se eliminan las combinaciones repetidas.
- El nombre es `LRFD-n` o `ASD-n` más etiquetas (`+SX`, `-SX`, `Ω0`); `source` guarda la cláusula, por ejemplo `ASCE 7-22 §2.3.6 (6)`.

## Sismo

Requiere `SDS` cuando hay casos `E` y `include_code` es verdadero; si falta, la validación del proyecto da error (antes los casos `E` se omitían sin aviso). `SDS = 0` genera las combinaciones sin E_v. Para cada sismo y cada signo:
- **LRFD:** (1,2 + 0,2 S_DS) D + ρ E + L + 0,15 S y (0,9 − 0,2 S_DS) D + ρ E.
- **ASD:** los equivalentes de §2.4.5.

Con `omega0` se repiten con Ω0 en lugar de ρ. Esas combinaciones se marcan `overstrength`, y en ASD llevan `allowable_increase = 1,2`.

## Combinaciones propias

`custom` agrega combinaciones con factores por nombre de caso. Con `include_code = false` son las únicas. Se valida que los nombres sean únicos, que cada caso citado exista y que haya al menos un factor distinto de cero.

## Combinar

`combine(combinación, fuerzas)` suma factor × fuerzas de cada caso, componente a componente (P, V2, V3, T, M2, M3), conservando los signos.
