# h3-R4: integración independiente H1/H2, sólo offline

> **Estado final acreditado — 2026-10-28: H3_R4_OFFLINE_VALIDATED.**
> Validación específica: **H3_R4_F523D_IMPLEMENTATION_VALIDATED**.
> El cuerpo histórico siguiente conserva el estado anterior
> `IMPLEMENTED_WITH_BLOCKERS`, sus intentos fallidos y sus pendientes de entonces.
> No describe el estado actual: esos bloqueos fueron resueltos en fases posteriores,
> según el cierre técnico al final de este documento. La validación es exclusivamente
> offline; no autoriza activación live, trading ni publicación Git.

Estado de entrega: **IMPLEMENTED_WITH_BLOCKERS**, no validación live ni autorización
de publicación. La persistencia física y el backend OCR completo requieren terminar
la validación en un contexto donde Python pueda acceder a sus temporales privados.

## Entrada y separación de responsabilidades

`IndependentCurrentVisualPriceExtractor` implementa la entrada ordinaria del
extractor delegando **siempre** a `PocketOptionCurrentVisualPriceExtractor`.
`IndependentPriceConfig.enabled` es `False` por defecto; configuración ausente
también significa OFF. Incluso una instancia offline habilitada conserva la
delegación legacy en `extract` y `extract_with_trace`.

La única entrada H1/H2 es `evaluate_offline(image, geometry)`, o su adaptador
`MarketAnalysisPipeline.analyze_offline_current_visual_price(...)`. Este método
devuelve `OfflinePriceEvaluation`, no `MarketAnalysis`, no ejecuta velas, señales,
captura, GUI ni outcomes. No hay binding a configuración live ni scheduler.
La observación ya disponible se suministra completa: no se recaptura ni se recorta
alrededor de una propuesta. La comparación con legacy es diagnóstica, nunca un
fallback que elija el resultado más favorable.

Las etapas son: OCR sustituible → contexto H1 → propuestas por píxeles H2 → GUIDE
externa → asociación → selección de identidad única → calidad → CVP y traza.
La selección no compara scores entre objetos. Calidad sólo puede vetar una identidad
única; no puede resolver competidores ni acreditar identidad.

## Contratos

- `ObservationGeometry`: origen del ROI en el frame y dimensiones exactas de la
  imagen recibida. No es una región semántica. `to_frame` suma el origen y `to_roi`
  lo resta; no hay clipping ni escala implícita. Todas las cajas son semiabiertas.
- H1: estados AVAILABLE, INSUFFICIENT, AMBIGUOUS e INVALID; ticks numéricos con
  grid externo, coherencia/alineación y separación de panel. `observed_grid` es
  sólo huella observada, jamás el gráfico completo. Contexto ligado al SHA-256 de
  los píxeles BGR originales y a su geometría; H2 rechaza reutilización cruzada.
- OCR: `PriceTextRecognizer` es inyectable. `WindowsPriceTextRecognizer` usa sólo
  Windows.Media.Ocr local/es-ES, conserva TextAngle mediante transformación de
  esquinas, no instala ni descarga nada. Su construcción no lanza procesos.
  La ejecución explícita usa un PNG temporal privado, PowerShell oculto, timeout,
  límites de imagen/palabras/salida y errores sanitizados. La copia temporal es de
  la imagen entregada, no una captura nueva. El puente está incluido como package data.
- H2: `LabelProposalGenerator`, `ExternalGuideObserver`, `LabelRoleAssociator`,
  `ConservativeRoleSelector` e `IndependentLabelRoleResolver`. Morfología sólo
  propone envelopes; soporte, glyphs e ingress se leen de píxeles originales.
  No reconstruye gaps, no toma soporte de UI ni de otras regiones.
- R3C-01/R3d: `observed_grid.contains(box)` exige x0>=gx, x1<=gr, y0>=gy, y1<=gb,
  independientemente de docking. x1==gr es admisible; excesos de 1/3 píxeles
  conservan propuesta y `OUTSIDE_OBSERVED_H1_FOOTPRINT`, sin identidad positiva.
- Un competidor relevante no resuelto impide selección; dos verificados producen
  ambigüedad; ninguno no autoriza declarar ausencia real.
- Calidad v1: fracción de píxeles de fill original dentro del cuerpo, umbral
  configurable 0.60. Es una métrica técnica, no probabilidad calibrada. No participa
  en identidad y no ordena candidatos. La coordenada CVP es la mediana de filas
  GUIDE aceptadas; no un precio monetario ni el tick OCR.
