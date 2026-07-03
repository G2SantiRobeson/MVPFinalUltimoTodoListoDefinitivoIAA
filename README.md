# Plataforma de Validacion del Perfil de Egreso

Aplicacion web para apoyar la validacion del perfil de egreso mediante analisis
documental de tesis, memorias o trabajos academicos. El sistema cruza documentos,
mallas curriculares, cursos, competencias y criterios de evaluacion para generar
evidencia textual trazable, un mapa de calor y reportes agregados.

## Checklist de entrega

Este repositorio contiene el codigo fuente completo del proyecto:

- Frontend web: `index.html`, `styles.css`, `app.js`.
- Backend FastAPI: `backend/app`.
- Dependencias Python declaradas en `backend/pyproject.toml`.
- Orquestacion local con Docker: `docker-compose.yml` y `backend/Dockerfile`.
- Plantilla de variables de entorno: `backend/.env.example`.
- Manuales complementarios: `docs/MANUAL_INSTALACION.md`, `docs/MANUAL_USUARIO.md` y `docs/ARCHITECTURE.md`.
- Pruebas automatizadas: `backend/tests`.

## Que incluye

- Carga de matrices curriculares desde `matrices_tributacion/` o desde la interfaz.
- Creacion de periodos academicos asociados a una matriz curricular.
- Subida de documentos PDF, DOCX y TXT.
- Extraccion de texto, segmentacion en fragmentos y generacion de embeddings.
- Embeddings semanticos locales con `BAAI/bge-m3` mediante Sentence-Transformers.
- Analisis hibrido por similitud vectorial, coincidencia lexica y senales academicas.
- Mapa de calor por ramo y competencia.
- Detalle trazable por celda, con fragmentos, documento y pagina.
- Revision manual de evidencias.
- Indicadores por periodo y por competencia.
- Exportacion de reportes Excel.

## Dependencias necesarias

### Requisitos base

- Docker Desktop 24+ o Docker Engine 24+ con Docker Compose.
- Navegador moderno: Chrome, Edge o Firefox.
- Git, si se clona desde repositorio.

### Servicios usados por Docker Compose

- API FastAPI.
- PostgreSQL con pgvector.
- Volumen `huggingface_cache` para conservar la descarga del modelo `BAAI/bge-m3`.

### Dependencias Python del backend

Las dependencias se declaran en `backend/pyproject.toml`.

Dependencias principales:

- `fastapi`
- `uvicorn[standard]`
- `pydantic-settings`
- `SQLAlchemy`
- `python-multipart`
- `pypdf`
- `python-docx`
- `psycopg[binary]`
- `pgvector`
- `XlsxWriter`

Dependencias IA opcionales para instalacion manual:

- `sentence-transformers`
- `openai`
- `google-genai`

La imagen Docker instala PyTorch con soporte CUDA desde el indice oficial de
PyTorch y luego instala el extra `.[ai]`.

### GPU

El sistema puede funcionar en CPU o GPU:

- Por defecto, `EMBEDDING_DEVICE=auto` detecta CUDA si el contenedor tiene acceso a GPU; si no, usa CPU.
- El `docker-compose.yml` trae `gpus: all` activo para usar GPU NVIDIA cuando el entorno lo soporta.
- Si no tienes GPU NVIDIA o Docker falla al solicitar GPU, comenta o elimina `gpus: all`; el backend seguirá funcionando en CPU.
- En Windows con Docker Desktop normalmente basta con tener drivers NVIDIA y WSL2 habilitado.
- En Linux nativo o Docker Engine dentro de WSL2 puede ser necesario instalar NVIDIA Container Toolkit.

## Instalacion recomendada con Docker

Desde la raiz del proyecto:

```powershell
docker compose up --build
```

La primera ejecucion puede tardar porque descarga imagenes Docker, dependencias
CUDA/PyTorch y el modelo `BAAI/bge-m3`. La descarga del modelo queda persistida
en el volumen `huggingface_cache`.

Servicios principales:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

Para detener los servicios sin borrar datos:

```powershell
docker compose down
```

Para borrar tambien datos y volumenes:

```powershell
docker compose down -v
```

## Activar GPU NVIDIA

1. Verifica que Windows o el host vea la GPU:

```powershell
nvidia-smi
```

2. En `docker-compose.yml`, deja activa la línea:

```yaml
gpus: all
```

Si no tienes GPU NVIDIA, comenta o elimina esa línea antes de levantar Docker.

3. Reconstruye y levanta la API:

```powershell
docker compose up --build
```

