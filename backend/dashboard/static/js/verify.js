(function () {
  const theme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', theme);
  document.getElementById('themeToggle').textContent = theme === 'dark' ? '☀️' : '🌙';
  document.getElementById('themeToggle').addEventListener('click', () => {
    const cur = document.documentElement.getAttribute('data-theme');
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    document.getElementById('themeToggle').textContent = next === 'dark' ? '☀️' : '🌙';
  });

  const errTop = document.getElementById('errTop');
  const loading = document.getElementById('loadingMsg');
  const step0 = document.getElementById('step0');
  const step1 = document.getElementById('step1');
  const step2 = document.getElementById('step2');
  const token = sessionStorage.getItem('token');

  function esc(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function showErr(msg) { errTop.textContent = msg; errTop.style.display = 'block'; }

  if (!token) {
    showErr('Tidak ada sesi login. Silakan login dulu.');
    loading.style.display = 'none';
    return;
  }

  async function api(path, opts) {
    const res = await fetch(path, {
      ...(opts || {}),
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token, ...((opts||{}).headers||{}) },
    });
    return res;
  }

  function showStep(n) {
    loading.style.display = 'none';
    step0.style.display = n === 0 ? 'block' : 'none';
    step1.style.display = n === 1 ? 'block' : 'none';
    step2.style.display = n === 2 ? 'block' : 'none';
  }

  let questions = [];
  let challengeId = '';
  const selected = {};

  async function loadQuiz() {
    try {
      const res = await api('/api/admin/seed/challenge3', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Gagal memuat kuis.');
      challengeId = data.challenge_id;
      questions = data.questions;
      renderQuiz();
      showStep(2);
    } catch (e) {
      showErr(e.message);
    }
  }

  function renderQuiz() {
    const wrap = document.getElementById('questions');
    wrap.innerHTML = '';
    questions.forEach((q, i) => {
      const block = document.createElement('div');
      block.className = 'q-block';
      const h = document.createElement('h4');
      h.textContent = 'Kata ke-' + q.position;
      block.appendChild(h);
      const row = document.createElement('div');
      row.className = 'opt-row';
      q.options.forEach(w => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'btn-secondary';
        b.textContent = w;
        b.dataset.word = w;
        b.addEventListener('click', () => {
          row.querySelectorAll('button').forEach(x => { x.classList.remove('btn-success'); x.classList.add('btn-secondary'); });
          b.classList.remove('btn-secondary');
          b.classList.add('btn-success');
          selected[q.position] = w;
        });
        row.appendChild(b);
      });
      block.appendChild(row);
      wrap.appendChild(block);
    });
  }

  async function generateAndShow() {
    const res = await api('/api/admin/setup-seed-and-key', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Gagal generate seed.');
    document.getElementById('seedPhraseOut').textContent = data.seed_phrase;
    document.getElementById('mappingOut').innerHTML =
      data.mapping.map(m => '<div><strong>' + m[0] + '</strong> &rarr; ' + esc(m[2]) + ' <small>(' + esc(m[1]) + ')</small></div>').join('');
    document.getElementById('recoveryOut').value = data.recovery_key;
    showStep(1);
  }

  document.getElementById('copyKeyBtn').addEventListener('click', () => {
    const v = document.getElementById('recoveryOut').value;
    if (!v) return;
    (navigator.clipboard ? navigator.clipboard.writeText(v) : Promise.reject())
      .then(() => alert('Recovery Key disalin ke clipboard. Segera simpan ke flashdisk!'))
      .catch(() => { document.getElementById('recoveryOut').select(); document.execCommand('copy'); alert('Recovery Key disalin. Simpan ke flashdisk!'); });
  });

  document.getElementById('nextBtn').addEventListener('click', loadQuiz);

  document.getElementById('regenerateBtn').addEventListener('click', async () => {
    if (!confirm('Seed lama akan DIHAPUS dan diganti seed + recovery key baru. Lanjutkan?')) return;
    selected.updated = undefined;
    try {
      await generateAndShow();
    } catch (e) {
      showErr(e.message);
    }
  });

  document.getElementById('verifyBtn').addEventListener('click', async () => {
    const vr = document.getElementById('verifyResult');
    vr.classList.remove('ok', 'err');
    vr.style.display = 'none';
    const answers = {};
    let missing = false;
    questions.forEach(q => { const w = selected[q.position]; if (!w) missing = true; else answers[q.position] = w; });
    if (missing) {
      vr.classList.add('err');
      vr.textContent = 'Lengkapi semua 3 kata dulu.';
      vr.style.display = 'block';
      return;
    }
    try {
      const btn = document.getElementById('verifyBtn');
      btn.disabled = true; btn.textContent = 'Memeriksa…';
      const res = await api('/api/admin/seed/verify3', { method: 'POST', body: JSON.stringify({ challenge_id: challengeId, answers: answers }) });
      const data = await res.json();
      if (res.ok) {
        vr.classList.add('ok');
        vr.textContent = '✅ ' + (data.message || 'Verifikasi berhasil!');
        vr.style.display = 'block';
        setTimeout(() => { window.location.href = '/dashboard?_=' + Date.now(); }, 900);
      } else {
        vr.classList.add('err');
        vr.textContent = data.detail || 'Jawaban belum tepat.';
        vr.style.display = 'block';
        loadQuiz();
      }
    } catch (e) {
      vr.classList.add('err');
      vr.textContent = 'Gagal terhubung ke server.';
      vr.style.display = 'block';
    } finally {
      const btn = document.getElementById('verifyBtn');
      btn.disabled = false; btn.textContent = '✅ Selesai Verifikasi';
    }
  });

  document.getElementById('pwBtn').addEventListener('click', async () => {
    const res = document.getElementById('pwResult');
    res.classList.remove('ok', 'err');
    res.style.display = 'none';
    const old = document.getElementById('oldPw').value;
    const n1 = document.getElementById('newPw').value;
    const n2 = document.getElementById('newPw2').value;
    if (!old || !n1 || !n2) { res.classList.add('err'); res.textContent = 'Isi semua kolom password.'; res.style.display = 'block'; return; }
    try {
      const btn = document.getElementById('pwBtn');
      btn.disabled = true; btn.textContent = 'Menyimpan…';
      const r = await api('/api/admin/change-password', { method: 'POST', body: JSON.stringify({ old_password: old, new_password: n1, new_password2: n2 }) });
      const d = await r.json();
      if (r.ok) {
        res.classList.add('ok'); res.textContent = '✅ Password diganti. Lanjut verifikasi seed...'; res.style.display = 'block';
        generateAndShow();
      } else {
        res.classList.add('err'); res.textContent = d.detail || 'Gagal ganti password.'; res.style.display = 'block';
      }
    } catch (e) {
      res.classList.add('err'); res.textContent = 'Gagal terhubung ke server.'; res.style.display = 'block';
    } finally {
      const btn = document.getElementById('pwBtn');
      btn.disabled = false; btn.textContent = 'Ganti Password & Lanjut';
    }
  });

  // Isi halaman: cek status seed
  (async () => {
    try {
      const res = await api('/api/admin/seed/status');
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Gagal cek status.');
      if (data.must_change_password) {
        showStep(0);
      } else if (data.seed_verified) {
        loadQuiz();
      } else {
        generateAndShow();
      }
    } catch (e) {
      showErr(e.message);
      loading.style.display = 'none';
    }
  })();
})();