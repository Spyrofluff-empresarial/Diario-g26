// Simple accessible menu toggle for small screens
document.addEventListener('DOMContentLoaded', function(){
  const toggle = document.querySelector('.nav-toggle');
  const menu = document.getElementById('main-nav');
  if(!toggle || !menu) return;

  toggle.addEventListener('click', function(){
    const expanded = this.getAttribute('aria-expanded') === 'true';
    this.setAttribute('aria-expanded', String(!expanded));
    menu.classList.toggle('open');
    menu.setAttribute('aria-hidden', String(expanded));
  });

  // Close menu when clicking a link
  menu.addEventListener('click', function(e){
    if(e.target.tagName === 'A'){
      menu.classList.remove('open');
      toggle.setAttribute('aria-expanded','false');
      menu.setAttribute('aria-hidden','true');
    }
  });

  // Close on escape key
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape'){
      if(menu.classList.contains('open')){
        menu.classList.remove('open');
        toggle.setAttribute('aria-expanded','false');
        menu.setAttribute('aria-hidden','true');
        toggle.focus();
      }
    }
  });

  // Publish form handling (anonymous)
  const form = document.getElementById('publish-form');
  if(form){
    const btn = document.getElementById('publish-btn');
    const clearBtn = document.getElementById('publish-clear');
    const status = document.getElementById('publish-status');
    const contentEl = document.getElementById('content');
    const charcount = document.getElementById('charcount');

    function updateCount(){
      const len = (contentEl.value || '').length;
      charcount.textContent = `${len}/2000`;
    }
    updateCount();
    contentEl.addEventListener('input', updateCount);

    clearBtn.addEventListener('click', function(){ form.reset(); updateCount(); status.textContent = ''; });

    form.addEventListener('submit', async function(e){
      e.preventDefault();
      status.textContent = '';
      const content = (contentEl.value || '').trim();
      const tagsRaw = (document.getElementById('tags').value || '').trim();
      if(!content){
        status.textContent = 'Escribe algo antes de publicar.';
        return;
      }
      if(content.length > 2000){
        status.textContent = 'El texto es demasiado largo.';
        return;
      }
      btn.disabled = true; clearBtn.disabled = true;
      status.textContent = 'Enviando…';
      try{
        const resp = await fetch('/api/submit', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({content, tags: tagsRaw})
        });
        if(resp.ok){
          status.textContent = 'Publicado (anónimo). Gracias.';
          form.reset();
          updateCount();
        } else {
          const j = await resp.json().catch(()=>({message:'Error'}));
          status.textContent = j.message || 'Error al publicar.';
        }
      }catch(err){
        status.textContent = 'Fallo de red al publicar.';
      }finally{btn.disabled = false; clearBtn.disabled = false;}
    });
  }

  // --- Cookie consent & per-device identifier ---
  function setCookie(name, value, days){
    const maxAge = days ? days*24*60*60 : 10*365*24*60*60; // default 10 years
    document.cookie = `${name}=${value}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
  }
  function getCookie(name){
    const v = document.cookie.match('(^|;)\\s*'+name+'\\s*=\\s*([^;]+)');
    return v ? v.pop() : '';
  }

  const consentBanner = document.getElementById('consent-banner');
  const consentAccept = document.getElementById('consent-accept');
  const consentDecline = document.getElementById('consent-decline');
  function showConsent(){ if(consentBanner) consentBanner.style.display='block'; }
  function hideConsent(){ if(consentBanner) consentBanner.style.display='none'; }
  if(!getCookie('user_id')){
    showConsent();
  }
  if(consentAccept){
    consentAccept.addEventListener('click', function(){
      const id = (crypto && crypto.randomUUID) ? crypto.randomUUID() : ('u'+Date.now()+'-'+Math.random().toString(36).slice(2,9));
      setCookie('user_id', id, 3650);
      hideConsent();
    });
  }
  if(consentDecline){ consentDecline.addEventListener('click', hideConsent); }

  // --- Entries rendering, voting and reporting ---
  const entriesList = document.getElementById('entries-list');

  async function fetchEntries(){
    try{
      const resp = await fetch('/api/entries?limit=50');
      if(!resp.ok) return;
      const data = await resp.json();
      renderEntries(data.entries || []);
    }catch(e){ console.error('fetchEntries',e); }
  }

  function makeEntryNode(entry){
    const div = document.createElement('div');
    div.className = 'entry-card card';
    div.dataset.entryId = entry.id;
    const content = document.createElement('div');
    content.className = 'entry-content';
    content.innerHTML = `<div class="entry-title">Entrada #${entry.id}</div><div class="entry-body">${escapeHtml(entry.content).slice(0,400)}</div>`;
    const controls = document.createElement('div');
    controls.className = 'entry-controls';
    controls.innerHTML = `
      <button class="btn-vote" data-vote="1">▲</button>
      <span class="count up">${entry.upvotes||0}</span>
      <button class="btn-vote" data-vote="-1">▼</button>
      <span class="count down">${entry.downvotes||0}</span>
      <button class="btn-report">Reportar</button>
      <a class="entry-link small" href="entrada${entry.id}.html">Ver entrada</a>
    `;
    div.appendChild(content);
    div.appendChild(controls);
    return div;
  }

  function escapeHtml(s){ return (s||'').replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

  function renderEntries(entries){
    if(!entriesList) return;
    entriesList.innerHTML = '';
    entries.forEach(e=>{
      const node = makeEntryNode(e);
      entriesList.appendChild(node);
      // fetch vote counts for each entry
      fetch(`/api/entries?limit=1`).catch(()=>{}); // noop placeholder
    });
  }

  // Event delegation for votes and reports
  document.addEventListener('click', async function(ev){
    const b = ev.target.closest && ev.target.closest('.btn-vote');
    if(b){
      const vote = parseInt(b.dataset.vote || '0');
      const card = b.closest('.entry-card');
      const entryId = card && card.dataset.entryId;
      if(!entryId) return;
      try{
        const res = await fetch('/api/vote', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({entry_id: entryId, vote})});
        const j = await res.json().catch(()=>({}));
        if(res.ok){
          const up = j.upvotes||0; const down = j.downvotes||0;
          card.querySelector('.count.up').textContent = up;
          card.querySelector('.count.down').textContent = down;
        } else {
          alert(j.message||'Error al votar');
        }
      }catch(e){ console.error('vote err',e); }
    }
    const rp = ev.target.closest && ev.target.closest('.btn-report');
    if(rp){
      const card = rp.closest('.entry-card');
      const entryId = card && card.dataset.entryId;
      if(!entryId) return;
      const reason = prompt('Motivo del reporte (opcional):');
      if(reason === null) return; // cancelled
      try{
        const res = await fetch('/api/report', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({entry_id: entryId, reason})});
        const j = await res.json().catch(()=>({}));
        if(res.ok){
          if(j.archived){
            // remove card
            card.remove();
            alert('La entrada ha sido archivada por la comunidad.');
          } else {
            alert('Reporte enviado. Gracias.');
          }
        } else {
          alert(j.message||'Error al reportar');
        }
      }catch(e){ console.error('report err',e); }
    }
  });

  // initial load
  fetchEntries();
});