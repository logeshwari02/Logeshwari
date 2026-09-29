const API_BASE = window.POCKETSMART_API_BASE || localStorage.getItem('pocketsmart_api_base') || 'http://127.0.0.1:8000';

function authHeaders(extra = {}) {
  const token = localStorage.getItem('pocketsmart_token');
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = localStorage.getItem('pocketsmart_token');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let data = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) data = await response.json();
  else data = await response.text();

  if (response.status === 401) {
    localStorage.removeItem('pocketsmart_token');
    localStorage.removeItem('pocketsmart_user');
  }
  if (!response.ok) {
    const detail = typeof data === 'object' && data?.detail ? data.detail : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

function formatINR(value) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(Number(value || 0));
}

function saveUser(user) {
  localStorage.setItem('pocketsmart_user', JSON.stringify(user));
}
function getUser() {
  try { return JSON.parse(localStorage.getItem('pocketsmart_user') || 'null'); } catch { return null; }
}
function isLoggedIn() { return Boolean(localStorage.getItem('pocketsmart_token')); }

function requireAuth() {
  if (!isLoggedIn()) {
    window.location.href = 'login.html';
    return false;
  }
  return true;
}

function toast(message) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = message;
  el.style.display = 'block';
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => { el.style.display = 'none'; }, 3200);
}

function renderAuthNav() {
  const target = document.querySelector('[data-auth-nav]');
  if (!target) return;
  if (isLoggedIn()) {
    target.innerHTML = `<a href="dashboard.html">Dashboard</a><a href="history.html">History</a><button class="btn-ghost" id="logoutBtn">Logout</button>`;
    const logout = document.getElementById('logoutBtn');
    logout?.addEventListener('click', async () => {
      try { await apiFetch('/auth/logout', { method:'POST', body:undefined }); } catch (_) {}
      localStorage.removeItem('pocketsmart_token');
      localStorage.removeItem('pocketsmart_user');
      window.location.href = 'index.html';
    });
  } else {
    target.innerHTML = `<a href="testimonials.html">Testimonials</a><a href="login.html">Login</a><a class="btn btn-primary" href="register.html">Get Started</a>`;
  }
}

function plannerResultKey(type) { return `pocketsmart_result_${type}`; }
function storePlannerResult(type, result) { sessionStorage.setItem(plannerResultKey(type), JSON.stringify(result)); }
function loadPlannerResult(type) {
  try { return JSON.parse(sessionStorage.getItem(plannerResultKey(type)) || 'null'); } catch { return null; }
}

function renderRecommendationCards(result) {
  if (!result?.recommendations?.length) return '<div class="empty">No recommendations were returned.</div>';
  return `<div class="results-grid">${result.recommendations.map(rec => `
    <article class="result-card">
      <div class="result-top">
        <div>
          <div class="badge ${rec.priority === 'high' ? 'badge-high' : rec.priority === 'low' ? 'badge-low' : ''}">${escapeHtml(rec.priority)}</div>
          <h3 style="margin:12px 0 0">${escapeHtml(rec.item_name)}</h3>
        </div>
        <div class="price">${formatINR(rec.estimated_price)}</div>
      </div>
      <div class="result-meta">${escapeHtml(rec.category)} · ${escapeHtml(rec.platform)} · Qty ${rec.quantity}</div>
      <div class="result-reason">${escapeHtml(rec.reason)}</div>
      ${rec.search_url ? `<a class="result-link" href="${escapeHtml(rec.search_url)}" target="_blank" rel="noopener">Search platform ↗</a>` : ''}
    </article>`).join('')}</div>`;
}

function renderAllocations(result) {
  if (!result?.budget_allocations?.length) return '<div class="empty">No budget allocation details were returned.</div>';
  return `<div class="allocation-list">${result.budget_allocations.map(item => `
    <div class="allocation">
      <div class="allocation-line"><span>${escapeHtml(item.category)}</span><span>${formatINR(item.allocated_amount)} · ${Number(item.percentage).toFixed(1)}%</span></div>
      <div class="progress"><span style="width:${Math.max(0,Math.min(100,Number(item.percentage)||0))}%"></span></div>
      <div class="help">${escapeHtml(item.rationale)}</div>
    </div>`).join('')}</div>`;
}

function renderWarnings(result) {
  if (!result?.warnings?.length) return '';
  return `<section class="section" style="padding-bottom:0"><div class="warnings">${result.warnings.map(w => `<div class="warning">${escapeHtml(w)}</div>`).join('')}</div></section>`;
}

function renderResultPage(type) {
  const result = loadPlannerResult(type);
  if (!result) { root.innerHTML = '<div class="empty">No recommendation is loaded yet. Return to the planner and submit a request.</div>'; return; }

  document.getElementById('summary').textContent = result.summary || '';
  document.getElementById('budgetStat').textContent = formatINR(result.budget);
  document.getElementById('totalStat').textContent = formatINR(result.estimated_total);
  document.getElementById('remainingStat').textContent = formatINR(result.remaining_budget);
  document.getElementById('aiStat').textContent = result.ai_used ? 'Gemini AI' : 'Fallback';
  document.getElementById('allocationRoot').innerHTML = renderAllocations(result);
  document.getElementById('recommendationRoot').innerHTML = renderRecommendationCards(result);
  document.getElementById('warningsRoot').innerHTML = renderWarnings(result);
}


function renderFooter() {
  if (document.querySelector('.footer')) return;
  const footer = document.createElement('footer');
  footer.className = 'footer site-footer';
  footer.innerHTML = `<div class="container footer-inner"><span>© <span data-year></span> PocketSmart AI</span><div class="footer-links"><a href="index.html">Home</a><a href="testimonials.html">Testimonials</a><a href="history.html">History</a></div></div>`;
  document.body.appendChild(footer);
}

document.addEventListener('DOMContentLoaded', () => {
  renderAuthNav();
  renderFooter();
  const year = document.querySelector('[data-year]');
  if (year) year.textContent = new Date().getFullYear();
});
