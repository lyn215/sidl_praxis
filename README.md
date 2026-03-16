# SiDL: Smart Interface & Documentation Lens

### Proyecto Ganador – Hackathon Praxis & UTVM 2026

**SiDL** es una solución de vanguardia que integra **Visión Computacional** e **IA Generativa** para automatizar la auditoría visual y funcional en el proceso de Aseguramiento de la Calidad (QA). A diferencia de las herramientas convencionales, nuestra plataforma contrasta la interfaz real de una aplicación contra las reglas de negocio y requerimientos técnicos predefinidos.

---

##  El Desafío (Contexto)

En la ingeniería de software actual, el testing manual consume hasta un **30% del tiempo de desarrollo** y suele carecer de trazabilidad frente a los requerimientos originales. **SiDL** resuelve esta desconexión mediante **Inferencia Cruzada Multimodal**, permitiendo que la IA "entienda" un documento de requerimientos y actúe como juez sobre la interfaz.

---

##  Funcionalidades Clave (MVP)

* **Req-Parser AI:** Motor que procesa documentos SRS (PDF/DOCX) y extrae reglas de validación atómicas para eliminar la lectura manual extensiva.
* **V-Audit (Visión Multimodal):** Auditoría por visión computacional que compara la UI real contra el checklist de requerimientos técnicos.
* **Test-Gen AI:** Generador de casos de prueba dinámicos y editables, otorgando al tester control total sobre la lógica de auditoría antes de la ejecución.
* **Reporte "Inside the Lens":** Desglose transparente de las técnicas de QA aplicadas (Análisis Heurístico, Contraste, etc.), eliminando el efecto de "caja negra" de la IA.
* **Integración Jira-Ready:** Generación automática de tickets de defecto con evidencia visual y severidad sugerida.

---

##  Stack Tecnológico

| Componente | Tecnología | Justificación |
| --- | --- | --- |
| **Backend & AI Engine** | Python, FastAPI, Groq, HuggingFace Qwen | Procesamiento asíncrono y capacidad multimodal para análisis cruzado. |
| **Orquestación de IA** | LangChain | Extracción eficiente de reglas de negocio y manejo de flujos de datos. |
| **Frontend** | HTML5, JavaScript, CSS3 | Interfaz responsiva con editores de tablas dinámicos y visor de auditoría dual. |
| **Persistencia** | SQLite3 | Almacenamiento seguro de sesiones de auditoría y repositorios de pruebas. |

---

##  Impacto e Innovación

* **Reducción de Costos:** Pruebas preliminares demuestran un ahorro del **50% en tiempo de documentación** y una reducción del **30% en el ciclo de vida de desarrollo (SDLC)**.
* **Trazabilidad Directa:** Primer sistema en vincular un error de UI directamente con la cláusula exacta del documento de requerimientos original.
* **Explicabilidad Técnica:** El sistema educa al tester detallando la metodología aplicada en cada hallazgo.

---

##  Equipo de Desarrollo

Este proyecto fue posible gracias a la colaboración estratégica de:

* **Evelyn Leyva Juárez**
* **Hugo Alfonso Aguirre Muñoz**
* **Willam Arturo Badillo Larios**
