/* ── Config ── */
const API = '';  // Relative URL, karena served dari FastAPI

/* ── Auth guard ── */
const token    = sessionStorage.getItem('token') || localStorage.getItem('token');
const unit     = sessionStorage.getItem('unit')  || localStorage.getItem('unit');
const username = sessionStorage.getItem('username') || localStorage.getItem('username');

if (!token) { window.location.href = 'login.html'; }

/* ── Theme ── */
const savedTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);
updateThemeBtn();

function toggleTheme() {
  const cur  = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  updateThemeBtn();
}
function updateThemeBtn() {
  const t = document.documentElement.getAttribute('data-theme');
  document.querySelectorAll('.theme-toggle').forEach(b => b.textContent = t === 'dark' ? '☀️' : '🌙');
}

/* ── Init ── */
window.addEventListener('DOMContentLoaded', () => {
  // Set info
  document.getElementById('sidebarUser').textContent  = username || '-';
  document.getElementById('unitTitle').textContent    = 'RestuSec — Absensi Murid';
  document.getElementById('pageTitle').textContent    = 'Data Absensi';

  // Set tanggal hari ini
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById('filterTgl').value = today;
  document.getElementById('todayDate').textContent = formatTanggal(today);

  // Default range rekap: 1-7 hari ini (bulan berjalan)
  const firstDay = new Date().toISOString().slice(0, 7) + '-01';
  document.getElementById('rekapStart').value = firstDay;
  document.getElementById('rekapEnd').value   = today;

  // Event bindings (no inline handlers, aman untuk CSP tanpa 'unsafe-inline')
  document.querySelectorAll('.nav-item').forEach(el =>
    el.addEventListener('click', (e) => { e.preventDefault(); showPage(el.dataset.page, el); }));
  document.getElementById('menuToggle').addEventListener('click', toggleSidebar);
  document.getElementById('themeToggle').addEventListener('click', toggleTheme);
  document.getElementById('sidebarBackdrop').addEventListener('click', closeSidebar);
  document.getElementById('logoutBtn').addEventListener('click', logout);
  document.getElementById('filterTgl').addEventListener('change', loadAbsensi);
  document.getElementById('calPrev').addEventListener('click', () => calMove(-1));
  document.getElementById('calNext').addEventListener('click', () => calMove(1));
  document.getElementById('exportBtn').addEventListener('click', exportExcel);
  document.getElementById('cancelSelectBtn').addEventListener('click', cancelSelect);
  document.getElementById('selectAllBtn').addEventListener('click', selectAll);
  document.getElementById('deleteSelBtn').addEventListener('click', deleteSelected);
  document.getElementById('addMuridBtn').addEventListener('click', addMurid);
  document.getElementById('rekapBtn').addEventListener('click', loadRekap);
  document.getElementById('exportRekapBtn').addEventListener('click', exportRekap);
  document.getElementById('addMateriBtn').addEventListener('click', addMateri);
  document.getElementById('addNilaiBtn').addEventListener('click', addNilai);

  loadAbsensi();
  loadStats();
  initCalendar();
});

/* ── Navigation ── */
function showPage(page, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.add('active');
  if (el) el.classList.add('active');
  const titles = { absensi: 'Data Absensi', murid: 'Murid & QR', rekap: 'Rekap', materi: 'Materi', nilai: 'Nilai' };
  document.getElementById('pageTitle').textContent = titles[page] || 'Absensi';
  if (page === 'murid') loadMurid();
  if (page === 'materi') loadMateri();
  if (page === 'nilai') { loadMuridOptions(); loadNilai(); loadRata2(); }
  closeSidebar();
}

function toggleSidebar() {
  const s = document.getElementById('sidebar');
  s.classList.toggle('open');
  document.getElementById('sidebarBackdrop').classList.toggle('show', s.classList.contains('open'));
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarBackdrop').classList.remove('show');
}

