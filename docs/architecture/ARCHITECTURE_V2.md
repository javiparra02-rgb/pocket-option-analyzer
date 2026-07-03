# Pocket Option Analyzer

# Arquitectura de Software v2.0

**Versión:** 2.0

**Estado:** En desarrollo

**Python:** 3.12.10

---

# 1. Objetivo

Este documento define la arquitectura oficial del proyecto Pocket Option Analyzer.

Todo el desarrollo futuro deberá respetar las reglas aquí descritas.

El objetivo es construir una aplicación profesional, modular, escalable y mantenible para el análisis en tiempo real de gráficos financieros utilizando visión artificial.

La arquitectura prioriza:

- Clean Architecture
- SOLID
- Inversión de dependencias
- Bajo acoplamiento
- Alta cohesión
- Testabilidad
- Escalabilidad
- Rendimiento

---

# 2. Objetivos del producto

El sistema será capaz de:

- localizar automáticamente la ventana de Pocket Option;
- capturar el gráfico en tiempo real;
- detectar la región útil del gráfico;
- identificar velas japonesas;
- calcular indicadores;
- detectar patrones;
- ejecutar estrategias;
- generar señales de compra y venta;
- visualizar información en una interfaz gráfica;
- almacenar históricos;
- permitir backtesting;
- soportar múltiples estrategias;
- soportar futuras integraciones con IA.

---

# 3. Principios de arquitectura

Todo componente deberá cumplir los siguientes principios.

## 3.1 Responsabilidad Única

Cada clase tendrá una única responsabilidad.

Nunca se crearán clases "todopoderosas".

---

## 3.2 Inversión de Dependencias

El dominio nunca dependerá de infraestructura.

Siempre se programará contra interfaces.

---

## 3.3 Arquitectura por capas

Las dependencias solo podrán apuntar hacia el interior.

Nunca al revés.

---

## 3.4 Inmutabilidad

Siempre que sea posible los modelos serán inmutables.

---

## 3.5 Tipado

Todo el código utilizará type hints completos.

---

## 3.6 Documentación

Toda clase pública deberá estar documentada.

---

## 3.7 Tests

No se aceptará código nuevo sin pruebas.

---

# 4. Arquitectura General

```
+------------------------------------------------------+
|                     Desktop UI                       |
+------------------------------------------------------+
                     ▲
                     │
+------------------------------------------------------+
|                Application Layer                     |
+------------------------------------------------------+
                     ▲
                     │
+------------------------------------------------------+
|                  Domain Layer                        |
+------------------------------------------------------+
                     ▲
                     │
+------------------------------------------------------+
|              Infrastructure Layer                    |
+------------------------------------------------------+
                     ▲
                     │
+------------------------------------------------------+
|                    Windows API                       |
+------------------------------------------------------+
```

---

# 5. Organización del proyecto

```
src/

pocket_option_analyzer/

    application/

    domain/

    infrastructure/

    vision/

    market/

    candles/

    indicators/

    patterns/

    strategies/

    signals/

    runtime/

    ui/

    alerts/

    metrics/

    storage/

    backtesting/

    plugins/

    configuration/
```

---

# 6. Flujo principal

```
Windows

↓

Captura

↓

Preprocesamiento

↓

Detección del gráfico

↓

Extracción de velas

↓

Indicadores

↓

Patrones

↓

Estrategia

↓

Señales

↓

Interfaz

↓

Usuario
```

---

# 7. Módulos principales

## Infrastructure

Responsable de:

- captura
- sistema operativo
- logging
- configuración
- persistencia

Nunca contendrá lógica de negocio.

---

## Vision

Responsable de:

- OpenCV
- filtros
- ROI
- transformaciones
- detección del gráfico

---

## Candles

Responsable de construir objetos Candle.

---

## Indicators

Responsable de:

- EMA
- SMA
- RSI
- ATR
- MACD
- Bollinger

---

## Patterns

Responsable de:

- Engulfing
- Doji
- Hammer
- Pin Bar
- Inside Bar

---

## Strategies

Responsable únicamente de reglas de trading.

Nunca accederá directamente a OpenCV.

---

## Signals

Convierte decisiones de estrategia en señales.

---

## Runtime

Controla el ciclo de vida completo de la aplicación.

---

## UI

Interfaz gráfica.

Nunca contendrá lógica de negocio.

---

## Storage

Persistencia.

---

## Backtesting

Simulación.

---

## Plugins

Sistema de extensiones futuras.

---

# 8. Reglas de dependencias

```
UI

↓

Application

↓

Domain

↓

Infrastructure

↓

Windows
```

Dependencias prohibidas:

UI → Windows

Vision → UI

Strategies → OpenCV

Indicators → Windows

Patterns → MSS

---

# 9. Eventos del sistema

FrameCaptured

FrameValidated

FrameProcessed

ChartDetected

CandlesDetected

IndicatorsCalculated

PatternDetected

SignalGenerated

AlertTriggered

FrameStored

---

# 10. Ciclo de ejecución

```
Capturar

↓

Validar

↓

Procesar

↓

Detectar gráfico

↓

Extraer velas

↓

Actualizar indicadores

↓

Buscar patrones

↓

Evaluar estrategia

↓

Generar señal

↓

Actualizar interfaz

↓

Esperar siguiente frame
```

---

# 11. Calidad

Cada archivo nuevo deberá cumplir obligatoriamente:

- responsabilidad única;
- documentación;
- type hints;
- pruebas unitarias;
- integración con el contenedor;
- compatibilidad con PEP 8.

---

# 12. Convenciones

## Clases

PascalCase

## Métodos

snake_case

## Constantes

UPPER_CASE

## Archivos

snake_case

---

# 13. Estrategia de pruebas

Cada módulo tendrá:

- pruebas unitarias;
- pruebas de integración;
- pruebas funcionales.

No se permitirá código sin cobertura.

---

# 14. Roadmap

## Fase 1

Infraestructura

Estado: En progreso

---

## Fase 2

Captura profesional mediante Win32

---

## Fase 3

Pipeline de visión

---

## Fase 4

Detección de velas

---

## Fase 5

Indicadores técnicos

---

## Fase 6

Detección de patrones

---

## Fase 7

Motor de estrategias

---

## Fase 8

Generación de señales

---

## Fase 9

Interfaz gráfica

---

## Fase 10

Optimización

---

## Fase 11

Backtesting

---

## Fase 12

IA

---

# 15. Regla de Oro

**La estabilidad de la arquitectura tiene prioridad sobre la velocidad de desarrollo.**

Ninguna nueva funcionalidad deberá comprometer la mantenibilidad, la testabilidad o la separación de responsabilidades del proyecto.

Toda modificación arquitectónica deberá justificarse técnicamente y mantener la compatibilidad con los principios definidos en este documento.
