async function loadHistory() {
  if (!requireAuth()) return;
  const root = document.getElementById('historyRoot');
  try {
    const data = await apiFetch('/history?limit=100&offset=0');
    if (!data.items?.length) { root.innerHTML = '<div class="empty">No recommendation history yet.</div>'; return; }
    root.innerHTML = `<div class="table-wrap"><table><thead><tr><th>Planner</th><th>Budget</th><th>Date</th><th>AI</th><th>Summary</th></tr></thead><tbody>${data.items.map(item => `<tr>
      <td><span class="badge">${escapeHtml(item.planner_type)}</span></td>
      <td>${formatINR(item.budget)}</td>
      <td>${new Date(item.created_at).toLocaleString('en-IN')}</td>
      <td>${item.response?.ai_used ? 'Gemini AI' : 'Fallback'}</td>
      <td>${escapeHtml(item.response?.summary || '')}</td>
    </tr>`).join('')}</tbody></table></div>`;
  } catch (error) { root.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`; }
}

document.addEventListener('DOMContentLoaded', loadHistory);
