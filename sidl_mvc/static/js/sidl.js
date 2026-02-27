/**
 * SiDL — Smart Interface & Documentation Lens
 * JavaScript principal — lógica de la aplicación
 * Se comunica con el backend FastAPI MVC via fetch API
 */

'use strict';

// ═══════════════════════════════════════════════════════════════════════
// ESTADO GLOBAL
// ═══════════════════════════════════════════════════════════════════════
const API = '';                // misma origen — FastAPI sirve el frontend
let usuarioActual      = null; // { id, nombre, email, num_auditorias }
let sessionId          = null; // ID de la sesión de archivos en SQLite
let auditId            = null; // ID de la auditoría guardada en SQLite
let filasCasos         = [];   // Casos de prueba editables
let hallazgosData      = [];   // Hallazgos del análisis
let wcagData           = [];   // Resultados WCAG
let filtroActivo       = 'todos';
let hallazgosDescartados = new Set();
let hallazgoTicketActual = null;
let pasoAlcanzado      = 1;
let textoSrsActual     = '';   // Texto extraído del SRS para el visor

// SRS de demostración para el modo demo
const SRS_DEMO = `ESPECIFICACIÓN DE REQUISITOS DEL SISTEMA
Documento: SRS-SECUREBANK-AUTH v1.4
Autor: Equipo de Arquitectura y QA
Estado: APROBADO — Versión para Producción

§1  ALCANCE
Este documento define los requisitos del Módulo de Autenticación
de la plataforma SecureBank para la versión de producción 2.3.0.

§3  REQUISITOS DE INTERFAZ DE USUARIO
3.2.1  El botón de acción primario DEBE usar el color corporativo #1565C0.
       No se permiten variaciones de color sin aprobación del equipo de marca.
3.5.2  El campo de contraseña DEBE incluir un control de mostrar/ocultar
       representado por un ícono de ojo (visible o tachado).
3.7.1  Todos los campos de formulario DEBEN tener placeholder descriptivo.

§5  REQUISITOS DE ACCESIBILIDAD
5.1  TODOS los elementos interactivos DEBEN incluir atributos aria-label.
5.4  TODO el texto informativo DEBE cumplir contraste mínimo de 4.5:1
     según el estándar WCAG 2.1 Nivel AA (criterio 1.4.3).

§8  VERSIONADO Y METADATOS
8.1  El pie de página DEBE mostrar exactamente la versión del release
     aprobado actual: v2.3.0. No se aceptan versiones anteriores.`;

// ═══════════════════════════════════════════════════════════════════════
// NAVEGACIÓN ENTRE PANTALLAS
// ═══════════════════════════════════════════════════════════════════════
const PANTALLAS = { 's-ingesta': 1, 's-casos': 2, 's-visor': 3, 's-resultados': 4 };

function goScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  const n = PANTALLAS[id] || 1;
  document.querySelectorAll('.step-item').forEach((el, i) => {
    el.classList.remove('active', 'done');
    const sn = i + 1;
    if (sn < n) el.classList.add('done');
    else if (sn === n) el.classList.add('active');
  });
  window.scrollTo(0, 0);
}

function pasoProtegido(s, n) {
  if (n > pasoAlcanzado) {
    toast('Completa el paso actual primero.');
    return;
  }
  goScreen(s);
}

// ═══════════════════════════════════════════════════════════════════════
// DRAG & DROP — ZONA DE CARGA
// ═══════════════════════════════════════════════════════════════════════
function dzOver(e, id)  { e.preventDefault(); document.getElementById(id).classList.add('over'); }
function dzLeave(id)    { document.getElementById(id).classList.remove('over'); }

function dzDrop(e, dzId, inpId) {
  e.preventDefault();
  dzLeave(dzId);
  const inp = document.getElementById(inpId);
  // Asignar archivos al input de manera compatible con todos los browsers
  const dt = e.dataTransfer;
  if (dt.files.length) {
    const file = dt.files[0];
    const dummyInput = document.getElementById(inpId);
    // Guardar en variable global para FormData
    window['_file_' + inpId] = file;
    document.getElementById(dzId).classList.add('filled');
    document.getElementById(dzId).querySelector('.dz-filename').textContent = '✓ ' + file.name;
  }
}

function dzArchivo(inp, dzId) {
  const f = inp.files[0];
  if (!f) return;
  window['_file_' + inp.id] = f;
  document.getElementById(dzId).classList.add('filled');
  document.getElementById(dzId).querySelector('.dz-filename').textContent = '✓ ' + f.name;
}

