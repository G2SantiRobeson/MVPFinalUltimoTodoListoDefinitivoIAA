# Manual de Instalación y Despliegue

## Plataforma de Validación del Perfil de Egreso

---

| Versión | Fecha | Descripción |
|---------|-------|-------------|
| 1.1     | 2026-06 | Versión reestructurada |

---

## Índice

1. [Introducción y requisitos](#1-introducción-y-requisitos)
2. [⭐ Quick Start — 3 pasos para arrancar](#2--quick-start--3-pasos-para-arrancar)
3. [Variables de entorno (`.env`)](#3-variables-de-entorno-env)
   - 3.1. Dónde crear el archivo
   - 3.2. Tabla de variables
   - 3.3. Ejemplo completo
4. [Instalación con Docker Compose (detallado)](#4-instalación-con-docker-compose-detallado)
   - 4.1. Requisitos previos
   - 4.2. Pasos detallados
   - 4.3. Activar GPU (solo si tienes GPU NVIDIA)
   - 4.4. Iniciar servicios
   - 4.5. Servicios levantados
   - 4.6. Comandos útiles
5. [Instalación Manual (sin Docker)](#5-instalación-manual-sin-docker)
   - 5.1. Requisitos previos
   - 5.2. Pasos de instalación
6. [Estructura del proyecto](#6-estructura-del-proyecto)
7. [Verificación de la instalación](#7-verificación-de-la-instalación)
8. [Problemas frecuentes y soluciones](#8-problemas-frecuentes-y-soluciones)
9. [Mantenimiento](#9-mantenimiento)

---

## 1. Introducción y requisitos

Sistema web para validar que las tesis/memorias evidencian las competencias del perfil de egreso.
Backend en Python/FastAPI, frontend vanilla JS, base de datos PostgreSQL con pgvector.

### Requisitos mínimos

| Componente | Especificación |
|------------|---------------|
| Sistema | Windows 10+, macOS 12+, Ubuntu 20.04+ |
| RAM | 4 GB (16 GB recomendado) |
| Disco | 10 GB libres |
| Docker | Docker Desktop 24+ o Docker Engine + Compose |
| Python | 3.11+ (solo para instalación manual) |

### ¿CPU o GPU?

El backend usa `EMBEDDING_DEVICE=auto`: si Docker expone una GPU NVIDIA, los embeddings usan CUDA; si no, usan CPU.

El `docker-compose.yml` del repositorio trae `gpus: all` activo para acelerar el procesamiento cuando el entorno lo soporta. Si tu equipo no tiene GPU NVIDIA o Docker falla al solicitar GPU, comenta o elimina esa línea y el sistema funcionará en CPU.

> Revisa la sección [4.3. Activar GPU](#43-activar-gpu-solo-si-tienes-gpu-nvidia) para las instrucciones completas.

---

## 2. ⭐ Quick Start — pasos para arrancar

### Paso 1: Verifica tu GPU (opcional — da igual si no tienes)

El sistema funciona en CPU sin problemas. Si quieres aceleración y tienes GPU NVIDIA:

```bash
nvidia-smi
```

Si ves información de tu GPU, puedes activarla más adelante. Si no, no pasa nada.

### Paso 2: (Opcional) Crea `backend/.env` para comentarios con IA

Solo si quieres comentarios generados por IA en el heatmap:

```bash
cp backend/.env.example backend/.env
```

Edita `backend/.env` y descomenta el proveedor que uses:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...
```

Sin esto, el sistema funciona igual con comentarios locales.

### Paso 3: Revisa la configuración de GPU

Si tienes GPU NVIDIA y Docker la soporta, deja `gpus: all` activo en `docker-compose.yml`.

Si no tienes GPU o Docker muestra un error relacionado con NVIDIA, comenta o elimina esa línea:

```yaml
    # gpus: all
```

Con `EMBEDDING_DEVICE=auto`, el backend seguirá funcionando en CPU.

### Paso 4: Levanta todo con Docker

```bash
docker compose up --build
```

La primera ejecución descarga PostgreSQL con pgvector, construye la imagen del backend y descarga el modelo de IA `BAAI/bge-m3` (~2 GB). Esto toma unos minutos.

[SCREENSHOT: Terminal mostrando docker compose up --build ejecutándose]

### Paso 5: Abre la aplicación

1. Abre `index.html` en tu navegador.
2. Carga una matriz curricular (archivo Excel desde "Mallas cargadas").
3. Crea un período académico (ej: `2026-1`).
4. Sube una tesis (PDF, DOCX o TXT).
5. Espera a que se procese.
6. Haz clic en **Analizar con API**.
7. Explora el heatmap, las evidencias y los KPIs.

[SCREENSHOT: Aplicación abierta en el navegador mostrando el dashboard]

### ✅ Lo lograste

Si ves el heatmap con datos, la instalación fue exitosa.

---

## 3. Variables de entorno (`.env`)

### 3.1. Dónde crear el archivo

El archivo de configuración se llama `.env` y debe estar en la carpeta `backend/`:

```
MVPFinalUltimoTodoListoDefinitivoIAA/
└── backend/
    └── .env          ← aquí (copiado de .env.example)
```

### 3.2. Tabla de variables

| Variable | Obligatorio | Descripción | Valor por defecto |
|----------|-------------|-------------|-------------------|
| `LLM_COMMENTS_ENABLED` | No | Activa comentarios con IA | `true` |
| `LLM_PROVIDER` | No | Proveedor LLM: `gemini` o `openai` | `gemini` |
| `GEMINI_API_KEY` | Si usas Gemini | API key de Google Gemini | — |
| `OPENAI_API_KEY` | Si usas OpenAI | API key de OpenAI | — |
| `OPENAI_MODEL` | No | Modelo de OpenAI | `gpt-5.5` |
| `EMBEDDING_DEVICE` | No | `auto` (detecta GPU), `cpu` o `cuda` | `auto` |
| `LOG_LEVEL` | No | Nivel de logging | `INFO` |

> **Con Docker Compose**, la variable de conexión a la base de datos se configura sola. Solo necesitas tocar las variables de LLM y embeddings si quieres personalizarlas.

### 3.3. Ejemplo completo de `backend/.env`

```env
# --- Comentarios con LLM (opcional) ---
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...

# --- Embeddings (auto detecta GPU, sino CPU) ---
EMBEDDING_DEVICE=auto

# --- Logging ---
LOG_LEVEL=INFO
```

---

## 4. Instalación con Docker Compose (detallado)

### 4.1. Requisitos previos

- **Git** instalado
- **Docker Engine 24+** con Compose o **Docker Desktop 24+**

### 4.2. Pasos detallados

```bash
# 1. Clonar el repositorio (si no lo has hecho)
git clone <url-del-repositorio>
cd MVPFinalUltimoTodoListoDefinitivoIAA

# 2. (Opcional) Crear .env para API key de LLM
cp backend/.env.example backend/.env
# Editar backend/.env con tu editor favorito
```

### 4.3. Activar GPU (solo si tienes GPU NVIDIA)

Si quieres acelerar los embeddings con tu GPU, sigue los pasos según tu entorno.
**Si no tienes GPU o no te interesa, revisa [4.3.4](#434-revisar-gpus-all-en-docker-composeyml) para comentar `gpus: all` y luego salta a [4.4. Iniciar servicios](#44-iniciar-servicios).**

> **¿No sabes qué entorno tienes?**
> - Si instalaste Docker desde `docker.com` → **Docker Desktop**
> - Si instalaste Docker con `sudo apt install docker` → **Docker Engine**
> - Para saber si estás en WSL2: ejecuta `wsl.exe --status` en PowerShell o
>   revisa si `cat /proc/version` menciona "Microsoft"

#### 4.3.1. Windows + Docker Desktop

No necesitas instalar nada extra. Docker Desktop para Windows incluye el soporte
GPU si tienes:
1. Drivers NVIDIA instalados en Windows (desde nvidia.com)
2. WSL2 configurado como backend de Docker Desktop
3. Integración WSL2 activada en Docker Desktop Settings → Resources → WSL Integration

**Listo, salta a [4.3.4](#434-revisar-gpus-all-en-docker-composeyml).**

#### 4.3.2. Linux nativo (Ubuntu/Debian)

Agrega el repositorio de NVIDIA e instala el toolkit:

```bash
# 1. Agregar clave GPG de NVIDIA
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# 2. Agregar repositorio
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 3. Instalar
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

#### 4.3.3. WSL2 + Docker Engine (dentro de WSL2)

> **No sigas esto si usas Docker Desktop. Es solo para Docker Engine instalado
> directamente dentro de WSL2.**

Instala el toolkit igual que en Linux nativo (pasos 1-3 de arriba) y luego
agrega esta configuración adicional necesaria para que funcione en WSL2:

```bash
# Configurar no-cgroups (necesario en WSL2)
sudo sed -i 's/#no-cgroups = false/no-cgroups = true/' /etc/nvidia-container-runtime/config.toml
sudo systemctl restart docker
```

Sin este paso, Docker fallará al iniciar contenedores con GPU en WSL2 con el
error `libdxcore.so: no such file or directory`.

#### 4.3.4. Revisar `gpus: all` en `docker-compose.yml`

El archivo trae `gpus: all` activo para usar GPU cuando esté disponible:

```yaml
    gpus: all
```

Si tu equipo no tiene GPU NVIDIA o Docker falla al iniciar por falta de soporte NVIDIA, comenta o elimina esa línea:

```yaml
    # gpus: all
```

### 4.4. Iniciar servicios

```bash
# 3. Iniciar todo
docker compose up --build
```

[SCREENSHOT: Terminal mostrando docker compose up --build]

El sistema ya trae `EMBEDDING_DEVICE=auto`, que detecta la GPU automáticamente si está disponible. Para ejecutar en CPU, basta con comentar o eliminar `gpus: all` si tu Docker no soporta GPU.

Para verificar que la GPU quedó activa:

```bash
curl http://localhost:8000/api/v1/ai-status
# → {"device": "cuda", ...}  ← GPU activa
# → {"device": "cpu", ...}   ← CPU (normal si no hay GPU o no la activaste)
```

### 4.5. Servicios levantados

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| API (FastAPI) | `8000` | Backend de la aplicación |
| PostgreSQL / pgvector | `5432` | Base de datos |

### 4.6. Comandos útiles

```bash
# Detener servicios (conserva datos)
docker compose down

# Detener y borrar datos
docker compose down -v

# Ver logs en vivo
docker compose logs -f

# Reconstruir solo la API
docker compose build api

# Acceder al contenedor
docker compose exec api sh

# Verificar que la IA está activa
curl http://localhost:8000/api/v1/ai-status
```

---

## 5. Instalación Manual (sin Docker)

Usa este método si no puedes o no quieres usar Docker.

### 5.1. Requisitos previos

- Python 3.11+ instalado
- PostgreSQL 15+ con extensión pgvector instalada y corriendo
- Git

### 5.2. Pasos de instalación

```bash
# 1. Clonar
git clone <url-del-repositorio>
cd MVPFinalUltimoTodoListoDefinitivoIAA

# 2. Entorno virtual
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# .\venv\Scripts\Activate.ps1  # Windows

# 3. Instalar backend
cd backend
pip install -e ".[ai]"    # con IA (embeddings + LLM)
# O pip install -e .      # solo base (sin embeddings locales)

# 4. Crear .env con la conexión a BD
cat > .env << EOF
DATABASE_URL=postgresql+psycopg://perfil:perfil@localhost:5432/perfil_egreso
EMBEDDING_DEVICE=auto
EOF

# 5. Iniciar PostgreSQL con pgvector (usa Docker solo para la base de datos)
docker compose up -d db

# 6. Iniciar la API
uvicorn app.main:app --reload --port 8000
```

Abre `index.html` en tu navegador.

---

## 6. Estructura del proyecto

```
MVPFinalUltimoTodoListoDefinitivoIAA/
├── index.html              # Frontend (interfaz web)
├── app.js                  # Frontend (lógica)
├── styles.css              # Frontend (estilos)
├── docker-compose.yml      # Orquestación Docker
│
├── backend/
│   ├── Dockerfile          # Imagen Docker del backend
│   ├── pyproject.toml      # Dependencias Python
│   ├── .env                # Configuración local (crear desde .env.example)
│   ├── .env.example        # Plantilla de configuración
│   │
│   ├── app/                # Código fuente
│   │   ├── main.py         # Punto de entrada FastAPI
│   │   ├── api/routes/     # Endpoints REST
│   │   ├── services/       # Lógica de negocio
│   │   ├── db/             # Modelos y conexión BD
│   │   ├── schemas/        # Validación de datos
│   │   └── core/           # Configuración y seguridad
│   │
│   ├── scripts/            # Utilidades
│   ├── tests/              # Pruebas
│   ├── storage/            # Archivos subidos
│   └── logs/               # Registros del servidor
│
├── matrices_tributacion/   # Matrices curriculares de ejemplo
└── docs/                   # Documentación
    ├── MANUAL_USUARIO.md
    └── MANUAL_INSTALACION.md
```

---

## 7. Verificación de la instalación

```bash
# Health check básico
curl http://localhost:8000/api/v1/health
# → {"status":"ok","database":"connected",...}

# Estado del motor de IA
curl http://localhost:8000/api/v1/ai-status
# → {"provider":"sentence-transformers","device":"auto",
#     "is_real_ai":true,...}
# Si device muestra "cuda" → GPU disponible y activa
# Si device muestra "cpu" → funciona en CPU (normal si no hay GPU)

# Swagger (documentación interactiva)
# Abrir http://localhost:8000/docs en el navegador
```

### Checklist

- [ ] `docker compose up --build` finaliza sin errores
- [ ] `http://localhost:8000/api/v1/health` responde `ok`
- [ ] `http://localhost:8000/api/v1/ai-status` muestra el modelo activo
- [ ] `http://localhost:8000/docs` abre Swagger UI
- [ ] Se puede cargar una matriz curricular
- [ ] Se puede crear un período académico
- [ ] Se pueden subir documentos
- [ ] Se puede ejecutar el análisis
- [ ] Se puede exportar un reporte Excel

---

## 8. Problemas frecuentes y soluciones

| Problema | Causa | Solución |
|----------|-------|----------|
| **Error de conexión a PostgreSQL** | BD no arrancó o URL incorrecta | Con Docker: `docker compose logs db`. Sin Docker: verifica que PostgreSQL esté activo. |
| **Error: extension vector not found** | pgvector no instalado | `CREATE EXTENSION vector;` en PostgreSQL. |
| **Error: libnvidia-ml.so.1 not found** | `docker-compose.yml` pide GPU (`gpus: all`) pero NVIDIA Container Toolkit no está instalado | Sigue [4.3.2](#432-linux-nativo-ubuntudebian) (Linux) o [4.3.3](#433-wsl2--docker-engine-dentro-de-wsl2) (WSL2) para instalarlo. O comenta `gpus: all`. |
| **Error: libdxcore.so: no such file or directory** | Estás en WSL2 + Docker Engine y falta `no-cgroups` en la config de NVIDIA | Sigue el paso extra de [4.3.3](#433-wsl2--docker-engine-dentro-de-wsl2): `sudo sed -i 's/#no-cgroups = false/no-cgroups = true/' /etc/nvidia-container-runtime/config.toml && sudo systemctl restart docker` |
| **CUDA out of memory** | GPU no tiene suficiente VRAM | Usa CPU: pon `EMBEDDING_DEVICE=cpu` en `.env`. |
| **sentence-transformers tarda mucho** | Primera descarga del modelo (~2 GB) | Es normal. Docker lo cachea en el volumen `huggingface_cache`. |
| **El frontend no conecta** | Backend no está en `localhost:8000` | Verifica que la API esté corriendo y en ese puerto. |
| **Los documentos se marcan "ocr_required"** | PDF escaneado, sin texto seleccionable | Usa PDF digital o DOCX en vez de escaneado. |
| **El análisis no comienza** | Documentos no terminaron de procesarse | Espera a que los documentos queden en estado `ready`. |
| **Error "No module named 'torch'"** | Dependencias de IA no instaladas (solo manual) | `pip install -e ".[ai]"` |
| **El token demo no funciona** | `DEMO_AUTH_ENABLED` en `false` | No debería pasar con la configuración por defecto. |

---

## 9. Mantenimiento

### Actualizar dependencias

```bash
cd backend
pip install -e ".[ai]" --upgrade
```

### Logs

```bash
# Con Docker
docker compose logs -f api

# Sin Docker
tail -f backend/logs/uvicorn.out.log
```

### Limpiar datos

```bash
# Con Docker (borra BD, archivos y caché)
docker compose down -v

# Sin Docker
rm -rf backend/storage/documents/*
```

### Cambiar modelo de embeddings

En `backend/.env`:

```env
EMBEDDING_MODEL_NAME=otro-modelo
EMBEDDING_DIMENSIONS=768
```

> Cambiar el modelo invalida todos los embeddings existentes.

---

*Fin del Manual de Instalación y Despliegue*
