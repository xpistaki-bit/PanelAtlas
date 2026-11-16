'use strict';
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const h = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const TE = 17.5;
let LANG = localStorage.getItem('vs_lang') || ((navigator.language || 'de').startsWith('de') ? 'de' : 'en');
/* t('Deutscher Text {n}', {n: 3}) – Deutsch ist der Schlüssel, Englisch steht in i18n.js */
function t(s, v) {
  let o = LANG === 'en' ? (window.I18N_EN[s] ?? s) : s;
  if (v) for (const k in v) o = o.replaceAll('{' + k + '}', v[k]);
  return o;
}
const CAT_KEYS = { ls: 'LS-Schalter', rcd: 'FI-Schalter', rcbo: 'FI/LS', afdd: 'Brandschutzschalter', spd: 'Überspannungsschutz', switch: 'Schalter', meter: 'Zähler', hlak: 'Hauptleitungsabzweigklemmen', terminal: 'Reihenklemmen', relay: 'Schaltgeräte', blank: 'Leerplätze', other: 'Sonstiges' };
const MOUNT = { AP: 'Aufputz', UP: 'Unterputz', HW: 'Hohlwand' };
const catName = k => t(CAT_KEYS[k] || k);
const loc = () => (LANG === 'en' ? 'en' : 'de');
const num = n => Number(n).toLocaleString(loc());
const q = url => url + (url.includes('?') ? '&' : '?') + 'lang=' + LANG;
const app = $('#app');
let catalogCache = null;

function toast(msg, err) {
  const el = $('#toast'); el.textContent = msg; el.className = 'on' + (err ? ' err' : '');
  clearTimeout(toast.t); toast.t = setTimeout(() => el.className = '', err ? 5000 : 2200);
}
async function api(method, url, body, raw) {
  const opt = { method, headers: { 'X-Lang': LANG } };
  if (raw) opt.body = body; else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
  const r = await fetch(url, opt);
  const data = (r.headers.get('content-type') || '').includes('json') ? await r.json() : await r.text();
  if (!r.ok) { const e = new Error(data?.error || data?.detail || (t('Fehler') + ' ' + r.status)); e.status = r.status; throw e; }
  return data;
}
async function catalog(force) {
  if (!catalogCache || force) catalogCache = await api('GET', '/api/catalog');
  return catalogCache;
}
function dialog(title, html, { ok = t('Speichern'), onOk, onOpen, wide } = {}) {
  return new Promise(res => {
    const d = $('#dlg'), f = $('#dlgform');
    d.classList.toggle('wide', !!wide);
    f.innerHTML = `<h3>${h(title)}</h3><div class="c">${html}</div><div class="f"><button type="button" data-x>${ok ? t('Abbrechen') : t('Schließen')}</button>${ok ? `<button class="pri" type="submit">${h(ok)}</button>` : ''}</div>`;
    const close = v => { d.close(); f.onsubmit = null; res(v); };
    $('[data-x]', f).onclick = () => close(null);
    d.oncancel = () => res(null);
    f.onsubmit = async ev => {
      ev.preventDefault();
      try { const v = onOk ? await onOk(f) : true; if (v !== false) close(v ?? true); } catch (e) { toast(e.message, true); }
    };
    d.showModal();
    onOpen && onOpen(f, close);
    const first = $('input,select,textarea', f); first && first.focus();
  });
}
const fd = f => Object.fromEntries(new FormData(f).entries());
function crumbs(parts) { $('#crumbs').innerHTML = parts.map(([txt, href]) => href ? `<a href="${href}">${h(txt)}</a>` : h(txt)).join(' › '); }
function teStr(mm) { const n = mm / TE; return Math.abs(n * 2 - Math.round(n * 2)) < 0.02 ? num(Math.round(n * 2) / 2) + ' ' + t('TE') : num(mm) + ' mm'; }
function drawHeader() {
  document.documentElement.lang = LANG;
  $('#nav').innerHTML = `<a href="#/">${t('Profile')}</a><a href="#/katalog">${t('Katalog')}</a><a href="#/einstellungen">${t('Einstellungen')}</a>
    <span class="lang" role="group" aria-label="Sprache / Language"><button data-l="de" class="${LANG === 'de' ? 'on' : ''}">DE</button><button data-l="en" class="${LANG === 'en' ? 'on' : ''}">EN</button></span>`;
  $$('#nav [data-l]').forEach(b => b.onclick = () => { LANG = b.dataset.l; localStorage.setItem('vs_lang', LANG); drawHeader(); route(); });
}