/* ── API Helper ── */
async function apiFetch(url, opts = {}) {
  const res = await fetch(API + url, {
    ...opts,
    headers: {
      'Authorization': `Bearer ${token}`,
      ...(opts.headers || {}),
    },
  });
  if (res.status === 401) { logout(); return null; }
  return res;
}

/* ── Kalender (Wall Planner) ── */
const BULAN = ['Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember'];
let calYear, calMonth;
const calDays = ['Min','Sen','Sel','Rab','Kam','Jum','Sab'];

function initCalendar() {
  const now = new Date();
  calYear  = now.getFullYear();
  calMonth = now.getMonth();
  renderCalendar();
}

function renderCalendar() {
  const title = document.getElementById('calTitle');
  title.textContent = `${BULAN[calMonth]} ${calYear}`;

  const first = new Date(calYear, calMonth, 1);
  const startPad = first.getDay();
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
  const monthPrefix = `${calYear}-${String(calMonth + 1).padStart(2, '0')}`;

  // Hari-hari yang punya absensi pada bulan tampil (pakai endpoint tanpa tanggal = 200 terakhir)
  const byDate = {};
  fetch('/api/absensi')
    .then(r => r.ok ? r.json() : [])
    .then(rows => {
      rows.forEach(r => {
        if (r.tanggal && r.tanggal.startsWith(monthPrefix)) {
          byDate[r.tanggal] = byDate[r.tanggal] || { Hadir: 0, Izin: 0, Sakit: 0 };
          byDate[r.tanggal][r.status] = (byDate[r.tanggal][r.status] || 0) + 1;
        }
      });
      drawCells(byDate, startPad, daysInMonth);
    })
    .catch(() => drawCells(byDate, startPad, daysInMonth));
}

function calMove(dir) {
  calMonth += dir;
  if (calMonth < 0)  { calMonth = 11; calYear--; }
  if (calMonth > 11) { calMonth = 0;  calYear++; }
  renderCalendar();
}

function drawCells(byDate, startPad, daysInMonth) {
  const grid = document.getElementById('calGrid');
  let html = '';
  for (let i = 0; i < startPad; i++) html += '<div class="cal-cell empty"></div>';

  const selected = document.getElementById('filterTgl').value;

  for (let d = 1; d <= daysInMonth; d++) {
    const iso = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const today = iso === new Date().toISOString().slice(0, 10);
    const c = byDate[iso];
    const cls = ['cal-cell', today ? 'today' : '', selected === iso ? 'selected' : ''].filter(Boolean).join(' ');
    let dots = '';
    if (c) {
      dots = '<span class="cal-dots">'
        + (c.Hadir ? `<i class="dot h" title="Hadir ${c.Hadir}"></i>` : '')
        + (c.Izin  ? `<i class="dot i" title="Izin ${c.Izin}"></i>` : '')
        + (c.Sakit ? `<i class="dot s" title="Sakit ${c.Sakit}"></i>` : '')
        + '</span>';
    }
    html += `<div class="${cls}" data-date="${iso}" role="button" tabindex="0">${dots}<span class="day">${d}</span></div>`;
  }
  grid.innerHTML = html;

  grid.querySelectorAll('.cal-cell:not(.empty)').forEach(cell => {
    const go = () => {
      document.getElementById('filterTgl').value = cell.dataset.date;
      loadAbsensi();
      renderCalendar();
    };
    cell.addEventListener('click', go);
    cell.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
  });
}

/* ── Load Absensi ── */

async function loadAbsensi() {
  const tgl = document.getElementById('filterTgl').value;
  const url = tgl ? `/api/absensi?tanggal=${tgl}` : '/api/absensi';
  const res = await apiFetch(url);
  if (!res) return;

  renderTable(await res.json());
  loadStats(tgl);
}

