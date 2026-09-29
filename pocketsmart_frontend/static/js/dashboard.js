async function loadDashboard() {
  if (!requireAuth()) return;
  const user = getUser();
  if (user) document.getElementById('welcomeName').textContent = user.full_name;
  try {
    const session = await apiFetch('/session-info');
    document.getElementById('historyCount').textContent = session.history_count;
    document.getElementById('sessionExpiry').textContent = new Date(session.token_expires_at).toLocaleString('en-IN');
    const data = await apiFetch('/session-data');
    const root = document.getElementById('recentRoot');
    if (!data.recent_recommendations?.length) {
      root.innerHTML = '<div class="empty">No saved recommendations yet. Start with a planner.</div>';
      return;
    }
    root.innerHTML = data.recent_recommendations.slice(0,4).map(item => `
      <div class="card">
        <div class="badge">${escapeHtml(item.planner_type || 'planner')}</div>
        <h3 style="margin-top:10px">${escapeHtml(item.summary || 'Recommendation plan')}</h3>
        <p>Budget: ${formatINR(item.budget)} · Total: ${formatINR(item.estimated_total)}</p>
      </div>`).join('');
  } catch (error) {
    toast(error.message);
  }
}

document.addEventListener('DOMContentLoaded', loadDashboard);