- No se añadieron estados públicos CVP. `NO_VISUAL_PRICE_CANDIDATE` significa aquí
  que no hay precio público elegible; la traza preserva contexto/insuficiencia/
  ausencia de propuesta/presupuesto/contradicciones y `absence_certified=false`.
  `LOW_CONFIDENCE` sólo ocurre después de identidad única; INVALID y AMBIGUOUS se
  mantienen diferenciados. Sin fallback geométrico o temporal.

## Procedencia y adaptaciones

H1 congelado agregado:
`fbebf36ea2e428e191d3a7037266ae5d607b4e00cfb1bdb300b95979141011f8`.
H2 original agregado (sólo procedencia, NO referencia de contención):
`81e3269cc6b5ff645d89bfce1b096ea470ac1e827a0b4ea85b9c95e5ad7ebeb9`.
Referencia funcional: **H2-R3D-CONTAINMENT-V2**, manifest físico
`155b6e411ce60ffc0e9b43768281e22cb9d0021470f06936ab327e69faf81755`.

Se adaptaron dicts experimentales a dataclasses tipadas, dependencias inyectadas,
configuración inmutable validada y componentes separados. No se copió el runner
experimental ni se incorporaron frame IDs, ground truth o rutas históricas al
runtime. Se añadieron binding de imagen/geometría, calidad posterior, wrapper
offline y serialización aditiva. Se conservaron los criterios geométricos H1 y H2.

## Presupuestos y persistencia

Defaults: H1 4 Mpx, 400 palabras, 80 candidatos numéricos, 12 grupos, OCR 15 s y
presupuesto cooperativo total 20 s. H2 4 Mpx, 96 colores elegibles, 256 propuestas
crudas, 64 propuestas/asociaciones y 4 s cooperativos. Las llamadas nativas
individuales no se interrumpen a mitad; los límites no son garantía hard-real-time.
Un límite excedido produce abstención, nunca selección parcial.

`OfflinePriceEvaluation.h1_seconds/h2_seconds` son diagnósticos de ejecución y no
forman parte del contenido persistido. `independent_identity` contiene versiones,
config digest, procedencia, contexto, propuestas y evidencia, sin rutas temporales
ni IDs aleatorios. `legacy_row_metrics_applicable=false`: H2 no inventa mediciones
de máscara por fila del detector legacy. Los contadores de esa máscara quedan a
cero; los grupos de candidatos sí describen la salida pública correspondiente.

La clave `independent_identity` se omite completamente cuando no existe. Una
evidencia histórica sin esa clave significa NO REGISTRADO, no identidad verificada.
El serializer legacy se comparó con su copia pre-R4: mismo payload y hash canónico
`48ce55a3b1b504d4a8c687d663102000d576aaa5e82e5525d1bbf79cd0a2de51`
para el fixture de regresión. No se cambia el recorder ni su fingerprint. No se
migran ni sobrescriben evidencias históricas. Una evaluación offline nueva necesita
un espacio de evidencia separado; no debe reutilizar una identidad histórica con
contenido distinto. Se añadieron tests de idempotencia y rechazo de sobrescritura,
pero su acreditación física quedó bloqueada por los temporales del entorno.

## Nueve regresiones R1

Se reprodujo el baseline: **9 FAILED, 108 PASSED** en los tres módulos afectados.
No se cambió el comportamiento del extractor legacy para hacerlos pasar.

| Caso original | Etapa/supuesto incorrecto y corrección del test |
|---|---|
| exact_raster… nominal-gap-22 | Plan sin pares: no acredita asociación. Exige abstención/no pares/no grupos y verifica por separado la fusión exacta tras calificación. |
| exact_raster… resized-gap-22 | Igual; conserva las dos procedencias en el grupo unitario. |
| exact_raster… resized-gap-23 | Igual; no rellena el gap para fabricar una GUIDE. |
| semantic_edge… 10-8-9 | Un píxel externo no satisface GUIDE. Se comprueba propuesta conservada/no fila calificada; se añade positivo 40-32-38 con dominio suficiente. |
| distinct_semantic_prices… | El segundo objeto previo eran puntos desconectados, no identidad. Ahora son dos marcadores asociados, uno con menor soporte, y se exige ambigüedad, dos candidatos y scores distintos. |
| valid_marker… strict_threshold | Antes se pedía LOW antes de identidad. Ahora cuerpo conectado y GUIDE calificada, con umbral .999; se exige grupo acreditado y calidad menor al umbral. |
| sparse_label… label_columns0 | Métrica histórica de soporte, no identidad dinámica. Se hace explícita la banda fija y se mantienen cuatro filas de soporte y OK. |
| line_continuity_boundary… | El .90 corresponde al dominio legacy de 20 píxeles. Banda fija explícita; se verifica .90 exacto y rechazo del caso inferior, sin prestar cuerpo a GUIDE dinámica. |
| label_support_density… | Puntos escasos prueban densidad legacy, no asociación. Banda fija explícita; se conserva el contraste 2 píxeles aceptado / 1 rechazado. |

