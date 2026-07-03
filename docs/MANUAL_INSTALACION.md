# Manual de Instalación y Despliegue

## Plataforma de Validación del Perfil de Egreso

---

| Versión | Fecha | Descripción |
|---------|-------|-------------|
| 1.2     | 2026-06 | Versión reestructurada — pasos detallados multiplataforma (Linux, WSL2, Windows) |

---

## Índice

1. [Introducción y requisitos](#1-introducción-y-requisitos)
2. [⭐ Quick Start](#2--quick-start)
3. [Variables de entorno (`.env`)](#3-variables-de-entorno-env)
   - 3.1. Dónde crear el archivo
   - 3.2. Tabla de variables
   - 3.3. Ejemplo completo
4. [Instalación con Docker Compose (detallado)](#4-instalación-con-docker-compose-detallado)
   - 4.1. Requisitos previos
   - 4.2. Pasos detallados
   - 4.3. GPU (solo si tienes GPU NVIDIA)
   - 4.4. Iniciar servicios
   - 4.5. Servicios levantados
   - 4.6. Comandos útiles
5. [Instalación Manual (sin Docker)](#5-instalación-manual-sin-docker)
   - 5.1. Requisitos previos
   - 5.2. Preparar la base de datos
   - 5.3. Pasos de instalación
   - 5.4. Alternativa mixta
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
| Sistema | Windows 10+ (con WSL2), Ubuntu 22.04+, Debian 12+, macOS 12+ |
| RAM | 8 GB (16 GB+ recomendado para ejecutar junto con el modelo de IA) |
| Disco | 15 GB libres (~2 GB para el modelo de embeddings, ~5 GB para imágenes Docker) |
| Docker | Docker Desktop 4.24+ o Docker Engine 24+ con Compose plugin |
| Python | 3.11+ (solo para instalación manual sin Docker) |

### ¿CPU o GPU?

El backend usa `EMBEDDING_DEVICE=auto`: si Docker expone una GPU NVIDIA, los embeddings usan CUDA; si no, usan CPU.

El `docker-compose.yml` del repositorio trae `gpus: all` activo para acelerar el procesamiento cuando el entorno lo soporta. Si tu equipo no tiene GPU NVIDIA o Docker falla al solicitar GPU, comenta o elimina esa línea y el sistema funcionará en CPU.

> **Atención:** El `docker-compose.yml` viene con `gpus: all` activado por defecto.
> Si **no** tienes GPU NVIDIA, debes **comentar o eliminar** esa línea en
> `docker-compose.yml` (línea 10) antes de ejecutar `docker compose up`,
> de lo contrario Docker fallará al intentar reservar una GPU inexistente.

### Servicios que componen el sistema

| Servicio | Rol | Imagen Docker |
|----------|-----|---------------|
| **API** (FastAPI) | Backend principal, orquesta el análisis | Construida desde `backend/Dockerfile` |
| **PostgreSQL + pgvector** | Base de datos con extension vectorial | `pgvector/pgvector:pg16` |
| **Redis** | Caché y cola de tareas | `redis:7-alpine` |
| **MinIO** | Almacenamiento de documentos subidos | `minio/minio:latest` |

---

## 2. ⭐ Quick Start

Tres pasos rápidos para tener el sistema funcionando.

### Paso 1: Prepara el entorno (requisitos)

**Identifica tu plataforma:**

| Plataforma | Requisito mínimo |
|-----------|-----------------|
| **Windows** | Docker Desktop 4.24+ con WSL2 backend, o Docker Engine dentro de WSL2 |
| **WSL2 (Ubuntu 22.04/24.04)** | Docker Engine 24+ con Docker Compose plugin |
| **Linux (Ubuntu 22.04+ / Debian 12+)** | Docker Engine 24+ con Docker Compose plugin |
| **Otros Linux / macOS** | Docker Engine 24+ o Docker Desktop |

**Verifica tu GPU (opcional):**

El sistema funciona en CPU sin problemas. Si quieres aceleración y tienes GPU NVIDIA:

```bash
nvidia-smi
```

Si ves información de tu GPU, puedes activar soporte GPU. Si no, no pasa nada.

> **Importante:** El archivo `docker-compose.yml` viene con `gpus: all` ACTIVADO por defecto.
> Si **no** tienes GPU NVIDIA, debes **comentar o eliminar** esa línea antes de iniciar
> (ver sección [4.3](#43-gpu-solo-si-tienes-gpu-nvidia)).

### Paso 2: Configura las variables de entorno (opcional)

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

# (Opcional) Si NO tienes GPU NVIDIA, comenta `gpus: all` en docker-compose.yml
# antes de continuar (ver sección 4.3)

# Inicia todos los servicios
docker compose up --build
```

La primera ejecución descarga PostgreSQL con pgvector, construye la imagen del backend y descarga el modelo de IA `BAAI/bge-m3` (~2 GB). Esto toma unos minutos.

**En WSL2**, ejecuta el comando desde la terminal de WSL2 (Ubuntu), no desde PowerShell.

### Una vez levantado: Abre la aplicación

1. Abre `index.html` en tu navegador (doble clic o arrastra al navegador).
   - **En WSL2:** puedes abrirlo desde Windows. `index.html` está accesible en `\\wsl.localhost\Ubuntu\...` o copia la ruta con `wslpath -w $(pwd)/index.html`.
2. Carga una matriz curricular: ve a "Mallas cargadas", selecciona un archivo Excel de `matrices_tributacion/`.
3. Crea un período académico (ej: `2026-1`).
4. Sube una tesis (PDF, DOCX o TXT).
5. Espera a que se procese (verás el progreso en la interfaz).
6. Haz clic en **Analizar con API**.
7. Explora el heatmap, las evidencias y los KPIs.

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

### 4.1. Requisitos previos por plataforma

#### Windows + Docker Desktop

| Requisito | Instalación |
|-----------|-------------|
| **Git** | Descargar desde https://git-scm.com/download/win (incluye Git Bash) |
| **Docker Desktop** | Descargar desde https://www.docker.com/products/docker-desktop/ |
| **WSL2** | Docker Desktop instala y configura WSL2 automáticamente; si no, ejecuta `wsl --install` en PowerShell (Admin) |

> **Importante:** Docker Desktop debe estar configurado con **WSL2 backend**
> (Settings → General → "Use WSL 2 based engine"). Verifica que el motor esté
> en ejecución (icono de Docker en la bandeja del sistema, debe estar sólido,
> no en blanco y negro).

> **Rendimiento:** Clona el repositorio dentro del sistema de archivos de WSL2
> (`\\wsl.localhost\Ubuntu\home\<tu-usuario>\`) para mejor rendimiento de E/S.
> Si clonas en `C:\Users\...` (NTFS), funciona pero es más lento.

#### WSL2 (Ubuntu 22.04/24.04) + Docker Engine nativo

| Requisito | Comando de instalación |
|-----------|------------------------|
| **WSL2** | `wsl --install -d Ubuntu-24.04` (desde PowerShell Admin) |
| **Docker Engine** | `curl -fsSL https://get.docker.com | sh` (dentro de WSL2) |
| **Git** | `sudo apt install -y git` (dentro de WSL2) |

#### Linux (Ubuntu 22.04+ / Debian 12+)

| Requisito | Comando de instalación |
|-----------|------------------------|
| **Docker Engine + Compose** | `curl -fsSL https://get.docker.com | sh` |
| **Git** | `sudo apt install -y git` |
| **Permisos Docker** | `sudo usermod -aG docker $USER && newgrp docker` |

### 4.2. Pasos detallados

```bash
# 1. Clonar el repositorio
git clone https://github.com/G2SantiRobeson/MVPFinalUltimoTodoListoDefinitivoIAA.git
cd MVPFinalUltimoTodoListoDefinitivoIAA

# 2. (Opcional) Crear .env para API key de LLM
cp backend/.env.example backend/.env
# Editar backend/.env con nano, vim, VS Code, etc.

# 3. (IMPORTANTE) Verificar configuración de GPU
#    docker-compose.yml línea 10 tiene gpus: all ACTIVADO por defecto.
#    Si NO tienes GPU NVIDIA → comenta o borra esa línea ahora:
#    nano docker-compose.yml → # gpus: all
```

### 4.3. GPU (solo si tienes GPU NVIDIA)

Si quieres acelerar los embeddings con tu GPU, sigue los pasos según tu entorno.
**Si no tienes GPU o no te interesa, revisa [4.3.4](#434-revisar-gpus-all-en-docker-composeyml) para comentar `gpus: all` y luego salta a [4.4. Iniciar servicios](#44-iniciar-servicios).**

> **¿No sabes qué entorno tienes?** Preguntas guía:
> - ¿Instalaste Docker desde docker.com? → **Docker Desktop**
> - ¿Instalaste Docker con `sudo apt install docker` o `curl get.docker.com`? → **Docker Engine**
> - ¿Estás en WSL2? Ejecuta `wsl.exe --status` en PowerShell o revisa si
>   `cat /proc/version` menciona "Microsoft"

#### 4.3.1. Windows + Docker Desktop

No necesitas instalar nada extra. Docker Desktop para Windows ya incluye el
soporte GPU si cumples todo esto:

**Listo, salta a [4.3.4](#434-revisar-gpus-all-en-docker-composeyml).**

#### 4.3.2. Linux nativo (Ubuntu/Debian)

Primero verifica que tienes drivers NVIDIA instalados:

```bash
nvidia-smi
# Si sale "command not found", instala los drivers:
# sudo ubuntu-drivers autoinstall && sudo reboot
```

Luego instala NVIDIA Container Toolkit:

```bash
# 1. Agregar clave GPG de NVIDIA
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# 2. Agregar repositorio del toolkit
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 3. Instalar el toolkit
sudo apt update && sudo apt install -y nvidia-container-toolkit

# 4. Reiniciar Docker
sudo systemctl restart docker
```

**En Fedora / RHEL / Arch:** Consulta la documentación oficial:
https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html

#### 4.3.3. WSL2 + Docker Engine (dentro de WSL2, sin Docker Desktop)

> ⚠️ **No sigas esto si usas Docker Desktop.** Esta sección es solo para
> quienes instalaron Docker Engine directamente dentro de WSL2.

Sigue los 4 pasos de Linux nativo (arriba) y **además** agrega esta
configuracion necesaria para WSL2:

```bash
# Configurar no-cgroups (obligatorio en WSL2)
sudo sed -i 's/#no-cgroups = false/no-cgroups = true/' /etc/nvidia-container-runtime/config.toml
sudo systemctl restart docker
```

Sin este paso, Docker fallará con `libdxcore.so: no such file or directory`
al iniciar contenedores con GPU.

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

**Tiempo estimado (primera vez):**
| Conexión | Tiempo |
|----------|--------|
| Fibra óptica (100+ Mbps) | 3-8 min |
| ADSL/LTE | 15-30 min |
| Ejecuciones posteriores | 10-30 seg |

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

Usa este método si no puedes o no quieres usar Docker. Requiere instalar y
configurar cada servicio por separado.

### 5.1. Requisitos previos

- Python 3.11+ instalado
- PostgreSQL 15+ con extensión pgvector instalada y corriendo
- Git

**Linux / macOS / WSL2:**

```bash
# 1. Clonar
git clone https://github.com/G2SantiRobeson/MVPFinalUltimoTodoListoDefinitivoIAA.git
cd MVPFinalUltimoTodoListoDefinitivoIAA

# 2. Entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar backend con todas las dependencias de IA
cd backend
pip install -e ".[ai]"

# 4. Crear .env con la conexión a BD
cat > .env << 'EOF'
DATABASE_URL=postgresql+psycopg://perfil:perfil@localhost:5432/perfil_egreso
EMBEDDING_DEVICE=auto
LOG_LEVEL=INFO
EOF

# 5. Iniciar PostgreSQL con pgvector (usa Docker solo para la base de datos)
docker compose up -d db

# 2. Entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Instalar backend con todas las dependencias de IA
cd backend
pip install -e ".[ai]"

# 4. Crear .env con la conexión a BD
@"
DATABASE_URL=postgresql+psycopg://perfil:perfil@localhost:5432/perfil_egreso
EMBEDDING_DEVICE=auto
LOG_LEVEL=INFO
"@ | Out-File -FilePath .env -Encoding utf8

# 5. Iniciar PostgreSQL y Redis (deben estar instalados como servicios de Windows)
#    Normalmente ya arrancan automáticamente al iniciar Windows

# 6. Inicializar la base de datos
cd ..
python -c "from app.db.init_db import init_database; from app.db.session import SessionLocal; init_database(next(SessionLocal()))"

# 7. Iniciar la API
cd backend
uvicorn app.main:app --reload --port 8000
```

### 5.4. Alternativa mixta (backend fuera de Docker, servicios en Docker)

Si ya tienes Python pero no quieres instalar PostgreSQL y Redis nativos:

```bash
docker compose up -d db redis minio
```

Esto levanta solo los servicios de infraestructura. Luego sigue los pasos
5.3 desde el paso 2 (entorno virtual) para correr la API fuera del contenedor.

Abre `index.html` desde tu navegador (doble clic).

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

### 8.1. Docker / GPU

| Problema | Causa | Solución |
|----------|-------|----------|
| **Error: no available devices** | `gpus: all` activo pero no hay GPU NVIDIA | Comenta `gpus: all` en `docker-compose.yml` línea 10. |
| **Error: libnvidia-ml.so.1 not found** | `gpus: all` activo pero NVIDIA Container Toolkit no instalado | Sigue [4.3.2](#432-linux-nativo-ubuntudebian) (Linux) o [4.3.3](#433-wsl2--docker-engine-dentro-de-wsl2) (WSL2). O comenta `gpus: all`. |
| **Error: libdxcore.so: no such file or directory** | WSL2 + Docker Engine sin `no-cgroups` | `sudo sed -i 's/#no-cgroups = false/no-cgroups = true/' /etc/nvidia-container-runtime/config.toml && sudo systemctl restart docker` |
| **CUDA out of memory** | VRAM insuficiente para el modelo BGE-M3 | Usa CPU: `EMBEDDING_DEVICE=cpu` en `.env`. |
| **docker: 'compose' is not a command** | Docker Compose no está instalado como plugin | `sudo apt install docker-compose-plugin` o usa `docker compose` (con espacio). |
| **Permission denied al ejecutar docker** | Usuario no está en grupo docker | `sudo usermod -aG docker $USER && newgrp docker` |
| **Docker Desktop no inicia en Windows** | WSL2 no está instalado o desactualizado | `wsl --update` en PowerShell (Admin). |
| **WSL2: 'wsl: command not found'** | WSL no está habilitado en Windows | `wsl --install` en PowerShell (Admin). |

### 8.2. Base de datos

| Problema | Causa | Solución |
|----------|-------|----------|
| **Error de conexión a PostgreSQL** | BD no arrancó o URL incorrecta | Docker: `docker compose logs db`. Manual: verifica que PostgreSQL esté activo. |
| **Error: extension vector not found** | pgvector no instalado en PostgreSQL | `CREATE EXTENSION vector;` dentro de la BD. |
| **FATAL: role "perfil" does not exist** | Usuario de BD no creado | `sudo -u postgres psql -c "CREATE USER perfil WITH PASSWORD 'perfil';"` |
| **FATAL: database "perfil_egreso" does not exist** | Base de datos no creada | `sudo -u postgres psql -c "CREATE DATABASE perfil_egreso OWNER perfil;"` |

### 8.3. Aplicación / análisis

| Problema | Causa | Solución |
|----------|-------|----------|
| **sentence-transformers tarda mucho** | Primera descarga del modelo (~2 GB) | Normal. Docker lo cachea en `huggingface_cache`. Ejecuciones siguientes son rápidas. |
| **El frontend no conecta** | Backend no está en `localhost:8000` | Verifica que la API esté corriendo. Revisa `docker compose ps` o `curl localhost:8000/api/v1/health`. |
| **Los documentos se marcan "ocr_required"** | PDF escaneado, sin texto seleccionable | Usa PDF digital o DOCX en vez de escaneado. |
| **El análisis no comienza** | Documentos no terminaron de procesarse | Espera a que los documentos queden en estado `ready`. |
| **Error "No module named 'torch'"** | Dependencias de IA no instaladas (solo manual) | `pip install -e ".[ai]"` |
| **El token demo no funciona** | `DEMO_AUTH_ENABLED` en `false` | No debería pasar con la configuración por defecto. |

---

## 9. Mantenimiento

### Actualizar el repositorio

```bash
git pull origin main
docker compose up --build -d api   # reconstruye solo la API
```

### Actualizar dependencias Python (solo manual)

```bash
cd backend
pip install -e ".[ai]" --upgrade
```

### Logs

```bash
# Con Docker (todos los servicios)
docker compose logs -f

# Solo la API
docker compose logs -f api

# Solo la base de datos
docker compose logs -f db

# Sin Docker
tail -f backend/logs/uvicorn.out.log
# o
journalctl -u uvicorn -f  # si usas systemd
```

### Limpiar datos

```bash
# Con Docker (borra BD, archivos, caché y volúmenes)
docker compose down -v

# Sin Docker
rm -rf backend/storage/documents/*
# Para limpiar la BD: DROP DATABASE perfil_egreso; CREATE DATABASE perfil_egreso;
```

### Restaurar desde cero

Si el sistema queda en un estado inconsistente:

```bash
docker compose down -v
docker compose up --build
```

Esto borra todos los datos (BD, documentos subidos, caché del modelo) y
reconstruye todo desde cero.

### Cambiar modelo de embeddings

En `backend/.env`:

```env
EMBEDDING_MODEL_NAME=otro-modelo
EMBEDDING_DIMENSIONS=768
```

> Cambiar el modelo invalida todos los embeddings existentes y requiere
> reprocesar todos los documentos.

---

*Fin del Manual de Instalación y Despliegue*
