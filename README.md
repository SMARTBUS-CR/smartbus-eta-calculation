# 🚌 SmartBus Global - ETA Prediction Service

Microservicio de Inteligencia Artificial para el cálculo del **ETA (Estimated Time of Arrival)** de los autobuses de SmartBus Global.

Este servicio utiliza un modelo de Machine Learning desarrollado en Python con **Scikit-Learn** para estimar el tiempo restante de llegada de un autobús a una parada utilizando principalmente:

- Distancia restante.
- Velocidad actual del autobús.

Además, el sistema cuenta con un mecanismo de **fallback determinístico** que permite continuar calculando el ETA incluso cuando el modelo de Machine Learning no está disponible.

---

## 📌 Proyecto SmartBus Global

SmartBus Global es una plataforma inteligente de transporte público que permite:

- Visualizar autobuses en tiempo real.
- Consultar rutas.
- Monitorear recorridos.
- Visualizar el ETA hacia las diferentes paradas.
- Recibir notificaciones de retrasos o llegada próxima.
- Administrar autobuses, conductores y rutas.

La plataforma utiliza una arquitectura basada en microservicios.

El microservicio de ETA es responsable específicamente de calcular el tiempo estimado que tardará un autobús en llegar a una parada.

---

# 🎯 Objetivo del módulo ETA

Calcular dinámicamente el tiempo estimado de llegada utilizando:

```text
distancia_restante_m
velocidad_actual_kmh
```

El flujo principal es:

```text
Datos del recorrido
        │
        ▼
Distancia restante + Velocidad actual
        │
        ▼
    Modelo ML
        │
   ¿Disponible?
     /     \
   Sí       No
   │         │
   ▼         ▼
Predicción  Fallback
   │         │
   └────┬────┘
        ▼
    ETA final
```

---

# 🤖 Modelo de Machine Learning

El modelo utiliza **Scikit-Learn** para realizar una regresión basada inicialmente en dos características:

| Variable | Descripción |
|---|---|
| `distancia_restante_m` | Distancia restante hasta la parada en metros |
| `velocidad_actual_kmh` | Velocidad actual del autobús en km/h |

La variable objetivo del modelo es:

```text
eta_segundos
```

El modelo entrenado se almacena utilizando `joblib`.

Ejemplo:

```text
app/models/eta_model.joblib
```

El modelo se carga una sola vez en memoria para evitar acceso al disco en cada solicitud y mantener un buen rendimiento.

---

# 🛡️ Fallback determinístico

Si el modelo de Machine Learning no puede cargarse o falla durante una predicción, el servicio utiliza automáticamente una fórmula matemática.

La fórmula utilizada es:

```text
ETA = distancia / velocidad
```

Como la distancia se recibe en metros y la velocidad en kilómetros por hora, primero se convierte la velocidad:

```text
velocidad_m_s = velocidad_actual_kmh / 3.6
```

Después:

```text
eta_segundos = distancia_restante_m / velocidad_m_s
```

### Ejemplo

Para:

```text
distancia_restante_m = 1000
velocidad_actual_kmh = 36
```

La velocidad equivale a:

```text
36 km/h = 10 m/s
```

Por lo tanto:

```text
ETA = 1000 / 10
ETA = 100 segundos
```

Resultado:

```text
1 min 40 s
```

---

# 📁 Estructura del módulo

La estructura principal del módulo ETA es:

```text
app/
│
├── models/
│   └── eta_model.joblib
│
├── services/
│   ├── fallback.py
│   ├── ml_model.py
│   └── eta_service.py
│
├── schemas/
│   └── eta_schema.py
│
└── api/
    └── v1/
        └── eta.py

scripts/
│
└── train_eta_model.py

tests/
│
└── services/
    ├── test_fallback.py
    ├── test_ml_model.py
    └── test_eta_service.py
```

### Responsabilidad de cada archivo

#### `fallback.py`

Contiene la lógica matemática utilizada cuando el modelo ML no está disponible.

---

#### `ml_model.py`

Responsable de:

- Cargar el modelo `.joblib`.
- Mantenerlo disponible en memoria.
- Preparar las variables de entrada.
- Realizar la predicción.

---

#### `eta_service.py`

Orquesta el cálculo del ETA.

Primero intenta utilizar Machine Learning y, en caso de error, utiliza automáticamente el fallback.

---

#### `train_eta_model.py`

Script utilizado para:

- Generar o cargar datos de entrenamiento.
- Entrenar el modelo de Scikit-Learn.
- Exportar el modelo utilizando `joblib`.

---

#### `eta_schema.py`

Contiene los modelos de validación utilizados por la capa API.

---

#### `api/v1/eta.py`

Controlador REST encargado de recibir solicitudes y comunicarse con el servicio de ETA.

---

# 🌿 Ramas de desarrollo

El desarrollo del cálculo ETA se divide en tres ramas principales.

### 1. Deterministic Fallback

```bash
feature/eta-fallback
```

Responsable de:

```text
app/services/fallback.py
```

Incluye:

- Conversión de velocidad.
- Cálculo distancia / velocidad.
- Conversión del resultado a segundos.
- Manejo de condiciones matemáticas inválidas.

---

### 2. Machine Learning Model

```bash
feature/eta-ml-model
```

Responsable de:

```text
scripts/train_eta_model.py
app/services/ml_model.py
app/models/eta_model.joblib
```

Incluye:

- Entrenamiento del modelo.
- Generación del archivo `.joblib`.
- Carga del modelo en memoria.
- Predicciones de ETA.

---

### 3. ETA Orchestrator

```bash
feature/eta-orchestrator
```

Responsable de:

```text
app/services/eta_service.py
```

Incluye:

```text
Modelo ML
    ↓
¿Funciona?
 ├── Sí → utilizar predicción ML
 └── No → utilizar fallback
            ↓
        ETA final
```

También genera:

```text
eta_segundos
eta_formato
confianza
calculado_en
```

---


### Modelo ML

Se verifica que:

- El modelo pueda cargarse.
- La predicción sea numérica.
- La predicción sea válida.
- El ETA sea positivo para datos válidos.

---

# 🏗️ Arquitectura relacionada

El flujo general del sistema es:

```text
Aplicación Conductor
        │
        │ GPS
        ▼
Servicio de Rastreo
        │
        ├──────────────► Actualización en tiempo real
        │
        ▼
Distancia restante + velocidad
        │
        ▼
Microservicio IA - ETA
        │
        ├── Modelo ML
        │
        └── Fallback
        │
        ▼
ETA calculado
        │
        ▼
Backend / API Gateway
        │
        ▼
Aplicación Pasajero
```

---

# 📚 Tecnologías

- Python
- Scikit-Learn
- Joblib
- FastAPI
- Pydantic
- REST API
- Machine Learning
- Git / GitHub

---

# 🎓 SmartBus Global

Proyecto desarrollado como parte del curso **Aplicaciones Informáticas Globales** de la Universidad Nacional de Costa Rica.

El objetivo del proyecto es desarrollar una plataforma inteligente que permita mejorar el monitoreo del transporte público mediante geolocalización, comunicación en tiempo real, arquitectura de microservicios e Inteligencia Artificial.