function renderTable(data) {
  const body = document.getElementById('absensiBody');
  if (!data.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty-msg">📭 Belum ada data absensi</td></tr>';
    return;
  }

  body.innerHTML = data.map(row => `
    <tr data-id="${row.id}">
      <td><input type="checkbox" class="row-check" data-id="${row.id}"></td>
      <td>${formatTanggal(row.tanggal)}</td>
      <td>${esc(row.jam)}</td>
      <td><strong>${esc(row.nama)}</strong></td>
      <td>${esc(row.kelas)}</td>
      <td>${badgeStatus(row.status)}</td>
    </tr>
  `).join('');

  body.querySelectorAll('.row-check').forEach(cb => cb.addEventListener('change', onCheckChange));

  // Pasang long-press ke setiap row
  body.querySelectorAll('tr').forEach(attachLongPress);
}

function badgeStatus(status) {
  const cls = { Hadir: 'badge-hadir', Izin: 'badge-izin', Sakit: 'badge-sakit' }[status] || '';
  const ico = { Hadir: '✅', Izin: '📋', Sakit: '🏥' }[status] || '';
  return `<span class="badge ${cls}">${ico} ${status}</span>`;
}

/* ── Stats ── */
async function loadStats(tgl) {
  const url = tgl ? `/api/stats?tanggal=${tgl}` : '/api/stats';
  const res = await apiFetch(url);
  if (!res) return;
  const s = await res.json();
  document.getElementById('statTotal').textContent = s.total  || 0;
  document.getElementById('statHadir').textContent = s.hadir  || 0;
  document.getElementById('statIzin').textContent  = s.izin   || 0;
  document.getElementById('statSakit').textContent = s.sakit  || 0;
}

/* ── Long Press Delete ── */
let pressTimer   = null;
const PRESS_MS   = 600;
let selectMode   = false;

function attachLongPress(tr) {
  let pressing = false;

  const start = () => {
    pressing = true;
    tr.classList.add('pressing');
    pressTimer = setTimeout(() => {
      if (pressing) enterSelectMode(tr.dataset.id);
      tr.classList.remove('pressing');
    }, PRESS_MS);
  };

  const cancel = () => {
    pressing = false;
    clearTimeout(pressTimer);
    tr.classList.remove('pressing');
  };

  // Mouse
  tr.addEventListener('mousedown',  start);
  tr.addEventListener('mouseup',    cancel);
  tr.addEventListener('mouseleave', cancel);

  // Touch — no preventDefault, allow scroll to work
  tr.addEventListener('touchstart', start, { passive: true });
  tr.addEventListener('touchend',   cancel);
  tr.addEventListener('touchmove',  cancel);

  // Keyboard — Enter/Space to enter select mode on focused row
  tr.setAttribute('tabindex', '0');
  tr.setAttribute('role', 'row');
  tr.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      enterSelectMode(tr.dataset.id);
    }
  });
}

function enterSelectMode(firstId) {
  if (selectMode) return;
  selectMode = true;
  document.getElementById('deleteToolbar').style.display = 'flex';

  // Centang row yang di-hold
  const cb = document.querySelector(`.row-check[data-id="${firstId}"]`);
  if (cb) { cb.checked = true; cb.closest('tr').classList.add('selected'); }

  updateSelectedCount();
}

function cancelSelect() {
  selectMode = false;
  document.getElementById('deleteToolbar').style.display = 'none';
  document.querySelectorAll('.row-check').forEach(cb => {
    cb.checked = false;
    cb.closest('tr').classList.remove('selected');
  });
  updateSelectedCount();
}

function selectAll() {
  document.querySelectorAll('.row-check').forEach(cb => {
    cb.checked = true;
    cb.closest('tr').classList.add('selected');
  });
  updateSelectedCount();
}

function onCheckChange() {
  if (!selectMode) {
    // Masuk select mode jika user klik checkbox secara langsung
    selectMode = true;
    document.getElementById('deleteToolbar').style.display = 'flex';
  }
  document.querySelectorAll('.row-check').forEach(cb => {
    cb.closest('tr').classList.toggle('selected', cb.checked);
  });
  updateSelectedCount();
}