4. Verifica el dispositivo activo:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/ai-status
```

Resultado esperado con GPU:

```json
{
  "provider": "sentence-transformers",
  "model": "BAAI/bge-m3",
  "device": "cuda",
  "is_real_ai": true
}
```

Resultado esperado sin GPU:

```json
{
  "provider": "sentence-transformers",
  "model": "BAAI/bge-m3",
  "device": "cpu",
  "is_real_ai": true
}
```

## Instalacion manual del backend

Usa esta opcion solo si no quieres ejecutar la API dentro de Docker.

1. Levanta PostgreSQL con pgvector:

```powershell
docker compose up -d db
```

2. Crea entorno virtual:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instala dependencias:

```powershell
python -m pip install -e ".[ai]"
```

4. Crea configuracion local si necesitas cambiar valores:

```powershell
Copy-Item .env.example .env
```

5. Ejecuta la API:

```powershell
uvicorn app.main:app --reload --port 8000
```

## Configuracion

El backend lee variables desde `backend/.env` y desde el entorno.

Variables utiles:

| Variable | Uso | Valor por defecto |
| --- | --- | --- |
| `DATABASE_URL` | Conexion PostgreSQL | `postgresql+psycopg://perfil:perfil@localhost:5432/perfil_egreso` |
| `MATRICES_DIR` | Carpeta de matrices curriculares | `matrices_tributacion` |
| `EMBEDDING_PROVIDER` | Proveedor de embeddings | `bge-m3` |
| `EMBEDDING_MODEL_NAME` | Modelo semantico | `BAAI/bge-m3` |
| `EMBEDDING_DEVICE` | `auto`, `cpu` o `cuda` | `auto` |
| `LLM_PROVIDER` | `gemini` u `openai` | `gemini` |
| `GEMINI_API_KEY` | API key para comentarios Gemini | vacio |
| `OPENAI_API_KEY` | API key para comentarios OpenAI | vacio |

Los comentarios LLM son opcionales. Sin API key, el sistema sigue funcionando con
comentarios locales trazables.

## Uso rapido

1. Levanta el backend con Docker.
2. Abre `index.html` en el navegador.
3. Carga una matriz curricular desde la seccion de mallas.
4. Crea un periodo academico asociado a esa matriz.
5. Sube documentos PDF, DOCX o TXT.
6. Espera a que terminen de procesarse.
7. Ejecuta el analisis.
8. Revisa el mapa de calor, evidencias e indicadores.
9. Exporta el reporte Excel si necesitas respaldo.

## Verificacion

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
```

Estado de IA:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/ai-status
```

Pruebas del backend:

```powershell
cd backend
pytest
```

## Estructura del proyecto

```text
MVPFinalUltimoTodoListoDefinitivoIAA/
|-- index.html
|-- app.js
|-- styles.css
|-- docker-compose.yml
|-- backend/
|   |-- Dockerfile
|   |-- pyproject.toml
|   |-- .env.example
|   |-- app/
|   |   |-- main.py
|   |   |-- api/routes/
|   |   |-- core/
|   |   |-- db/
|   |   |-- schemas/
|   |   `-- services/
|   |-- scripts/
|   `-- tests/
|-- docs/
|   |-- ARCHITECTURE.md
|   |-- MANUAL_INSTALACION.md
|   `-- MANUAL_USUARIO.md
`-- matrices_tributacion/
```

## Comentarios relevantes en el codigo

El codigo incluye comentarios y docstrings en los puntos que concentran la logica
del sistema:

- `backend/app/services/embeddings.py`: explica el proveedor BGE, el fallback local,
  la seleccion de dispositivo (`auto`, `cpu`, `cuda`) y el metodo `embed`.
- `backend/app/services/analysis.py`: documenta la orquestacion del analisis por
  periodo, scoring y detalle trazable por celda.
- `backend/app/services/document_processing.py`: documenta extraccion, chunking y
  generacion de embeddings por documento.
- `backend/app/services/llm_comments.py`: documenta el uso opcional de Gemini/OpenAI
  para comentarios, sin enviar documentos completos.
- `docker-compose.yml`: contiene comentarios para activar GPU solo cuando el entorno
  tenga soporte NVIDIA.
- `backend/Dockerfile`: documenta la instalacion de PyTorch CUDA y dependencias IA.

## Endpoints principales

- `GET /api/v1/health`
- `GET /api/v1/ai-status`
- `GET /api/v1/auth/me`
- `GET /api/v1/curricula`
- `POST /api/v1/curricula`
- `GET /api/v1/curricula/current/matrix`
- `GET /api/v1/periods`
- `POST /api/v1/periods`
- `POST /api/v1/documents`
- `GET /api/v1/documents/{id}/processing-status`
- `POST /api/v1/periods/{id}/analysis/run`
- `GET /api/v1/periods/{id}/analysis`
- `GET /api/v1/periods/{id}/analysis/cell-detail`
- `GET /api/v1/evidence`
- `PATCH /api/v1/evidence/{id}`
- `GET /api/v1/reports`

## Datos y almacenamiento

Los documentos subidos se almacenan en:

```text
backend/storage/documents/{period_id}/{document_id}/archivo.pdf
```

La base de datos guarda documentos, versiones, chunks, embeddings, evidencias,
resultados de evaluacion y revisiones manuales.

## Limitaciones actuales

- OCR real aun no esta integrado; los PDF escaneados se marcan como `ocr_required`.
- Los umbrales de evidencia deben calibrarse con datos historicos revisados por humanos.
- Los comentarios LLM requieren API key externa.
- Para alto volumen se recomienda reemplazar `BackgroundTasks` por Celery o RQ.
- El sistema usa autenticacion demo; para produccion se debe integrar SSO institucional.

## Manuales complementarios

- `docs/MANUAL_INSTALACION.md`: instalacion, GPU, variables de entorno y problemas frecuentes.
- `docs/MANUAL_USUARIO.md`: flujo de uso para usuarios finales.
- `docs/ARCHITECTURE.md`: componentes y arquitectura tecnica.
