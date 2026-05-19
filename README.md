# Plataforma de Validación del Perfil de Egreso

Este proyecto contiene un frontend de referencia y una primera base backend para una
plataforma de revisión automática/asistida de memorias académicas. El objetivo es medir
trazabilidad entre documentos, malla curricular, cursos, competencias y criterios
académicos, conservando evidencia textual auditable.

## Estado actual

- `index.html`, `styles.css` y `app.js` mantienen el mockup navegable original.
- El frontend ahora intenta conectarse a `http://localhost:8000/api/v1`.
- Si la API no está disponible, el frontend sigue funcionando con datos simulados.
- `backend/app` implementa una API FastAPI modular.
- La matriz curricular se carga desde `Matriz Tributación PE 2025 COMPUTACION.xlsx`.
- La API permite subir documentos PDF, DOCX o TXT, extraer texto, generar chunks,
  crear embeddings locales, calcular evidencia y exponer resultados para dashboard.

## Estructura

| Ruta | Descripción |
| --- | --- |
| `index.html` | Interfaz web base. |
| `styles.css` | Estilos visuales del mockup. |
| `app.js` | Interacción frontend y conexión opcional con API. |
| `backend/app` | Backend FastAPI. |
| `backend/app/db/models.py` | Modelo de datos inicial. |
| `backend/app/services` | Carga de matriz, storage, embeddings, procesamiento y análisis. |
| `backend/app/api/routes` | Endpoints REST. |
| `docker-compose.yml` | Entorno local con API, PostgreSQL/pgvector, Redis y MinIO. |
| `docs/ARCHITECTURE.md` | Resumen técnico de arquitectura. |

## Ejecutar solo el frontend

Abre `index.html` directamente en el navegador. Si no hay backend levantado, se usa el
modo mockup con datos simulados.

## Ejecutar backend local con Python

Abre Docker Desktop y levanta primero PostgreSQL:

```powershell
docker compose up -d db redis minio
```

Luego ejecuta la API:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
uvicorn app.main:app --reload --port 8000
```

Luego abre:

```text
http://localhost:8000/docs
```

El backend usa PostgreSQL por defecto:

```text
postgresql+psycopg://perfil:perfil@localhost:5432/perfil_egreso
```

Al iniciar, crea las tablas necesarias y siembra usuarios demo, períodos y la matriz
curricular real desde el XLSX.

## Base de datos de tesis subidas

La aplicacion persiste las tesis subidas en PostgreSQL. La SQLite antigua queda solo
como respaldo/migracion:

```text
backend/data/app.db
```

Los archivos completos no se guardan como blobs dentro de la base; se guardan en disco
para evitar inflar la BD:

```text
backend/storage/documents/{period_id}/{document_id}/archivo.pdf
```

La base guarda los metadatos y trazabilidad:

- `documents`: tesis/memorias registradas.
- `document_versions`: version del archivo, nombre original, ruta, checksum, MIME,
  paginas y calidad de extraccion.
- `processing_jobs`: estado de extraccion, chunking y embeddings.
- `document_chunks`: fragmentos textuales extraidos con pagina y offsets.
- `chunk_embeddings`: vector IA de cada fragmento.
- `evidence`: evidencia encontrada por criterio, curso y competencia.
- `evaluation_results`: resultados del analisis por celda de la matriz.

Para inicializar la base y revisar que tesis quedaron guardadas:

```powershell
python backend\scripts\db_status.py
```

Tambien puedes limitar el listado:

```powershell
python backend\scripts\db_status.py --limit 5
```

Cada subida desde la interfaz llama a `POST /api/v1/documents`; ese endpoint crea el
registro en `documents`, guarda una version en `document_versions`, copia el archivo al
storage local y deja un job de procesamiento asociado.

Para migrar los datos existentes desde SQLite a PostgreSQL:

```powershell
docker compose up -d db
python backend\scripts\migrate_sqlite_to_postgres.py --replace
```

Luego puedes inspeccionar PostgreSQL con:

```powershell
python backend\scripts\db_status.py --limit 5
```

Si ejecutas la API dentro de Docker y quieres reutilizar archivos migrados desde Windows,
reescribe las rutas de storage durante la migracion:

```powershell
python backend\scripts\migrate_sqlite_to_postgres.py --replace `
  --rewrite-file-uri-from "C:\Users\Studying\Desktop\IAAPLICADA\backend\storage" `
  --rewrite-file-uri-to "/app/storage"