// ═══════════════════════════════════════════════════════════════════════
// PANTALLA 1 → 2: SUBIR ARCHIVOS AL BACKEND PYTHON
// ═══════════════════════════════════════════════════════════════════════
async function iniciarAnalisis() {
  const srsFile = window['_file_fi-srs'] || document.getElementById('fi-srs').files[0];
  const uiFile  = window['_file_fi-ui']  || document.getElementById('fi-ui').files[0];

  if (!srsFile) {
    toast('Por favor carga el documento SRS primero.');
    return;
  }

  mostrarLoading('Enviando archivos al servidor Python...\n(Gemini 1.5 Pro generará los casos de prueba)');

  const form = new FormData();
  form.append('srs', srsFile);
  if (uiFile) form.append('captura', uiFile);

  try {
    const resp = await fetch(`${API}/api/auditoria/subir`, { method: 'POST', body: form });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Error del servidor');
    }
    const data = await resp.json();
    sessionId     = data.session_id;
    filasCasos    = data.casos;
    textoSrsActual = data.texto_srs_preview || SRS_DEMO;

    ocultarLoading();
    goScreen('s-casos');
    pasoAlcanzado = Math.max(pasoAlcanzado, 2);

    // Mostrar log del proceso en tiempo real
    mostrarLogAnalisis([
      ['hi',   '[FastAPI]  Archivos recibidos y guardados en el servidor.'],
      ['',     '[PyMuPDF]  Extrayendo texto del documento SRS...'],
      ['ok',   `[PyMuPDF]  ✓ ${data.texto_srs_preview?.length || 0} caracteres extraídos.`],
      ['hi',   `[Gemini]   Analizando requisitos... (fuente: ${data.fuente})`],
      ['ok',   `[Gemini]   ✓ ${filasCasos.length} casos de prueba generados.`],
      ['warn', '[Control]  Human-in-the-loop: Revisa y edita antes de continuar.'],
      ['ok',   `[SQLite]   ✓ Sesión ${sessionId.substring(0,8)}... guardada en la base de datos.`],
    ]);

    const fuente = data.fuente === 'gemini' ? 'Gemini 1.5 Pro' : 'Modo Fallback (configura GEMINI_API_KEY)';
    document.getElementById('tc-fuente').textContent = `// FUENTE: ${fuente.toUpperCase()} — EDITA ANTES DE AUDITAR`;
    renderizarTablaCasos();

  } catch (e) {
    ocultarLoading();
    toastError('Error: ' + e.message);
  }
}

function iniciarDemo() {
  // Cargar datos demo sin llamar al servidor
  sessionId      = 'demo-' + Date.now();
  textoSrsActual = SRS_DEMO;
  filasCasos = [
    { id:'CP-001', prioridad:'critical', nombre:'Cumplimiento del Color del Botón CTA Principal',        pre:'Usuario en /login, página completamente cargada', pasos:'1. Inspeccionar el botón CTA principal\n2. Comparar el color computado con DevTools\n3. Validar contra SRS §3.2.1', esperado:'Color del botón = #1565C0 (Azul Corporativo)', ref:'§3.2.1' },
    { id:'CP-002', prioridad:'high',     nombre:'Relación de Contraste WCAG AA — Texto Informativo',    pre:'Página de login renderizada al 100% de zoom',      pasos:'1. Seleccionar el elemento de texto informativo\n2. Medir la relación de contraste con herramienta\n3. Comparar con umbral WCAG 1.4.3', esperado:'Relación de contraste ≥ 4.5:1 en todo el texto', ref:'§5.4' },
    { id:'CP-003', prioridad:'high',     nombre:'Toggle de Visibilidad en Campo de Contraseña',         pre:'Formulario de login renderizado',                  pasos:'1. Localizar el campo de contraseña\n2. Verificar ícono de mostrar/ocultar\n3. Clic y verificar cambio de tipo', esperado:'Toggle presente; input cambia entre password↔text', ref:'§3.5.2' },
    { id:'CP-004', prioridad:'medium',   nombre:'Etiquetas ARIA en Elementos Interactivos',             pre:'DOM de la página completamente cargado',            pasos:'1. Inspeccionar todos los enlaces y botones\n2. Verificar atributos aria-label presentes', esperado:'Todos los elementos interactivos tienen aria-label', ref:'§5.1' },
    { id:'CP-005', prioridad:'medium',   nombre:'Versión del Pie de Página Coincide con Release',       pre:'Aplicación desplegada en entorno objetivo',         pasos:'1. Navegar a cualquier página\n2. Leer la cadena de versión en el pie\n3. Comparar con release aprobado v2.3.0', esperado:'El pie de página muestra v2.3.0', ref:'§8.1' },
    { id:'CP-006', prioridad:'low',      nombre:'Orden de Tabulación — Navegación por Teclado',         pre:'Página activa, foco de teclado reiniciado',         pasos:'1. Presionar Tab desde el campo de correo\n2. Verificar orden correo→contraseña→toggle→CTA', esperado:'Orden de tabulación coincide con especificación §5.2', ref:'§5.2' },
  ];
  goScreen('s-casos');
  pasoAlcanzado = Math.max(pasoAlcanzado, 2);
  document.getElementById('tc-fuente').textContent = '// MODO DEMO — Datos de ejemplo (activa GEMINI_API_KEY para análisis real)';
  renderizarTablaCasos();
  toast('Modo demo activado — puedes probar el flujo completo ✓');
}

function mostrarLogAnalisis(msgs) {
  const logPanel = document.getElementById('log-analisis');
  const logEl    = document.getElementById('log-analisis-body');
  logPanel.style.display = 'block';
  logEl.innerHTML = '';
  msgs.forEach(([cls, msg], i) => {
    setTimeout(() => {
      const l = document.createElement('div');
      l.className = 'log-line ' + cls;
      l.textContent = msg;
      logEl.appendChild(l);
      logEl.scrollTop = logEl.scrollHeight;
    }, i * 400);
  });
  setTimeout(() => {
    logPanel.style.display = 'none';
    renderizarTablaCasos();
  }, msgs.length * 400 + 300);
}