function updateSelectedCount() {
  const n = document.querySelectorAll('.row-check:checked').length;
  document.getElementById('selectedCount').textContent = `${n} dipilih`;
}

async function deleteSelected() {
  const ids = [...document.querySelectorAll('.row-check:checked')].map(cb => +cb.dataset.id);
  if (!ids.length) { showToast('Pilih data yang ingin dihapus'); return; }

  if (!confirm(`Hapus ${ids.length} data absensi? Aksi ini tidak dapat dibatalkan.`)) return;

  const res = await apiFetch('/api/absensi', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  });

  if (res && res.ok) {
    const d = await res.json();
    showToast(`✅ ${d.deleted} data berhasil dihapus`);
    cancelSelect();
    loadAbsensi();
  } else {
    showToast('❌ Gagal menghapus data');
  }
}

/* ── Export Excel ── */
async function exportExcel() {
  const tgl = document.getElementById('filterTgl').value;
  const url = tgl ? `/api/absensi/export?tanggal=${tgl}` : '/api/absensi/export';

  showToast('⏳ Menyiapkan file Excel…');
  try {
    const res = await apiFetch(url);
    if (!res || !res.ok) { showToast('❌ Gagal export'); return; }

    const blob = await res.blob();
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `absensi_${unit}_${tgl || 'semua'}.xlsx`;
    a.click();
    URL.revokeObjectURL(a.href);
    showToast('✅ File Excel berhasil diunduh');
  } catch {
    showToast('❌ Gagal mengunduh file');
  }
}

/* ── Rekap ── */
async function loadRekap() {
  const start = document.getElementById('rekapStart').value;
  const end   = document.getElementById('rekapEnd').value;
  if (!start || !end) { showToast('Pilih tanggal awal & akhir dulu'); return; }
  if (start > end)    { showToast('Tanggal awal tidak boleh melewati tanggal akhir'); return; }

  const res = await apiFetch(`/api/rekap?start=${start}&end=${end}`);
  if (!res) return;

  const data = await res.json();
  renderRekap(data);
  document.getElementById('rekapRange').textContent =
    `${formatTanggal(start)} — ${formatTanggal(end)}`;
}

function renderRekap(data) {
  const body = document.getElementById('rekapBody');
  if (!data.length) {
    body.innerHTML = '<tr><td colspan="9" class="empty-msg">📭 Tidak ada data pada rentang tanggal ini</td></tr>';
    return;
  }

  body.innerHTML = data.map((r, i) => {
    const pct  = r.total ? Math.round((r.hadir / r.total) * 100) : 0;
    const pcls = pct >= 80 ? 'badge-hadir' : pct >= 50 ? 'badge-izin' : 'badge-sakit';
    return `
      <tr>
        <td>${i + 1}</td>
        <td><strong>${esc(r.nama)}</strong></td>
        <td>${esc(r.kelas)}</td>
        <td><span class="badge badge-hadir">✅ ${r.hadir}</span></td>
        <td><span class="badge badge-izin">📋 ${r.izin}</span></td>
        <td><span class="badge badge-sakit">🏥 ${r.sakit}</span></td>
        <td><strong>${r.total}</strong></td>
        <td><span class="badge ${pcls}">${pct}%</span></td>
      </tr>`;
  }).join('');
}

async function exportRekap() {
  const start = document.getElementById('rekapStart').value;
  const end   = document.getElementById('rekapEnd').value;
  if (!start || !end) { showToast('Pilih tanggal awal & akhir dulu'); return; }

  showToast('⏳ Menyiapkan file Excel rekap…');
  try {
    const res = await apiFetch(`/api/rekap/export?start=${start}&end=${end}`);
    if (!res || !res.ok) { showToast('❌ Gagal export'); return; }

    const blob = await res.blob();
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `rekap_${unit}_${start}_${end}.xlsx`;
    a.click();
    URL.revokeObjectURL(a.href);
    showToast('✅ File rekap berhasil diunduh');
  } catch {
    showToast('❌ Gagal mengunduh file');
  }
}

