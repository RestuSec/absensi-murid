// Theme
const saved = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', saved);
document.querySelector('.theme-toggle').textContent = saved === 'dark' ? '☀️' : '🌙';

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  document.querySelector('.theme-toggle').textContent = next === 'dark' ? '☀️' : '🌙';
}

function togglePw() {
  const inp = document.getElementById('password');
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

// Brand RestuSec statis di halaman login admin
document.getElementById('username').value = localStorage.getItem('savedUser') || '';

document.getElementById('themeToggle').addEventListener('click', toggleTheme);
document.getElementById('togglePwBtn').addEventListener('click', togglePw);

document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('loginBtn');
  const err = document.getElementById('loginError');
  btn.textContent = 'Memuat...';
  btn.disabled = true;
  err.style.display = 'none';

  const form = new FormData();
  form.append('username', document.getElementById('username').value);
  form.append('password', document.getElementById('password').value);

  try {
    const res  = await fetch('/api/login', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok) {
      sessionStorage.setItem('token', data.access_token);
      sessionStorage.setItem('unit',  data.unit);
      sessionStorage.setItem('username', data.username);
      localStorage.setItem('savedUser', data.username);
      window.location.href = 'index.html';
    } else {
      err.textContent = data.detail || 'Login gagal';
      err.style.display = 'block';
    }
  } catch {
    err.textContent = 'Tidak dapat terhubung ke server';
    err.style.display = 'block';
  } finally {
    btn.textContent = 'Masuk';
    btn.disabled = false;
  }
});