// ═══════════════════════════════════════════════════════════════════════
// TABLA DE CASOS DE PRUEBA
// ═══════════════════════════════════════════════════════════════════════
function renderizarTablaCasos() {
  const tbody = document.getElementById('tc-body');
  tbody.innerHTML = '';
  filasCasos.forEach((f, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span style="font-family:var(--mono);font-size:.7rem;color:var(--sky)">${escHtml(f.id)}</span></td>
      <td>
        <span class="prio ${f.prioridad}" id="pd-${idx}" onclick="togglePrioEdit(${idx})" style="cursor:pointer">
          <i class="bi bi-circle-fill" style="font-size:.4rem"></i>${prioBadge(f.prioridad)}
        </span>
        <select style="display:none;background:var(--card);border:1px solid var(--edge);color:var(--text-1);border-radius:4px;font-family:var(--mono);font-size:.65rem;padding:2px 6px;cursor:pointer;outline:none"
                id="ps-${idx}" onchange="actuPrio(${idx},this.value)">
          <option value="critical" ${f.prioridad==='critical'?'selected':''}>CRÍTICO</option>
          <option value="high"     ${f.prioridad==='high'    ?'selected':''}>ALTO</option>
          <option value="medium"   ${f.prioridad==='medium'  ?'selected':''}>MEDIO</option>
          <option value="low"      ${f.prioridad==='low'     ?'selected':''}>BAJO</option>
        </select>
      </td>
      <td><div class="cell-edit" contenteditable="true" onblur="saveCell(${idx},'nombre',this)">${escHtml(f.nombre)}</div></td>
      <td><div class="cell-edit" contenteditable="true" onblur="saveCell(${idx},'pre',this)" style="font-family:var(--mono);font-size:.68rem;color:var(--text-2)">${escHtml(f.pre)}</div></td>
      <td><div class="cell-edit" contenteditable="true" onblur="saveCell(${idx},'pasos',this)" style="font-family:var(--mono);font-size:.68rem;color:var(--text-2);white-space:pre-line">${escHtml(f.pasos)}</div></td>
      <td><div class="cell-edit" contenteditable="true" onblur="saveCell(${idx},'esperado',this)">${escHtml(f.esperado)}</div></td>
      <td><span style="font-family:var(--mono);font-size:.65rem;color:var(--sky)">${escHtml(f.ref)}</span></td>
      <td>
        <div class="row-actions">
          <button class="row-btn" onclick="togglePrioEdit(${idx})" title="Cambiar prioridad">
            <i class="bi bi-flag"></i>
          </button>
          <button class="row-btn del" onclick="elimFila(${idx})" title="Eliminar caso">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      </td>`;
    tbody.appendChild(tr);
  });
  document.getElementById('tc-count').textContent =
    filasCasos.length + ' caso' + (filasCasos.length !== 1 ? 's' : '');
}

function prioBadge(p) {
  const m = { critical:'CRÍTICO', high:'ALTO', medium:'MEDIO', low:'BAJO' };
  return m[p] || p.toUpperCase();
}

function saveCell(idx, campo, el) {
  filasCasos[idx][campo] = el.textContent.trim();
}

function actuPrio(idx, val) {
  filasCasos[idx].prioridad = val;
  const sp = document.getElementById('pd-' + idx);
  sp.className = 'prio ' + val;
  sp.innerHTML = '<i class="bi bi-circle-fill" style="font-size:.4rem"></i>' + prioBadge(val);
  document.getElementById('ps-' + idx).style.display = 'none';
  sp.style.display = '';
}

function togglePrioEdit(idx) {
  document.getElementById('pd-' + idx).style.display = 'none';
  const sel = document.getElementById('ps-' + idx);
  sel.style.display = '';
  sel.focus();
}

function elimFila(idx) {
  filasCasos.splice(idx, 1);
  renderizarTablaCasos();
}

function agregarFila() {
  const n = filasCasos.length + 1;
  filasCasos.push({
    id: `CP-${String(n).padStart(3,'0')}`,
    prioridad: 'medium',
    nombre: 'Nuevo Caso de Prueba',
    pre: 'Precondición del sistema',
    pasos: '1. Navegar a la sección objetivo\n2. Interactuar con el elemento\n3. Verificar resultado',
    esperado: 'Comportamiento esperado según el SRS',
    ref: '§—'
  });
  renderizarTablaCasos();
  setTimeout(() => {
    const rows = document.querySelectorAll('#tc-body tr');
    const last = rows[rows.length - 1];
    if (last) last.querySelector('.cell-edit').focus();
  }, 50);
}

// ═══════════════════════════════════════════════════════════════════════
// EXPORTAR CSV — Backend Python
// ═══════════════════════════════════════════════════════════════════════
async function exportarCSV() {
  if (!filasCasos.length) { toast('Sin casos de prueba para exportar.'); return; }
  mostrarLoading('Generando CSV en el servidor Python...');
  try {
    const resp = await fetch(`${API}/api/exportar/csv`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId || 'demo', casos: filasCasos }),
    });
    if (!resp.ok) throw new Error('Error al generar CSV');
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = 'sidl-casos-de-prueba.csv'; a.click();
    ocultarLoading();
    toast('CSV exportado correctamente ✓');
  } catch (e) {
    ocultarLoading();
    toastError('Error: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════════════════════
// PANTALLA 2 → 3: LANZAR AUDITORÍA REAL EN BACKEND
// ═══════════════════════════════════════════════════════════════════════
async function lanzarAuditoria() {
  if (!filasCasos.length) { toast('Agrega al menos un caso de prueba.'); return; }

  mostrarLoading('Enviando casos de prueba al motor de auditoría...\n(Gemini 1.5 Pro Vision analizará la imagen)');

  try {
    const body = {
      session_id:  sessionId || 'demo',
      casos:       filasCasos,
      usuario_id:  usuarioActual?.id || null,
    };
    const resp = await fetch(`${API}/api/auditoria/lanzar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Error del servidor');
    }
    const data = await resp.json();
    auditId      = data.audit_id;
    hallazgosData = data.hallazgos;
    wcagData      = data.wcag;

    ocultarLoading();
    goScreen('s-visor');
    pasoAlcanzado = Math.max(pasoAlcanzado, 3);

    construirVisorSRS();
    construirCanvasUI();
    ejecutarSecuenciaVisor(data.puntaje);

    // Actualizar contador de auditorías en el navbar
    if (usuarioActual) {
      usuarioActual.num_auditorias++;
      actualizarNavbar();
    }

  } catch (e) {
    ocultarLoading();
    toastError('Error: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════════════════════
// VISOR DUAL — SRS + Canvas UI
// ═══════════════════════════════════════════════════════════════════════
function construirVisorSRS() {
  const texto = textoSrsActual || SRS_DEMO;
  // Recopilar cláusulas violadas de los hallazgos
  const clausulasVioladas = hallazgosData
    .map(h => h.clausula?.split('—')[0]?.trim()?.replace('§','') || '')
    .filter(Boolean);

  document.getElementById('srs-viewer').innerHTML = texto
    .split('\n')
    .map(linea => {
      const violada = clausulasVioladas.some(c => linea.includes(c) && c.length > 1);
      return `<span class="srs-clause ${violada ? 'highlighted' : ''}">${escHtml(linea) || ' '}</span>`;
    })
    .join('\n');
}

function construirCanvasUI() {
  // Construir mock de la UI de demostración con bounding boxes
  const bboxes = hallazgosData.map(h => {
    const bb = h.bbox || {};
    return `<div class="bbox ${bb.tipo || 'error'}" id="bbox-${h.id}"
              style="left:${bb.x || '8%'};top:${bb.y || '50%'};width:${bb.w || '84%'};height:${bb.h || '8%'}">
              <div class="bbox-label">${escHtml(bb.etiqueta || h.id)}</div>
            </div>`;
  }).join('');

  document.getElementById('ui-canvas').innerHTML = `
    <div class="ui-mock-wrap" id="ui-mock">
      <div style="background:#1a237e;padding:10px 14px;color:#fff;font-size:12px;font-weight:bold;display:flex;justify-content:space-between;font-family:sans-serif">
        <span>🔐 Portal SecureBank</span>
        <span style="font-size:10px;opacity:.7">v2.1.0</span>
      </div>
      <div style="padding:14px;font-family:sans-serif">
        <div style="font-size:10px;color:#555;margin-bottom:3px">CORREO ELECTRÓNICO</div>
        <input style="width:100%;border:1.5px solid #ccc;border-radius:4px;padding:6px 10px;font-size:12px;margin-bottom:10px;outline:none" placeholder="usuario@empresa.com" readonly>
        <div style="font-size:10px;color:#555;margin-bottom:3px">CONTRASEÑA</div>
        <input type="password" style="width:100%;border:1.5px solid #ccc;border-radius:4px;padding:6px 10px;font-size:12px;margin-bottom:10px;outline:none" placeholder="••••••••" readonly>
        <button style="width:100%;background:#e57373;color:#fff;border:none;padding:9px;border-radius:4px;font-size:12px;font-weight:bold;margin-bottom:10px;cursor:default">INICIAR SESIÓN</button>
        <div style="font-size:9px;color:#b0b0b0;background:#d0d0d0;padding:4px 6px;border-radius:3px">Texto de baja visibilidad — contraste insuficiente</div>
        <div style="font-size:10px;color:#777;margin-top:8px">¿Olvidaste tu contraseña? Haz clic aquí</div>
      </div>
      <div style="background:#f5f5f5;padding:6px 14px;font-size:9px;color:#aaa;border-top:1px solid #eee;font-family:sans-serif">
        © 2025 SecureBank — v2.1
      </div>
      <div class="scan-line" id="scan-line"></div>
      <div class="scan-overlay show" id="scan-overlay">
        <div style="position:relative;width:56px;height:56px">
          <svg viewBox="0 0 54 54" width="54" height="54" style="transform:rotate(-90deg)">
            <circle class="ring-track" cx="27" cy="27" r="24"/>
            <circle class="ring-fill"  id="ring-fill" cx="27" cy="27" r="24"/>
          </svg>
          <div class="ring-pct" id="ring-pct">0%</div>
        </div>
        <div style="font-family:var(--mono);font-size:.6rem;color:var(--sky);letter-spacing:1px">GEMINI ANALIZANDO...</div>
      </div>
      ${bboxes}
    </div>`;
}

function ejecutarSecuenciaVisor(puntaje) {
  const logEl  = document.getElementById('audit-log');
  const barEl  = document.getElementById('audit-bar');
  const pctEl  = document.getElementById('audit-pct');
  logEl.innerHTML = '';
  document.getElementById('scan-line').classList.add('running');

  // Barra de progreso animada
  let prog = 0;
  const iv = setInterval(() => {
    prog = Math.min(prog + 0.8, 100);
    barEl.style.width = prog + '%';
    pctEl.textContent = Math.round(prog) + '%';
    const rf = document.getElementById('ring-fill');
    if (rf) {
      rf.style.strokeDashoffset = 151 - (151 * prog / 100);
      document.getElementById('ring-pct').textContent = Math.round(prog) + '%';
    }
    if (prog >= 100) clearInterval(iv);
  }, 80);

  // Log de análisis
  const msgs = [
    [0,    'hi',   '[FastAPI]  Auditoría recibida — iniciando pipeline de análisis.'],
    [600,  '',     '[PyMuPDF]  Preprocesando imagen de la captura de pantalla...'],
    [1200, 'ok',   '[Gemini]   ✓ Visión activada — analizando elementos de la UI.'],
    [1800, 'hi',   '[Motor]    Referenciando casos de prueba contra elementos visuales...'],
    [2400, 'warn', `[Resultado] ⚠ ${hallazgosData.filter(h=>h.severidad==='critical').length} hallazgos críticos detectados.`],
    [3000, 'ok',   '[WCAG]     ✓ Análisis de accesibilidad WCAG 2.1 AA completado.'],
    [3500, 'ok',   `[Puntaje]  ✓ QA Score calculado: ${puntaje}/100`],
    [3800, 'ok',   '[SQLite]   ✓ Auditoría guardada en la base de datos.'],
    [4100, 'hi',   '[SiDL]     Auditoría completa — generando reporte...'],
  ];

  msgs.forEach(([t, cls, msg]) => {
    setTimeout(() => {
      const l = document.createElement('div');
      l.className = 'log-line ' + cls;
      l.textContent = msg;
      logEl.appendChild(l);
      logEl.scrollTop = logEl.scrollHeight;
    }, t);
  });

  // Mostrar bounding boxes progresivamente
  hallazgosData.forEach((h, i) => {
    setTimeout(() => {
      const el = document.getElementById('bbox-' + h.id);
      if (el) el.classList.add('show');
      document.getElementById('highlight-count').textContent =
        (i + 1) + ' cláusula' + ((i + 1) !== 1 ? 's violadas' : ' violada');
      document.getElementById('bbox-count').textContent =
        (i + 1) + ' anomalía' + ((i + 1) !== 1 ? 's detectadas' : ' detectada');
    }, 2500 + i * 500);
  });

  // Finalizar secuencia
  setTimeout(() => {
    document.getElementById('scan-line').classList.remove('running');
    const ov = document.getElementById('scan-overlay');
    if (ov) ov.classList.remove('show');
    document.getElementById('btn-ver-res').style.display = '';
    renderizarResultados(puntaje);
    pasoAlcanzado = Math.max(pasoAlcanzado, 4);
    toast('Auditoría completa — ' + hallazgosData.length + ' hallazgos guardados en SQLite ✓');
  }, 4800);
}

// ═══════════════════════════════════════════════════════════════════════
// PANTALLA 4: RESULTADOS
// ═══════════════════════════════════════════════════════════════════════
function renderizarResultados(puntaje) {
  // Anillo de puntaje
  document.getElementById('score-big').textContent = puntaje;
  document.getElementById('score-sub').textContent = 'Guardado el ' + new Date().toLocaleString('es-MX');
  const fill = document.getElementById('score-ring-fill');
  fill.style.strokeDashoffset = 263 - (263 * puntaje / 100);
  fill.style.stroke = puntaje >= 80 ? '#10b981' : puntaje >= 55 ? '#f59e0b' : '#ef4444';

  // Stats de severidad
  const crit = hallazgosData.filter(h => h.severidad === 'critical').length;
  const alto = hallazgosData.filter(h => h.severidad === 'high').length;
  const med  = hallazgosData.filter(h => h.severidad === 'medium').length;
  const bajo = hallazgosData.filter(h => h.severidad === 'low').length;

  document.getElementById('score-stats').innerHTML = `
    <div class="score-stat"><div class="score-stat-n" style="color:var(--red)">${crit}</div><div class="score-stat-l">CRÍTICO</div></div>
    <div class="score-stat"><div class="score-stat-n" style="color:var(--amber)">${alto}</div><div class="score-stat-l">ALTO</div></div>
    <div class="score-stat"><div class="score-stat-n" style="color:var(--sky)">${med}</div><div class="score-stat-l">MEDIO</div></div>
    <div class="score-stat"><div class="score-stat-n" style="color:var(--green)">${bajo}</div><div class="score-stat-l">BAJO</div></div>`;

  // WCAG summary
  document.getElementById('wcag-summary').innerHTML = (wcagData || []).map(w => `
    <div style="display:flex;align-items:center;gap:8px;padding:.4rem 0;border-bottom:1px solid var(--edge);font-size:.78rem">
      <span class="prio ${w.estado==='pass'?'low':w.estado==='fail'?'critical':'medium'}"
            style="min-width:56px;justify-content:center">
        ${w.estado === 'pass' ? 'PASA' : w.estado === 'fail' ? 'FALLA' : 'AVISO'}
      </span>
      <span style="font-family:var(--mono);font-size:.65rem;color:var(--text-3);min-width:36px">${escHtml(w.id)}</span>
      <span>${escHtml(w.nombre)}</span>
      <span class="prio medium" style="margin-left:auto;font-size:.52rem">${w.nivel}</span>
    </div>`).join('');

  renderizarHallazgos('todos');
}

function renderizarHallazgos(filtro) {
  filtroActivo = filtro;
  const list = document.getElementById('findings-list');
  const mostrados = filtro === 'todos'
    ? hallazgosData
    : hallazgosData.filter(h => h.severidad === filtro);

  const etiqSev = { critical:'CRÍTICO', high:'ALTO', medium:'MEDIO', low:'BAJO' };

  list.innerHTML = mostrados.map(h => {
    const desc = hallazgosDescartados.has(h.id);
    const tecnicas = Array.isArray(h.tecnicas)
      ? h.tecnicas
      : (typeof h.tecnicas === 'string' ? JSON.parse(h.tecnicas || '[]') : []);
    return `
    <div class="finding ${desc ? 'dismissed' : ''}" id="fc-${h.id}" onclick="toggleH('${h.id}')">
      <div class="finding-top">
        <span class="finding-id">${escHtml(h.id)}</span>
        <span class="prio ${h.severidad}">${etiqSev[h.severidad] || h.severidad.toUpperCase()}</span>
        <span class="finding-name">${escHtml(h.titulo)}</span>
        <i class="bi bi-chevron-right finding-chevron"></i>
      </div>
      <div class="finding-detail">
        <div class="clause-link"><i class="bi bi-link-45deg me-1"></i>${escHtml(h.clausula || '')}</div>
        <div class="finding-desc">${escHtml(h.desc || h.descripcion || '')}</div>
        <div class="finding-desc" style="font-family:var(--mono);font-size:.68rem">
          <span style="color:var(--green)">ESPERADO: </span>${escHtml(h.esperado || '')}<br>
          <span style="color:var(--red)">OBTENIDO: </span>${escHtml(h.obtenido || '')}
        </div>
        <div class="technique-row">
          ${tecnicas.map(t => `<span class="tech-badge"><i class="bi bi-cpu-fill"></i>${escHtml(t)}</span>`).join('')}
        </div>
        <div class="finding-actions">
          <button class="fa-btn" onclick="abrirTicket(event,'${h.id}')">
            <i class="bi bi-ticket-detailed"></i> TICKET JIRA
          </button>
          <button class="fa-btn" onclick="descartar(event,'${h.id}')">
            <i class="bi bi-${desc ? 'arrow-counterclockwise' : 'slash-circle'}"></i>
            ${desc ? 'RESTAURAR' : 'FALSO POSITIVO'}
          </button>
          <span style="font-family:var(--mono);font-size:.58rem;color:var(--text-3);margin-left:auto">
            ${escHtml(h.refCaso || h.ref_caso || '')}
          </span>
        </div>
      </div>
    </div>`;
  }).join('') || `<div style="padding:2rem;text-align:center;font-family:var(--mono);font-size:.7rem;color:var(--text-4)">Sin hallazgos para este filtro.</div>`;
}

function filtrar(f, btn) {
  document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  renderizarHallazgos(f);
}

function toggleH(id) {
  document.getElementById('fc-' + id).classList.toggle('expanded');
}

function descartar(e, id) {
  e.stopPropagation();
  hallazgosDescartados.has(id)
    ? hallazgosDescartados.delete(id)
    : hallazgosDescartados.add(id);
  renderizarHallazgos(filtroActivo);
  toast(hallazgosDescartados.has(id) ? id + ' marcado como falso positivo.' : id + ' restaurado.');
}

// ═══════════════════════════════════════════════════════════════════════
// EXPORTAR PDF — Backend Python con ReportLab
// ═══════════════════════════════════════════════════════════════════════
async function exportarPDF() {
  if (!auditId) {
    toast('Ejecuta una auditoría primero para generar el PDF.');
    return;
  }
  const btn = document.getElementById('btn-pdf');
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> GENERANDO PDF CON REPORTLAB...';

  try {
    const resp = await fetch(`${API}/api/exportar/pdf/${auditId}`);
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Error al generar PDF');
    }
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = 'SiDL-Reporte-Auditoria-QA.pdf'; a.click();
    toast('Reporte PDF descargado correctamente ✓');
  } catch (e) {
    toastError('Error PDF: ' + e.message + '. Verifica que ReportLab esté instalado.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-file-pdf"></i> DESCARGAR REPORTE PDF (ReportLab)';
  }
}

// ═══════════════════════════════════════════════════════════════════════
// TICKET JIRA
// ═══════════════════════════════════════════════════════════════════════
function abrirTicket(e, id) {
  e.stopPropagation();
  const h = hallazgosData.find(x => x.id === id);
  if (!h) return;
  hallazgoTicketActual = h;
  const etiqSev = { critical:'CRÍTICO', high:'ALTO', medium:'MEDIO', low:'BAJO' };
  const tecnicas = Array.isArray(h.tecnicas) ? h.tecnicas : [];
  document.getElementById('ticket-body').innerHTML = `
    <div class="t-field"><div class="t-label">RESUMEN</div>
      <div class="t-val">[${escHtml(h.id)}][${etiqSev[h.severidad]}] ${escHtml(h.titulo)}</div>
    </div>
    <div class="t-field"><div class="t-label">REQUISITO VINCULADO</div>
      <div class="t-val">${escHtml(h.clausula || '')}</div>
    </div>
    <div class="t-field"><div class="t-label">DESCRIPCIÓN</div>
      <div class="t-val">${escHtml(h.desc || h.descripcion || '')}</div>
    </div>
    <div class="t-field"><div class="t-label">TÉCNICAS DE DETECCIÓN</div>
      <div class="t-val">${escHtml(tecnicas.join(' · '))}</div>
    </div>
    <div class="t-field"><div class="t-label">PASOS PARA REPRODUCIR</div>
      <div class="t-val">1. Navegar a la página objetivo.\n2. Inspeccionar el elemento referenciado.\n3. Comparar con requisito SRS ${escHtml(h.clausula?.split('—')[0]?.trim() || '')}.\n4. Documentar discrepancia visual.</div>
    </div>
    <div class="t-field"><div class="t-label">RESULTADO ESPERADO</div>
      <div class="t-val">${escHtml(h.esperado || '')}</div>
    </div>
    <div class="t-field"><div class="t-label">RESULTADO ACTUAL</div>
      <div class="t-val">${escHtml(h.obtenido || '')}</div>
    </div>
    <div class="t-field"><div class="t-label">SEVERIDAD / PRIORIDAD</div>
      <div class="t-val">${etiqSev[h.severidad]} / ${h.severidad==='critical'||h.severidad==='high'?'P1':'P2'}</div>
    </div>
    <div class="t-field"><div class="t-label">ID AUDITORÍA (SQLite)</div>
      <div class="t-val">${escHtml(auditId || 'demo')}</div>
    </div>
    <div class="t-field"><div class="t-label">GENERADO POR</div>
      <div class="t-val">SiDL MVC v2.0 — FastAPI + SQLite + Gemini 1.5 Pro — ${new Date().toISOString()}</div>
    </div>`;
  abrirModal('modal-ticket');
}

function copiarTicket() {
  if (!hallazgoTicketActual) return;
  const h = hallazgoTicketActual;
  const etiqSev = { critical:'CRÍTICO', high:'ALTO', medium:'MEDIO', low:'BAJO' };
  const tecnicas = Array.isArray(h.tecnicas) ? h.tecnicas : [];
  const t = `[${h.id}][${etiqSev[h.severidad]}] ${h.titulo}

Cláusula: ${h.clausula || ''}
Esperado: ${h.esperado || ''}
Obtenido: ${h.obtenido || ''}
Técnicas: ${tecnicas.join(', ')}
ID Auditoría: ${auditId || 'demo'}

Generado por SiDL MVC v2.0 — Smart Interface & Documentation Lens`;
  navigator.clipboard.writeText(t).then(() => {
    toast('Ticket copiado para Jira ✓');
    cerrarModal('modal-ticket');
  });
}

function exportarJiraLote() {
  const etiqSev = { critical:'CRÍTICO', high:'ALTO', medium:'MEDIO', low:'BAJO' };
  const out = hallazgosData.map(h => {
    const tecnicas = Array.isArray(h.tecnicas) ? h.tecnicas : [];
    return `[${h.id}][${etiqSev[h.severidad]}] ${h.titulo}
Cláusula: ${h.clausula || ''}
Esperado: ${h.esperado || ''}
Obtenido: ${h.obtenido || ''}
Técnicas: ${tecnicas.join(', ')}`;
  }).join('\n\n---\n\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([out], { type: 'text/plain;charset=utf-8' }));
  a.download = 'sidl-jira-lote.txt';
  a.click();
  toast('Exportación masiva Jira descargada ✓');
}

// ═══════════════════════════════════════════════════════════════════════
// AUTENTICACIÓN — Llama al Backend Python + SQLite
// ═══════════════════════════════════════════════════════════════════════
function tabAuth(t) {
  document.getElementById('auth-in').style.display  = t === 'in'  ? 'block' : 'none';
  document.getElementById('auth-reg').style.display = t === 'reg' ? 'block' : 'none';
  document.getElementById('atab-in').classList.toggle('active',  t === 'in');
  document.getElementById('atab-reg').classList.toggle('active', t === 'reg');
  document.getElementById('si-err').style.display = 'none';
  document.getElementById('rg-err').style.display = 'none';
}

async function doLogin() {
  const email     = document.getElementById('si-email').value.trim().toLowerCase();
  const contrasena = document.getElementById('si-pass').value;
  const err = document.getElementById('si-err');
  err.style.display = 'none';

  if (!email || !contrasena) {
    err.textContent = 'Por favor completa todos los campos.';
    err.style.display = 'block';
    return;
  }

  try {
    const resp = await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, contrasena }),
    });
    if (!resp.ok) {
      const e = await resp.json();
      err.textContent = e.detail;
      err.style.display = 'block';
      return;
    }
    const data = await resp.json();
    usuarioActual = { id: data.id, nombre: data.nombre, email: data.email, num_auditorias: data.num_auditorias };
    cerrarModal('modal-auth');
    actualizarNavbar();
    toast(`¡Bienvenido de nuevo, ${data.nombre.split(' ')[0]}! ✓`);
  } catch (e) {
    err.textContent = 'Error de conexión con el servidor Python.';
    err.style.display = 'block';
  }
}

