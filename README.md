# Plataforma de Validacion del Perfil de Egreso

Aplicacion web para apoyar la validacion del perfil de egreso mediante analisis
automatico/asistido de tesis o memorias academicas. El sistema cruza documentos,
malla curricular, cursos, competencias y criterios de evaluacion para generar
evidencia textual trazable y resultados agregados en un dashboard.

## Que incluye

- Frontend web en `index.html`, `styles.css` y `app.js`.
- Backend FastAPI en `backend/app`.
- Carga de matrices curriculares desde `matrices_tributacion/` y desde la interfaz web.
- Subida de documentos PDF, DOCX o TXT.
- Extraccion de texto, segmentacion en chunks y generacion de embeddings.
- Analisis semantico de evidencia por criterio, curso y periodo academico.
- Dashboard con mapa de calor, KPI y detalle de evidencia recuperada.
- Modo demo: si el backend no esta disponible, el frontend puede abrirse igual con
  datos simulados.

## Requisitos

- Python 3.11 o superior.
- Docker Desktop, si se quiere usar PostgreSQL, Redis y MinIO con `docker compose`.
- GPU NVIDIA con controladores compatibles y acceso GPU habilitado en Docker para acelerar BGE.
- Navegador moderno.
- Dependencias IA locales con `sentence-transformers` para ejecutar embeddings BGE.
- Opcional: API key de Gemini u OpenAI para comentarios generados por LLM.

## Estructura del proyecto

| Ruta | Descripcion |
| --- | --- |
| `index.html` | Interfaz web principal. |
| `styles.css` | Estilos del dashboard. |
| `app.js` | Logica del frontend y conexion con la API. |
| `backend/app` | API FastAPI. |
| `backend/app/db/models.py` | Modelos de datos. |
| `backend/app/services` | Servicios de matriz, storage, embeddings, analisis y reportes. |
| `backend/app/api/routes` | Endpoints REST. |
| `backend/scripts` | Scripts de utilidad y migracion. |
| `docker-compose.yml` | Servicios locales: API, PostgreSQL/pgvector, Redis y MinIO. |
| `docs/ARCHITECTURE.md` | Resumen tecnico de arquitectura. |

## Uso rapido sin backend

Abre `index.html` directamente en el navegador. En este modo se puede revisar la
interfaz y el flujo general, pero no se procesan documentos reales.

## Ejecutar backend local con Python

Desde la raiz del repositorio:

```powershell
docker compose up -d db redis minio
```

Luego instala y ejecuta la API:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[ai]"
uvicorn app.main:app --reload --port 8000
```

En macOS/Linux, activa el entorno con:

```bash
source .venv/bin/activate
```

La documentacion interactiva queda disponible en:

```text
http://localhost:8000/docs
```

El frontend intenta conectarse por defecto a:

```text
http://localhost:8000/api/v1
```

## Ejecutar todo con Docker Compose

Desde la raiz del repositorio:

```powershell
docker compose up --build
```

La primera ejecucion descarga `BAAI/bge-m3`. Docker conserva esa descarga en el
volumen `huggingface_cache` para reutilizarla al recrear la API.
La API solicita la GPU NVIDIA del host y ejecuta BGE en CUDA. Puedes comprobarlo
consultando `/api/v1/ai-status`, que debe informar `device: cuda`.

Servicios principales:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- PostgreSQL/pgvector: `localhost:5432`
- Redis: `localhost:6379`
- MinIO Console: `http://localhost:9001`

## Configuracion

El backend usa PostgreSQL por defecto:

```text
postgresql+psycopg://perfil:perfil@localhost:5432/perfil_egreso
```

Puedes sobreescribir esta configuracion con variables de entorno o creando
`backend/.env`.

Ejemplo para comentarios con Gemini:

```env
LLM_COMMENTS_ENABLED=true
LLM_PROVIDER=gemini
GEMINI_API_KEY=tu_api_key
GEMINI_MODEL=gemini-2.0-flash
```