Los nueve casos están PASSED en `focused-final.xml`. Los nuevos tests de H1/H2
acreditan por separado contención, guía externa, gaps, soporte prestado, propuestas,
competidores, ambigüedad, calidad posterior, OFF, geometría y límites.

## Validación y bloqueos

- Suite focalizada ejecutable sin temporales privados: 207 PASSED, 0 FAILED,
  0 ERRORS, 0 SKIPPED; 4 tests de proceso OCR excluidos explícitamente por el bloqueo
  ya demostrado. Incluye 54 tests nuevos H1/H2, 6 del adaptador sin IO temporal,
  pipeline OFF, golden serializer y los nueve R1.
- Intento focalizado completo anterior: 254 tests, 208 PASSED, 3 FAILED,
  43 ERRORS, 0 SKIPPED. Los fallos/errores son PermissionError en temporales
  privados de Python/pytest. La finalización de pytest también falló por ese acceso.
  Estos resultados NO se convierten en PASSED ni en defecto de seguridad del writer.
- PowerShell pudo crear/escribir/eliminar un archivo de prueba ordinario en
  LOCALAPPDATA/Temp. Repetir pytest allí no resolvió el acceso a sus directorios
  privados. Una invocación directa de las dos assertions de persistencia también
  se detuvo en la escritura del PNG temporal del recorder; no acreditó idempotencia.
- La solicitud previa de ejecución fuera del entorno restringido no llegó a
  ejecutarse: la revisión automática falló por límite de uso, no por veredicto de
  inseguridad. No se reintentó esa elevación ni se cambiaron permisos globales.
- La suite general queda pendiente por el mismo bloqueo, sin nuevos replays ni
  capturas. OCR Windows real/H1 completo sobre fotografías también pendiente.
- Ruff y Black: aprobados en los diez archivos Python nuevos. Ruff aprobado en
  los otros siete archivos modificados comprobados; el serializer conserva ocho
  E501 preexistentes (tenía diez diagnósticos, incluyendo imports). No se formateó
  código histórico ajeno al cambio. Black completo del pipeline aún señala dos
  expresiones históricas sin cambios; se formatearon sólo los rangos R4.
- Mypy focalizado: cero errores en los siete módulos productivos nuevos, con
  imports seguidos silenciosamente; no equivale a un mypy global aprobado.
  El puente PowerShell tiene cero errores de parseo. `git diff --check` aprobado.

Regresión fotográfica H2: 16 originales Session08, hashes verificados contra bundle
`53b8e198821a69f7b9f0343f33531ff83fdbf56f5b197d74ee64663899eb3091`.
Se usó H1 congelado, NO recalculado: coincidencia 16/16 en propuestas, estados,
selección y causas por candidato con la referencia corregida.

| Frames | Resultado H2 |
|---|---|
| 144, 289, 434, 1478, 2158 | Identidad verificada, misma caja |
| 579, 1251, 1705, 1931 | Insuficiencia de H1 |
| 724, 869 | Cobertura H1 insuficiente |
| 2385 | GUIDE no acreditada |
| 1019, 1020 | Insuficiencia H1; no se fuerza recuperación |
| 1021 | Verificado [745,385,814,413) |
| 1067 | Verificado [745,157,814,185), misma selección y rechazo del confusor que la referencia |

Esto es regresión histórica conocida, no holdout nuevo ni validación integral de
OCR. No permite inferir tasas de éxito reales, latencia live o rendimiento financiero.

## Inventario del cambio respecto al inicio R4

Nuevos: modelo `independent_visual_price`; servicios `independent_price_config`,
`price_text_recognizer`, `independent_scale_context_resolver`,
`independent_label_role_resolver`, `independent_current_visual_price_extractor`;
paquete infrastructure/vision con `__init__`, adaptador Windows y puente PS1;
dos módulos de tests nuevos y este documento.

Modificados: pyproject (package data, sin dependencia nueva); MarketAnalysisPipeline
(entrada offline separada); DetectionTrace (campo opcional y contadores no aplicables
en H2); serializer (clave aditiva); tests de pipeline/persistencia y tres módulos R1.

De los ocho dirty iniciales, cuatro reciben cambios R4: serializer, DetectionTrace,
test del recorder y test de búsqueda dinámica. Los otros cuatro conservan bytes
pre-R4: current_visual_price_search, extractor legacy, resolver legacy y test del
modelo de búsqueda. El baseline/diff de los ocho se preserva externamente.

No hay cambios en SQ-03, SQ-04C/harness, STRICT, gates, outcomes,
CandleSeries.latest, comparadores, referencias o telemetry. No hay Git writes.

