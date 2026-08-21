// Galeri portfolio: tarik daftar file dari server, render img/video
(async function () {
  const grid = document.getElementById('galeriGrid');
  if (!grid) return;
  let files = [];
  try {
    const r = await fetch('/api/portfolio/list');
    if (r.ok) files = await r.json();
  } catch (e) { /* offline → biarkan kosong */ }
  if (!Array.isArray(files) || !files.length) {
    grid.innerHTML = '<p class="hint">// belum ada foto — upload dari dashboard admin (menu Portfolio)</p>';
    return;
  }
  grid.innerHTML = files.map(f => /\.(mp4|webm)$/i.test(f)
    ? `<div class="gitem"><video src="static/img/portfolio/${f}" muted autoplay loop playsinline></video></div>`
    : `<div class="gitem"><img src="static/img/portfolio/${f}" alt="Hasil karya RestuSec" loading="lazy"></div>`
  ).join('');
})();
