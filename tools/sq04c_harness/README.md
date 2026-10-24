# SQ-04C-S8 / S9-R1 / S9-R3: harness externo, exclusivamente sintético

Este módulo prepara el piloto futuro; no dispone de un backend live. `OFF`,
`ON` y cualquier modo distinto de `SYNTHETIC` se rechazan. La fuente construida
por `build_synthetic()` genera matrices en memoria: no acepta ventanas,
adaptadores de captura, rutas de imágenes ni callbacks de adquisición.
Importar el harness no importa el producto ni inicia sesiones.

## Ejecución reproducible

Desde la raíz del repositorio, con el intérprete del entorno virtual:

```powershell
& '.venv\Scripts\python.exe' -I -B 'tools\sq04c_harness\validate.py' `
  --repository 'C:\Users\Javier\Documents\Programas\pocket-option-analyzer' `
  --output-parent "$env:LOCALAPPDATA\Temp\sq04c-s8-validation"
```

El comando ejecuta **sólo las pruebas nuevas** de este directorio. Crea una
carpeta única, conserva todos los resultados y no limpia carpetas anteriores.
No requiere administrador ni modificaciones de ACL. Si el sandbox del Work
deniega Temp, corresponde usar su autorización normal de ejecución; un error
de permisos no acredita un fallo del writer.

`--test-filter 's9_'` selecciona las regresiones S9-R1 por `pytest -k` y queda
registrado en `validation.json`. Es una ejecución dirigida, no sustituye la
suite completa sin filtro. Esta ampliación de `validate.py` permite separar
la reproducción previa de los defectos y su validación posterior sin saltarse
el snapshot ni sus comprobaciones. No pasa comandos a un shell.

No ejecutar directamente estos tests contra la instalación editable: el
`conftest` exige el snapshot ya activado por el lanzador. No usar los ejemplos
como autorización para adquirir imágenes reales.

## Archivos y responsabilidades

- `isolation.py`: baseline protegido; árbol Git, recuperación binaria de blobs,
  OID Git y SHA-256; rutas; snapshot e importaciones.
- `config.py`: configuración explícita y coherencia captura/pipeline.
- `composition.py`: fuente sintética, composición por API pública y censo.
- `supervisor.py`: sesión continua, parada, flush, incidencias y rechazo de retry.
- `reconcile.py`: contraste de censo, SQ-03, journal, manifiestos, roles y objetos.
- `metrics.py`: muestras acotadas y percentiles; CPU, memoria e I/O del proceso.
- `validate.py`: proceso aislado de pytest y evidencias antes/después.
- `tests/`: fakes deterministas y fixtures originales con píxeles sintéticos.

## Aislamiento y protección

Se exige rama `feat/visual-price-resolution`, HEAD
`0db4b65448746acf5cf1434df44d3f36576fcb42`, índice vacío y exactamente los cinco
archivos h3 modificados con sus hashes protegidos. Se comparan los 431 archivos
tracked antes y después. Los archivos nuevos del harness se inventarían aparte.

`git ls-tree -rz` enumera el árbol y `git cat-file --batch`, por pipes binarios,
recupera los bytes exactos. Se verifica cada OID SHA-1 de objeto Git y SHA-256
del contenido; el SHA-1 identifica el objeto, no sustituye al hash de contenido.
No se usa archive ZIP, checkout, index, overlay ni conversión LF/CRLF.
Se rechazan symlinks/submódulos, colisiones por mayúsculas, rutas especiales,
traversal, ADS y solapamiento con el repositorio. `pyproject.toml` se conserva.

Las importaciones productivas proceden de `snapshot/src`; un guard comprueba
archivos y rutas de paquetes namespace (éstos legítimamente no tienen
`__file__`). Un módulo productivo ya cargado desde otro lugar provoca rechazo.
Se registran Python, plataforma, dependencias y procedencia de cada módulo.
El snapshot completo se verifica antes y después; no se generan `.pyc`.