## Siguiente paso único

Completar la validación pendiente de persistencia/OCR real y regresión completa en
un contexto autorizado con temporales privados funcionales, manteniendo OFF y sin
publicar. No declarar IMPLEMENTATION_VALIDATED antes de esas comprobaciones.

## Cierre técnico final — 2026-10-28

**H3_R4_OFFLINE_VALIDATED** y **H3_R4_F523D_IMPLEMENTATION_VALIDATED**.
Los bloqueos de temporales, persistencia y validación descritos en el historial
anterior fueron resueltos o completados mediante las validaciones posteriores.
No se eliminan ni se convierten retrospectivamente en éxitos los intentos fallidos.

La suite general fue ejecutada por Principal en PowerShell normal de Windows,
no por el entorno restringido Work: **1797 PASSED, 0 FAILED, 0 ERRORS,
0 SKIPPED, 0 XFAILED y 0 XPASSED**, `sessionfinish=true` y `exit_code=0`.
El control posterior registró **PASS, 463 archivos** para el checkpoint F523D.
Los XML, log, resumen, control de integridad y baseline original se conservan
fuera del repositorio y no se incorporan a Git.

Las validaciones focales anteriores acreditaron **264 PASS**, **Session06:
15 PASS** y **Session08: 12 PASS**. Son conjuntos solapados: no se suman para
construir un total. La suite de 1797 pruebas es el resultado global relevante.
La persistencia física, idempotencia, fingerprints y rechazo de sobrescrituras
quedaron acreditados offline. El adaptador OCR Windows y la ruta independiente
con OCR real sobre evidencia histórica se comprobaron en fases posteriores;
la integración H1/H2 permanece exclusivamente offline.

### Contratos y regresiones preservados

- `dynamic_guide_label_v1` continúa como comportamiento ordinario predeterminado.
- `dynamic_guide_label_v2` es un contrato experimental de entrada offline explícita;
  permanece OFF para el uso ordinario, incluso en instancias habilitadas offline.
- H1/H2 independiente permanece OFF por defecto; no hay activación automática ni
  selección entre v1, v2 y H1/H2 por máximo score.
- F523 se reconoce mediante v2 con soporte GUIDE compuesto observado, asociación
  GUIDE–LABEL y una única identidad acreditada. La abstención de v1 se conserva y
  no niega la existencia visual del marcador. La separación contractual autorizada
  conserva la banda raster 265–266 y verifica la fórmula productiva del centroide;
  no fuerza la reproducción del decimal histórico.
- F1067 conserva el precio real alrededor de y=171 y rechaza el confusor UI alrededor
  de y=121 en ambas rutas, sin falsa ambigüedad. Las nueve regresiones R1 permanecen
  aprobadas, junto con continuidad, deduplicación, ambigüedad real y compatibilidad OFF.
- SQ-03, SQ-04C/harness, STRICT, signal gate, outcomes legacy, recorder y componentes
  protegidos no recibieron alteraciones indebidas. Los freezes H1, H2 original y
  H2-R3D, las fuentes Session06/08, el ground truth y la adjudicación/sello F523
  conservaron su integridad.

El contrato y sus límites se detallan en
[DYNAMIC_GUIDE_LABEL_V2.md](DYNAMIC_GUIDE_LABEL_V2.md). Las referencias externas son
el informe final **h3-R4-F523D — FINAL TECHNICAL CLOSURE**, el baseline
`validation-baseline.json`, los artefactos `suite-native.xml`, `suite-native.txt`,
`suite-native-summary.json`, `suite-native-integrity.json` y las evidencias
Session06/Session08. Se mantienen como fuentes privadas externas, sin rutas
personales absolutas ni copias de capturas en este documento.

### Alcance y límites del cierre

Esta es **validación técnica offline**, no validación live, autorización de trading
ni certificación de rendimiento financiero. No demuestra robustez estadística
general, ausencia universal de falsos positivos/negativos ni robustez sobre capturas
nuevas. Las fotografías utilizadas son evidencia histórica conocida, no un nuevo
holdout independiente. Persisten los límites de cobertura, presupuesto, memoria,
OCR y abstención conservadora descritos en los contratos.

La actualización de este cierre es únicamente documental y posterior a la suite:
no implica que pytest se haya ejecutado después de editar el Markdown. La evidencia
de 1797 pruebas sigue siendo aplicable al código sin cambios. El baseline histórico
no se sustituye: esta edición se registra como **AUTHORIZED_DOCUMENTATION_DELTA**.

No se activaron automáticamente v2 ni H1/H2, no se realizaron nuevas capturas ni
operaciones y no se publicó en Git. Staging, commit, push y cualquier activación
operativa requieren autorizaciones nuevas y separadas.