/* ── Toast ── */
let toastTimer;
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
}

/* ── Murid & QR ── */
async function loadMurid() {
  const res = await apiFetch('/api/murid');
  if (!res) return;
  const data = await res.json();
  const body = document.getElementById('muridBody');
  if (!data.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-msg">📭 Belum ada murid. Tambah di atas.</td></tr>';
    return;
  }
  body.innerHTML = data.map(m => `
    <tr>
      <td><strong>${esc(m.urutan || '-')}</strong></td>
      <td><strong>${esc(m.nama)}</strong></td>
      <td>${esc(m.kelas)}</td>
      <td><a class="link-maps" href="#" data-id="${m.id}" data-nama="${esc(m.nama)}" data-token="${esc(m.token)}" data-action="showQR">📱 Tampilkan</a></td>
      <td><a class="link-maps" href="#" data-id="${m.id}" data-nama="${esc(m.nama)}" data-action="resetToken" title="Buat token baru">🔄</a>
          <a class="link-maps" href="#" data-id="${m.id}" data-nama="${esc(m.nama)}" data-action="delMurid">🗑</a></td>
    </tr>
  `).join('');

  body.querySelectorAll('a[data-action]').forEach(a =>
    a.addEventListener('click', (e) => {
      const fn = { showQR, resetToken, delMurid }[a.dataset.action];
      if (fn) fn(e, a);
    }));
}
async function addMurid() {
  const nama   = document.getElementById('mNama').value.trim();
  const kelas  = document.getElementById('mKelas').value.trim();
  const urutan = parseInt(document.getElementById('mUrutan').value, 10) || 0;
  if (!nama || !kelas) { showToast('Isi nama & kelas dulu'); return; }

  const res = await apiFetch('/api/murid', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nama, kelas, unit: 'MI', urutan }),
  });
  if (res && res.ok) {
    showToast('✅ Murid ditambahkan');
    ['mNama','mKelas','mUrutan'].forEach(id => document.getElementById(id).value = '');
    loadMurid();
  } else {
    showToast('❌ Gagal menambah murid');
  }
}

async function delMurid(e, el) {
  e.preventDefault();
  const id = Number(el.dataset.id), nama = el.dataset.nama;
  if (!confirm(`Hapus murid "${nama}"?`)) return;
  const res = await apiFetch(`/api/murid/${id}`, { method: 'DELETE' });
  if (res && res.ok) { showToast('✅ Murid dihapus'); loadMurid(); }
  else showToast('❌ Gagal menghapus');
}

async function resetToken(e, el) {
  e.preventDefault();
  const id = Number(el.dataset.id), nama = el.dataset.nama;
  if (!confirm(`Buat token baru untuk "${nama}"? QR lama langsung tidak berlaku lagi.`)) return;
  const res = await apiFetch(`/api/murid/${id}/reset-token`, { method: 'POST' });
  if (res && res.ok) { showToast('✅ Token baru dibuat'); loadMurid(); }
  else showToast('❌ Gagal membuat token');
}

