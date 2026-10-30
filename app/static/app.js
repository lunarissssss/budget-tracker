const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const EN=document.documentElement.lang==='en';
const rp=n=>(n<0?'-':'')+'Rp '+Math.abs(Math.round(n)).toLocaleString(EN?'en-US':'id-ID');
// format ribuan otomatis di input nominal
$$('.money').forEach(i=>{const f=()=>{const neg=i.value.trim().startsWith('-'),d=i.value.replace(/\D/g,'');i.value=(neg?'-':'')+(d?Number(d).toLocaleString('id-ID'):'')};i.addEventListener('input',f);f()});
// ganti status paid/planned -> tanggal otomatis
$$('input[name=status]').forEach(r=>r.addEventListener('change',()=>{const d=$('input[name=date]');if(d)d.value=r.value==='paid'?d.dataset.today:''}));
// split gajian: hitung sisa langsung
const sp=$('[data-split]');
if(sp){const inc=+sp.dataset.income,calc=()=>{let s=0;$$('input.money',sp).forEach(i=>s+=+i.value.replace(/\D/g,'')||0);$('#moved').textContent=rp(s);$('#left').textContent=rp(inc-s)};sp.addEventListener('input',calc);calc()}
// periode, tema
$('#per')?.addEventListener('change',e=>location.href='/period/'+e.target.value+'?next='+encodeURIComponent(location.pathname+location.search));
$('#theme')?.addEventListener('click',()=>{const d=document.documentElement,c=d.dataset.theme,e=c==='auto'?(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'):c,n=e==='light'?'dark':'light';d.dataset.theme=n;try{localStorage.setItem('theme',n)}catch(_){}});
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