Los directorios de snapshot, evidencia, SQ-03, supervisión y resultados se
separan. Las salidas no pueden coincidir ni contenerse entre sí, ni solaparse
con repositorio/snapshot. La preparación y el lector externo suponen un
directorio de trabajo controlado, sin actor hostil que sustituya rutas durante
la operación. No añaden al writer una garantía absoluta frente a administradores,
kernel o modificaciones concurrentes del mismo usuario.

## Contratos revisados y composición

Se verificaron las firmas de `ObservationalEvidenceConfig`, `Settings`,
`PocketOptionRuntimeFactory`, `SignalPipelineFactory`,
`VisualSignalRecordingPipeline`, `ObservationalEvidenceRecorder`,
`ObservationalEvidenceWriter`, `AnalyzeCapturedFrameUseCase`,
`FrameAnalysisLoopService` y `AnalysisRuntimeService` en el código aprobado.

Se conserva el pipeline retornado por
`SignalPipelineFactory.create_visual_signal_recording_pipeline()`, su campo
público `observational_evidence` y `recorder.writer`. El tipo concreto del
writer se comprueba: el protocolo mínimo de escritura por sí solo no garantiza
`flush`, contadores, `retry_failed` ni `read_package`.
También se retienen el caso de uso, el loop y el runtime. No se atraviesan
atributos privados ni se parchea el producto para controlarlo.

El supervisor posee una sesión mediante `start_session()`, varios `run_once()`
y `stop_session()` en `finally`. Estas APIs públicas permiten instrumentar
ciclos completos sin alterar evaluación, estrategia o gate. El supervisor
programa los ciclos; `loop.stop()` se acompaña de su propia señal de parada.
No se llama a `loop.start()` simultáneamente. La observación del caso de uso
delega una sola vez y conserva identidades públicas; no reevalúa decisiones.
La representación de PRE requiere una identidad nativa observada de forma
independiente; las observaciones de frames no sustituyen esa identidad.

`Settings.observational_evidence_enabled` continúa con default `False`.
El harness exige ambos switches iguales y el conjunto completo de presupuestos,
incluso en la comparación sintética sin recorder. S7 propuso 8 MiB por frame,
32 MiB retenidos, 4 aceptaciones, 8 tareas, 64 MiB de cola, 256 MiB de almacenamiento,
retención 60 s y contexto `None`; no son defaults productivos ni cifras calibradas.
También se exigen intervalo, límite de ciclos, capacidad de muestras y timeouts.

## Parada y resultados

Secuencia normal:
`CREATED -> CONFIGURED -> READY -> RUNNING -> STOP_REQUESTED -> SESSION_STOPPED
-> FLUSHING -> RECONCILING -> CLOSED_VERIFIED`.

El worker no es daemon. La parada impide programar nuevos ciclos, espera el
análisis activo y confirma el retorno de `stop_session()`. Se requiere cero
aceptaciones pendientes antes de hacer `flush(timeout)` desde el supervisor.
El cierre sólo se acredita tras `flush is True`, contadores de cola vacíos,
ausencia de pérdidas y reconciliación satisfactoria.

Hilo activo, excepción de cierre/flush, cola retenida, pérdidas de journal,
fallos no resueltos, fallos del hook observacional o contradicciones producen
`CLOSE_UNVERIFIED`. Se conservan referencias, traceback y diagnóstico. El
informe no equipara espera, `stop()` ni flush aislado con persistencia exitosa.
Los tests bloqueantes liberan explícitamente sus Events en `finally`; no dejan
hilos de prueba colgados ni usan sleeps largos.