```

## Ejecutar con Docker Compose

```powershell
docker compose up --build
```

Servicios principales:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- PostgreSQL/pgvector: `localhost:5432`
- Redis: `localhost:6379`
- MinIO Console: `http://localhost:9001`

## Tokens demo

La API usa autenticación demo mediante `Authorization: Bearer <token>`.

| Rol | Token |
| --- | --- |
| Estudiante | `demo-student` |
| Profesor guía | `demo-professor` |
| Evaluador | `demo-evaluator` |
| Administrador académico | `demo-academic-admin` |
| Administrador técnico | `demo-tech-admin` |

## Endpoints clave

- `GET /api/v1/health`
- `GET /api/v1/auth/me`
- `GET /api/v1/curricula/current/matrix`
- `GET /api/v1/periods`
- `POST /api/v1/periods`
- `POST /api/v1/documents`
- `GET /api/v1/documents/{id}/processing-status`
- `POST /api/v1/periods/{id}/analysis/run`
- `GET /api/v1/periods/{id}/analysis`
- `GET /api/v1/periods/{id}/analysis/cell-detail?course_id=...&competency_id=...`
- `GET /api/v1/evidence`
- `GET /api/v1/reports`

## Estrategia IA implementada

La implementación inicial no entrena un modelo. Usa un pipeline reemplazable:

1. Validación y almacenamiento del archivo.
2. Extracción de texto desde PDF, DOCX o TXT.
3. Estado `ocr_required` cuando no hay texto seleccionable.
4. Segmentación en chunks con página y offsets.
5. Embeddings reales con Sentence-Transformers cuando el extra IA está instalado.
   Si no está disponible, cae a embeddings locales determinísticos para desarrollo.
6. Scoring híbrido: similitud vectorial, coincidencia léxica normalizada,
   frases clave y señales de secciones académicas.
7. Evidencia trazable por curso, competencia, criterio, documento, página y fragmento.
8. Reporte agregado por período.

El modelo configurado por defecto es:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Para instalar la IA local:

```powershell
cd backend
python -m pip install -e ".[ai]"
```

Puedes verificar qué proveedor está activo en:

```text
http://localhost:8000/api/v1/ai-status
```

## Comentarios con API key de Gemini

El detalle trazable de cada celda puede redactarse con Gemini si defines una API key en
`backend/.env`:

```env
LLM_COMMENTS_ENABLED=true
LLM_PROVIDER=gemini
GEMINI_API_KEY=tu_api_key
GEMINI_MODEL=gemini-2.0-flash
```

Tambien puedes volver a OpenAI cambiando `LLM_PROVIDER=openai` y definiendo
`OPENAI_API_KEY`.

La API no recibe tesis completas para generar el comentario. Solo recibe el contexto
minimo de la celda seleccionada: curso, competencia, criterio, score, confianza,
fragmento recuperado, documento y pagina. Si no hay key, si el SDK no esta instalado o
si la llamada falla, el sistema vuelve automaticamente al comentario local trazable.

OCR real todavía debe agregarse con Tesseract, Azure Document Intelligence, AWS Textract
o equivalente.

## Calidad del modelo actual

El sistema ya no depende solo del embedding demo si `sentence-transformers` está instalado.
Usa embeddings multilingües reales y un ranker híbrido que reduce falsos positivos porque
exige más señales textuales explícitas antes de considerar un fragmento como evidencia
fuerte. Aun así, para afirmar calidad académica se requiere una muestra de memorias
históricas con evidencia validada por profesores/evaluadores.

## Próximos pasos recomendados

- Agregar migraciones Alembic.
- Añadir OCR efectivo.
- Reemplazar BackgroundTasks por Celery/RQ cuando aumente el volumen.
- Implementar eliminación/versionado completo desde frontend.
- Calibrar umbrales con memorias históricas revisadas por humanos.
- Agregar pruebas automáticas de extracción, chunking, scoring y permisos.