async function showQR(e, el) {
  e.preventDefault();
  const id = Number(el.dataset.id), nama = el.dataset.nama, token = el.dataset.token;
  const old = document.querySelector('#qrOverlay');
  if (old) old.remove();

  const absenUrl = new URL('/absen?t=' + token, location.origin).href;

  const overlay = document.createElement('div');
  overlay.id = 'qrOverlay';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;z-index:999';
  overlay.innerHTML = `
    <style>
      .qr-pop { animation: qrIn .4s cubic-bezier(.2,.9,.3,1.2) both; }
      @keyframes qrIn { from { opacity:0; transform:scale(.85);} to { opacity:1; transform:scale(1);} }
      .qr-img { animation: qrImgIn .5s ease .1s both; }
      @keyframes qrImgIn { from { opacity:0; transform:translateY(6px);} to { opacity:1; transform:translateY(0);} }
      @media (prefers-reduced-motion: reduce) { .qr-pop,.qr-img{ animation:none !important; } }
    </style>
    <div class="qr-pop" style="background:#fff;border-radius:14px;padding:24px;text-align:center;max-width:340px;width:90%">
      <h3 style="margin:0 0 4px;color:#111">${esc(nama)}</h3>
      <img id="qrImg" class="qr-img" src="" alt="Memuat..." style="width:220px;height:220px;margin:12px 0;image-rendering:pixelated">
      <a id="qrDownload" href="#" download="qr-${esc(nama)}.png" style="display:block;padding:10px;margin-bottom:8px;border-radius:8px;background:#16a34a;color:#fff;font-weight:bold;text-decoration:none">⬇️ Unduh</a>
      <a id="qrWa" href="#" target="_blank" rel="noopener" style="display:block;padding:10px;margin-bottom:8px;border-radius:8px;background:#25D366;color:#fff;font-weight:bold;text-decoration:none">💬 Kirim via WhatsApp</a>
      <button id="qrClose" style="width:100%;padding:11px;border:none;border-radius:8px;background:#3b82f6;color:#fff;font-weight:bold;cursor:pointer">Tutup</button>
    </div>`;

  const close = () => overlay.remove();
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  overlay.querySelector('#qrClose').onclick = close;
  overlay.querySelector('#qrWa').href = 'https://wa.me/?text=' + encodeURIComponent('Absen QR: ' + absenUrl);
  document.body.appendChild(overlay);

  const res = await apiFetch(`/api/murid/${id}/qr`);
  if (res && res.ok) {
    const blob = await res.blob();
    const fr   = new FileReader();
    fr.onload  = () => {
      overlay.querySelector('#qrImg').src       = fr.result;
      overlay.querySelector('#qrDownload').href = fr.result;
    };
    fr.readAsDataURL(blob);
  } else {
    overlay.querySelector('#qrImg').alt = '❌ Gagal memuat QR';
  }
}

/* ── Logout ── */
function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('unit');
  localStorage.removeItem('username');
  localStorage.removeItem('savedUser');
  sessionStorage.removeItem('token');
  sessionStorage.removeItem('unit');
  sessionStorage.removeItem('username');
  window.location.href = 'login.html';
}

/* ── Materi ── */
async function loadMateri() {
  const res = await apiFetch('/api/materi');
  if (!res) return;
  const data = await res.json();
  const body = document.getElementById('materiBody');
  if (!data.length) { body.innerHTML = '<tr><td colspan="4" class="empty-msg">Belum ada materi.</td></tr>'; return; }
  body.innerHTML = data.map(m => `
    <tr>
      <td>${esc(m.tanggal)}</td>
      <td><strong>${esc(m.judul)}</strong></td>
      <td style="white-space:pre-wrap">${esc(m.isi)}</td>
      <td><a class="link-maps" href="#" data-id="${m.id}" data-action="delMateri">🗑</a></td>
    </tr>`).join('');

  body.querySelectorAll('a[data-action="delMateri"]').forEach(a =>
    a.addEventListener('click', (e) => delMateri(e, a)));
}

async function addMateri() {
  const judul = document.getElementById('mJudul').value.trim();
  const isi   = document.getElementById('mIsi').value.trim();
  if (!judul || !isi) { showToast('Isi judul & isi materi dulu'); return; }
  const res = await apiFetch('/api/materi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ judul, isi }),
  });
  if (res && res.ok) {
    showToast('✅ Materi disimpan');
    document.getElementById('mJudul').value = '';
    document.getElementById('mIsi').value = '';
    loadMateri();
  } else showToast('❌ Gagal menyimpan materi');
}

