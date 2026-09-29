function csvList(value) {
  return value.split(',').map(v => v.trim()).filter(Boolean);
}

async function submitHome(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.getElementById('formStatus');
  status.textContent = 'Generating recommendations…';
  try {
    const items = [...document.querySelectorAll('[data-home-item]')].map(row => ({
      name: row.querySelector('.item-name').value.trim(),
      quantity: Number(row.querySelector('.item-qty').value),
      preferred_style: row.querySelector('.item-style').value.trim() || null
    })).filter(item => item.name);
    if (!items.length) throw new Error('Add at least one home item.');
    const payload = {
      budget: Number(form.budget.value),
      rooms: csvList(form.rooms.value),
      items,
      city: form.city.value.trim() || null,
      style: form.style.value.trim() || null,
      notes: form.notes.value.trim() || null
    };
    const result = await apiFetch('/planners/home', { method:'POST', body: JSON.stringify(payload) });
    storePlannerResult('home', result);
    window.location.href = 'home_recommendations.html';
  } catch (error) { status.className = 'error'; status.textContent = error.message; }
}

async function submitParty(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.getElementById('formStatus');
  status.textContent = 'Generating recommendations…';
  try {
    const payload = {
      budget: Number(form.budget.value),
      guest_count: Number(form.guest_count.value),
      event_type: form.event_type.value.trim(),
      venue: form.venue.value.trim() || null,
      city: form.city.value.trim() || null,
      food_preference: form.food_preference.value.trim() || null,
      decoration_style: form.decoration_style.value.trim() || null,
      notes: form.notes.value.trim() || null
    };
    const result = await apiFetch('/planners/party', { method:'POST', body: JSON.stringify(payload) });
    storePlannerResult('party', result);
    window.location.href = 'party_recommendations.html';
  } catch (error) { status.className = 'error'; status.textContent = error.message; }
}

async function submitJewelry(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.getElementById('formStatus');
  status.textContent = 'Analyzing your plan and generating recommendations…';
  try {
    const file = form.outfit_image.files[0];
    const useImageRoute = Boolean(file);
    let result;
    if (useImageRoute) {
      const body = new FormData();
      body.append('budget', form.budget.value);
      body.append('occasion', form.occasion.value.trim());
      body.append('style', form.style.value.trim());
      body.append('metal_preference', form.metal_preference.value.trim());
      body.append('outfit_color', form.outfit_color.value.trim());
      body.append('notes', form.notes.value.trim());
      body.append('outfit_image', file);
      result = await apiFetch('/planners/jewelry-upload', { method:'POST', body });
    } else {
      const payload = {
        budget: Number(form.budget.value),
        occasion: form.occasion.value.trim(),
        style: form.style.value.trim() || null,
        metal_preference: form.metal_preference.value.trim() || null,
        outfit_color: form.outfit_color.value.trim() || null,
        notes: form.notes.value.trim() || null
      };
      result = await apiFetch('/planners/jewelry', { method:'POST', body: JSON.stringify(payload) });
    }
    storePlannerResult('jewelry', result);
    window.location.href = 'jewelry_recommendations.html';
  } catch (error) { status.className = 'error'; status.textContent = error.message; }
}

function addHomeItem() {
  const wrap = document.getElementById('homeItems');
  const row = document.createElement('div');
  row.className = 'card'; row.dataset.homeItem = '';
  row.style.padding = '16px';
  row.innerHTML = `<div class="form-grid">
    <div class="form-group"><label>Item</label><input class="item-name" placeholder="e.g. Sofa" required></div>
    <div class="form-group"><label>Quantity</label><input class="item-qty" type="number" min="1" value="1" required></div>
    <div class="form-group"><label>Preferred style</label><input class="item-style" placeholder="Modern"></div>
    <div class="form-group"><label>&nbsp;</label><button type="button" class="btn btn-secondary" onclick="this.closest('[data-home-item]').remove()">Remove item</button></div>
  </div>`;
  wrap.appendChild(row);
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.body.dataset.authRequired === 'true') requireAuth();
  const previewInput = document.getElementById('outfit_image');
  const preview = document.getElementById('imagePreview');
  const previewImg = document.getElementById('previewImg');
  if (previewInput && preview && previewImg) {
    previewInput.addEventListener('change', () => {
      const file = previewInput.files[0];
      if (!file) { preview.style.display = 'none'; return; }
      if (!['image/jpeg','image/png','image/webp'].includes(file.type)) return;
      previewImg.src = URL.createObjectURL(file);
      preview.style.display = 'block';
    });
  }
});