Tambien se puede usar OpenAI cambiando:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=tu_api_key
```

## Datos y almacenamiento

La aplicacion persiste metadatos y resultados en la base de datos. Los archivos
subidos no se guardan como blobs dentro de la BD; se almacenan en disco para evitar
inflarla:

```text
backend/storage/documents/{period_id}/{document_id}/archivo.pdf
```

La base guarda:

- `documents`: tesis o memorias registradas.
- `document_versions`: version del archivo, nombre original, ruta, checksum, MIME,
  paginas y calidad de extraccion.
- `processing_jobs`: estado de extraccion, chunking y embeddings.
- `document_chunks`: fragmentos textuales extraidos con pagina y offsets.
- `chunk_embeddings`: vector IA de cada fragmento.
- `evidence`: evidencia encontrada por criterio, curso y competencia.
- `evaluation_results`: resultados del analisis por celda de la matriz.

Para revisar el estado de la base:

```powershell
python backend\scripts\db_status.py
```

Para limitar la salida:

```powershell
python backend\scripts\db_status.py --limit 5
```

## Migracion desde SQLite

Si existe una base SQLite previa en:

```text
backend/data/app.db
```

puedes migrarla a PostgreSQL con:

```powershell
docker compose up -d db
python backend\scripts\migrate_sqlite_to_postgres.py --replace
```

Si las rutas de archivos guardadas en SQLite apuntan a otro equipo, usa rutas
relativas al repositorio o reemplaza el prefijo de storage por la ruta del entorno
actual. Ejemplo generico:

```powershell
python backend\scripts\migrate_sqlite_to_postgres.py --replace `
  --rewrite-file-uri-from "<ruta-antigua-del-repo>\backend\storage" `
  --rewrite-file-uri-to "<ruta-actual-del-repo>\backend\storage"
```

Si la API corre dentro de Docker, normalmente el destino debe apuntar al storage del
contenedor:

```powershell
python backend\scripts\migrate_sqlite_to_postgres.py --replace `
  --rewrite-file-uri-from "<ruta-antigua-del-repo>\backend\storage" `
  --rewrite-file-uri-to "/app/storage"
```

## Tokens demo

La API usa autenticacion demo mediante `Authorization: Bearer <token>`.

| Rol | Token |
| --- | --- |
| Estudiante | `demo-student` |
| Profesor guia | `demo-professor` |
| Evaluador | `demo-evaluator` |
| Administrador academico | `demo-academic-admin` |
| Administrador tecnico | `demo-tech-admin` |

## Endpoints principales

- `GET /api/v1/health`
- `GET /api/v1/auth/me`
- `GET /api/v1/curricula`
- `POST /api/v1/curricula`
- `GET /api/v1/curricula/current/matrix`
- `GET /api/v1/curricula/{id}/matrix`
- `GET /api/v1/periods`
- `POST /api/v1/periods`
- `POST /api/v1/documents`
- `GET /api/v1/documents/{id}/processing-status`
- `POST /api/v1/periods/{id}/analysis/run`
- `GET /api/v1/periods/{id}/analysis`
- `GET /api/v1/periods/{id}/analysis/cell-detail?course_id=...&competency_id=...`
- `GET /api/v1/evidence`
- `PATCH /api/v1/evidence/{id}`
- `GET /api/v1/reports`

## Estrategia IA

La implementacion inicial no entrena un modelo propio. Usa un pipeline reemplazable:

1. Validacion y almacenamiento del archivo.
2. Extraccion de texto desde PDF, DOCX o TXT.
3. Estado `ocr_required` cuando no hay texto seleccionable.
4. Segmentacion en chunks con pagina y offsets.
5. Embeddings semanticos locales con `BAAI/bge-m3` mediante Sentence-Transformers.
   La ejecucion normal exige que este proveedor pueda cargarse; el embedding hash
   queda reservado para pruebas o configuraciones explicitas de desarrollo.
6. Scoring hibrido: similitud vectorial, coincidencia lexica normalizada, frases
   clave y senales de secciones academicas.
7. Evidencia trazable por curso, competencia, criterio, documento, pagina y fragmento.
8. Reporte agregado por periodo.

Modelo configurado por defecto:

```text
BAAI/bge-m3
```

Para instalar las dependencias IA:

```powershell
cd backend
python -m pip install -e ".[ai]"
```

Puedes verificar el proveedor activo en:

```text
http://localhost:8000/api/v1/ai-status
```

Una ejecucion lista para analisis debe informar `provider: sentence-transformers`,
`model: BAAI/bge-m3` e `is_real_ai: true`.

## Comentarios generados por LLM

El detalle trazable de cada celda puede redactarse con Gemini u OpenAI si se define
una API key. La API no envia tesis completas para generar comentarios; solo envia el
contexto minimo de la celda seleccionada: curso, competencia, criterio, score,
confianza, fragmento recuperado, documento y pagina.

Si no hay API key, si el SDK no esta instalado o si la llamada falla, el sistema vuelve
automaticamente al comentario local trazable.

## Limitaciones actuales

- OCR real aun debe integrarse con Tesseract, Azure Document Intelligence, AWS
  Textract o equivalente.
- La calidad academica debe validarse con una muestra historica revisada por
  profesores o evaluadores.
- Los umbrales de evidencia deben calibrarse con datos reales.

## Proximos pasos recomendados

- Agregar migraciones Alembic.
- Integrar OCR efectivo.
- Reemplazar `BackgroundTasks` por Celery/RQ si aumenta el volumen.
- Implementar eliminacion y versionado completo desde el frontend.
- Calibrar umbrales con memorias historicas revisadas por humanos.
- Agregar pruebas automaticas de extraccion, chunking, scoring y permisos.
