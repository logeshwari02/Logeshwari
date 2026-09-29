async function submitRegister(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.getElementById('formStatus');
  status.textContent = '';
  try {
    const full_name = form.full_name.value.trim();
    const email = form.email.value.trim();
    const password = form.password.value;
    const confirm = form.confirm_password.value;
    if (password !== confirm) throw new Error('Passwords do not match.');
    const user = await apiFetch('/auth/register', { method:'POST', body: JSON.stringify({ full_name, email, password }) });
    saveUser(user);
    status.className = 'success';
    status.textContent = 'Account created. Redirecting to login…';
    setTimeout(() => window.location.href = 'login.html', 700);
  } catch (error) {
    status.className = 'error';
    status.textContent = error.message;
  }
}

async function submitLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.getElementById('formStatus');
  status.textContent = '';
  try {
    const data = await apiFetch('/auth/login', {
      method:'POST',
      body: JSON.stringify({ email: form.email.value.trim(), password: form.password.value })
    });
    localStorage.setItem('pocketsmart_token', data.access_token);
    saveUser(data.user);
    status.className = 'success';
    status.textContent = 'Login successful. Redirecting…';
    setTimeout(() => window.location.href = 'dashboard.html', 500);
  } catch (error) {
    status.className = 'error';
    status.textContent = error.message;
  }
}