/* ---------------------------------------------------------------- Router */
async function route() {
  const p = location.hash.replace(/^#\/?/, '').split('/');
  document.body.classList.toggle('home', !p[0]);
  try {
    if (p[0] === 'p' && p[1]) await viewProfile(+p[1]);
    else if (p[0] === 'c' && p[1]) await viewEditor(+p[1]);
    else if (p[0] === 'katalog') await viewCatalog();
    else if (p[0] === 'einstellungen') await viewSettings();
    else await viewProfiles();
  } catch (e) {
    if (e.status === 401) return needLogin(e.message);
    app.innerHTML = `<div class="page"><h1>${t('Das hat nicht geklappt')}</h1><p class="sub">${h(e.message)}</p><a class="btn" href="#/">${t('Zur Übersicht')}</a></div>`;
  }
}
async function needLogin(msg) {
  const admin = /Admin/.test(msg);
  const p = location.hash.replace(/^#\/?/, '').split('/');
  const pid = p[0] === 'p' ? +p[1] : null;
  app.innerHTML = `<div class="page"><h1>${t('Geschützt')}</h1><p class="sub">${h(msg)}</p><div class="row"><button class="pri" id="lg">${t('Anmelden')}</button><a class="btn" href="#/">${t('Zur Übersicht')}</a></div></div>`;
  $('#lg').onclick = async () => {
    const ok = await dialog(admin ? t('Admin-Anmeldung') : t('Profil entsperren'), `<label>${t('Passwort')}</label><input type="password" name="password" required>`, {
      ok: t('Anmelden'), onOk: async f => {
        if (admin) await api('POST', '/api/admin/login', fd(f));
        else if (pid) await api('POST', `/api/profiles/${pid}/login`, fd(f));
        else {
          const all = await api('GET', '/api/profiles'); let hit = false;
          for (const pr of all.filter(x => x.locked && !x.open)) { try { await api('POST', `/api/profiles/${pr.id}/login`, fd(f)); hit = true; } catch (e) { /* nächstes Profil */ } }
          if (!hit) throw new Error(t('Falsches Passwort'));
        }
      }
    });
    if (ok) route();
  };
  $('#lg').click();
}
window.addEventListener('hashchange', route);

/* ---------------------------------------------------------------- Profile (Startseite) */
async function viewProfiles() {
  crumbs([]);
  const list = await api('GET', '/api/profiles');
  app.innerHTML = `<div class="hero"><div class="herotext"><img src="/logo.svg" alt="" width="64" height="64"><div><h1>PanelAtlas</h1>
    <p>${t('Stromkreisverteiler maßhaltig dokumentieren, beschriften und drucken.')}</p></div></div>
    <div class="heropanel"><h2>${t('Profile')}</h2>
    <div class="cards">${list.map(p => `<button class="card" data-id="${p.id}"><b>${p.locked ? '🔒 ' : ''}${h(p.name)}</b><small>${p.configs === 1 ? t('1 Konfiguration') : t('{n} Konfigurationen', { n: p.configs })}</small></button>`).join('')}
    <button class="card new" id="newp">${t('+ Neues Profil')}</button></div>
    <p class="hint">${t('Ein Profil bündelt Verteiler-Konfigurationen, zum Beispiel pro Haus oder Kunde. Ein Passwort ist optional.')}</p></div></div>`;
  $$('.card[data-id]').forEach(b => b.onclick = () => location.hash = '#/p/' + b.dataset.id);
  $('#newp').onclick = async () => {
    const r = await dialog(t('Neues Profil'), `<label>${t('Name')}</label><input name="name" required placeholder="${t('z. B. Zuhause')}"><label>${t('Passwort (optional)')}</label><input name="password" type="password" autocomplete="new-password"><div class="info">${t('Mit Passwort sind die Konfigurationen dieses Profils erst nach Anmeldung sichtbar und änderbar.')}</div>`,
      { ok: t('Anlegen'), onOk: f => api('POST', '/api/profiles', fd(f)) });
    if (r) location.hash = '#/p/' + r.id;
  };
}

async function viewProfile(pid) {
  const { profile, configs } = await api('GET', `/api/profiles/${pid}/configs`);
  crumbs([[profile.name]]);
  app.innerHTML = `<div class="page"><div class="row"><h1>${h(profile.name)}</h1><span class="grow"></span>
    <button id="pset">${t('Profil bearbeiten')}</button><button class="pri" id="newc">${t('+ Neue Konfiguration')}</button></div>
  <p class="sub">${profile.locked ? '🔒 ' + t('Passwortgeschützt') : t('Ohne Passwort')}</p>
  ${configs.length ? `<table><tr><th>${t('Name')}</th><th>${t('Ort')}</th><th>${t('Schrank')}</th><th>${t('Belegung')}</th><th>${t('Geändert')}</th><th></th></tr>${configs.map(c => `
    <tr><td><a href="#/c/${c.id}"><b>${h(c.name)}</b></a></td><td>${h(c.location)}</td><td class="mono">${h(c.enclosure)}</td>
    <td><div class="meter ${c.stats.used_te > c.stats.total_te ? 'over' : ''}"><i style="width:${Math.min(100, c.stats.used_te / c.stats.total_te * 100)}%"></i></div><small>${num(c.stats.used_te)} / ${num(c.stats.total_te)} ${t('TE')}</small></td>
    <td>${h((c.updated || '').replace('T', ' ').slice(0, 16))}</td>
    <td class="act"><a class="btn sm" href="${q(`/api/configs/${c.id}/pdf`)}" target="_blank">PDF</a> <a class="btn sm" href="${q(`/api/configs/${c.id}/csv`)}">CSV</a>
      <button class="sm" data-dup="${c.id}">${t('Duplizieren')}</button> <button class="sm danger" data-del="${c.id}" data-name="${h(c.name)}">${t('Löschen')}</button></td></tr>`).join('')}</table>`
      : `<div class="info">${t('Noch keine Konfiguration. Lege die erste an und wähle dabei den Schrank aus.')}</div>`}</div>`;
  $('#newc').onclick = () => newConfig(pid);
  $$('[data-dup]').forEach(b => b.onclick = async () => { await api('POST', `/api/profiles/${pid}/configs`, { copy_of: +b.dataset.dup }); route(); });
  $$('[data-del]').forEach(b => b.onclick = async () => {
    if (await dialog(t('Konfiguration löschen'), `<p>${t('„{n}“ wird endgültig gelöscht.', { n: h(b.dataset.name) })}</p>`, { ok: t('Löschen') })) { await api('DELETE', '/api/configs/' + b.dataset.del); route(); }
  });
  $('#pset').onclick = async () => {
    const r = await dialog(t('Profil bearbeiten'), `<label>${t('Name')}</label><input name="name" value="${h(profile.name)}" required>
      <label>${t('Passwort')}</label><select name="pwmode"><option value="keep">${t('unverändert lassen')}</option><option value="set">${t('neu setzen')}</option>${profile.locked ? `<option value="clear">${t('entfernen')}</option>` : ''}</select>
      <input name="password" type="password" placeholder="${t('Neues Passwort')}" style="margin-top:6px" autocomplete="new-password">
      <p style="margin-top:16px"><button type="button" class="danger" id="delp">${t('Profil mit allen Konfigurationen löschen')}</button></p>`, {
      onOpen: f => $('#delp', f).onclick = async () => { if (confirm(t('Profil „{n}“ wirklich mit allen Konfigurationen löschen?', { n: profile.name }))) { await api('DELETE', '/api/profiles/' + pid); $('#dlg').close(); location.hash = '#/'; } },
      onOk: async f => {
        const v = fd(f), body = { name: v.name };
        if (v.pwmode === 'set') { if (!v.password) throw new Error(t('Bitte ein Passwort eingeben')); body.password = v.password; }
        if (v.pwmode === 'clear') body.password = '';
        await api('PUT', '/api/profiles/' + pid, body);
      }
    });
    if (r) route();
  };
}

function enclosurePicker(encs, selId) {
  const mans = [...new Set(encs.map(e => e.manufacturer))];
  return `<div class="two"><div><label>${t('Hersteller')}</label><select id="fman"><option value="">${t('alle')}</option>${mans.map(m => `<option>${h(m)}</option>`).join('')}</select></div>
    <div><label>${t('Montage')}</label><select id="fmount"><option value="">${t('alle')}</option>${Object.entries(MOUNT).map(([k, v]) => `<option value="${k}">${t(v)}</option>`).join('')}</select></div></div>
    <div class="pick" id="pick"></div><input type="hidden" name="enclosure_id" value="${selId || ''}">`;
}
function wirePicker(f, encs) {
  const draw = () => {
    const m = $('#fman', f).value, mo = $('#fmount', f).value, cur = $('[name=enclosure_id]', f).value;
    $('#pick', f).innerHTML = encs.filter(e => (!m || e.manufacturer === m) && (!mo || e.mount === mo)).map(e =>
      `<div data-id="${e.id}" class="${cur == e.id ? 'on' : ''}"><b class="mono">${h(e.article)}</b><span>${h(e.manufacturer)} ${h(e.series)} · ${h(t(MOUNT[e.mount] || ''))} · ${e.fields > 1 ? t('{n} Felder', { n: e.fields }) + ' · ' : ''}${t('{n} Reihen', { n: e.rows })} · ${e.rows * e.fields * e.te_per_row} ${t('TE')} · ${e.height_mm}×${e.width_mm} mm</span></div>`).join('') || `<div><span>${t('Kein Schrank passt zum Filter.')}</span></div>`;
    $$('#pick div[data-id]', f).forEach(d => d.onclick = () => { $('[name=enclosure_id]', f).value = d.dataset.id; draw(); });
  };
  $('#fman', f).onchange = $('#fmount', f).onchange = draw; draw();
}
async function newConfig(pid) {
  const encs = (await catalog()).filter(e => e.kind === 'enclosure');
  const r = await dialog(t('Neue Konfiguration'), `<div class="two"><div><label>${t('Name')}</label><input name="name" required placeholder="${t('z. B. Unterverteilung Keller')}"></div>
    <div><label>${t('Ort (optional)')}</label><input name="location" placeholder="${t('z. B. Keller')}"></div></div>
    <h2 style="margin-top:14px">${t('Schrank')}</h2>${enclosurePicker(encs)}
    <div class="info">${t('Fehlt dein Schrank? Unter „Katalog“ lassen sich eigene Schränke mit Maßen, Reihen und TE anlegen.')}</div>`, {
    ok: t('Anlegen'), onOpen: f => wirePicker(f, encs),
    onOk: f => { const v = fd(f); if (!v.enclosure_id) throw new Error(t('Bitte einen Schrank auswählen')); return api('POST', `/api/profiles/${pid}/configs`, { name: v.name, location: v.location, enclosure_id: +v.enclosure_id }); }
  });
  if (r) location.hash = '#/c/' + r.id;
}

/* ---------------------------------------------------------------- Editor */
const ed = {};
async function viewEditor(cid) {
  const [c, cat] = await Promise.all([api('GET', '/api/configs/' + cid), catalog()]);
  Object.assign(ed, { id: cid, name: c.name, cfg: c.data, checks: c.checks, stats: c.stats, sel: null, selRow: null, tab: 'dev', zoom: null, devs: cat.filter(x => x.kind === 'device'), pid: c.profile_id });
  crumbs([[c.profile_name, '#/p/' + c.profile_id], [c.name]]);
  const mans = [...new Set(ed.devs.map(d => d.manufacturer))];
  app.innerHTML = `<div class="editor">
   <aside class="pane left"><div class="head"><div class="two"><select id="pman" aria-label="${t('Hersteller')}"><option value="">${t('Alle Hersteller')}</option>${mans.map(m => `<option>${h(m)}</option>`).join('')}</select>
      <select id="pcat" aria-label="${t('Art')}"><option value="">${t('Alle Arten')}</option>${Object.keys(CAT_KEYS).map(k => `<option value="${k}">${catName(k)}</option>`).join('')}</select></div>
      <input id="psearch" placeholder="${t('Suchen: B16, FI 40, PT 2,5 …')}" style="margin-top:8px">
      <div class="legend"><span class="w p1">${t('1-polig')}</span><span class="w p2">${t('2-polig')}</span><span class="w p3">${t('3-polig')}</span><span class="w p4">${t('4-polig')}</span></div></div>
      <div class="body" style="padding:0"><ul class="pal" id="pal"></ul></div></aside>
   <section class="stage"><div class="tools"><input class="name" id="cname" value="${h(c.name)}" aria-label="${t('Name der Konfiguration')}">
      <span class="save" id="save">${t('gespeichert')}</span><span class="grow"></span>
      <button class="sm" id="zo" title="${t('Verkleinern')}">−</button><button class="sm" id="zf">${t('Einpassen')}</button><button class="sm" id="zi" title="${t('Vergrößern')}">+</button>
      <button class="sm" id="bpdf">${t('Drucken / PDF')}</button><button class="sm" id="blabel">${t('Etiketten')}</button>
      <a class="btn sm" href="${q(`/api/configs/${cid}/csv`)}">CSV</a><a class="btn sm" href="${q(`/api/configs/${cid}/csv?light=1`)}" title="${t('Nur Reihe, Position, Funktion, Raum')}">CSV light</a></div>
     <div class="canvas" id="canvas"></div></section>
   <aside class="pane right"><div class="tabs"><button data-tab="dev">${t('Gerät')}</button><button data-tab="chk">${t('Prüfung')}</button><button data-tab="enc">${t('Schrank')}</button></div><div class="body" id="insp"></div></aside></div>`;
  $('#pman').value = localStorage.getItem('vs_man') || '';
  $('#pman').onchange = () => { localStorage.setItem('vs_man', $('#pman').value); drawPalette(); };
  $('#pcat').onchange = drawPalette; $('#psearch').oninput = drawPalette;
  $('#cname').onchange = e => { ed.name = e.target.value.trim() || ed.name; save(); };
  $$('.tabs button').forEach(b => b.onclick = () => { ed.tab = b.dataset.tab; drawInspector(); });
  $('#zi').onclick = () => { ed.zoom *= 1.25; applyZoom(); };
  $('#zo').onclick = () => { ed.zoom /= 1.25; applyZoom(); };
  $('#zf').onclick = () => { ed.zoom = null; applyZoom(); };
  $('#blabel').onclick = labelDialog; $('#bpdf').onclick = pdfDialog;
  drawPalette(); drawSvg(c.svg); drawInspector(); wireCanvas();
}
function drawPalette() {
  const m = $('#pman').value, c = $('#pcat').value, words = $('#psearch').value.toLowerCase().trim().split(/\s+/).filter(Boolean);
  let list = ed.devs.filter(d => (!m || d.manufacturer === m || d.manufacturer === 'Allgemein') && (!c || d.category === c));
  if (words.length) list = list.filter(d => { const s = `${d.manufacturer} ${d.article} ${d.name} ${d.characteristic || ''}${d.current_a || ''}`.toLowerCase(); return words.every(w => s.includes(w)); });
  let out = '', last = '';
  const order = Object.keys(CAT_KEYS);
  list.sort((a, b) => order.indexOf(a.category) - order.indexOf(b.category) || a.manufacturer.localeCompare(b.manufacturer) || (a.poles || 0) - (b.poles || 0) || (a.characteristic || '').localeCompare(b.characteristic || '') || (a.current_a || 0) - (b.current_a || 0));
  const modular = ['ls', 'rcd', 'rcbo', 'afdd', 'spd', 'switch'];
  for (const d of list.slice(0, 500)) {
    if (d.category !== last) { out += `<li class="grp">${h(catName(d.category))}</li>`; last = d.category; }
    const pc = modular.includes(d.category) ? 'p' + Math.min(4, Math.max(1, d.poles || 1)) : 'p0';
    out += `<li data-id="${d.id}" class="${pc}" title="${h(d.name)} – ${t('klicken zum Einsetzen')}">${d.image ? `<img src="/media/${h(d.image)}" alt="">` : ''}<div class="t"><b>${h(d.article)}</b><span>${h(d.manufacturer)} · ${h(d.name)}</span></div><span class="w ${pc}">${teStr(d.width_mm)}</span></li>`;
  }
  if (list.length > 500) out += `<li class="grp more">${t('Weitere {n} Treffer – bitte Suche eingrenzen', { n: list.length - 500 })}</li>`;
  $('#pal').innerHTML = out || `<li class="grp">${t('Nichts gefunden')}</li>`;
  $$('#pal li[data-id]').forEach(li => li.onclick = () => addDevice(ed.devs.find(d => d.id == li.dataset.id)));
}
const rowCount = () => ed.cfg.enclosure.rows * (ed.cfg.enclosure.fields || 1);
const rowWidth = () => (ed.cfg.enclosure.te_per_row || 12) * TE;
const rowUsed = r => ed.cfg.items.filter(i => i.row === r).reduce((s, i) => s + i.dev.width_mm, 0);
function nextTag(cat) {
  const pre = { ls: 'F', rcd: 'F', rcbo: 'F', afdd: 'F', spd: 'F', switch: 'Q', relay: 'K', hlak: 'X', meter: 'P' }[cat];
  if (!pre) return '';
  const nums = ed.cfg.items.map(i => (i.tag || '').match(new RegExp('^' + pre + '(\\d+)$'))).filter(Boolean).map(m => +m[1]);
  return pre + ((nums.length ? Math.max(...nums) : 0) + 1);
}
function addDevice(d) {
  let row = ed.selRow ?? (ed.sel ? ed.cfg.items.find(i => i.id === ed.sel)?.row : null);
  if (row == null) { row = 0; for (let r = 0; r < rowCount(); r++) if (rowUsed(r) + d.width_mm <= rowWidth() + 0.01) { row = r; break; } }
  const { id, kind, custom, ...dev } = d;
  const it = { id: Math.random().toString(36).slice(2, 12), row, dev, tag: nextTag(d.category), function: '', room: '', phase: '', rcd_id: '', note: '' };
  if (d.category === 'ls') { const rc = [...ed.cfg.items].reverse().find(i => i.row === row && i.dev.category === 'rcd'); if (rc) it.rcd_id = rc.id; autoPhase(it); }
  ed.cfg.items.push(it); ed.selPen = null; ed.sel = it.id; ed.tab = 'dev';
  if (rowUsed(row) > rowWidth() + 0.01) toast(t('Reihe {n} ist damit überbelegt', { n: row + 1 }), true);
  save(); drawInspector();
}
let saveT = null, saveSeq = 0;
function save(delay = 0) {
  $('#save').textContent = t('speichert …');
  clearTimeout(saveT);
  saveT = setTimeout(async () => {
    const seq = ++saveSeq;
    try {
      const r = await api('PUT', '/api/configs/' + ed.id, { name: ed.name, data: ed.cfg });
      if (seq !== saveSeq) return;
      ed.checks = r.checks; ed.stats = r.stats; drawSvg(r.svg);
      if (ed.tab !== 'dev' || !$('#insp').contains(document.activeElement)) drawInspector(); else updateTabCounts();
      $('#save').textContent = t('gespeichert');
    } catch (e) { $('#save').textContent = t('nicht gespeichert'); toast(e.message, true); }
  }, delay);
}
function drawSvg(svg) {
  const cv = $('#canvas'), st = [cv.scrollLeft, cv.scrollTop];
  cv.innerHTML = svg; applyZoom(); markSel();
  cv.scrollLeft = st[0]; cv.scrollTop = st[1];
}
function applyZoom() {
  const svg = $('#canvas svg'); if (!svg) return;
  const vb = svg.viewBox.baseVal, cv = $('#canvas');
  if (!ed.zoom) ed.zoom = Math.max(0.5, Math.min((cv.clientWidth - 40) / vb.width, 2.2));
  ed.zoom = Math.max(0.3, Math.min(ed.zoom, 8));
  svg.setAttribute('width', vb.width * ed.zoom); svg.setAttribute('height', vb.height * ed.zoom);
}
function markSel() {
  $$('#canvas .item').forEach(g => g.classList.toggle('sel', g.dataset.id === ed.sel));
  $$('#canvas .row').forEach(g => g.classList.toggle('sel', ed.selRow != null && +g.dataset.row === ed.selRow));
  $$('#canvas .pen').forEach(g => g.classList.toggle('sel', g.dataset.pen === ed.selPen));
}
function svgPoint(ev) {
  const svg = $('#canvas svg'), pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
  return pt.matrixTransform(svg.getScreenCTM().inverse());
}
function wireCanvas() {
  const cv = $('#canvas'); let drag = null;
  cv.onpointerdown = ev => {
    const g = ev.target.closest('.item');
    const pn = ev.target.closest('.pen');
    if (pn && !g) { ed.selPen = pn.dataset.pen; ed.sel = null; ed.selRow = null; ed.tab = 'dev'; markSel(); drawInspector(); return; }
    ed.selPen = null;
    if (g) { drag = { id: g.dataset.id, g, start: svgPoint(ev), moved: false }; ed.sel = g.dataset.id; ed.selRow = null; ed.tab = 'dev'; markSel(); drawInspector(); cv.setPointerCapture(ev.pointerId); return; }
    const r = ev.target.closest('.rowhit');
    if (r) { ed.selRow = +r.dataset.row; ed.sel = null; markSel(); drawInspector(); }
  };
  cv.onpointermove = ev => {
    if (!drag) return;
    const p = svgPoint(ev), dx = p.x - drag.start.x, dy = p.y - drag.start.y;
    if (!drag.moved && Math.hypot(dx, dy) < 3) return;
    drag.moved = true; drag.g.classList.add('drag'); drag.g.setAttribute('transform', `translate(${dx} ${dy})`);
  };
  cv.onpointerup = ev => {
    if (!drag) return; const d = drag; drag = null;
    if (!d.moved) return;
    const p = svgPoint(ev);
    let row = null;
    for (const r of $$('#canvas .rowhit')) { const x = +r.getAttribute('x'), y = +r.getAttribute('y'), w = +r.getAttribute('width'), hh = +r.getAttribute('height'); if (p.x >= x && p.x <= x + w && p.y >= y && p.y <= y + hh) row = +r.dataset.row; }
    if (row == null) { d.g.removeAttribute('transform'); d.g.classList.remove('drag'); return; }
    const others = $$(`#canvas .item[data-row="${row}"]`).filter(g => g.dataset.id !== d.id);
    moveItem(d.id, row, others.filter(g => +g.dataset.x + +g.dataset.w / 2 < p.x).length);
  };
}
function moveItem(id, row, k) {
  const items = ed.cfg.items, it = items.find(i => i.id === id);
  items.splice(items.indexOf(it), 1); it.row = row;
  const inRow = items.filter(i => i.row === row);
  if (k >= inRow.length) items.push(it); else items.splice(items.indexOf(inRow[k]), 0, it);
  save();
}
function shift(id, dir) {
  const it = ed.cfg.items.find(i => i.id === id), inRow = ed.cfg.items.filter(i => i.row === it.row), k = inRow.indexOf(it) + dir;
  if (k < 0 || k >= inRow.length) return; moveItem(id, it.row, k);
}
function removeItem(id) {
  ed.cfg.items = ed.cfg.items.filter(i => i.id !== id);
  ed.cfg.items.forEach(i => { if (i.rcd_id === id) i.rcd_id = ''; });
  ed.sel = null; save(); drawInspector();
}
function removePen(pos) {
  const e = ed.cfg.enclosure; e.pen_blocks = (e.pen_blocks || ['top', 'bottom']).filter(k => k !== pos);
  ed.selPen = null; save(); drawInspector();
}
document.addEventListener('keydown', ev => {
  if (!location.hash.startsWith('#/c/') || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || $('#dlg').open) return;
  if (ed.selPen && (ev.key === 'Delete' || ev.key === 'Backspace')) { removePen(ed.selPen); ev.preventDefault(); return; }
  if (!ed.sel) return;
  if (ev.key === 'Delete' || ev.key === 'Backspace') { removeItem(ed.sel); ev.preventDefault(); }
  if (ev.key === 'ArrowLeft') { shift(ed.sel, -1); ev.preventDefault(); }
  if (ev.key === 'ArrowRight') { shift(ed.sel, 1); ev.preventDefault(); }
});
function updateTabCounts() {
  const open = ed.checks.filter(c => !c.ignored && c.level !== 'info').length;
  $$('.tabs button').forEach(b => { b.classList.toggle('on', b.dataset.tab === ed.tab); if (b.dataset.tab === 'chk') b.innerHTML = t('Prüfung') + (open ? ` <span class="badge ${ed.checks.some(c => !c.ignored && c.level === 'error') ? 'err' : 'warn'}">${open}</span>` : ' <span class="badge ok">✓</span>'); });
}
const MARKS = { red: '#ff1744', yellow: '#ffea00', magenta: '#ff00e5', cyan: '#00e5ff' };
const LCOLS = { yellow: '#fff176', orange: '#ffb74d', red: '#e53935', pink: '#f48fb1', purple: '#8e44ad', blue: '#1e88e5', lightblue: '#90caf9', cyan: '#4dd0e1', green: '#43a047', lime: '#dce775', brown: '#8d6e63', grey: '#cfd8dc' };
const swatches = (attr, map, cur) => `<div class="sw"><button type="button" class="swb none ${!cur ? 'on' : ''}" ${attr}="" title="${t('keine')}">×</button>${Object.entries(map).map(([k, c]) => `<button type="button" class="swb ${cur === k ? 'on' : ''}" ${attr}="${k}" style="background:${c}" title="${k}"></button>`).join('')}</div>`;
function autoPhase(it) {
  const rc = ed.cfg.items.find(i => i.id === it.rcd_id);
  if (!rc || (rc.dev.poles || 2) < 3 || rc.auto_phase === false) return;
  if ((it.dev.poles || 1) >= 3) { it.phase = 'L1-L3'; return; }
  const n = ed.cfg.items.filter(i => i !== it && i.rcd_id === rc.id && (i.dev.poles || 1) < 3).length;
  it.phase = ['L1', 'L2', 'L3'][n % 3];
}
const FN = ['Steckdosen', 'Licht', 'Herd', 'Backofen', 'Geschirrspüler', 'Waschmaschine', 'Trockner', 'Kühlschrank', 'Heizung', 'Wärmepumpe', 'Wallbox', 'Rollläden', 'Netzwerk', 'Reserve'];
function drawInspector() {
  updateTabCounts();
  const el = $('#insp'), cfg = ed.cfg;
  if (ed.tab === 'dev') {
    const it = cfg.items.find(i => i.id === ed.sel);
    if (!it && ed.selPen) {
      const nm = { top: t('oben'), middle: t('Mitte'), bottom: t('unten') }[ed.selPen];
      el.innerHTML = `<div class="info"><b>${t('PE/N-Klemmenblock')} (${nm})</b><br>${t('Mit der Entf-Taste oder dem Knopf wird der Block aus diesem Schrank entfernt. Im Reiter „Schrank“ lässt er sich wieder einschalten.')}</div><button class="danger" id="pendel">${t('Entfernen')}</button>`;
      $('#pendel').onclick = () => removePen(ed.selPen);
      return;
    }
    if (!it) {
      el.innerHTML = ed.selRow != null
        ? `<div class="info">${t('<b>Reihe {n}</b> ist als Ziel gewählt ({u} von {w} TE belegt). Ein Klick auf ein Gerät im Katalog links setzt es hier ein.', { n: ed.selRow + 1, u: num(rowUsed(ed.selRow) / TE), w: rowWidth() / TE })}</div>`
        : `<div class="info">${t('Klicke links auf ein Gerät, um es einzusetzen. Mit einem Klick auf eine Hutschiene legst du die Zielreihe fest. Geräte lassen sich mit der Maus verschieben, auch zwischen Reihen.')}</div>`;
      return;
    }
    const d = it.dev, prot = ['ls', 'rcbo', 'afdd'].includes(d.category), rcds = cfg.items.filter(i => i.dev.category === 'rcd');
    el.innerHTML = `<div class="info"><b class="mono">${h(d.article)}</b> · ${h(d.manufacturer)}<br>${h(d.name)}<br>${teStr(d.width_mm)} · ${d.width_mm} × ${d.height_mm} mm
      ${d.verified === false ? `<br><span class="badge warn">${t('Maße ungeprüft')}</span> ` + h(d.note || t('bitte mit Datenblatt abgleichen')) : (d.note ? '<br>' + h(d.note) : '')}</div>
      <label>${t('Kennzeichnung')}</label><input data-f="tag" value="${h(it.tag)}" placeholder="${t('z. B. F3')}">
      <label>${t('Funktion')}</label><input data-f="function" value="${h(it.function)}" placeholder="${t('z. B. Steckdosen')}" list="fnlist">
      <datalist id="fnlist">${FN.map(x => `<option>${h(t(x))}</option>`).join('')}</datalist>
      <label>${t('Raum')}</label><input data-f="room" value="${h(it.room)}" placeholder="${t('z. B. Küche')}" list="rmlist">
      <datalist id="rmlist">${[...new Set(cfg.items.map(i => i.room).filter(Boolean))].map(x => `<option>${h(x)}</option>`).join('')}</datalist>
      ${prot || d.category === 'rcd' ? `<div class="two"><div><label>${t('Außenleiter')}</label><select data-f="phase">${['', 'L1', 'L2', 'L3', 'L1-L3'].map(p => `<option value="${p}" ${it.phase === p ? 'selected' : ''}>${p || '–'}</option>`).join('')}</select></div>
      ${prot ? `<div><label>${t('Zugeordneter FI')}</label><select data-f="rcd_id"><option value="">${t('– keiner –')}</option>${rcds.map(r => `<option value="${r.id}" ${it.rcd_id === r.id ? 'selected' : ''}>${h(r.tag || r.dev.article)} (${r.dev.current_a} A)</option>`).join('')}</select></div>` : '<div></div>'}</div>` : ''}
      ${prot ? `<label>${t('Angeschlossene Leiter am Abgang')}</label><select data-f="wires"><option value="1" ${it.wires !== '2' ? 'selected' : ''}>${t('1 Leiter (Standard)')}</option><option value="2" ${it.wires === '2' ? 'selected' : ''}>${t('2 Leiter – mit Markierung „2×“')}</option></select>` : ''}
      ${d.category === 'rcd' && (d.poles || 2) >= 3 ? `<label class="chk" style="margin-top:10px"><input type="checkbox" id="autoph" ${it.auto_phase !== false ? 'checked' : ''}> ${t('Nachfolgende Sicherungen automatisch auf L1, L2, L3 verteilen')}</label>` : ''}
      <label>${t('Markierung (Signalfarbe)')}</label>${swatches('data-mark', MARKS, it.mark)}
      <label>${t('Farbe der Beschriftung')}</label>${swatches('data-lcol', LCOLS, it.label_color)}
      <label>${t('Notiz')}</label><textarea data-f="note" rows="2">${h(it.note)}</textarea>
      <div class="two"><div><label>${t('Breite mm')}</label><input type="number" step="0.1" min="1" data-d="width_mm" value="${d.width_mm}"></div><div><label>${t('Höhe mm')}</label><input type="number" step="0.1" min="1" data-d="height_mm" value="${d.height_mm}"></div></div>
      <div class="row" style="margin-top:14px"><button class="sm" id="il" title="${t('nach links')}">←</button><button class="sm" id="ir" title="${t('nach rechts')}">→</button><button class="sm" id="idup">${t('Duplizieren')}</button><span class="grow"></span><button class="sm danger" id="idel">${t('Entfernen')}</button></div>`;
    $$('[data-f]', el).forEach(i => i.oninput = () => { it[i.dataset.f] = i.value; save(i.tagName === 'SELECT' ? 0 : 350); });
    $$('[data-d]', el).forEach(i => i.onchange = () => { const v = parseFloat(i.value); if (v > 0) { d[i.dataset.d] = v; save(); } });
    $$('[data-mark]', el).forEach(b => b.onclick = () => { it.mark = b.dataset.mark; save(); drawInspector(); });
    $$('[data-lcol]', el).forEach(b => b.onclick = () => { it.label_color = b.dataset.lcol; save(); drawInspector(); });
    if ($('#autoph')) $('#autoph').onchange = ev => {
      it.auto_phase = ev.target.checked;
      if (ev.target.checked) cfg.items.filter(i => i.rcd_id === it.id && !i.phase).forEach(autoPhase);
      save();
    };
    $('#il').onclick = () => shift(it.id, -1); $('#ir').onclick = () => shift(it.id, 1);
    $('#idel').onclick = () => removeItem(it.id);
    $('#idup').onclick = () => {
      const c = JSON.parse(JSON.stringify(it)); c.id = Math.random().toString(36).slice(2, 12); c.tag = nextTag(d.category); c.function = ''; c.room = ''; c.mark = '';
      if (c.rcd_id && c.phase) autoPhase(c);
      cfg.items.splice(cfg.items.indexOf(it) + 1, 0, c); ed.sel = c.id; save(); drawInspector();
    };
  } else if (ed.tab === 'chk') {
    const lvl = { error: t('Fehler'), warn: t('Warnung'), info: t('Hinweis') };
    el.innerHTML = `<label class="chk"><input type="checkbox" id="norm" ${cfg.norm_checks ? 'checked' : ''}> ${t('Normhinweise anzeigen (DIN / VDE)')}</label>
      <div class="info">${t('Hinweise blockieren nichts. Wer bewusst abweicht, hakt den Punkt ab; er erscheint dann im Ausdruck als „bewusst abgewichen“. Die Prüfung ersetzt keine Abnahme durch eine Elektrofachkraft.')}</div>
      ${ed.checks.map(c => `<div class="chkitem ${c.level} ${c.ignored ? 'ign' : ''}" data-items="${h(c.items.join(','))}">${h(c.text)}
        <div class="n"><span>${lvl[c.level]}${c.norm ? ' · ' + h(c.norm) : ''}</span>${c.level === 'error' && /^(overflow|meter)/.test(c.id) ? '' : `<label class="chk" style="font-size:12px;margin:0"><input type="checkbox" data-ign="${h(c.id)}" ${c.ignored ? 'checked' : ''}> ${t('abweichen')}</label>`}</div></div>`).join('') || `<p>${t('Keine Hinweise.')}</p>`}`;
    $('#norm').onchange = e => { cfg.norm_checks = e.target.checked; save(); };
    $$('[data-ign]', el).forEach(c => c.onchange = () => { const s = new Set(cfg.ignored); c.checked ? s.add(c.dataset.ign) : s.delete(c.dataset.ign); cfg.ignored = [...s]; save(); });
    $$('.chkitem', el).forEach(d => {
      const ids = d.dataset.items.split(',');
      d.onmouseenter = () => $$('#canvas .item').forEach(g => g.classList.toggle('hl', ids.includes(g.dataset.id)));
      d.onmouseleave = () => $$('#canvas .item.hl').forEach(g => g.classList.remove('hl'));
    });
  } else {
    const e = cfg.enclosure, s = ed.stats;
    el.innerHTML = `<div class="info"><b class="mono">${h(e.article)}</b> · ${h(e.manufacturer)} ${h(e.series || '')}<br>${h(e.name)}<br>${e.height_mm} × ${e.width_mm}${e.depth_mm ? ' × ' + e.depth_mm : ''} mm (${t('H × B × T')})<br>${e.fields > 1 ? t('{n} Felder', { n: e.fields }) + ', ' : ''}${t('{r} Reihen à {t} TE, Reihenabstand {p} mm', { r: e.rows, t: e.te_per_row, p: e.row_pitch_mm })}${e.note ? '<br>' + h(e.note) : ''}</div>
      <div class="info">${t('<b>{u} von {t} TE</b> belegt, {f} TE frei', { u: num(s.used_te), t: num(s.total_te), f: num(s.free_te) })}</div>
      <div class="row"><button id="chg">${t('Schrank wechseln')}</button><button id="xfer">${t('Bestückung übernehmen …')}</button></div>
      <label>${t('Ort')}</label><input id="loc" value="${h(cfg.location || '')}" placeholder="${t('z. B. Keller')}">
      <label>${t('Notizen (erscheinen im Ausdruck)')}</label><textarea id="notes" rows="4">${h(cfg.notes || '')}</textarea>
      <label class="chk" style="margin-top:12px"><input type="checkbox" id="cover" ${cfg.view?.cover ? 'checked' : ''}> ${t('Abdeckung mit Beschriftungsfeld anzeigen')}</label>
      <label>${t('Schriftgröße der Beschriftung (Ansicht und PDF)')}</label><select id="lscale">${[[1, '100 %'], [1.3, '130 %'], [1.6, '160 %'], [2, '200 %']].map(([v, l]) => `<option value="${v}" ${(+cfg.view?.label_scale || 1.3) === v ? 'selected' : ''}>${l}${v === 1.3 ? ' (' + t('Standard') + ')' : ''}</option>`).join('')}</select>
      <label>${t('PE/N-Klemmenblöcke im Schrank')}</label><div class="row">${[['top', t('oben')], ['middle', t('Mitte')], ['bottom', t('unten')]].map(([k, l]) => `<label class="chk" style="margin:0"><input type="checkbox" data-pen="${k}" ${(e.pen_blocks || ['top', 'bottom']).includes(k) ? 'checked' : ''}> ${l}</label>`).join('')}</div>
      <h2>${t('Als Datei')}</h2><div class="row"><a class="btn sm" href="/api/configs/${ed.id}/svg" target="_blank">${t('SVG-Bild')}</a><a class="btn sm" href="/api/configs/${ed.id}/json">JSON</a>
        <a class="btn sm" href="${q(`/api/configs/${ed.id}/pdf?download=1`)}">${t('PDF speichern')}</a></div>`;
    $('#loc').oninput = ev => { cfg.location = ev.target.value; save(400); };
    $('#notes').oninput = ev => { cfg.notes = ev.target.value; save(400); };
    $('#cover').onchange = ev => { cfg.view = { ...(cfg.view || {}), cover: ev.target.checked }; save(); };
    $('#lscale').onchange = ev => { cfg.view = { ...(cfg.view || {}), label_scale: +ev.target.value }; save(); };
    $$('[data-pen]', el).forEach(c => c.onchange = () => { e.pen_blocks = $$('[data-pen]', el).filter(x => x.checked).map(x => x.dataset.pen); save(); });
    $('#xfer').onclick = transferDialog;
    $('#chg').onclick = async () => {
      const encs = (await catalog()).filter(x => x.kind === 'enclosure');
      const ok = await dialog(t('Schrank wechseln'), enclosurePicker(encs) + `<div class="info">${t('Die Bestückung bleibt erhalten. Geräte aus Reihen, die es im neuen Schrank nicht gibt, wandern in die letzte Reihe.')}</div>`, {
        ok: t('Übernehmen'), onOpen: f => wirePicker(f, encs), onOk: f => {
          const n = encs.find(x => x.id == fd(f).enclosure_id); if (!n) throw new Error(t('Bitte einen Schrank auswählen'));
          const { id, kind, custom, ...enc } = n; cfg.enclosure = enc;
          const max = enc.rows * (enc.fields || 1) - 1; cfg.items.forEach(i => { if (i.row > max) i.row = max; });
        }
      });
      if (ok) { ed.zoom = null; save(); }
    };
  }
}

/* ---------------------------------------------------------------- Etiketten */
function pdfDialog() {
  let o = { overview: true, detail: true, list: true, notes: true };
  try { o = { ...o, ...JSON.parse(localStorage.getItem('vs_pdf') || '{}') }; } catch (e) { }
  const cb = (k, l) => `<label class="chk"><input type="checkbox" name="${k}" ${o[k] ? 'checked' : ''}> ${l}</label>`;
  dialog(t('Drucken / PDF'), `<p class="sub" style="margin:10px 0 4px">${t('Was soll das PDF enthalten?')}</p>
    ${cb('overview', t('Gesamtansicht des Schranks'))}${cb('detail', t('Detailseiten (Reihen vergrößert)'))}${cb('list', t('Stromkreis- und Geräteliste'))}${cb('notes', t('Hinweise aus der Prüfung und Notizen'))}
    <div class="row" style="margin-top:14px"><button type="submit" class="pri" name="go" value="open">${t('PDF öffnen')}</button><button type="submit" name="go" value="save">${t('PDF speichern')}</button></div>`, {
    ok: '', onOpen: f => $$('[name=go]', f).forEach(b => b.onclick = () => { f.dataset.go = b.value; }),
    onOk: f => {
      const v = fd(f), parts = ['overview', 'detail', 'list'].filter(k => v[k]);
      if (!parts.length) throw new Error(t('Bitte mindestens eine Ansicht auswählen'));
      localStorage.setItem('vs_pdf', JSON.stringify({ overview: !!v.overview, detail: !!v.detail, list: !!v.list, notes: !!v.notes }));
      const url = q(`/api/configs/${ed.id}/pdf?parts=${parts.join(',')}&notes=${v.notes ? 1 : 0}`);
      if (f.dataset.go === 'save') location.href = url + '&download=1'; else window.open(url, '_blank');
    }
  });
}
async function transferDialog() {
  const profs = (await api('GET', '/api/profiles')).filter(p => p.open);
  const groups = [];
  for (const p of profs) { const r = await api('GET', `/api/profiles/${p.id}/configs`); groups.push([p.name, r.configs.filter(c => c.id !== ed.id)]); }
  if (!groups.some(g => g[1].length)) { toast(t('Es gibt keine andere Konfiguration, aus der übernommen werden könnte.'), true); return; }
  let src = null;
  const rows = rowCount();
  const ok = await dialog(t('Bestückung aus anderer Konfiguration übernehmen'), `<label>${t('Quelle')}</label><select name="src"><option value="">${t('– bitte wählen –')}</option>${groups.map(([n, cs]) => cs.length ? `<optgroup label="${h(n)}">${cs.map(c => `<option value="${c.id}">${h(c.name)} (${h(c.enclosure)})</option>`).join('')}</optgroup>` : '').join('')}</select>
    <label>${t('Reihen der Quelle')}</label><div id="xrows" class="info">${t('Zuerst die Quelle wählen.')}</div>
    <div class="two"><div><label>${t('Ziel')}</label><select name="target"><option value="same">${t('gleiche Reihennummer')}</option>${Array.from({ length: rows }, (_, i) => `<option value="${i}">${t('ab Reihe {n}', { n: i + 1 })}</option>`).join('')}</select></div>
    <div><label>${t('Vorhandene Geräte in den Zielreihen')}</label><select name="mode"><option value="replace">${t('ersetzen')}</option><option value="append">${t('behalten, dahinter anfügen')}</option></select></div></div>
    <div class="info">${t('Übernommen werden Geräte mit Beschriftung, Außenleiter, FI-Zuordnung, Farben und Markierungen. Reihen, die es in diesem Schrank nicht gibt, werden ausgelassen.')}</div>`, {
    ok: t('Übernehmen'), wide: true,
    onOpen: f => {
      $('[name=src]', f).onchange = async ev => {
        src = ev.target.value ? await api('GET', '/api/configs/' + ev.target.value) : null;
        if (!src) { $('#xrows', f).innerHTML = t('Zuerst die Quelle wählen.'); return; }
        const used = [...new Set(src.data.items.map(i => i.row))].sort((a, b) => a - b);
        $('#xrows', f).innerHTML = used.length ? `<label class="chk"><input type="checkbox" id="xall" checked> <b>${t('alle Reihen')}</b></label>` + used.map(r => `<label class="chk"><input type="checkbox" name="row_${r}" checked> ${t('Reihe {n}', { n: r + 1 })} · ${t('{n} Geräte', { n: src.data.items.filter(i => i.row === r).length })}</label>`).join('') : t('Die Quelle enthält keine Geräte.');
        if ($('#xall', f)) $('#xall', f).onchange = e2 => $$('[name^=row_]', f).forEach(c => c.checked = e2.target.checked);
      };
    },
    onOk: f => {
      const v = fd(f);
      if (!src) throw new Error(t('Bitte eine Quelle wählen'));
      const pick = [...new Set(src.data.items.map(i => i.row))].sort((a, b) => a - b).filter(r => v['row_' + r]);
      if (!pick.length) throw new Error(t('Bitte mindestens eine Reihe auswählen'));
      const map = new Map(pick.map((r, k) => [r, v.target === 'same' ? r : +v.target + k]));
      const targets = [...map.values()].filter(r => r < rows);
      if (v.mode === 'replace') {
        const gone = new Set(ed.cfg.items.filter(i => targets.includes(i.row)).map(i => i.id));
        ed.cfg.items = ed.cfg.items.filter(i => !gone.has(i.id));
        ed.cfg.items.forEach(i => { if (gone.has(i.rcd_id)) i.rcd_id = ''; });
      }
      const ids = new Map(); const fresh = [];
      for (const it of src.data.items) {
        const tr = map.get(it.row); if (tr == null || tr >= rows) continue;
        const c = JSON.parse(JSON.stringify(it)); c.id = Math.random().toString(36).slice(2, 12); c.row = tr; ids.set(it.id, c.id); fresh.push(c);
      }
      fresh.forEach(c => { c.rcd_id = ids.get(c.rcd_id) || ''; });
      ed.cfg.items.push(...fresh);
      return { n: fresh.length, skipped: pick.length - targets.length };
    }
  });
  if (ok) { ed.sel = null; save(); toast(t('{n} Geräte übernommen', { n: ok.n }) + (ok.skipped ? ' · ' + t('{n} Reihen ausgelassen', { n: ok.skipped }) : '')); }
}
async function labelDialog() {
  const first = await api('GET', `/api/configs/${ed.id}/labels`);
  const o = first.options;
  const chk = (k, label) => `<label class="chk"><input type="checkbox" name="${k}" ${o[k] ? 'checked' : ''}> ${label}</label>`;
  const sel = (k, opts) => `<select name="${k}">${opts.map(([v, l]) => `<option value="${v}" ${String(o[k]) === String(v) ? 'selected' : ''}>${l}</option>`).join('')}</select>`;
  await dialog(t('Etiketten / Beschriftungsstreifen'), `<div class="lblgrid"><div>
      <div class="two"><div><label>${t('Modulbreite (1 TE)')}</label>${sel('module', [[17.5, '17,5 mm'], [17.8, '17,8 mm'], [18, '18 mm'], [18.5, '18,5 mm']])}</div>
      <div><label>${t('Höhe mm')}</label><input type="number" name="height" min="6" max="80" step="0.5" value="${o.height}"></div>
      <div><label>${t('Schriftgröße mm')}</label><input type="number" name="font" min="1.5" max="8" step="0.1" value="${o.font}"></div>
      <div><label>${t('Ausrichtung')}</label>${sel('orient', [['auto', t('automatisch')], ['vertical', t('hochkant')], ['horizontal', t('waagerecht')]])}</div>
      <div><label>${t('Schnittrahmen')}</label>${sel('frame', [['solid', t('Linie')], ['dashed', t('gestrichelt')], ['thick', t('dick')], ['none', t('ohne')]])}</div>
      <div><label>${t('Abstand der Streifen mm')}</label><input type="number" name="gap" min="0" max="30" step="1" value="${o.gap}"></div></div>
      <h2>${t('Inhalt')}</h2>${chk('tag', t('Kennzeichnung'))}${chk('function', t('Funktion'))}${chk('room', t('Raum'))}${chk('rating', t('Nennstrom (z. B. B16)'))}${chk('phase', t('Außenleiter als Farbbalken'))}${chk('bold_tag', t('Kennzeichnung fett'))}${chk('upper', t('Großbuchstaben'))}${chk('terminals', t('Auch Klemmen beschriften'))}
      <div class="info">${t('Ein Streifen je belegter Reihe, Zellen so breit wie die Geräte. Mit 100 % drucken (nicht „an Seite anpassen“), am besten auf selbstklebendes A4-Papier. Der 100-mm-Balken auf dem Ausdruck dient zur Kontrolle.')}</div>
    </div><div><div class="lblprev" id="lprev"></div><div class="row" style="margin-top:8px"><span id="lpages" class="sub" style="margin:0"></span><span class="grow"></span><a class="btn pri" id="lpdf" target="_blank">${t('PDF öffnen (1:1)')}</a></div></div></div>`, {
    ok: '', wide: true, onOpen: f => {
      const read = () => { const v = {}; $$('input,select', f).forEach(i => { if (i.name) v[i.name] = i.type === 'checkbox' ? i.checked : i.value; }); return v; };
      const upd = async persist => {
        const v = read(), qs = new URLSearchParams(Object.entries(v).map(([k, x]) => [k, String(x)])).toString();
        $('#lpdf', f).href = q(`/api/configs/${ed.id}/labels?format=pdf&${qs}`);
        const r = await api('GET', `/api/configs/${ed.id}/labels?${qs}`);
        $('#lprev', f).innerHTML = r.pages[0];
        $('#lpages', f).textContent = r.pages.length > 1 ? t('{n} Seiten, Vorschau zeigt Seite 1', { n: r.pages.length }) : '';
        if (persist) { ed.cfg.labels = r.options; save(); }
      };
      $$('input,select', f).forEach(i => i.onchange = () => upd(true).catch(e => toast(e.message, true)));
      upd(false);
    }
  });
}

/* ---------------------------------------------------------------- Katalog */
async function viewCatalog(kind = 'device') {
  crumbs([[t('Katalog')]]);
  const all = await catalog(true), list = all.filter(x => x.kind === kind);
  const mans = [...new Set(list.map(x => x.manufacturer))];
  app.innerHTML = `<div class="page"><div class="row"><h1>${t('Katalog')}</h1><span class="grow"></span>
      <button id="cbme">${t('BMEcat / ETIM importieren')}</button><button id="ccsv">${t('CSV importieren')}</button><input type="file" id="ccsvf" accept=".csv,text/csv" hidden>
      <a class="btn" href="/api/catalog/export.csv?kind=${kind}">${t('CSV exportieren')}</a><button class="pri" id="cnew">${t('+ Eigener Eintrag')}</button></div>
    <p class="sub">${t('Startkatalog mit Maßen. Herstellerbilder kannst du je Artikel hochladen oder per Bildadresse laden; ohne Bild wird maßstäblich gezeichnet.')}
      <a href="/api/catalog/export.csv?template=1">${t('CSV-Vorlage herunterladen')}</a></p>
    <div class="row" style="margin-bottom:12px"><button data-k="device" class="${kind === 'device' ? 'pri' : ''}">${t('Geräte und Klemmen')}</button><button data-k="enclosure" class="${kind === 'enclosure' ? 'pri' : ''}">${t('Schränke')}</button>
      <select id="cman" style="width:auto"><option value="">${t('Alle Hersteller')}</option>${mans.map(m => `<option>${h(m)}</option>`).join('')}</select><input id="cq" placeholder="${t('Suchen …')}" style="width:220px"><span class="sub" id="ccount" style="margin:0"></span></div>
    <table id="ctab"></table></div>`;
  $$('[data-k]').forEach(b => b.onclick = () => viewCatalog(b.dataset.k));
  const draw = () => {
    const m = $('#cman').value, s = $('#cq').value.toLowerCase();
    const rows = list.filter(x => (!m || x.manufacturer === m) && (!s || `${x.article} ${x.name} ${x.series}`.toLowerCase().includes(s)));
    $('#ccount').textContent = rows.length > 400 ? t('{n} Einträge, 400 angezeigt', { n: rows.length }) : t('{n} Einträge', { n: rows.length });
    $('#ctab').innerHTML = `<tr><th></th><th>${t('Hersteller')}</th><th>${t('Artikel')}</th><th>${t('Bezeichnung')}</th><th>${kind === 'device' ? t('Breite') : t('Maße H×B')}</th><th></th><th></th></tr>` + rows.slice(0, 400).map(x => `<tr>
      <td>${x.image ? `<img class="thumb" src="/media/${h(x.image)}" alt="">` : ''}</td><td>${h(x.manufacturer)}<br><small style="color:var(--mute)">${h(x.series)}</small></td><td class="mono">${h(x.article)}</td><td>${h(x.name)}</td>
      <td>${kind === 'device' ? teStr(x.width_mm) : `${x.height_mm}×${x.width_mm} mm<br><small>${x.rows * x.fields * x.te_per_row} ${t('TE')}</small>`}</td>
      <td>${x.source ? `<span class="badge">${h(x.source)}</span> ` : x.custom ? `<span class="badge">${t('eigen')}</span> ` : ''}${x.verified === false ? `<span class="badge warn">${t('ungeprüft')}</span>` : x.custom ? '' : `<span class="badge ok">${t('geprüft')}</span>`}</td>
      <td class="act"><button class="sm" data-edit="${x.id}">${t('Bearbeiten')}</button></td></tr>`).join('');
    $$('[data-edit]').forEach(b => b.onclick = () => editCatalog(list.find(x => x.id == b.dataset.edit), kind));
  };
  $('#cman').onchange = draw; $('#cq').oninput = draw; draw();
  $('#cnew').onclick = () => editCatalog(null, kind);
  $('#ccsv').onclick = () => $('#ccsvf').click();
  $('#ccsvf').onchange = async ev => {
    const d = new FormData(); d.append('file', ev.target.files[0]);
    try {
      const r = await api('POST', '/api/catalog/import/csv', d, true);
      await dialog(t('CSV-Import'), `<p>${t('{n} neu, {u} aktualisiert.', { n: r.new, u: r.updated })}</p>${r.errors.length ? `<div class="info"><b>${t('Übersprungen')}:</b><br>${r.errors.map(h).join('<br>')}</div>` : ''}`, { ok: '' });
      catalogCache = null; viewCatalog(kind);
    } catch (e) { toast(e.message, true); }
  };
  $('#cbme').onclick = () => bmecatDialog(kind);
}
async function bmecatDialog(kind) {
  let token = null;
  const done = await dialog(t('BMEcat / ETIM importieren'), `<div class="info">${t('BMEcat ist das Austauschformat der Hersteller, die technischen Merkmale darin sind nach ETIM klassifiziert. Lade die XML- oder ZIP-Datei des Herstellers hoch; übernommen werden nur die Geräteklassen, die in einen Verteiler gehören.')}<br>
      <b>Phoenix Contact:</b> ${t('BMEcat im Kundenkonto „My Phoenix Contact“ selbst erzeugen (Self-Service, Anmeldung nötig).')}<br>
      <b>ABB / Striebel &amp; John:</b> ${t('BMEcat mit ETIM auf der Seite „Artikelstammdaten“ von ABB Deutschland.')}<br>
      <b>Hager, Schneider, DEHN:</b> ${t('über Kundenportal, Großhandel oder auf Anfrage beim Hersteller.')}</div>
    <input type="file" id="bfile" accept=".xml,.zip"><div id="bres"></div>`, {
    ok: t('Importieren'), wide: true,
    onOpen: f => {
      const btn = $('button.pri', f); btn.disabled = true;
      const show = (r, defaults, verified) => {
        const cls = Object.entries(r.by_class).sort((a, b) => b[1].total - a[1].total);
        $('#bres', f).innerHTML = `<p>${t('{n} Produkte in der Datei, {m} davon verwendbar.', { n: r.total, m: r.matched })}</p>
          <table><tr><th></th><th>${t('ETIM-Klasse')}</th><th>${t('Art')}</th><th>${t('Produkte')}</th><th>${t('verwendbar')}</th></tr>${cls.slice(0, 40).map(([c, v]) => `<tr><td>${v.category ? `<input type="checkbox" data-cls="${c}" checked>` : ''}</td><td class="mono">${c}</td>
            <td>${v.category ? h(v.category === 'enclosure' ? t('Schrank') : catName(v.category)) + (verified.includes(c) ? '' : ` <span class="badge warn">${t('ungeprüft')}</span>`) : '<span style="color:var(--mute)">–</span>'}</td><td>${v.total}</td><td>${v.usable}</td></tr>`).join('')}</table>
          <div class="two"><div><label>${t('Textfilter (optional, z. B. „PT 2,5“)')}</label><input id="bfilter"></div><div><label>${t('Höchstens importieren')}</label><input id="blimit" type="number" value="2000" min="1" max="20000"></div></div>
          <label>${t('Weitere ETIM-Klassen zuordnen (z. B. EC000905=rcbo, EC001234=switch)')}</label><input id="bclasses" placeholder="EC…=ls|rcd|rcbo|afdd|spd|switch|terminal|hlak|relay|other|enclosure">
          <div class="row" style="margin-top:8px"><button type="button" id="bcount">${t('Neu zählen')}</button><span id="bcnt" class="sub" style="margin:0"></span></div>
          ${r.entries.length ? `<h2>${t('Beispiele')}</h2><table>${r.entries.slice(0, 8).map(e => `<tr><td class="mono">${h(e.article)}</td><td>${h(e.manufacturer)}</td><td>${h(e.name)}</td><td>${e.kind === 'device' ? teStr(e.data.width_mm) : e.data.rows + '×' + e.data.te_per_row}</td></tr>`).join('')}</table>` : ''}`;
        btn.disabled = false;
        $('#bcount', f).onclick = async () => { try { const x = await api('POST', '/api/catalog/import/bmecat/' + token, { ...opts(), dry: true }); $('#bcnt', f).textContent = t('{m} verwendbare Produkte mit diesen Einstellungen', { m: x.matched }); } catch (e) { toast(e.message, true); } };
      };
      const opts = () => ({ filter: $('#bfilter', f).value, limit: +$('#blimit', f).value, classes: $('#bclasses', f).value, only: $$('[data-cls]:checked', f).map(i => i.dataset.cls) });
      f._opts = opts;
      $('#bfile', f).onchange = async ev => {
        if (!ev.target.files[0]) return;
        $('#bres', f).innerHTML = `<p>${t('Datei wird hochgeladen und gelesen …')}</p>`;
        const d = new FormData(); d.append('file', ev.target.files[0]);
        try { const r = await api('POST', '/api/catalog/import/bmecat', d, true); token = r.token; show(r, r.defaults, r.verified); }
        catch (e) { $('#bres', f).innerHTML = ''; toast(e.message, true); }
      };
    },
    onOk: async f => {
      if (!token) return false;
      const r = await api('POST', '/api/catalog/import/bmecat/' + token, f._opts());
      toast(t('{n} neu, {u} aktualisiert.', { n: r.new, u: r.updated }) + (r.truncated ? ' ' + t('Grenze erreicht, nicht alles importiert.') : ''));
    }
  });
  if (done) { catalogCache = null; viewCatalog(kind); }
}
function collect(f, preview) {
  const v = fd(f);
  for (const k of ['width_mm', 'height_mm', 'depth_mm', 'poles', 'current_a', 'rcd_ma', 'fields', 'rows', 'te_per_row', 'row_pitch_mm']) if (k in v) v[k] = v[k] === '' ? null : parseFloat(v[k]);
  if ('look_actuator' in v) {
    v.look = v.look_actuator ? { actuator: v.look_actuator, actuator_pos: v.look_actuator_pos, actuator_color: v.look_actuator_color, symbol: v.look_symbol, led: v.look_led,
      text1: v.look_text1, text2: v.look_text2, window: !!v.look_window, show_rating: !!v.look_show_rating } : null;
    for (const k of Object.keys(v)) if (k.startsWith('look_')) delete v[k];
  }
  if (preview) { delete v.image; delete v.image_url; }
  return v;
}
async function editCatalog(x, kind) {
  const n = !x; x = x || (kind === 'device' ? { kind, category: 'ls', width_mm: 17.5, height_mm: 85, poles: 1 } : { kind, rows: 4, fields: 1, te_per_row: 12, row_pitch_mm: 125, mount: 'AP', width_mm: 300, height_mm: 650 });
  const inp = (k, label, type = 'text', step) => `<div><label>${label}</label><input name="${k}" type="${type}" ${step ? `step="${step}"` : ''} value="${h(x[k] ?? '')}"></div>`;
  const body = `<div class="two">${inp('manufacturer', t('Hersteller'))}${inp('series', t('Serie'))}${inp('article', t('Artikel / Typ'))}${inp('name', t('Bezeichnung'))}
    ${kind === 'device' ? `<div><label>${t('Art')}</label><select name="category">${Object.keys(CAT_KEYS).map(k => `<option value="${k}" ${x.category === k ? 'selected' : ''}>${catName(k)}</option>`).join('')}</select></div>
      ${inp('width_mm', t('Breite mm (1 TE = 17,5)'), 'number', '0.1')}${inp('height_mm', t('Höhe mm'), 'number', '0.1')}${inp('poles', t('Pole'), 'number', '1')}${inp('current_a', t('Nennstrom A'), 'number', '0.1')}${inp('characteristic', t('Charakteristik (B, C …)'))}${inp('rcd_ma', t('Fehlerstrom mA'), 'number', '1')}${inp('rcd_type', t('FI-Typ (A, F, B …)'))}
      <div><label>${t('Klemmenfarbe')}</label><select name="color">${[['', t('grau')], ['blue', t('blau (N)')], ['pe', t('grün-gelb (PE)')], ['brown', t('braun')], ['black', t('schwarz')]].map(([k, v]) => `<option value="${k}" ${x.color === k ? 'selected' : ''}>${v}</option>`).join('')}</select></div>
      <div><label>${t('Zählerart (nur Zähler)')}</label><select name="meter_type">${[['', '–'], ['mme', t('mME, digital')], ['ferraris', t('kME, Ferraris')], ['imsys', t('iMSys, Smart Meter')]].map(([k, v]) => `<option value="${k}" ${(x.meter_type || '') === k ? 'selected' : ''}>${v}</option>`).join('')}</select></div>`
      : `${inp('height_mm', t('Höhe mm'), 'number', '0.1')}${inp('width_mm', t('Breite mm'), 'number', '0.1')}${inp('depth_mm', t('Tiefe mm'), 'number', '0.1')}${inp('fields', t('Felder nebeneinander'), 'number', '1')}${inp('rows', t('Reihen je Feld'), 'number', '1')}${inp('te_per_row', t('TE je Reihe'), 'number', '1')}${inp('row_pitch_mm', t('Reihenabstand mm'), 'number', '1')}
      <div><label>${t('Montage')}</label><select name="mount">${Object.entries(MOUNT).map(([k, v]) => `<option value="${k}" ${x.mount === k ? 'selected' : ''}>${t(v)}</option>`).join('')}</select></div>
      <div><label>${t('PE/N-Klemmenblöcke im Schrank')}</label><div class="row">${[['top', t('oben')], ['middle', t('Mitte')], ['bottom', t('unten')]].map(([k, l]) => `<label class="chk" style="margin:0"><input type="checkbox" name="pen_${k}" ${(x.pen_blocks || ['top', 'bottom']).includes(k) ? 'checked' : ''}> ${l}</label>`).join('')}</div></div>`}
    ${inp('note', t('Hinweis'))}</div>
    ${kind === 'device' ? (() => {
      const L = x.look || {}, sel = (name, opts, cur) => `<select name="${name}">${opts.map(([k, v]) => `<option value="${k}" ${(cur || '') === k ? 'selected' : ''}>${v}</option>`).join('')}</select>`;
      const cols = [['grey', t('grau')], ['black', t('schwarz')], ['white', t('weiß')], ['red', t('rot')], ['blue', t('blau')], ['green', t('grün')], ['yellow', t('gelb')], ['orange', t('orange')]];
      return `<h2>${t('Darstellung (gezeichnete Front)')}</h2><div class="designer"><div class="two" style="flex:1">
        <div><label>${t('Bedienelement')}</label>${sel('look_actuator', [['', t('Standard nach Art')], ['lever', t('Kipphebel')], ['slide', t('kleiner Schiebeschalter')], ['button', t('Taster')], ['rotary', t('Drehschalter')], ['none', t('keins')]], L.actuator)}</div>
        <div><label>${t('Position')}</label>${sel('look_actuator_pos', [['center', t('Mitte')], ['left', t('links')], ['right', t('rechts')]], L.actuator_pos || 'center')}</div>
        <div><label>${t('Farbe des Bedienelements')}</label>${sel('look_actuator_color', cols, L.actuator_color || 'grey')}</div>
        <div><label>${t('Schaltzeichen')}</label>${sel('look_symbol', [['', t('keins')], ['relay', t('Relais / Fernschalter')], ['contactor', t('Schütz')], ['timer', t('Zeitschaltuhr')], ['bell', t('Klingel')], ['transformer', t('Transformator')], ['socket', t('Steckdose')], ['lamp', t('Leuchte')]], L.symbol)}</div>
        <div><label>${t('Anzeige-LED')}</label>${sel('look_led', [['', t('keine')], ['green', t('grün')], ['red', t('rot')], ['orange', t('orange')]], L.led)}</div>
        <div><label>${t('Aufdruck Zeile 1')}</label><input name="look_text1" value="${h(L.text1 || '')}" placeholder="16 AX"></div>
        <div><label>${t('Aufdruck Zeile 2')}</label><input name="look_text2" value="${h(L.text2 || '')}" placeholder="250 V~"></div>
        <div><label class="chk" style="margin-top:22px"><input type="checkbox" name="look_window" ${L.window ? 'checked' : ''}> ${t('Beschriftungsfenster')}</label>
          <label class="chk"><input type="checkbox" name="look_show_rating" ${L.show_rating === false ? '' : 'checked'}> ${t('Nennstrom groß anzeigen')}</label></div>
        </div><div class="lookprev"><div id="lookprev"></div><small>${t('Vorschau')}</small></div></div>
        <div class="info">${t('Die Einstellungen gelten für Reiheneinbaugeräte ohne eigenes Bild. Mit „Standard nach Art“ zeichnet die App wie bisher.')}</div>`;
    })() : ''}
    ${n ? `<div class="info">${t('Ein Bild lässt sich nach dem Anlegen hinzufügen.')}</div>` : kind === 'device' ? `<h2>${t('Herstellerbild (Frontansicht)')}</h2>
      <div class="row">${x.image ? `<img class="thumb" src="/media/${h(x.image)}" alt="">` : ''}<input type="file" id="img" accept="image/*" style="flex:1"></div>
      <div class="row" style="margin-top:8px"><input id="imgurl" placeholder="${t('oder Bildadresse (https://…)')}" value="${h(x.image_url || '')}" style="flex:1"><button type="button" id="imgload">${t('Laden')}</button>${x.image ? `<button type="button" class="danger" id="imgdel">${t('Bild entfernen')}</button>` : ''}</div>
      <div class="info">${t('Das Bild wird auf die echten Gerätemaße gestreckt. Am besten eignet sich eine freigestellte, gerade Frontansicht ohne Rand.')}</div>` : ''}
    ${!n ? `<p><button type="button" class="danger" id="cdel">${t('Eintrag löschen')}</button></p>` : ''}`;
  const r = await dialog(n ? t('Eigener Katalogeintrag') : t('Katalogeintrag bearbeiten'), body, {
    wide: true,
    onOpen: f => {
      const prev = $('#lookprev', f);
      if (prev) {
        let pt = null;
        const draw = () => { clearTimeout(pt); pt = setTimeout(async () => { try { prev.innerHTML = await api('POST', '/api/preview/device', collect(f, true)); } catch (e) { prev.textContent = e.message; } }, 150); };
        f.addEventListener('input', draw); draw();
      }
      const done = () => { $('#dlg').close(); catalogCache = null; viewCatalog(kind); };
      const guard = fn => async () => { try { await fn(); toast(t('Bild gespeichert')); done(); } catch (e) { toast(e.message, true); } };
      if ($('#img', f)) $('#img', f).onchange = guard(async () => { const d = new FormData(); d.append('file', $('#img', f).files[0]); await api('POST', `/api/catalog/${x.id}/image`, d, true); });
      if ($('#imgload', f)) $('#imgload', f).onclick = guard(() => api('POST', `/api/catalog/${x.id}/image-url`, { url: $('#imgurl', f).value }));
      if ($('#imgdel', f)) $('#imgdel', f).onclick = guard(() => api('DELETE', `/api/catalog/${x.id}/image`));
      if ($('#cdel', f)) $('#cdel', f).onclick = async () => { if (confirm(t('Eintrag löschen? Bereits eingesetzte Geräte bleiben in den Konfigurationen erhalten.'))) { try { await api('DELETE', '/api/catalog/' + x.id); done(); } catch (e) { toast(e.message, true); } } };
    },
    onOk: async f => {
      const v = collect(f);
      v.kind = kind; if (n) v.verified = true;
      if (!v.article || !(v.width_mm > 0) || !(v.height_mm > 0)) throw new Error(t('Artikel, Breite und Höhe sind erforderlich'));
      if (kind === 'enclosure' && !(v.rows > 0 && v.te_per_row > 0)) throw new Error(t('Reihen und TE je Reihe sind erforderlich'));
      if (kind === 'enclosure') { v.fields = v.fields || 1; v.pen_blocks = ['top', 'middle', 'bottom'].filter(k => v['pen_' + k]); }
      for (const k of ['pen_top', 'pen_middle', 'pen_bottom']) delete v[k];
      await api(n ? 'POST' : 'PUT', '/api/catalog' + (n ? '' : '/' + x.id), v);
    }
  });
  if (r) { catalogCache = null; viewCatalog(kind); }
}

/* ---------------------------------------------------------------- Einstellungen */
async function viewSettings() {
  crumbs([[t('Einstellungen')]]);
  const [st, b] = await Promise.all([api('GET', '/api/state'), api('GET', '/api/backup')]);
  const s = b.settings;
  const tHtml = (x, i) => `<tr data-i="${i}"><td><select data-k="type"><option value="local" ${x.type === 'local' ? 'selected' : ''}>${t('Ordner / NAS')}</option><option value="webdav" ${x.type === 'webdav' ? 'selected' : ''}>WebDAV</option><option value="rclone" ${x.type === 'rclone' ? 'selected' : ''}>rclone</option></select></td>
    <td>${x.type === 'local' ? `<input data-k="path" value="${h(x.path || '')}" placeholder="/mnt/nas/verteiler">`
      : x.type === 'webdav' ? `<input data-k="url" value="${h(x.url || '')}" placeholder="https://cloud.example.de/remote.php/dav/files/NAME/Verteiler"><div class="two" style="margin-top:6px"><input data-k="user" value="${h(x.user || '')}" placeholder="${t('Benutzer')}"><input data-k="password" type="password" value="${h(x.password || '')}" placeholder="${t('Passwort / App-Token')}"></div>`
        : `<input data-k="remote" value="${h(x.remote || '')}" placeholder="gdrive:Verteiler">`}</td><td class="act"><button class="sm danger" data-rm="${i}">${t('Entfernen')}</button></td></tr>`;
  app.innerHTML = `<div class="page"><h1>${t('Einstellungen')}</h1><p class="sub">${t('Sicherung und Zugriffsschutz')}</p>
    <h2>${t('Sicherungsziele')}</h2><table id="tg">${s.targets.map(tHtml).join('') || `<tr><td>${t('Noch kein Ziel eingerichtet.')}</td></tr>`}</table>
    <div class="row" style="margin-top:10px"><button id="tadd">${t('+ Ziel hinzufügen')}</button><label class="chk" style="margin:0"><input type="checkbox" id="auto" ${s.auto_hours ? 'checked' : ''}> ${t('täglich automatisch sichern, wenn sich etwas geändert hat')}</label><span class="grow"></span><button id="tsave">${t('Ziele speichern')}</button><button class="pri" id="trun">${t('Jetzt sichern')}</button></div>
    <div class="info">${t('Jede Sicherung ist eine ZIP-Datei mit allen Profilen und Konfigurationen, eigenen Katalogeinträgen, Bildern sowie PDF und CSV je Konfiguration.')}<br>
      ${t('<b>rclone</b> erreicht Google Drive, OneDrive, Dropbox und viele andere: im Container einmal <span class="mono">runuser -u verteiler -- rclone config</span> ausführen und hier den Remote-Namen eintragen, z. B. <span class="mono">gdrive:Verteiler</span>.')}</div>
    <div id="last">${b.last ? `<div class="info"><b>${t('Letzte Sicherung')} ${h(b.last.time.replace('T', ' '))}</b> (${Math.round(b.last.size / 1024)} kB)<br>${b.last.results.map(r => `${r.ok ? '✓' : '✗'} ${h(r.target)} ${r.ok ? '' : '– ' + h(r.detail)}`).join('<br>')}</div>` : ''}</div>
    <h2>${t('Manuell')}</h2><div class="row"><a class="btn" href="/api/backup/download">${t('Sicherung herunterladen')}</a><button id="imp">${t('Sicherung einspielen')}</button><input type="file" id="impf" accept=".zip" hidden></div>
    <h2>${t('Admin-Passwort')}</h2><p class="sub" style="margin-bottom:8px">${st.admin_locked ? t('Gesetzt: Katalog, Sicherung und Einstellungen verlangen eine Anmeldung.') : t('Nicht gesetzt: Katalog, Sicherung und Einstellungen sind für jeden im Netz erreichbar. Profile können unabhängig davon eigene Passwörter haben.')}</p>
    <div class="row"><input id="apw" type="password" placeholder="${st.admin_locked ? t('Neues Passwort (leer = entfernen)') : t('Passwort setzen')}" style="width:260px" autocomplete="new-password"><button id="apws">${t('Speichern')}</button><button id="lo">${t('Überall abmelden')}</button></div></div>`;
  const collect = () => $$('#tg tr[data-i]').map(tr => Object.fromEntries($$('[data-k]', tr).map(i => [i.dataset.k, i.value])));
  const store = async targets => { await api('PUT', '/api/backup', { targets, auto_hours: $('#auto').checked ? 24 : 0 }); };
  $('#tadd').onclick = async () => { await store([...collect(), { type: 'local', path: '' }]); route(); };
  $$('[data-rm]').forEach(bt => bt.onclick = async () => { const x = collect(); x.splice(+bt.dataset.rm, 1); await store(x); route(); });
  $$('#tg [data-k=type]').forEach(se => se.onchange = async () => { await store(collect()); route(); });
  $('#tsave').onclick = async () => { await store(collect()); toast(t('Gespeichert')); };
  $('#trun').onclick = async () => { try { await store(collect()); $('#trun').disabled = true; const r = await api('POST', '/api/backup/run'); const ok = r.results.every(x => x.ok); toast(ok ? t('Sicherung abgeschlossen') : t('Sicherung mit Fehlern'), !ok); route(); } catch (e) { toast(e.message, true); $('#trun').disabled = false; } };
  $('#imp').onclick = () => $('#impf').click();
  $('#impf').onchange = async ev => { const d = new FormData(); d.append('file', ev.target.files[0]); try { const r = await api('POST', '/api/backup/import', d, true); toast(t('{p} Profile und {c} Konfigurationen eingespielt', { p: r.profiles, c: r.configs })); } catch (e) { toast(e.message, true); } };
  $('#apws').onclick = async () => { try { await api('POST', '/api/admin/password', { password: $('#apw').value }); toast(t('Admin-Passwort gespeichert')); route(); } catch (e) { toast(e.message, true); } };
  $('#lo').onclick = async () => { await api('POST', '/api/logout'); toast(t('Abgemeldet')); location.hash = '#/'; route(); };
}

drawHeader();
route();
