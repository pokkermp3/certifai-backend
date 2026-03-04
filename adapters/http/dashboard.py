"""
adapters/http/dashboard.py

Insurance agent web dashboard.
Single-file HTML/JS app served directly by FastAPI.
Phase 2 addition.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

dashboard_router = APIRouter()

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CertifAI — Agent Dashboard</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0a0a0a; color: #e8e8f0; min-height: 100vh; }

    /* ── Topbar ── */
    .topbar {
      background: #111; border-bottom: 1px solid #222;
      padding: 0 32px; height: 56px;
      display: flex; align-items: center; justify-content: space-between;
      position: sticky; top: 0; z-index: 10;
    }
    .logo { font-size: 17px; font-weight: 700; letter-spacing: -0.3px; }
    .logo span { color: #7c6aff; }
    .logout-btn {
      background: transparent; border: 1px solid #333; color: #888;
      padding: 5px 14px; border-radius: 6px; cursor: pointer; font-size: 13px;
    }
    .logout-btn:hover { border-color: #7c6aff; color: #e8e8f0; }

    /* ── Views ── */
    .view { display: none; }
    .view.active { display: block; }
    #login-view { display: none; align-items: center; justify-content: center;
                  min-height: calc(100vh - 56px); }
    #login-view.active { display: flex; }

    /* ── Login ── */
    .login-card {
      background: #111; border: 1px solid #222; border-radius: 16px;
      padding: 44px 36px; width: 360px;
    }
    .login-card h2 { font-size: 20px; margin-bottom: 6px; }
    .login-card p  { color: #666; font-size: 14px; margin-bottom: 28px; }
    .field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
    .field label { font-size: 12px; color: #888; font-weight: 600;
                   text-transform: uppercase; letter-spacing: 0.05em; }
    .field input {
      background: #0a0a0a; border: 1px solid #222; border-radius: 8px;
      color: #e8e8f0; padding: 11px 13px; font-size: 14px; outline: none;
    }
    .field input:focus { border-color: #7c6aff; }
    .btn-primary {
      background: #7c6aff; color: #fff; border: none; border-radius: 8px;
      padding: 11px; font-size: 14px; font-weight: 600;
      cursor: pointer; width: 100%; margin-top: 4px;
    }
    .btn-primary:hover { background: #6a5ae0; }
    .btn-primary:disabled { background: #2a2a40; cursor: not-allowed; }
    .error-msg { color: #f87171; font-size: 13px; margin-top: 10px; min-height: 18px; }

    /* ── Content ── */
    .content { padding: 32px; max-width: 1080px; margin: 0 auto; }
    .page-header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 24px;
    }
    .page-header h1 { font-size: 20px; font-weight: 700; }
    .badge {
      display: inline-block; background: #1e1e2e; color: #888;
      border-radius: 20px; padding: 2px 10px; font-size: 12px; margin-left: 8px;
    }
    .search-box {
      background: #111; border: 1px solid #222; border-radius: 8px;
      color: #e8e8f0; padding: 9px 13px; font-size: 14px; outline: none; width: 240px;
    }
    .search-box:focus { border-color: #7c6aff; }

    /* ── Table ── */
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    thead th {
      text-align: left; padding: 10px 14px; font-size: 11px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.06em; color: #666;
      border-bottom: 1px solid #1e1e1e;
    }
    tbody tr { border-bottom: 1px solid #161616; cursor: pointer; transition: background 0.1s; }
    tbody tr:hover { background: #111; }
    tbody td { padding: 13px 14px; }
    .mono { font-family: monospace; font-size: 13px; color: #888; }
    .pill {
      display: inline-block; background: #1a1030; color: #a78bfa;
      border-radius: 20px; padding: 2px 10px; font-size: 12px; font-weight: 600;
    }

    /* ── Client detail ── */
    .back-btn {
      background: none; border: none; color: #7c6aff; font-size: 14px;
      cursor: pointer; padding: 0; margin-bottom: 20px;
      display: inline-flex; align-items: center; gap: 5px;
    }
    .back-btn:hover { text-decoration: underline; }
    .client-meta {
      background: #111; border: 1px solid #222; border-radius: 12px;
      padding: 20px 24px; margin-bottom: 24px;
      display: flex; gap: 40px;
    }
    .meta-item { display: flex; flex-direction: column; gap: 3px; }
    .meta-label { font-size: 11px; color: #666; text-transform: uppercase;
                  letter-spacing: 0.06em; }
    .meta-value { font-size: 15px; font-weight: 600; }

    /* ── Certificate rows ── */
    .cert-row {
      background: #111; border: 1px solid #1e1e1e; border-radius: 10px;
      margin-bottom: 10px; overflow: hidden;
    }
    .cert-header {
      display: flex; align-items: center; gap: 14px; padding: 14px 18px;
      cursor: pointer;
    }
    .cert-header:hover { background: #161616; }
    .cert-icon { font-size: 24px; flex-shrink: 0; }
    .cert-info { flex: 1; }
    .cert-name { font-weight: 600; font-size: 14px; margin-bottom: 3px; }
    .cert-date { font-size: 12px; color: #666; }
    .expand-icon { color: #444; transition: transform 0.2s; }
    .cert-row.open .expand-icon { transform: rotate(180deg); }

    .cert-body { display: none; padding: 0 18px 18px; border-top: 1px solid #1e1e1e; }
    .cert-row.open .cert-body { display: block; }

    .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 14px; }
    .detail-card {
      background: #0a0a0a; border: 1px solid #1e1e1e; border-radius: 8px; padding: 14px;
    }
    .detail-card h4 { font-size: 11px; color: #666; text-transform: uppercase;
                      letter-spacing: 0.06em; margin-bottom: 10px; }
    .hash-val { font-family: monospace; font-size: 11px; color: #a78bfa;
                word-break: break-all; line-height: 1.5; }
    .hash-label { font-size: 11px; color: #666; margin-bottom: 3px; }
    .verified-ok  { color: #4ade80; font-weight: 600; font-size: 13px; margin-top: 8px; }
    .verified-bad { color: #f87171; font-weight: 600; font-size: 13px; margin-top: 8px; }

    .cert-actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
    .btn-outline {
      background: transparent; border: 1px solid #2a2a2a; color: #ccc;
      padding: 7px 14px; border-radius: 7px; cursor: pointer; font-size: 13px;
      text-decoration: none; display: inline-flex; align-items: center; gap: 5px;
    }
    .btn-outline:hover { border-color: #7c6aff; color: #7c6aff; }

    /* ── Status badges ── */
    .s-certified { color: #4ade80; font-size: 12px; font-weight: 600; }
    .s-mismatch  { color: #f87171; font-size: 12px; font-weight: 600; }
    .s-pending   { color: #facc15; font-size: 12px; }

    /* ── Spinner / empty ── */
    .center { display: flex; justify-content: center; padding: 60px; }
    .spinner {
      width: 28px; height: 28px; border: 3px solid #222; border-top-color: #7c6aff;
      border-radius: 50%; animation: spin 0.7s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .empty { color: #666; text-align: center; padding: 60px; font-size: 14px; }

    /* ── Photo overlay ── */
    .overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,0.9);
      display: none; align-items: center; justify-content: center; z-index: 100;
    }
    .overlay.active { display: flex; }
    .overlay img { max-width: 90vw; max-height: 90vh; border-radius: 6px; }
    .overlay-close {
      position: absolute; top: 18px; right: 24px;
      color: #fff; font-size: 26px; cursor: pointer; background: none; border: none;
    }
  </style>
</head>
<body>
<div id="app">

  <nav class="topbar">
    <div class="logo">Certif<span>AI</span></div>
    <button class="logout-btn" id="logout-btn" style="display:none" onclick="logout()">Log out</button>
  </nav>

  <!-- LOGIN -->
  <div id="login-view" class="view">
    <div class="login-card">
      <h2>Agent Login</h2>
      <p>Insurance claims dashboard</p>
      <div class="field">
        <label>Password</label>
        <input type="password" id="pwd-input" placeholder="Enter agent password"
               onkeydown="if(event.key==='Enter')doLogin()">
      </div>
      <button class="btn-primary" id="login-btn" onclick="doLogin()">Sign in</button>
      <div class="error-msg" id="login-err"></div>
    </div>
  </div>

  <!-- CLIENTS LIST -->
  <div id="clients-view" class="view">
    <div class="content">
      <div class="page-header">
        <h1>Policyholders <span class="badge" id="client-count">—</span></h1>
        <input class="search-box" id="search" type="text"
               placeholder="Search by DNI or name…" oninput="filterClients()">
      </div>
      <div id="clients-loading" class="center"><div class="spinner"></div></div>
      <div id="clients-table" style="display:none">
        <table>
          <thead>
            <tr>
              <th>Full Name</th><th>DNI</th><th>Certificates</th><th>Last Submission</th>
            </tr>
          </thead>
          <tbody id="clients-tbody"></tbody>
        </table>
      </div>
      <div class="empty" id="clients-empty" style="display:none">No policyholders found.</div>
    </div>
  </div>

  <!-- CLIENT DETAIL -->
  <div id="detail-view" class="view">
    <div class="content">
      <button class="back-btn" onclick="showClients()">← Back</button>
      <div class="client-meta" id="client-meta"></div>
      <div id="detail-loading" class="center"><div class="spinner"></div></div>
      <div id="certs-list"></div>
    </div>
  </div>

</div>

<!-- Photo overlay -->
<div class="overlay" id="overlay">
  <button class="overlay-close" onclick="closeOverlay()">✕</button>
  <img id="overlay-img" src="" alt="">
</div>

<script>
  const BASE = '';
  let allClients = [];

  // ── Auth ──────────────────────────────────────────────────────────────────
  async function doLogin() {
    const pwd = document.getElementById('pwd-input').value;
    const btn = document.getElementById('login-btn');
    const err = document.getElementById('login-err');
    if (!pwd) { err.textContent = 'Enter a password.'; return; }
    btn.disabled = true; btn.textContent = 'Signing in…'; err.textContent = '';
    try {
      const res  = await fetch(BASE + '/api/v1/auth/verify', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({password: pwd}),
      });
      const data = await res.json();
      if (data.valid) {
        sessionStorage.setItem('ca_auth', '1');
        showClients();
      } else {
        err.textContent = 'Incorrect password.';
      }
    } catch { err.textContent = 'Cannot reach server.'; }
    finally { btn.disabled = false; btn.textContent = 'Sign in'; }
  }

  function logout() {
    sessionStorage.removeItem('ca_auth');
    showView('login-view');
    document.getElementById('logout-btn').style.display = 'none';
    document.getElementById('pwd-input').value = '';
  }

  // ── Navigation ─────────────────────────────────────────────────────────────
  function showView(id) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(id).classList.add('active');
  }

  function showClients() {
    showView('clients-view');
    document.getElementById('logout-btn').style.display = '';
    if (allClients.length === 0) loadClients();
  }

  // ── Clients ────────────────────────────────────────────────────────────────
  async function loadClients() {
    document.getElementById('clients-loading').style.display = 'flex';
    document.getElementById('clients-table').style.display   = 'none';
    document.getElementById('clients-empty').style.display   = 'none';
    try {
      const res  = await fetch(BASE + '/api/v1/clients');
      const data = await res.json();
      allClients = data.clients || [];
      renderClients(allClients);
    } catch {
      document.getElementById('clients-empty').style.display = '';
      document.getElementById('clients-empty').textContent   = 'Error loading clients.';
    } finally {
      document.getElementById('clients-loading').style.display = 'none';
    }
  }

  function renderClients(list) {
    document.getElementById('client-count').textContent = list.length;
    const tbody = document.getElementById('clients-tbody');
    tbody.innerHTML = '';
    if (!list.length) {
      document.getElementById('clients-empty').style.display = '';
      document.getElementById('clients-table').style.display  = 'none';
      return;
    }
    document.getElementById('clients-empty').style.display = 'none';
    document.getElementById('clients-table').style.display  = '';
    list.forEach(c => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${esc(c.name||'—')}</strong></td>
        <td class="mono">${esc(c.dni)}</td>
        <td><span class="pill">${c.certificate_count}</span></td>
        <td style="color:#666;font-size:13px">${fmtDate(c.last_submission)}</td>
      `;
      tr.onclick = () => loadDetail(c.dni, c.name);
      tbody.appendChild(tr);
    });
  }

  function filterClients() {
    const q = document.getElementById('search').value.toLowerCase();
    renderClients(q ? allClients.filter(c =>
      c.dni.toLowerCase().includes(q) || (c.name||'').toLowerCase().includes(q)
    ) : allClients);
  }

  // ── Detail ─────────────────────────────────────────────────────────────────
  async function loadDetail(dni, name) {
    showView('detail-view');
    document.getElementById('client-meta').innerHTML = metaHTML(name, dni, '…');
    document.getElementById('detail-loading').style.display = 'flex';
    document.getElementById('certs-list').innerHTML = '';
    try {
      const res  = await fetch(BASE + '/api/v1/clients/' + encodeURIComponent(dni) + '/certificates');
      const data = await res.json();
      const certs = data.certificates || [];
      document.getElementById('client-meta').innerHTML =
        metaHTML(data.client?.name || name, dni, certs.length);
      renderCerts(certs);
    } catch {
      document.getElementById('certs-list').innerHTML = '<div class="empty">Error loading.</div>';
    } finally {
      document.getElementById('detail-loading').style.display = 'none';
    }
  }

  function metaHTML(name, dni, count) {
    return `
      <div class="meta-item"><div class="meta-label">Full Name</div>
        <div class="meta-value">${esc(name||'—')}</div></div>
      <div class="meta-item"><div class="meta-label">DNI</div>
        <div class="meta-value mono">${esc(dni)}</div></div>
      <div class="meta-item"><div class="meta-label">Certificates</div>
        <div class="meta-value">${count}</div></div>
    `;
  }

  function renderCerts(certs) {
    const list = document.getElementById('certs-list');
    if (!certs.length) { list.innerHTML = '<div class="empty">No certificates.</div>'; return; }
    list.innerHTML = certs.map((c, i) => `
      <div class="cert-row" id="cr-${i}">
        <div class="cert-header" onclick="toggleCert(${i})">
          <div class="cert-icon">📷</div>
          <div class="cert-info">
            <div class="cert-name">${esc(c.file_name || c.file_info?.name || '—')}</div>
            <div class="cert-date">${fmtDate(c.captured_at)} · ${esc(c.device_model || c.device?.model || '—')}</div>
          </div>
          <div style="margin-right:12px">${statusBadge(c.status)}</div>
          <div class="expand-icon">⌄</div>
        </div>
        <div class="cert-body">
          <div class="detail-grid">
            <div class="detail-card">
              <h4>Hash Verification</h4>
              <div class="hash-label">Device hash</div>
              <div class="hash-val">${esc(c.device_hash)}</div>
              <div class="hash-label" style="margin-top:8px">Server hash</div>
              <div class="hash-val">${c.server_hash ? esc(c.server_hash) : '—'}</div>
              <div class="${c.hash_verified ? 'verified-ok' : 'verified-bad'}">
                ${c.hash_verified ? '✓ Hashes match — certified' : '✗ Mismatch or pending'}
              </div>
            </div>
            <div class="detail-card">
              <h4>Location &amp; Device</h4>
              <div style="font-size:13px;line-height:1.8;color:#ccc">
                📍 ${c.gps_lat != null ? `${c.gps_lat.toFixed(5)}, ${c.gps_lon.toFixed(5)}` : 'No GPS'}
                ${c.gps_lat != null ? `<a href="https://maps.google.com/?q=${c.gps_lat},${c.gps_lon}"
                  target="_blank" style="color:#7c6aff;margin-left:6px;font-size:12px">Maps ↗</a>` : ''}
                <br>📱 ${esc(c.device_model || c.device?.model || '—')}
                <br>🖥 ${esc(c.os_version || c.device?.os_version || '—')}
                <br>🕐 ${fmtDate(c.captured_at)}
              </div>
            </div>
          </div>
          <div class="cert-actions">
            ${c.pdf_url ? `<a class="btn-outline" href="${BASE+c.pdf_url}" target="_blank">⬇ PDF Certificate</a>` : ''}
            ${c.file_url ? `<a class="btn-outline" href="${BASE+c.file_url}" target="_blank">⬇ Original Photo</a>` : ''}
            ${c.file_url ? `<button class="btn-outline" onclick="previewPhoto('${BASE+c.file_url}')">🔍 Preview</button>` : ''}
          </div>
        </div>
      </div>
    `).join('');
  }

  function toggleCert(i) {
    document.getElementById('cr-' + i).classList.toggle('open');
  }

  // ── Photo preview ──────────────────────────────────────────────────────────
  function previewPhoto(url) {
    document.getElementById('overlay-img').src = url;
    document.getElementById('overlay').classList.add('active');
  }
  function closeOverlay() {
    document.getElementById('overlay').classList.remove('active');
  }
  document.getElementById('overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('overlay')) closeOverlay();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeOverlay();
  });

  // ── Helpers ────────────────────────────────────────────────────────────────
  function esc(s) {
    return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-ES', {dateStyle:'short', timeStyle:'short'});
  }
  function statusBadge(s) {
    if (s === 'certified')    return '<span class="s-certified">✓ Certified</span>';
    if (s === 'hash_mismatch') return '<span class="s-mismatch">✗ Mismatch</span>';
    return '<span class="s-pending">⏳ Pending</span>';
  }

  // ── Init ───────────────────────────────────────────────────────────────────
  window.onload = () => {
    if (sessionStorage.getItem('ca_auth') === '1') {
      showClients();
    } else {
      showView('login-view');
    }
  };
</script>
</body>
</html>"""


@dashboard_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=_HTML)
