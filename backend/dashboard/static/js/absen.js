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
    $('loc').textContent=`📍 ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
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
  const emoji = {Hadir:'✅',Izin:'📋',Sakit:'🏥'}[j.status];
  $('result').className = 'ok ' + (j.status === 'Hadir' ? 'ok-hadir' : j.status === 'Izin' ? 'ok-izin' : 'ok-sakit');
  $('result').textContent = `${emoji} Absen ${j.status} berhasil!\n${j.nama}\nJam ${j.jam} - ${j.tanggal}`;
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
  const emoji = {Hadir:'✅',Izin:'📋',Sakit:'🏥'}[status];
  $('confirmMsg').textContent = `Absen ${emoji} ${status}?`;
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