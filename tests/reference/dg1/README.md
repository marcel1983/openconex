# Casos de referencia — AISC Design Guide 1, 3ª ed. (2024)

Cada archivo `*.toml` resume **solo los datos numéricos** (entradas y resultados) de un ejemplo de diseño de *AISC Design Guide 1: Base Connection Design for Steel Structures*, 3.ª edición (2024). No se reproduce el texto, las figuras ni el procedimiento del libro: para eso hay que consultar la publicación de AISC, citada en el campo `source` de cada caso.

Estos casos son el criterio de aceptación del módulo de placas base (fase F2). Mientras una funcionalidad no esté implementada, su caso queda con `status = "pending"` y las pruebas solo validan el formato del archivo.

## Formato

```toml
id = "4.7-1"                      # número del ejemplo en la DG1
title = "…"                       # descripción breve (redacción propia)
source = "AISC DG1 3rd ed. (2024), Example 4.7-1, pp. 64–67"
feature = "base_plate.axial_compression"
status = "pending"                # pending | implemented
tolerance = 0.01                  # tolerancia relativa por defecto

[given]                           # datos de entrada
[expected]                        # resultados comunes a LRFD y ASD
[expected.lrfd]                   # resultados LRFD
[expected.asd]                    # resultados ASD
[tolerances]                      # tolerancias por clave, si hacen falta
```

- **Magnitudes con unidad** como texto que entiende `pint`: `"700 kip"`, `"12.7 in"`, `"3 ksi"`, `"940 kip*in"`, `"422 in**2"`, `"53.0 kip/in"`.
- **Números sin unidad** para valores adimensionales (`X`, `lambda`, factores ψ, relaciones).
- **Valores tal como los publica la DG1**, redondeados a tres cifras significativas. La tolerancia por defecto (1 %) cubre ese redondeo. Los valores que salen de restar números parecidos (por ejemplo, una longitud de apoyo `Y` pequeña) llevan su propia tolerancia en `[tolerances]`.
- **Cargas:** `Pu`/`Pa` positivas en compresión y negativas en tracción (levantamiento); `Mu`/`Ma` en el eje fuerte salvo que se indique `Mux`/`Muy`.

## Glosario de claves

| Clave | Significado |
|---|---|
| `column` | Perfil de la columna (catálogo AISC) |
| `d`, `bf`, `tf`, `tw` | Dimensiones del perfil usadas por el ejemplo |
| `fc` | Resistencia especificada del concreto f'c |
| `plate_grade`, `rod_grade`, `column_grade` | Materiales |
| `N`, `B`, `tp` | Placa base: largo (dirección del momento), ancho y espesor adoptados |
| `A2_over_A1` | Relación de áreas para el aumento por confinamiento (√(A2/A1) ≤ 2) |
| `pedestal_N`, `pedestal_B` | Dimensiones del pedestal |
| `f` | Distancia del eje de la columna a la línea de anclajes en tracción |
| `rod_diameter`, `rods`, `hef` | Barras de anclaje: diámetro, cantidad, empotramiento efectivo |
| `A1_req` | Área de placa requerida |
| `phiPp`, `Pp_over_Omega` | Resistencia de aplastamiento disponible (LRFD / ASD) |
| `fp_max`, `q_max` | Esfuerzo y fuerza por unidad de longitud máximos de aplastamiento |
| `m`, `n`, `lambda_n_prime`, `l` | Voladizos críticos de la placa |
| `X`, `lambda` | Parámetros del método de la DG1 para compresión |
| `e`, `e_crit` | Excentricidad y excentricidad crítica |
| `Y` | Longitud de apoyo |
| `T`, `r_rod` | Tracción total en anclajes y por barra |
| `tp_req`, `tp_req_compression`, `tp_req_tension` | Espesor requerido (que gobierna, por interfaz de compresión y de tracción) |

Las claves propias de un solo ejemplo se explican con un comentario en el archivo.
