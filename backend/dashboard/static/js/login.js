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

document.getElementById('themeToggle').addEventListener('click', toggleTheme);
document.getElementById('togglePwBtn')?.addEventListener('click', togglePw);

// ── STEP 1: Username ─────────────────────────────────────────────────────────
let sessionToken = '';

document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('loginBtn');
  const err = document.getElementById('loginError');
  btn.textContent = 'Memuat...';
  btn.disabled = true;
  err.style.display = 'none';

  const form = new FormData();
  form.append('username', document.getElementById('username').value);
  // form.append('password', ...) - dihapus, karena login seed pakai challenge

  try {
    const res  = await fetch('/api/login/challenge', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok && data.question) {
      // Step 1 berhasil → masuk ke step 2
      document.getElementById('challengeQuestion').textContent = data.question;
      sessionToken = data.session_token;
      document.getElementById('step1').style.display = 'none';
      document.getElementById('step2').style.display = 'block';
      document.getElementById('challengeAnswer').focus();
    } else {
      err.textContent = data.detail || 'User belum setup seed phrase.';
      err.style.display = 'block';
    }
  } catch {
    err.textContent = 'Tidak dapat terhubung ke server';
    err.style.display = 'block';
  } finally {
    btn.textContent = 'Lanjut →';
    btn.disabled = false;
  }
});

// ── STEP 2: Challenge ────────────────────────────────────────────────────────
document.getElementById('challengeForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('challengeBtn');
  const err = document.getElementById('challengeError');
  btn.textContent = 'Memverifikasi...';
  btn.disabled = true;
  err.style.display = 'none';

  const form = new FormData();
  form.append('session_token', sessionToken);
  form.append('answer', document.getElementById('challengeAnswer').value);

  try {
    const res  = await fetch('/api/login/verify-challenge', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok && data.success) {
      // Challenge benar → masuk ke step 3
      document.getElementById('step2').style.display = 'none';
      document.getElementById('step3').style.display = 'block';
      document.getElementById('seedPhrase').focus();
    } else {
      err.textContent = data.detail || 'Jawaban salah!';
      err.style.display = 'block';
    }
  } catch {
    err.textContent = 'Tidak dapat terhubung ke server';
    err.style.display = 'block';
  } finally {
    btn.textContent = 'Verifikasi';
    btn.disabled = false;
  }
});

document.getElementById('skipChallengeBtn').addEventListener('click', () => {
  // Lewati challenge → langsung ke recovery key
  document.getElementById('step2').style.display = 'none';
  document.getElementById('step4').style.display = 'block';
  document.getElementById('recoveryKey').focus();
});

// ── STEP 3: Seed Phrase ──────────────────────────────────────────────────────
document.getElementById('seedForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('seedBtn');
  const err = document.getElementById('seedError');
  btn.textContent = 'Login...';
  btn.disabled = true;
  err.style.display = 'none';

  const form = new FormData();
  form.append('session_token', sessionToken);
  form.append('seed_phrase', document.getElementById('seedPhrase').value);

  try {
    const res  = await fetch('/api/login/verify-seed', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok && data.access_token) {
      // Login sukses
      sessionStorage.setItem('token', data.access_token);
      sessionStorage.setItem('unit',  data.unit);
      sessionStorage.setItem('username', document.getElementById('username').value);
      localStorage.setItem('savedUser', document.getElementById('username').value);
      window.location.href = 'index.html';
    } else {
      err.textContent = data.detail || 'Seed phrase salah!';
      err.style.display = 'block';
    }
  } catch {
    err.textContent = 'Tidak dapat terhubung ke server';
    err.style.display = 'block';
  } finally {
    btn.textContent = 'Login';
    btn.disabled = false;
  }
});

document.getElementById('recoveryBtn').addEventListener('click', () => {
  document.getElementById('step3').style.display = 'none';
  document.getElementById('step4').style.display = 'block';
  document.getElementById('recoveryKey').focus();
});

// ── STEP 4: Recovery Key ─────────────────────────────────────────────────────
document.getElementById('recoveryForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('recoveryBtn2');
  const err = document.getElementById('recoveryError');
  btn.textContent = 'Login...';
  btn.disabled = true;
  err.style.display = 'none';

  const form = new FormData();
  form.append('recovery_key', document.getElementById('recoveryKey').value);

  try {
    const res  = await fetch('/api/login/recovery', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok && data.access_token) {
      sessionStorage.setItem('token', data.access_token);
      sessionStorage.setItem('unit',  data.unit);
      sessionStorage.setItem('username', data.username);
      localStorage.setItem('savedUser', data.username);
      window.location.href = 'index.html';
    } else {
      err.textContent = data.detail || 'Recovery key salah!';
      err.style.display = 'block';
    }
  } catch {
    err.textContent = 'Tidak dapat terhubung ke server';
    err.style.display = 'block';
  } finally {
    btn.textContent = 'Login';
    btn.disabled = false;
  }
});

document.getElementById('backToSeedBtn').addEventListener('click', () => {
  document.getElementById('step4').style.display = 'none';
  document.getElementById('step3').style.display = 'block';
  document.getElementById('seedPhrase').focus();
});

// Prefill username
document.getElementById('username').value = localStorage.getItem('savedUser') || '';