async function doRegistro() {
  const nombre    = document.getElementById('rg-name').value.trim();
  const email     = document.getElementById('rg-email').value.trim().toLowerCase();
  const contrasena = document.getElementById('rg-pass').value;
  const confirmar = document.getElementById('rg-conf').value;
  const err = document.getElementById('rg-err');
  err.style.display = 'none';

  try {
    const resp = await fetch(`${API}/api/auth/registro`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre, email, contrasena, confirmar }),
    });
    if (!resp.ok) {
      const e = await resp.json();
      err.textContent = e.detail;
      err.style.display = 'block';
      return;
    }
    const data = await resp.json();
    usuarioActual = { id: data.id, nombre: data.nombre, email: data.email, num_auditorias: 0 };
    cerrarModal('modal-auth');
    actualizarNavbar();
    toast(`¡Cuenta creada! Bienvenido, ${data.nombre.split(' ')[0]} ✓`);
  } catch (e) {
    err.textContent = 'Error de conexión con el servidor Python.';
    err.style.display = 'block';
  }
}

function cerrarSesion() {
  usuarioActual = null;
  actualizarNavbar();
  toast('Sesión cerrada correctamente.');
}

function abrirAuth() {
  abrirModal('modal-auth');
  tabAuth('in');
}

function actualizarNavbar() {
  const area = document.getElementById('nb-auth-area');
  area.style.cssText = 'display:flex;align-items:center;gap:6px;flex-wrap:nowrap;flex-shrink:0';
  if (usuarioActual) {
    const ini = usuarioActual.nombre.split(' ').map(w => w[0]).join('').substring(0,2).toUpperCase();
    area.innerHTML = `
      <div class="user-chip-nb" onclick="abrirHistorial()">
        <div class="u-avatar">${ini}</div>
        ${escHtml(usuarioActual.nombre.split(' ')[0].toUpperCase())}
        <span class="hist-badge">${usuarioActual.num_auditorias}</span>
      </div>
      <button class="topbar-btn" onclick="abrirHistorial()">
        <i class="bi bi-clock-history"></i> HISTORIAL
      </button>
      <button class="topbar-btn" onclick="cerrarSesion()" title="Cerrar sesión">
        <i class="bi bi-box-arrow-right"></i>
      </button>`;
  } else {
    area.innerHTML = `<button class="topbar-btn" onclick="abrirAuth()">
      <i class="bi bi-person"></i> INICIAR SESIÓN
    </button>`;
  }
}