async function delMateri(e, el) {
  e.preventDefault();
  if (!confirm('Hapus materi ini?')) return;
  const res = await apiFetch(`/api/materi/${el.dataset.id}`, { method: 'DELETE' });
  if (res && res.ok) { showToast('✅ Materi dihapus'); loadMateri(); }
  else showToast('❌ Gagal menghapus');
}

/* ── Nilai ── */
async function loadMuridOptions() {
  const res = await apiFetch('/api/murid');
  if (!res) return;
  const data = await res.json();
  const sel = document.getElementById('nMurid');
  const prev = sel.value;
  sel.innerHTML = '<option value="">Pilih murid…</option>' + data.map(m =>
    `<option value="${m.id}">${esc(m.nama)} — ${esc(m.kelas)}</option>`).join('');
  sel.value = prev;
}

async function loadNilai() {
  const res = await apiFetch('/api/nilai');
  if (!res) return;
  const data = await res.json();
  const body = document.getElementById('nilaiBody');
  const muridById = {};
  try { const mr = await apiFetch('/api/murid'); if (mr) (await mr.json()).forEach(m => muridById[m.id] = m.nama); } catch (e) {}
  if (!data.length) { body.innerHTML = '<tr><td colspan="5" class="empty-msg">Belum ada nilai.</td></tr>'; return; }
  body.innerHTML = data.map(n => `
    <tr>
      <td>${esc(n.tanggal)}</td>
      <td>${esc(muridById[n.murid_id] || n.murid_id)}</td>
      <td>${esc(n.mapel)}</td>
      <td><strong>${n.nilai}</strong></td>
      <td><a class="link-maps" href="#" data-id="${n.id}" data-action="delNilai">🗑</a></td>
    </tr>`).join('');

  body.querySelectorAll('a[data-action="delNilai"]').forEach(a =>
    a.addEventListener('click', (e) => delNilai(e, a)));
}

async function addNilai() {
  const murid_id = document.getElementById('nMurid').value;
  const mapel    = document.getElementById('nMapel').value.trim();
  const nilai    = document.getElementById('nNilai').value;
  if (!murid_id || !mapel || nilai === '') { showToast('Pilih murid, isi mapel & nilai'); return; }
  const res = await apiFetch('/api/nilai', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ murid_id: Number(murid_id), mapel, nilai: Number(nilai) }),
  });
  if (res && res.ok) {
    showToast('✅ Nilai disimpan');
    document.getElementById('nMapel').value = '';
    document.getElementById('nNilai').value = '';
    loadNilai(); loadRata2();
  } else {
    const d = await res.json().catch(() => ({}));
    showToast('❌ ' + (d.detail || 'Gagal menyimpan nilai'));
  }
}

async function delNilai(e, el) {
  e.preventDefault();
  if (!confirm('Hapus nilai ini?')) return;
  const res = await apiFetch(`/api/nilai/${el.dataset.id}`, { method: 'DELETE' });
  if (res && res.ok) { showToast('✅ Nilai dihapus'); loadNilai(); loadRata2(); }
  else showToast('❌ Gagal menghapus');
}

async function loadRata2() {
  const res = await apiFetch('/api/nilai/rata2');
  if (!res) return;
  const data = await res.json();
  const body = document.getElementById('rataBody');
  const withVal = data.filter(r => r.rata2 !== null);
  if (!withVal.length) { body.innerHTML = '<tr><td colspan="5" class="empty-msg">Belum ada nilai.</td></tr>'; return; }
  body.innerHTML = withVal.map((r, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><strong>${esc(r.nama)}</strong></td>
      <td>${esc(r.kelas)}</td>
      <td>${r.jumlah}</td>
      <td><strong>${r.rata2}</strong></td>
    </tr>`).join('');
}

/* ── Utils ── */
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

function formatTanggal(tgl) {
  if (!tgl) return '-';
  const d = new Date(tgl + 'T00:00:00');
  return d.toLocaleDateString('id-ID', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
}
