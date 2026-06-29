# Manual de Usuario

## Plataforma de Validación del Perfil de Egreso

---

| Versión | Fecha | Descripción |
|---------|-------|-------------|
| 1.0     | 2026-06 | Versión inicial |

---

## ⭐ Primeros pasos (recorrido rápido)

Sigue estos pasos para tu primera validación:

1. **Abre `index.html`** en tu navegador (Chrome, Firefox o Edge).
2. **Carga una matriz curricular**: en la sección "Mallas cargadas", sube un archivo Excel (usa uno de los ejemplos en `matrices_tributacion/`).
3. **Crea un período académico**: ingresa un nombre (ej: `2026-1`) y selecciona la matriz.
4. **Sube una tesis**: arrastra un archivo PDF o DOCX al área de carga.
5. **Ejecuta el análisis**: espera a que el documento se procese y haz clic en **Analizar con API**.
6. **Explora los resultados**: haz clic en las celdas del heatmap para ver la evidencia.

[SCREENSHOT: Los 6 pasos numerados en la interfaz]

> ¿Ya tienes el sistema instalado y funcionando? Entonces ve directo a estos pasos.
> ¿Necesitas instalarlo primero? Lee el [Manual de Instalación](MANUAL_INSTALACION.md).

---

## Índice

1. [Introducción](#1-introducción)
   - 1.1. Objetivo de la aplicación
   - 1.2. Público objetivo
   - 1.3. Requisitos para su utilización
2. [Acceso al Sistema](#2-acceso-al-sistema)
   - 2.1. URL y navegadores compatibles
   - 2.2. Inicio de sesión con tokens demo
   - 2.3. Roles de usuario
   - 2.4. Interfaz principal
3. [Gestión de Períodos Académicos](#3-gestión-de-períodos-académicos)
   - 3.1. Crear un período
   - 3.2. Seleccionar un período
   - 3.3. Eliminar un período
4. [Carga de Matriz Curricular](#4-carga-de-matriz-curricular)
   - 4.1. Formato esperado del archivo
   - 4.2. Subir una nueva matriz
   - 4.3. Seleccionar una matriz existente
5. [Subida de Documentos](#5-subida-de-documentos)
   - 5.1. Formatos aceptados
   - 5.2. Cómo subir uno o varios documentos
   - 5.3. Progreso y estados de procesamiento
   - 5.4. Eliminar un documento
6. [Ejecución del Análisis](#6-ejecución-del-análisis)
   - 6.1. Requisitos previos
   - 6.2. Iniciar el análisis
   - 6.3. Seguimiento del progreso
7. [Dashboard y Mapa de Calor](#7-dashboard-y-mapa-de-calor)
   - 7.1. Resumen general (tarjetas KPI)
   - 7.2. Promedio por competencia
   - 7.3. Mapa de calor (heatmap)
   - 7.4. Detalle trazable de una celda
8. [Indicadores (KPIs)](#8-indicadores-kpis)
   - 8.1. Tarjetas de resumen
   - 8.2. Distribución de evidencia
   - 8.3. Brechas críticas
   - 8.4. Cobertura por competencia
9. [Revisión de Evidencias](#9-revisión-de-evidencias)
   - 9.1. Listado de fragmentos recuperados
   - 9.2. Filtro por competencia
   - 9.3. Aprobar o rechazar evidencia
10. [Comentarios Generados por IA](#10-comentarios-generados-por-ia)
    - 10.1. Cómo funciona
    - 10.2. Generar comentarios para una celda
    - 10.3. Comentario local vs. comentario LLM
11. [Exportación de Reportes](#11-exportación-de-reportes)
    - 11.1. Exportar a Excel
    - 11.2. Contenido del reporte
12. [Casos de Uso](#12-casos-de-uso)
    - 12.1. Evaluador: validar una tesis
    - 12.2. Jefe de carrera: diagnosticar el período
    - 12.3. Profesor guía: comparar dos tesis
13. [Limitaciones Conocidas](#13-limitaciones-conocidas)
14. [Solución de Problemas](#14-solución-de-problemas)

---

## 1. Introducción

### 1.1. Objetivo de la aplicación

La **Plataforma de Validación del Perfil de Egreso** es una herramienta web que permite a instituciones de educación superior verificar de manera automática y trazable si las tesis y memorias académicas demuestran las competencias definidas en el perfil de egreso de una carrera.

El sistema cruza el contenido textual de los documentos con una matriz curricular (cursos, competencias y criterios de evaluación) para:

- Identificar fragmentos de texto que evidencian cada competencia.
- Generar un mapa de calor visual del nivel de evidencia por curso y competencia.
- Producir indicadores agregados (KPIs) sobre la cobertura del perfil.
- Exportar reportes detallados con las evidencias encontradas.

[SCREENSHOT: Pantalla principal del dashboard con heatmap y KPIS]

### 1.2. Público objetivo

| Rol | Descripción |
|-----|-------------|
| **Evaluador** | Revisa y califica tesis; usa el sistema para verificar que un documento cubre las competencias esperadas. |
| **Jefe de carrera** | Supervisa la calidad del programa; usa los KPIs y el heatmap para diagnosticar debilidades en el período. |
| **Profesor guía** | Orienta a estudiantes; usa el sistema para identificar qué competencias necesita reforzar un tesista. |
| **Estudiante** | Sube su tesis y visualiza el análisis para saber si su trabajo cubre las competencias requeridas. |
| **Administrador académico** | Gestiona matrices curriculares, períodos y usuarios. |
| **Administrador técnico** | Mantiene la infraestructura y configura el sistema. |

### 1.3. Requisitos para su utilización

- **Navegador web**: Chrome 90+, Firefox 88+, Edge 90+, Safari 14+. El sistema no requiere plugins adicionales.
- **Conexión a internet**: necesaria si el sistema está alojado en un servidor remoto. En redes locales, puede funcionar sin internet.
- **Archivos de entrada**:
  - Matriz curricular: archivo Excel (`.xlsx`) con formato específico.
  - Documentos: archivos PDF, DOCX o TXT (máximo 40 MB cada uno).
- **Opcional**: API key de Gemini u OpenAI si se desean comentarios generados por inteligencia artificial.

---

## 2. Acceso al Sistema

### 2.1. URL y navegadores compatibles

La plataforma es una aplicación web de página única (SPA). Para acceder, abra el archivo `index.html` en su navegador o navegue a la URL donde esté alojada.

[SCREENSHOT: Barra de direcciones del navegador apuntando a la URL del sistema]

Si el backend está disponible, el frontend se conectará automáticamente y cargará los datos reales. Si no, se mostrará un mensaje indicando que el backend está desconectado.

### 2.2. Inicio de sesión con tokens demo

El sistema utiliza autenticación mediante tokens. Para acceder en modo demostración, use uno de los siguientes tokens:

| Rol | Token |
|-----|-------|
| Estudiante | `demo-student` |
| Profesor guía | `demo-professor` |
| Evaluador | `demo-evaluator` |
| Administrador académico | `demo-academic-admin` |
| Administrador técnico | `demo-tech-admin` |

Para usar un token, incluya el encabezado `Authorization: Bearer <token>` en las solicitudes a la API. En el frontend, si la autenticación está habilitada, el sistema mostrará un selector de rol al cargar la página.

[SCREENSHOT: Selector de rol/token en la interfaz de inicio]

### 2.3. Roles de usuario

Cada rol tiene permisos específicos:

| Rol | Puede hacer |
|-----|-------------|
| Estudiante | Subir documentos, ver resultados propios. |
| Profesor guía | Gestionar períodos, matrices, documentos; ejecutar análisis; ver evidencias. |
| Evaluador | Revisar evidencias, aprobar/rechazar, exportar reportes. |
| Administrador académico | Gestión completa de matrices, períodos y usuarios. |
| Administrador técnico | Configuración, migraciones, monitoreo de servicios. |

### 2.4. Interfaz principal

La interfaz se divide en las siguientes secciones:

[SCREENSHOT: Vista general anotada de la interfaz con sidebar, topbar y panel central]

- **Barra lateral (sidebar)**: contiene el logo, la navegación entre vistas y el indicador de estado del backend.
  - Dashboard (mapa de calor y detalle)
  - Períodos y tesis (administración)
  - Evidencia (revisión de fragmentos)
  - Indicadores (KPIs)
- **Barra superior (topbar)**: selector de período académico, botón de exportar y botón de analizar.
- **Panel central**: cambia según la vista seleccionada.

---

## 3. Gestión de Períodos Académicos

Un **período académico** representa un semestre o año lectivo en el que se analizarán una o más tesis. Cada período está asociado a una matriz curricular.

### 3.1. Crear un período

1. Navegue a la vista **Períodos y tesis** desde la barra lateral.
2. En el panel "Períodos académicos", complete el formulario:
   - **Nuevo período**: ingrese un nombre (ej: `2026-1`).
   - **Matriz / carrera**: seleccione la matriz curricular que corresponde al período.
3. Haga clic en **Crear**.

[SCREENSHOT: Formulario de creación de período completado]

El nuevo período aparecerá en la lista debajo del formulario.

### 3.2. Seleccionar un período

- En la barra superior, use el selector desplegable **Período** para elegir el período activo.
- Al cambiar, el dashboard, el heatmap, las evidencias y los KPIs se actualizan automáticamente.

[SCREENSHOT: Selector de período desplegado mostrando las opciones disponibles]

### 3.3. Eliminar un período

- En la lista de períodos (vista "Períodos y tesis"), cada elemento tiene un botón **Eliminar** (ícono de papelera).
- Confirme la eliminación. Esto borrará todos los documentos, evidencias y resultados asociados al período.

---

## 4. Carga de Matriz Curricular

La **matriz curricular** (o "matriz de tributación") es un archivo Excel que define la relación entre cursos y competencias del perfil de egreso.

### 4.1. Formato esperado del archivo

El archivo Excel (`.xlsx`) debe contener las siguientes hojas con estos encabezados:

**Hoja 1 — Cursos** (nombre configurable):

| Columna | Descripción |
|---------|-------------|
| `COD_ASIG` | Código de la asignatura |
| `ASIGNATURA` | Nombre del curso |
| `SEMESTRE` | Semestre en que se imparte |
| `AREA` | Área de formación |
| `HRS_SEMANALES` | Horas semanales |

**Hoja 2 — Competencias** (nombre configurable):

| Columna | Descripción |
|---------|-------------|
| `COD_COMP` | Código de la competencia |
| `COMPETENCIA` | Nombre de la competencia |
| `DESCRIPCION` | Descripción detallada |
| `TIPO` | Tipo (genérica, específica, sello) |

**Hoja 3 — Tributación** (nombre configurable):

| Columna | Descripción |
|---------|-------------|
| `COD_ASIG` | Código de la asignatura (debe coincidir con el de Cursos) |
| `COD_COMP` | Código de la competencia (debe coincidir con el de Competencias) |

[SCREENSHOT: Ejemplo de archivo Excel abierto mostrando las hojas y su estructura]

Puede usar los archivos de ejemplo incluidos en `matrices_tributacion/` como referencia.

### 4.2. Subir una nueva matriz

1. En la vista **Períodos y tesis**, localice el panel "Mallas cargadas".
2. Complete el formulario:
   - **Nombre de la matriz**: nombre visible (ej: "PE 2026 Eléctrica").
   - **Carrera**: nombre de la carrera (ej: "Ingeniería Civil Eléctrica").
   - **Año**: año del plan de estudios.
   - **Archivo Excel**: seleccione el archivo `.xlsx` desde su computador.
3. Haga clic en **Cargar matriz**.

[SCREENSHOT: Formulario de carga de matriz con archivo seleccionado]

4. Espere a que el sistema procese el archivo. La nueva matriz aparecerá en la lista.

### 4.3. Seleccionar una matriz existente

Al crear un período académico, deberá asociarlo a una matriz ya cargada. Las matrices disponibles se muestran en el selector del formulario.

---

## 5. Subida de Documentos

### 5.1. Formatos aceptados

| Formato | Extensiones | Requisitos |
|---------|-------------|------------|
| PDF | `.pdf` | Texto seleccionable (no imágenes escaneadas). |
| DOCX | `.docx` | Documento de Microsoft Word. |
| TXT | `.txt` | Texto plano codificado en UTF-8. |

> **Nota**: Los documentos escaneados (imágenes sin texto seleccionable) se marcan como `ocr_required` y no se procesan hasta que se integre un módulo OCR.

### 5.2. Cómo subir uno o varios documentos

1. Seleccione el **período académico** al que pertenecerán los documentos.
2. En el panel "Tesis del período seleccionado", arrastre uno o más archivos al área de carga (rectángulo punteado) o haga clic en ella para seleccionar archivos desde su computador.

[SCREENSHOT: Área de carga con archivos arrastrados y progreso de subida]

3. Los archivos se subirán automáticamente. Verá una barra de progreso por cada uno.

### 5.3. Progreso y estados de procesamiento

Una vez subidos, los documentos pasan por varias etapas:

| Estado | Significado |
|--------|-------------|
| `pending` | Esperando ser procesado. |
| `extracting` | Extrayendo texto del archivo. |
| `extracted` | Texto extraído correctamente. |
| `chunking` | Segmentando el texto en fragmentos. |
| `embedding` | Generando vectores de embedding. |
| `completed` | Procesamiento completado. |
| `error` | Ocurrió un error durante el procesamiento. |
| `ocr_required` | El PDF no tiene texto seleccionable; se necesita OCR. |

En el pipeline visual de la vista "Períodos y tesis" puede ver el avance general de todos los documentos.

[SCREENSHOT: Pipeline visual mostrando las etapas completadas y pendientes]

### 5.4. Eliminar un documento

En la tabla de tesis, haga clic en **Eliminar** para remover un documento y todos sus datos asociados (versiones, chunks, embeddings y evidencias).

---

## 6. Ejecución del Análisis

### 6.1. Requisitos previos

Antes de ejecutar un análisis, asegúrese de tener:

1. Un **período académico** creado y seleccionado.
2. Una **matriz curricular** cargada y asociada al período.
3. Al menos un **documento** subido y procesado (estado `completed`).

### 6.2. Iniciar el análisis

1. En la barra superior, haga clic en **Analizar con API**.

[SCREENSHOT: Botón "Analizar con API" en la barra superior]

2. El sistema comenzará a procesar el período: generará embeddings (si no existen), calculará la similitud entre fragmentos y criterios de evaluación, y producirá las evidencias.
3. Durante el análisis, el botón se deshabilitará y aparecerá una barra de progreso.

### 6.3. Seguimiento del progreso

El sistema muestra el progreso del análisis en varios lugares:

- **Barra de progreso**: indica el porcentaje completado.
- **Pipeline visual**: muestra en qué etapa se encuentra el análisis.
- **Notificaciones**: mensajes de confirmación o error.

[SCREENSHOT: Barra de progreso del análisis en ejecución]

Una vez completado, los resultados estarán disponibles en el Dashboard, la sección de Evidencia y los KPIs.

---

## 7. Dashboard y Mapa de Calor

### 7.1. Resumen general (tarjetas KPI)

En la parte superior del Dashboard hay tarjetas que resumen el estado del período:

| Indicador | Descripción |
|-----------|-------------|
| **Cobertura general** | Porcentaje de celdas de la matriz con evidencia suficiente. |
| **Competencias sólidas** | Número de competencias con alta cobertura. |
| **Competencias críticas** | Número de competencias con baja cobertura. |
| **Total de evidencias** | Cantidad de fragmentos de evidencia encontrados. |

[SCREENSHOT: Tarjetas de resumen (KPIs) en la parte superior del dashboard]

### 7.2. Promedio por competencia

Debajo de las tarjetas, una sección muestra el **Promedio por competencia**. Cada competencia aparece con un indicador de color que refleja su nivel de cobertura (verde = alto, amarillo = medio, rojo = bajo).

[SCREENSHOT: Sección de promedios por competencia con colores]

Al hacer clic en una competencia, se muestra su descripción detallada.

### 7.3. Mapa de calor (heatmap)

El mapa de calor es la herramienta principal del dashboard. Muestra una matriz donde:

- **Filas**: cursos (asignaturas) del plan de estudios.
- **Columnas**: competencias del perfil de egreso.
- **Celdas**: nivel de evidencia encontrada para cada par curso-competencia.

**Escala de colores**:

| Color | Significado |
|-------|-------------|
| ![#4ade80](https://placehold.co/15x15/4ade80/4ade80) Verde | Alta evidencia (score ≥ 0.5) |
| ![#facc15](https://placehold.co/15x15/facc15/facc15) Amarillo | Media evidencia (score entre 0.3 y 0.5) |
| ![#f87171](https://placehold.co/15x15/f87171/f87171) Rojo | Baja o nula evidencia (score < 0.3) |
| Sin color | No existe tributación entre el curso y la competencia |

[SCREENSHOT: Mapa de calor completo mostrando varias celdas con diferentes colores]

> **Navegación**: si la matriz es grande, puede desplazarse horizontal y verticalmente dentro del heatmap. Use el filtro de grupos para agrupar competencias por bloque.

### 7.4. Detalle trazable de una celda

Al hacer clic en una celda con color (que tenga evidencia), el panel lateral derecho se actualiza con:

- **Curso y competencia**: nombres completos.
- **Score**: puntuación de evidencia (0 a 1).
- **Fragmentos de evidencia**: texto extraído del documento que respalda la celda, con documento y página de origen.
- **Justificación**: explicación de por qué el sistema considera que el fragmento es evidencia.
- **Comentario LLM** (si está configurado): comentario generado por inteligencia artificial.
- **Acción sugerida**: recomendación (revisar, aprobar, complementar).

[SCREENSHOT: Panel de detalle de celda con fragmento de evidencia y comentario]

---

## 8. Indicadores (KPIs)

La vista **Indicadores** ofrece un análisis más detallado del período.

### 8.1. Tarjetas de resumen

Cuatro tarjetas grandes resumen el estado del período:

- **Cobertura global**: porcentaje de celdas con evidencia aceptable.
- **Evidencia alta**: cantidad de celdas con score alto.
- **Evidencia media**: cantidad de celdas con score medio.
- **Brechas**: número de celdas sin evidencia suficiente.

[SCREENSHOT: Cuatro tarjetas grandes de KPI en la vista de indicadores]

### 8.2. Distribución de evidencia

Un gráfico de barras muestra cuántas celdas hay en cada nivel de cumplimiento:

[SCREENSHOT: Gráfico de barras con la distribución de niveles de evidencia]

### 8.3. Brechas críticas

Una tabla enumera las **5 celdas con menor evidencia**, ordenadas de menor a mayor score. Esto permite identificar rápidamente los puntos débiles del período.

| Curso | Competencia | Score | Acción recomendada |
|-------|-------------|-------|-------------------|
| ... | ... | 0.05 | Revisar documento |
| ... | ... | 0.12 | Revisar documento |

[SCREENSHOT: Tabla de brechas críticas con las 5 peores celdas]

### 8.4. Cobertura por competencia

Para cada competencia, se muestra:

- La **cantidad de cursos** asociados.
- Cuántos de esos cursos **alcanzaron el umbral** de evidencia.
- Una **barra de progreso** visual.

Ejemplo: `2/7` significa que de 7 cursos vinculados a la competencia, solo 2 tienen evidencia suficiente.

[SCREENSHOT: Lista de cobertura por competencia con barras de progreso]

---

## 9. Revisión de Evidencias

### 9.1. Listado de fragmentos recuperados

La vista **Evidencia** muestra todos los fragmentos de texto que el sistema identificó como relevantes para cada competencia.

Cada fragmento incluye:

- **Documento de origen**: nombre del archivo.
- **Número de página**: ubicación en el documento original.
- **Texto del fragmento**: cita textual.
- **Score de relevancia**: puntuación de 0 a 1.
- **Competencias asociadas**: qué competencias cubre.
- **Estado**: pendiente, aprobado o rechazado.

[SCREENSHOT: Listado de fragmentos de evidencia con sus detalles]

### 9.2. Filtro por competencia

Use el selector desplegable **Competencia** en la parte superior para filtrar los fragmentos de una competencia específica.

[SCREENSHOT: Selector de filtro por competencia en la vista de evidencias]

### 9.3. Aprobar o rechazar evidencia

Cada fragmento tiene botones para **aprobar** (marcar como evidencia válida) o **rechazar** (marcar como falso positivo). Esto permite al evaluador refinar los resultados automáticos.

[SCREENSHOT: Botones de aprobar/rechazar en un fragmento de evidencia]

Las decisiones de aprobación/rechazo se registran y pueden usarse para recalibrar el sistema.

---

## 10. Comentarios Generados por IA

### 10.1. Cómo funciona

Si el administrador ha configurado una API key de **Gemini** o **OpenAI**, el sistema puede generar comentarios en lenguaje natural que justifican el resultado de cada celda del heatmap.

El sistema **no envía el documento completo** a la API externa. Solo envía el contexto mínimo: curso, competencia, criterio, score, fragmento recuperado, documento y página.

### 10.2. Generar comentarios para una celda

1. Haga clic en una celda del heatmap.
2. Espere a que el sistema cargue el detalle.
3. Si hay un comentario LLM, aparecerá en el panel de detalle bajo la sección "Comentario generado por IA".

[SCREENSHOT: Panel de detalle mostrando un comentario LLM generado para una celda]

### 10.3. Comentario local vs. comentario LLM

- **Comentario local**: generado por el propio sistema basado en reglas. Siempre está disponible.
- **Comentario LLM**: generado por Gemini u OpenAI. Solo disponible si hay API key configurada y la llamada fue exitosa. Si falla, el sistema vuelve automáticamente al comentario local.

---

## 11. Exportación de Reportes

### 11.1. Exportar a Excel

1. Seleccione el período que desea exportar.
2. Haga clic en el botón **Exportar** (ícono de descarga) en la barra superior.

[SCREENSHOT: Botón Exportar en la barra superior]

3. El sistema generará un archivo Excel (`.xlsx`) y lo descargará automáticamente.

### 11.2. Contenido del reporte

El archivo Excel contiene:

- **Hoja "Resumen"**: indicadores generales del período.
- **Hoja "Mapa de Calor"**: matriz con scores por curso y competencia, coloreada.
- **Hoja "Detalle por Curso"**: lista de evidencias agrupadas por curso.
- **Hoja "Detalle por Competencia"**: lista de evidencias agrupadas por competencia.
- **Hoja "Brechas"**: celdas con evidencia insuficiente, ordenadas por criticidad.

[SCREENSHOT: Archivo Excel abierto mostrando las hojas del reporte]

---

## 12. Casos de Uso

### 12.1. Evaluador: validar una tesis

**Escenario**: Un evaluador recibe la tesis de un estudiante y debe verificar que cubre las competencias del perfil de egreso.

**Pasos**:

1. Accede al sistema con el rol **Evaluador** (token: `demo-evaluator`).
2. Selecciona el período correspondiente.
3. Sube la tesis en formato PDF.
4. Ejecuta el análisis.
5. Revisa el heatmap: busca celdas en rojo (sin evidencia).
6. Hace clic en cada celda con baja evidencia para leer los fragmentos asociados.
7. Para cada fragmento, decide si aprueba o rechaza la evidencia.
8. Si la cobertura general es aceptable (>80%), procede a aprobar la tesis.
9. Exporta el reporte Excel como respaldo de su evaluación.

### 12.2. Jefe de carrera: diagnosticar el período

**Escenario**: El jefe de carrera quiere saber cómo están las tesis del semestre en términos de cobertura del perfil de egreso.

**Pasos**:

1. Accede con el rol **Administrador académico**.
2. Carga todas las tesis del semestre en un mismo período.
3. Ejecuta el análisis.
4. En la vista de KPIs, revisa:
   - **Cobertura global**: ¿está por encima del umbral aceptable?
   - **Brechas críticas**: ¿qué competencias no se están cubriendo?
   - **Distribución**: ¿la mayoría de celdas están en verde o en rojo?
5. En el dashboard, identifica qué cursos tienen peor desempeño.
6. Toma decisiones: reforzar ciertos cursos, ajustar la matriz, solicitar cambios en las guías de tesis.

### 12.3. Profesor guía: comparar dos tesis

**Escenario**: Un profesor guía tiene dos estudiantes que están desarrollando su tesis y quiere comparar qué competencias cubre cada uno.

**Pasos**:

1. Crea un período para el semestre actual.
2. Sube ambas tesis (avances) al mismo período.
3. Ejecuta el análisis.
4. En el heatmap, el sistema muestra el promedio de las tesis. Para ver diferencias:
   - Revise la evidencia de cada celda para ver qué fragmentos provienen de cada documento.
   - En la vista de Evidencia, filtre por competencia para ver qué aporta cada tesis.
5. Identifique qué competencias cubre un estudiante y no el otro.
6. Oriente a cada estudiante sobre qué competencias reforzar.

---

## 13. Limitaciones Conocidas

1. **Sin OCR real**: los documentos escaneados (imágenes sin texto seleccionable) se detectan pero no se procesan. Se necesita integrar Tesseract, Azure Document Intelligence o equivalente.

2. **Umbrales empíricos**: los umbrales de evidencia (score mínimo, ratio de muestra) están configurados con valores por defecto basados en pruebas iniciales. Es necesario calibrarlos con datos históricos reales revisados por humanos.

3. **Comentarios LLM requieren API key**: los comentarios generados por Gemini/OpenAI solo funcionan si el administrador configura una API key. Sin ella, el sistema usa comentarios locales basados en reglas.

4. **Análisis síncrono**: el análisis se ejecuta en el mismo proceso (BackgroundTasks de FastAPI). Para alto volumen de documentos, se recomienda migrar a Celery o RQ.

5. **Sin autenticación real**: el sistema usa tokens demo fijos. Para producción, debe integrarse con SSO institucional (SAML, OAuth2, LDAP).

6. **Sin antivirus**: los archivos subidos no pasan por un escáner de virus. En producción, debe agregarse un paso de verificación.

7. **Dependencia de GPU**: los embeddings con `BAAI/bge-m3` se ejecutan en GPU por defecto. Sin GPU, el proceso es significativamente más lento.

8. **Calidad académica no validada**: el sistema encuentra similitud textual, pero la relevancia académica real debe ser validada por evaluadores humanos.

---

## 14. Solución de Problemas

| Problema | Causa posible | Solución |
|----------|---------------|----------|
| **No se carga la interfaz** | El backend no está disponible. | Abra el frontend igualmente; usará datos simulados. Si necesita datos reales, verifique que el backend esté corriendo. |
| **No puedo crear un período** | No hay matrices cargadas. | Primero cargue al menos una matriz curricular en la sección "Mallas cargadas". |
| **La matriz no se carga** | El archivo Excel no tiene el formato esperado. | Verifique que el Excel tenga hojas con los nombres y encabezados correctos (ver sección 4.1). |
| **Un documento aparece como "ocr_required"** | El PDF no tiene texto seleccionable. | Use un PDF con texto real (no escaneado) o convierta el documento a DOCX. |
| **El análisis no comienza** | No hay documentos procesados. | Espere a que los documentos terminen de procesarse (estado "completed"). |
| **El heatmap está vacío** | No se ha ejecutado el análisis o no hay evidencias. | Ejecute el análisis y verifique que los documentos contengan texto relevante. |
| **No aparecen comentarios LLM** | API key no configurada. | Contacte al administrador técnico. El sistema usará comentarios locales. |
| **La exportación falla** | No hay datos para el período. | Asegúrese de haber ejecutado el análisis al menos una vez. |
| **Error "CORS" en la consola** | El frontend no puede conectar con el backend. | Verifique que el backend esté corriendo en el puerto 8000 y que CORS esté configurado. |
| **El sistema está lento** | Sin GPU o muchos documentos. | Reduzca la cantidad de documentos por análisis o ejecute en un equipo con GPU NVIDIA. |

---

*Fin del Manual de Usuario*