// ═══════════════════════════════════════════════════════════════════════
// HISTORIAL — Llama al Backend con datos de SQLite
// ═══════════════════════════════════════════════════════════════════════
async function abrirHistorial() {
  if (!usuarioActual) { abrirAuth(); return; }
  abrirModal('modal-historial');
  document.getElementById('historial-body').innerHTML = `
    <div style="text-align:center;padding:2rem;font-family:var(--mono);font-size:.7rem;color:var(--text-3)">
      <div class="spinner" style="margin:0 auto 1rem"></div>
      Cargando historial desde SQLite...
    </div>`;
  try {
    const resp = await fetch(`${API}/api/auditoria/historial/${encodeURIComponent(usuarioActual.id)}`);
    const data = await resp.json();
    renderizarHistorial(data.auditorias || []);
  } catch (e) {
    document.getElementById('historial-body').innerHTML =
      `<div style="padding:2rem;text-align:center;color:var(--red);font-family:var(--mono);font-size:.7rem">Error al cargar el historial.</div>`;
  }
}

function renderizarHistorial(lista) {
  const el = document.getElementById('historial-body');
  if (!lista.length) {
    el.innerHTML = `<div class="hist-empty">
      <i class="bi bi-inbox"></i>
      Aún no hay auditorías guardadas.<br>
      Ejecuta una auditoría para iniciar tu historial en SQLite.
    </div>`;
    return;
  }
  el.innerHTML =
    `<div style="font-family:var(--mono);font-size:.6rem;color:var(--text-3);margin-bottom:1rem">
      ${lista.length} AUDITORÍA${lista.length !== 1 ? 'S' : ''} EN SQLITE
    </div>` +
    lista.map(a => {
      const col = a.puntaje >= 80 ? 'var(--green)' : a.puntaje >= 55 ? 'var(--amber)' : 'var(--red)';
      return `<div class="hist-item">
        <div class="hist-top">
          <div class="hist-score-chip" style="color:${col}">${a.puntaje}</div>
          <div style="flex:1">
            <div style="font-weight:700;font-size:.82rem">${escHtml(a.archivo_srs || '—')}</div>
            <div style="font-family:var(--mono);font-size:.6rem;color:var(--text-3);margin-top:2px">
              <i class="bi bi-image me-1" style="color:var(--sky)"></i>${escHtml(a.archivo_ui || '—')}
            </div>
          </div>
          <div style="font-family:var(--mono);font-size:.6rem;color:var(--text-3);text-align:right">
            ${escHtml(a.fecha || '—')}
          </div>
        </div>
        <div class="hist-bottom">
          <span class="prio critical" style="font-size:.55rem">${a.criticos || 0} CRÍT.</span>
          <span class="prio high"     style="font-size:.55rem">${a.altos    || 0} ALTO</span>
          <span class="prio medium"   style="font-size:.55rem">${a.medios   || 0} MED.</span>
          <span class="prio low"      style="font-size:.55rem">${a.bajos    || 0} BAJO</span>
          <span style="font-family:var(--mono);font-size:.55rem;color:var(--text-4);margin-left:auto">
            ${escHtml(a.id?.substring(0,8) || '')}
          </span>
          <button class="row-btn del" onclick="eliminarAudit('${a.id}')" title="Eliminar">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      </div>`;
    }).join('');
}