S9-R1 deshabilita todos los reintentos del harness: `retry_once()` rechaza con
`RETRY_UNVERIFIED`, incluso con aprobación y un WinError 32 aislado. La API
pública sólo expone contadores y el último error global; `retry_failed(id)`
reencola todas las tareas retenidas de esa aceptación, sin poder acreditar
individualmente sus causas. Un último fallo transitorio puede ocultar otro
de integridad. No se inspeccionan colas privadas, no se reinician contadores,
no se reencolan tareas y nunca se llama a `discard_failed()`. El diagnóstico,
las tareas y el cierre no acreditado se conservan. No existe una ruta de retry
autorizada con la API actual; una aprobación por sí sola no aporta esa prueba.

## Reconciliación

Se compara el censo independiente con `accepted_evidence` de SQ-03 (incluidas
rotaciones), `ACCEPTANCE_KNOWN`, selección nativa de EXIT y confirmaciones de
manifiesto. `read_package()` del **mismo writer** comprueba hashes de manifiesto
y PNG. El inventario detecta archivos inesperados, objetos huérfanos y temporales.
Se comprueban identidades de ENTRY, PRE y SQ03_EXIT, fuente/sesión, tiempos,
roles y motivos reconocidos de ausencia.

S9-01: `check_exit_binding()` exige la versión nativa 1 y sus campos realmente
persistidos: `entry_evaluation_id`, `event_id`, `exit_evaluation`, referencia
temporal nominal/observada, `lateness_seconds` y `source_identity_available`.
Contrasta aceptación, evaluación de entrada, salida nativa observada y selección
del journal (`exit_event_id`, `exit_evaluation_id`, lateness). La selección debe
ser única. Faltas o contradicciones impiden verificar el cierre; un manifiesto
íntegro no acredita por sí solo el vínculo SQ-03. Nada de esto calcula outcomes.

S9-02 distingue tres casos de PRE_EXPIRY:

- Presente, identidad nativa completa observada independientemente y coherente:
  puede verificarse.
- Ausente con motivo nativo reconocido: puede ser un parcial legítimo; no se
  fabrica un frame ni se declara corrupción sólo por la ausencia.
- Presente sin identidad nativa independiente: `EVALUATION_IDENTITY_UNVERIFIED`
  y `CLOSE_UNVERIFIED`, aunque PNG, geometría, tiempo y fuente concuerden.

`ObservedAnalysis` sólo obtiene identidades públicas de `last_accepted` y
`last_exit`; no obtiene la identidad de toda evaluación intermedia no aceptada.
La metadata observada del frame sirve para revisar el orden temporal, nunca
para autenticar `evaluation_id`. Por eso un PRE legítimo intermedio puede quedar
sin acreditar. `PACKAGE_FAILED` en la reconciliación significa comprobación
fallida y debe leerse junto al motivo; no afirma necesariamente corrupción de
bytes. Conseguir cierre acreditado para todos esos PRE es una limitación funcional
pendiente, no una razón para relajar la comprobación o modificar el producto aquí.

Un `PACKAGE_PARTIAL` cerrado y justificado puede reconciliarse; no se convierte
en completo por tener `WRITE_CONFIRMED`. Pérdidas y fallos quedan separados.
Sin aceptaciones se acredita el cierre de esa sesión, pero la cobertura se
declara incompleta. SQ03_EXIT es la selección observacional SQ-03, nunca una
liquidación de mercado. El fixture de reinicio es deliberadamente separado:
el supervisor no recrea el writer para inspeccionar evidencia, pues su constructor
puede marcar paquetes interrumpidos.

## Métricas y evidencias de validación

Se preparan duración/intervalo por ciclo, p50/p95/máximo (nearest rank), ciclos,
evaluaciones, errores, memoria residente, CPU, bytes escritos por el proceso,
cola y máximos observados, fallos y pérdidas; el informe contiene resultado del
flush, reconciliación, bytes/archivos de evidencia y estado final. El muestreo
es idéntico con recorder sintético habilitado o deshabilitado. Los máximos de
cola son muestreados; los bytes de proceso no son I/O físico del dispositivo.
Todo se etiqueta `SYNTHETIC_NOT_LIVE_PERFORMANCE`.

