const $ = id => document.getElementById(id);
const t = new URLSearchParams(location.search).get('t');
let lat = null, lon = null, info = null;

async function init(){
  if(!t){ $('result').className='err'; $('result').style.display='block';
          $('result').textContent='QR tidak valid. Hubungi admin.'; return; }
  try{
    const r = await fetch(`/api/absen/info/${t}`);
    if(!r.ok) throw new Error('QR tidak valid');
    info = await r.json();
    $('nm').textContent = info.nama;
    $('dt').textContent = info.kelas || '';
    $('who').style.display = 'block';
    getLoc();
  }catch(e){ $('result').className='err'; $('result').style.display='block';
             $('result').textContent=e.message; }
}

function getLoc(){
  if(!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(p=>{
    lat=p.coords.latitude; lon=p.coords.longitude;
    $('loc').textContent=`Lokasi: ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  }, ()=>{}); // gagal ambil lokasi → absen tetap jalan tanpa lokasi, tanpa pesan
}

async function absen(status){
  const fd = new FormData();
  fd.append('token', t);
  fd.append('status', status);
  if(lat!==null){ fd.append('latitude',lat); fd.append('longitude',lon); }
  const r = await fetch('/api/absen-web',{method:'POST',body:fd});
  const j = await r.json();
  if(!r.ok) return show('err', j.detail||'Gagal');
  // Balik ke menu pilih kehadiran, sembunyikan area konfirmasi.
  pending = null;
  $('confirm').style.display = 'none';
  statusBtn.forEach(id => $(id).style.display = '');
  $('result').className = 'ok ' + (j.status === 'Hadir' ? 'ok-hadir' : j.status === 'Izin' ? 'ok-izin' : 'ok-sakit');
  $('result').textContent = `Absen ${j.status} berhasil!\n${j.nama}\nJam ${j.jam} - ${j.tanggal}`;
  $('result').style.display = 'block';
}

function show(type,msg){
  $('result').className = type;
  $('result').textContent = msg;
  $('result').style.display = 'block';
}

let pending = null;
const statusBtn = ['hadir','izin','sakit'];
function ask(status){
  pending = status;
  $('confirmMsg').textContent = `Absen ${status}?`;
  statusBtn.forEach(id => $(id).style.display = 'none');
  $('confirm').style.display = 'block';
  $('result').style.display = 'none';
}
$('hadir').onclick=()=>ask('Hadir');
$('izin').onclick=()=>ask('Izin');
$('sakit').onclick=()=>ask('Sakit');
$('batal').onclick=()=>{
  pending = null;
  $('confirm').style.display = 'none';
  statusBtn.forEach(id => $(id).style.display = '');
};
$('kirim').onclick=()=>{ if(pending) absen(pending); };
// Typewriter sekali: "Welcome to website RestuSec" + garis ketik
function startPage(){
  (function(){
    const el = document.getElementById('typeTitle');
    if(!el) return;
    const full = 'Welcome to website RestuSec';
    let i = 0;
    const typer = setInterval(() => {
      el.innerHTML = full.slice(0, ++i) + '<span class="caret"></span>';
      if (i >= full.length) { clearInterval(typer); setTimeout(() => { el.innerHTML = full; }, 400); }
    }, 95);
  })();
  init();
}

// ── Boot Screen controller (dipindah dari inline HTML karena CSP script-src 'self') ──
// Fase 2 = layout boot yang SAMA: elemen bawah fade → cahaya kedip + garis turun
// → cahaya hilang → brand "RestuSec" tuing muncul. Tanpa overlay kedua.
function phase2(boot){
  boot.classList.add('phase2');
  // cahaya selesai (~1.45s) → baru RestuSec muncul
  setTimeout(() => boot.classList.add('showbrand'), 1450);
}

function finishAll(boot){
  if (!boot.isConnected) return startPage();
  boot.classList.add('done');
  document.body.classList.add('revealed');
  startPage();
  setTimeout(() => boot.remove(), 700);
}

function runBoot(boot){
  // Persentase — mirror timing CSS b-fill
  const stops = [[0,0],[600,18],[1350,47],[2100,72],[2640,90],[3000,100]];
  const pctEl = document.getElementById('pct');
  let t0 = null;
  function tick(ts){
    if(!t0) t0 = ts;
    const e = ts - t0;
    let v = 100;
    for(let i=1; i<stops.length; i++){
      if(e <= stops[i][0]){
        const p = (e - stops[i-1][0]) / (stops[i][0] - stops[i-1][0]);
        v = stops[i-1][1] + (stops[i][1]-stops[i-1][1]) * Math.min(p,1);
        break;
      }
    }
    pctEl.textContent = Math.min(Math.round(v),100) + '%';
    if(v < 100) requestAnimationFrame(tick);
  }
  setTimeout(() => requestAnimationFrame(tick), 2000);

  // Log status boot
  const msgs = [
    [2200, '<span class="ok">&#10003;</span> KERNEL MODULE LOADED'],
    [2900, '<span class="ok">&#10003;</span> DATABASE CONNECTION OK'],
    [3500, '<span class="ok">&#10003;</span> AUTH SERVICE READY'],
    [4200, '<span class="ok">&#10003;</span> QR SERVICE ONLINE'],
    [5000, '<span class="warn">&#9658;</span> LAUNCHING RESTUSEC...']
  ];
  const logEl = document.getElementById('log');
  msgs.forEach(m => setTimeout(() => { logEl.innerHTML = m[1]; }, m[0]));

  // Fase 1 selesai (bar penuh @5s, log terakhir @5s) → langsung fase 2, tanpa jeda
  setTimeout(() => phase2(boot), 5100);
  // Fase 2 tampil ~2.6s → buka halaman absen
  setTimeout(() => finishAll(boot), 7800);
}

// ── Entry point ──
const bootEl = document.getElementById('boot');
if (!bootEl) startPage();
else if (matchMedia('(prefers-reduced-motion: reduce)').matches) finishAll(bootEl);
else runBoot(bootEl);