async function eliminarAudit(id) {
  if (!usuarioActual) return;
  await fetch(`${API}/api/auditoria/eliminar/${id}/${usuarioActual.id}`, { method: 'DELETE' });
  if (usuarioActual.num_auditorias > 0) usuarioActual.num_auditorias--;
  actualizarNavbar();
  abrirHistorial();
  toast('Auditoría eliminada de SQLite ✓');
}

// ═══════════════════════════════════════════════════════════════════════
// UTILIDADES
// ═══════════════════════════════════════════════════════════════════════
function abrirModal(id)  { document.getElementById(id).classList.add('show'); }
function cerrarModal(id) { document.getElementById(id).classList.remove('show'); }

// Cerrar modales al clic en el backdrop
document.querySelectorAll('.modal-bd').forEach(m => {
  m.addEventListener('click', e => { if (e.target === m) m.classList.remove('show'); });
});

function toast(msg, tipo = '') {
  const t = document.getElementById('toast');
  t.className = 'toast-nb' + (tipo ? ' ' + tipo : '');
  t.innerHTML = `<i class="bi bi-${tipo === 'error' ? 'exclamation-circle-fill' : 'check-circle-fill'}"></i><span>${msg}</span>`;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3500);
}

function toastError(msg) { toast(msg, 'error'); }

function mostrarLoading(msg = 'Procesando...') {
  document.getElementById('loading-msg').textContent = msg;
  document.getElementById('loading').classList.add('show');
}

function ocultarLoading() {
  document.getElementById('loading').classList.remove('show');
}

function escHtml(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Inicializar
actualizarNavbar();