Cada ejecución conserva `snapshot_identity.json`, `harness_hashes.json`,
`repository_before.json`, `repository_after.json`, transcript, JUnit,
`import_provenance.json`, `environment.json` y `validation.json`. Las sesiones
sintéticas de integración conservan su propio `session-report.json`.
Un SKIP nunca se cuenta como PASS.

S9-R1 conserva los 87 casos S8; el caso de retry transitorio cambia deliberadamente
su expectativa de éxito por rechazo fail-closed. Las demás expectativas se
conservan. Las reproducciones anteriores a la corrección (21 fallos esperados,
3 rechazos ya existentes) son evidencia del defecto, no validación aprobada.
Los nuevos casos usan recorder/writer nativos del snapshot, píxeles sintéticos,
manifiestos/journal reales, bloqueo de archivo Windows real y un hard link
controlado en Temp. Las dobles de adquisición/control no acreditan recuperación
del writer. Se comprueba además el rechazo de namespaces de procedencia mixta.

Los resultados quedan locales: contienen rutas, identidades sintéticas, hashes
y copias del código committed. No se suben automáticamente ni se limpian datos
ajenos. Revisar/redactar esos datos antes de compartirlos; la retención en Temp
no es una política de custodia ni una protección frente a otro usuario autorizado.

## Límites pendientes

### S9-R3: composición real con aceptación

`build_synthetic(config, frames=...)` admite únicamente una tupla finita de
`SyntheticFrame`: píxeles BGR uint8 en memoria, fuente `SYNTHETIC_NO_SCREEN`,
timestamps explícitos crecientes y un frame por ciclo. No admite callbacks,
rutas ni proveedores live. El caso sin tupla conserva la fuente anterior.
`Supervisor.analysis` conserva el `ObservedAnalysis` realmente conectado al
loop para inspeccionar su censo, sin añadir identidades ni leerlas del manifest.
No se modifican `reconcile`, `supervisor`, el producto, STRICT ni el gate.

`test_s9_r3_real_composition_acceptance` usa la fábrica committed, estrategia
OTC Precision 10S predeterminada, detector, indicadores, gate, caso de uso,
loop y runtime originales; recorder y writer reales con escritura asíncrona.
No inyecta señales, aceptaciones, evaluaciones ni salidas. Los fixtures nativos
aislados anteriores siguen siendo pruebas unitarias, no prueba de aceptación
estratégica. La nueva prueba no utiliza `NativePackage` ni `FakeLoop`.

Estímulo: imagen 400×640×3 (768000 bytes), fondo negro, 31 cuerpos blancos sin
mechas ni etiquetas, ancho 11, alto 13, x=20+18*i, y=400-close. Las primeras 30
velas alimentan los indicadores; la última es la potencialmente abierta.
Los niveles exactos están en `tests/fixtures.py:s9_r3_frames`; un marcador
oscuro en (0,0) distingue los PNG sin constituir vela/precio. No representa
un instrumento real. Se escogieron niveles sintéticos mediante búsqueda
determinista de entradas; las decisiones se recalculan desde píxeles en cada
prueba. No se impone el resultado de esa búsqueda al pipeline.

La ENTRY calculada debe acreditar las siete condiciones CALL y el perfil
oficial completo. Frame IDs y tiempos son datos de la fuente sintética; sesión
y execution/evaluation/acceptance/event IDs son creados por el producto.
Los tiempos de frames comienzan en 2026-01-01T00:00:00Z. El reloj del caché de
indicadores y los timestamps de procesamiento siguen siendo los nativos del
producto: no se falsifican ni se equiparan al tiempo del frame. Los IDs y hashes
de paquetes no tienen por qué repetirse entre ejecuciones.

