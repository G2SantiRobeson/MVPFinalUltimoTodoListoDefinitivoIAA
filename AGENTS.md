# AGENTS.md — Estándar de ingeniería para asistentes de IA

> Archivo de contexto **agnóstico a la herramienta**. Define cómo quiero que
> cualquier asistente (Claude, Codex, Gemini, Cursor, etc.) diseñe, escriba,
> prueba y entrega código en este repositorio. Estos criterios tienen
> prioridad sobre defaults genéricos del modelo.

## Cómo usar este archivo en cada herramienta

Este es el archivo canónico. Para que cada agente lo lea, cópialo o crea un
enlace simbólico con el nombre que espera la herramienta:

- **Codex / agentes que siguen la convención abierta** → `AGENTS.md` (este mismo).
- **Claude Code** → `CLAUDE.md`
- **Gemini CLI** → `GEMINI.md`
- **Cursor** → `.cursorrules`

En Linux/macOS basta con enlazarlos para mantener una sola fuente de verdad:

```bash
ln -sf AGENTS.md CLAUDE.md
ln -sf AGENTS.md GEMINI.md
ln -sf AGENTS.md .cursorrules
```

Si una herramienta no soporta symlinks, copia el archivo (`cp AGENTS.md CLAUDE.md`)
y vuelve a copiarlo cuando edites el original.

---

## 0. Regla general de trabajo

Trabaja como un pipeline con *quality gates*, igual que CI/CD: **diseñar →
implementar → refactorizar → probar → revisar**. No avances de etapa si la
anterior no cumple. Si encuentras un problema serio en una etapa, deténte,
explícalo y propón la corrección antes de seguir.

Antes de escribir código no trivial, **describe brevemente el plan** (qué
entidades/clases tocas, qué responsabilidad tiene cada una) y espera o avanza
solo si el plan respeta las reglas de diseño de abajo.

---

## 1. Diseño antes de codear

- **Modela el dominio primero.** Identifica las entidades del problema y sus
  relaciones antes de pensar en clases concretas. Distingue el *modelo de
  dominio* (problema) del *modelo de diseño* (solución): el primero se traduce
  al segundo, no se mezclan.
- **Piensa en niveles de abstracción** (estilo C4): contexto del sistema →
  contenedores → componentes. No saltes directo a funciones sueltas.
- Usa **UML simplificado** (clases, atributos, relaciones) cuando ayude a
  comunicar estructura; no diagramar por diagramar.

### SOLID (obligatorio)

Todo diseño debe respetar:

- **S — Single Responsibility:** cada clase/módulo/función tiene **una sola
  razón para cambiar**. Alta cohesión.
- **O — Open/Closed:** abierto a extensión, cerrado a modificación. Para
  soportar un tipo nuevo, agrega una clase nueva, no edites la lógica existente.
- **L — Liskov Substitution:** una subclase debe poder reemplazar a su clase
  base sin romper el comportamiento esperado.
- **I — Interface Segregation:** interfaces pequeñas y específicas; no obligues
  a implementar métodos que no se usan.
- **D — Dependency Inversion:** depende de abstracciones, no de
  implementaciones concretas.

### Patrones de diseño

Cuando un patrón resuelve limpiamente el problema, **aplícalo y nómbralo
explícitamente** (y di por qué). Catálogo de referencia: Strategy, Observer,
Adapter, Singleton, Factory (Simple Factory / Factory Method), Decorator,
Command, State, Proxy, Chain of Responsibility. No fuerces un patrón donde una
solución simple basta (evita sobre-ingeniería).

---

## 2. Calidad de código y code smells

Nombres claros y código legible por encima de código "inteligente". Agrega
**type hints** siempre que el lenguaje lo permita.

Marca y corrige proactivamente estos *code smells*:

| Smell | Corrección |
|---|---|
| Nombres misteriosos | Renombrar para que sean claros |
| Funciones largas | Extraer a subfunciones |
| Código duplicado | Extraer a una estructura común |
| Magic literals (números/strings sueltos) | Constante con nombre o enum |
| Demasiadas responsabilidades | Dividir en subclases/módulos |
| Código difícil de entender | Reestructurar para claridad + type hints |
| Un cambio chico obliga a tocar muchos lugares | Crear abstracciones adicionales |

**Refactoriza en una pasada dedicada**, separada de agregar funcionalidad. No
mezcles "feature nueva" + "refactor grande" en el mismo cambio.

---

## 3. Pruebas

- Framework por defecto: **Pytest** (ajustar si el repo usa otro).
- Cada test sigue la estructura **Arrange – Act – Assert**, y comenta cada
  bloque explícitamente.
- Cada test es **independiente y autocontenido**: no depende del orden ni del
  estado dejado por otros tests.
- Cada test termina en una verificación (`assert`) concreta.
- **Justifica la relevancia** de cada test: por qué importa en el contexto del
  módulo que prueba. No agregues tests triviales solo para subir cobertura.
- Cubre el camino feliz y al menos los casos borde y de error relevantes.

Ejemplo de estructura mínima:

```python
def test_descripcion_clara_del_caso():
    # Arrange
    ...
    # Act
    resultado = ...
    # Assert
    assert resultado == esperado
```

---

## 4. Web APIs (cuando aplique)

- Diseña APIs **REST**: recursos con nombres claros, operaciones sobre esos
  recursos mediante los verbos HTTP correctos, y códigos de estado adecuados.
- **Valida siempre el input** que entra desde fuera del sistema.
- Maneja errores de forma explícita y devuelve respuestas consistentes.
- No expongas detalles internos ni secretos en respuestas, logs ni URLs.

---

## 5. Integración y entrega (CI/CD)

Antes de considerar un cambio terminado, debe pasar las mismas *gates* que un
pipeline de CI:

1. **Build** — el proyecto compila/levanta sin errores.
2. **Lint / formato** — sin warnings de estilo; formato consistente.
3. **Tests** — toda la suite pasa.

Conceptos a respetar:

- **CI:** integrar cambios pequeños y frecuentes; cada integración se verifica
  con build + tests automáticos para detectar errores cuanto antes.
- **Docker:** si el proyecto se containeriza, mantener el entorno reproducible
  (mismo comportamiento en local, CI y producción).
- **Continuous Delivery ≠ Continuous Deployment:** *Delivery* = siempre listo
  para desplegar; *Deployment* = despliegue automático. No asumas despliegue
  automático salvo que se indique.

---

## 6. Definition of Done (checklist final)

Antes de entregar un cambio, verifica:

- [ ] El diseño respeta SOLID y usa el patrón adecuado (o ninguno, justificado).
- [ ] Sin code smells de la tabla de la sección 2.
- [ ] Nombres claros + type hints.
- [ ] Tests en formato AAA, independientes y relevantes; suite verde.
- [ ] Si hay API: input validado y errores manejados.
- [ ] Build + lint + tests pasan (gates de CI).
- [ ] El cambio es enfocado (no mezcla feature + refactor grande).

---

## 7. Cómo comunicarte conmigo

- Si algo del requerimiento es ambiguo, **pregunta antes de asumir**.
- Al proponer un diseño, explica brevemente el *por qué*, no solo el *qué*.
- Si detectas que estoy pidiendo algo que viola estas reglas, **dímelo** en vez
  de obedecer en silencio.