| Escenario | Frames (segundos) | Resultado exigido |
|---|---|---|
| A: PRE acreditado | 0, 12 | Una aceptación real; PRE=ENTRY, última observación antes de T+10; EXIT nativo T+12; `PACKAGE_COMPLETE`, `CLOSED_VERIFIED`. |
| B: PRE ausente, EXIT presente | 0, 9, 12 | Contexto sintético de 2×2×3 en T+9 supera el presupuesto de candidato: 768012 > 768010 bytes. El recorder retorna None legítimamente, sin borrar registros; EXIT T+12 presente; `PACKAGE_PARTIAL`, `CLOSED_VERIFIED`. |
| C: PRE intermedio no acreditado | 0, 9, 12 | PNG y evaluación PRE presentes, pero sólo ENTRY/EXIT tienen identidad observada en el censo; `EVALUATION_IDENTITY_UNVERIFIED: PRE_EXPIRY`, `CLOSE_UNVERIFIED`. |
| D: sin aceptación | 0, 9, 12 | Fondo sin velas, ningún paquete; cierre de sesión verificado con `NO_ACCEPTANCES_COVERAGE_INCOMPLETE`. No demuestra utilidad con aceptación. |

En B, el motivo persistido por el writer es `NO_FRAME`: al capturar el EXIT
válido el recorder reinicia `candidate_failure`, por lo que no conserva en el
manifest la causa histórica `FRAME_BYTE_LIMIT` de PRE. Esa causa se comprueba
por los tamaños de entradas/presupuesto y el camino nativo de `capture()`;
no se presenta `NO_FRAME` como diagnóstico granular del límite de bytes.
El censo permanece exactamente limitado a aceptación y salida nativas. Los
frames intermedios sólo aportan metadata, nunca un evaluation_id inferido.

Cada escenario conserva `synthetic-inputs.json`, `composition-census.json`,
`session-report.json`, SQ-03, journal y originales. El mismo writer verifica
manifest/objetos; además se comparan SHA-256 y píxeles decodificados con el
frame de cada rol. El cierre exige productor detenido, sesión finalizada,
pendientes/cola/fallos/pérdidas a cero y flush verdadero; no usa sleeps para
sincronizar. La ausencia de retries permanece sin cambios.

S9-R3 añade cuatro escenarios y siete controles de secuencia; conserva los
125 casos anteriores (incluidos los negativos de ENTRY, EXIT, journal,
manifest/PNG, flush, tareas retenidas, pérdidas y cierre con hilo activo).
Para dirigir sólo los nuevos casos: `--test-filter s9_r3`. La suite completa
sigue siendo necesaria antes de solicitar revisión de publicación.

Esta cobertura resuelve la existencia de rutas sintéticas positivas A/B; no
resuelve la identidad de todo PRE intermedio, la recuperación de tareas ni
la viabilidad general de una cadencia real. No infiere tasas de éxito.

### Límites operativos no levantados

No hay captura, GUI, red necesaria, trading, piloto ON ni referencia OFF real.
Las pruebas prueban el harness y los contratos utilizados; no repiten las 28
pruebas físicas ya acreditadas ni los replays históricos.
La parada es cooperativa: no cancela una llamada productiva/I/O bloqueada.
El worker puede requerir intervención si nunca retorna. La API de flush tiene
timeout, pero no convierte bytes en una garantía fsync ni una transacción global.
No se promete RSS total limitado por los presupuestos de imágenes/cola.
No hay cuotas calibradas, duración o umbrales operativos validados con mercado.
La prueba de integridad no constituye firma, custodia o autenticación externa.

Antes de cualquier adquisición real siguen pendientes una revisión focalizada
del harness, la autorización correspondiente y un backend live separado con
controles explícitos, ruta privada y métricas OFF acreditadas. Este módulo no
contiene un flag que permita eludir ese límite.
La validación sintética de las correcciones no demuestra cobertura de PRE
intermedios en una sesión real ni recuperación segura de tareas retenidas.
Si esos objetivos son imprescindibles para el piloto, su habilitación queda
bloqueada hasta una decisión separada sobre las interfaces públicas necesarias.
