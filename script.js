// Utility functions
function escapeHtml(s){
  return (s||'').replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
  });
}

// Entry modal handler
function openEntryModal(entry){
  const entryModal = document.getElementById('entry-modal');
  const container = document.getElementById('entry-detail-container');
  
  let mediaHtml = '';
  if(entry.images && entry.images.length > 0){
    const images = Array.isArray(entry.images) ? entry.images : [entry.images];
    mediaHtml += '<div class="entry-detail-media">';
    images.forEach(img => {
      mediaHtml += `<img class="entry-image" src="/uploads/${img}" alt="Entry image" loading="lazy">`;
    });
    mediaHtml += '</div>';
  }
  if(entry.video){
    mediaHtml += `<div class="entry-detail-media"><video class="entry-video-player" controls><source src="/uploads/${entry.video}" type="video/mp4"></video></div>`;
  }
  
  container.innerHTML = `
    <div class="entry-detail-header">
      <h2 class="entry-detail-title">Entrada #${entry.id}</h2>
      <div class="entry-detail-meta">
        <span>ID: ${entry.id}</span>
        ${entry.tags ? `<span>Tags: ${escapeHtml(entry.tags)}</span>` : ''}
        <span>Votos: ${entry.upvotes || 0} up / ${entry.downvotes || 0} down</span>
      </div>
    </div>
    <div class="entry-detail-content">${escapeHtml(entry.content)}</div>
    ${mediaHtml}
    <div class="comments-section" id="comments-${entry.id}">
      <h3 class="comments-title">Comentarios</h3>
      <div class="comment-form">
        <textarea class="comment-input" placeholder="Escribe un comentario..." data-entry-id="${entry.id}"></textarea>
        <button class="comment-submit" data-entry-id="${entry.id}">Publicar comentario</button>
      </div>
      <div class="comments-list" id="comments-list-${entry.id}"></div>
    </div>
  `;
  
  entryModal.classList.add('open');
  loadComments(entry.id);
  
  // Setup comment form handlers
  const commentInput = container.querySelector('.comment-input');
  const submitBtn = container.querySelector('.comment-submit');
  
  submitBtn.addEventListener('click', async function(){
    const text = commentInput.value.trim();
    if(!text) return;
    
    submitBtn.disabled = true;
    try{
      const res = await fetch('/api/comments', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({entry_id: entry.id, content: text})
      });
      if(res.ok){
        commentInput.value = '';
        loadComments(entry.id);
      } else {
        const j = await res.json().catch(()=>({}));
        alert(j.message || 'Error al publicar comentario');
      }
    }catch(e){ 
      console.error('comment post err',e);
      alert('Error de conexión');
    }finally{
      submitBtn.disabled = false;
    }
  });
}

async function loadComments(entryId){
  try{
    const res = await fetch(`/api/comments/${entryId}`);
    if(!res.ok) return;
    const data = await res.json();
    const commentsList = document.getElementById(`comments-list-${entryId}`);
    if(!commentsList) return;
    
    commentsList.innerHTML = '';
    const comments = data.comments || [];
    
    if(comments.length === 0){
      commentsList.innerHTML = '<p style="color: var(--muted); text-align: center; padding: 20px;">Sin comentarios aún</p>';
      return;
    }
    
    comments.forEach(comment => {
      const commentEl = document.createElement('div');
      commentEl.className = 'comment-item';
      commentEl.dataset.commentId = comment.id;
      commentEl.innerHTML = `
        <div class="comment-header">
          <span class="comment-user">Usuario anónimo</span>
          <span class="comment-time">${new Date(comment.ts).toLocaleDateString()}</span>
        </div>
        <div class="comment-body">${escapeHtml(comment.content)}</div>
        <div class="comment-controls">
          <button class="comment-vote-btn" data-vote="1">▲</button>
          <span class="comment-vote-count up">${comment.upvotes || 0}</span>
          <button class="comment-vote-btn" data-vote="-1">▼</button>
          <span class="comment-vote-count down">${comment.downvotes || 0}</span>
          <button class="comment-vote-btn report-comment">🚩</button>
        </div>
      `;
      commentsList.appendChild(commentEl);
      
      const voteBtn1 = commentEl.querySelector('button[data-vote="1"]');
      const voteBtn2 = commentEl.querySelector('button[data-vote="-1"]');
      const reportBtn = commentEl.querySelector('.report-comment');
      
      voteBtn1.addEventListener('click', () => voteComment(comment.id, 1, commentEl));
      voteBtn2.addEventListener('click', () => voteComment(comment.id, -1, commentEl));
      reportBtn.addEventListener('click', () => reportComment(comment.id, entryId, commentEl));
    });
  }catch(e){ 
    console.error('load comments err',e);
  }
}

async function voteComment(commentId, vote, commentEl){
  try{
    const res = await fetch('/api/comment-vote', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({comment_id: commentId, vote})
    });
    if(res.ok){
      const j = await res.json();
      commentEl.querySelector('.comment-vote-count.up').textContent = j.upvotes || 0;
      commentEl.querySelector('.comment-vote-count.down').textContent = j.downvotes || 0;
    }
  }catch(e){ console.error('vote comment err',e); }
}

async function reportComment(commentId, entryId, commentEl){
  const reason = prompt('Motivo del reporte (opcional):');
  if(reason === null) return;
  
  try{
    const res = await fetch('/api/comment-report', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({comment_id: commentId, entry_id: entryId, reason})
    });
    const j = await res.json();
    if(res.ok){
      if(j.deleted){
        commentEl.remove();
        alert('Comentario eliminado por reportes de la comunidad');
      } else {
        alert('Reporte enviado. Gracias.');
      }
    } else {
      alert(j.message || 'Error al reportar');
    }
  }catch(e){
    console.error('report comment err',e);
    alert('Error de conexión');
  }
}

document.addEventListener('DOMContentLoaded', function(){
  // --- Disclaimer Modal ---
  const disclaimerModal = document.getElementById('disclaimer-modal');
  const disclaimerAccept = document.getElementById('disclaimer-accept');
  const disclaimerDontShow = document.getElementById('disclaimer-dontshow');

  // Show disclaimer only when needed (hidden by default to avoid CLS)
  const disclaimerSeen = localStorage.getItem('disclaimer_seen');
  if (!disclaimerSeen) {
    disclaimerModal.classList.add('open');
  }

  if (disclaimerAccept) {
    disclaimerAccept.addEventListener('click', function() {
      if (disclaimerDontShow.checked) {
        localStorage.setItem('disclaimer_seen', 'true');
      }
      disclaimerModal.classList.remove('open');
    });
  }

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
    const imagesInput = document.getElementById('images');
    const videoInput = document.getElementById('video');
    const imagePreview = document.getElementById('image-preview');
    const videoPreview = document.getElementById('video-preview');

    function updateCount(){
      const len = (contentEl.value || '').length;
      charcount.textContent = `${len}/2000`;
    }
    updateCount();
    contentEl.addEventListener('input', updateCount);

    // Handle image preview
    imagesInput.addEventListener('change', function(){
      imagePreview.innerHTML = '';
      const files = Array.from(this.files).slice(0, 3); // max 3 images
      files.forEach((file, idx) => {
        const reader = new FileReader();
        reader.onload = function(e){
          const div = document.createElement('div');
          div.className = 'preview-item';
          div.innerHTML = `<img class="preview-image" src="${e.target.result}" alt="Preview">
            <button class="preview-remove" type="button" data-index="${idx}">×</button>`;
          imagePreview.appendChild(div);
        };
        reader.readAsDataURL(file);
      });
      if(files.length < this.files.length){
        const warn = document.createElement('small');
        warn.className = 'muted';
        warn.textContent = `(Se mostrarán solo las primeras 3 imágenes)`;
        imagePreview.appendChild(warn);
      }
    });

    // Handle video preview
    videoInput.addEventListener('change', function(){
      videoPreview.innerHTML = '';
      if(this.files.length > 0){
        const file = this.files[0];
        const div = document.createElement('div');
        div.className = 'preview-item';
        const url = URL.createObjectURL(file);
        div.innerHTML = `<video class="preview-video" src="${url}"></video>
          <button class="preview-remove" type="button" data-index="0">×</button>`;
        videoPreview.appendChild(div);
      }
    });

    // Remove preview items
    imagePreview.addEventListener('click', function(e){
      if(e.target.classList.contains('preview-remove')){
        e.preventDefault();
        const dt = new DataTransfer();
        const files = Array.from(imagesInput.files);
        const idx = parseInt(e.target.dataset.index);
        files.splice(idx, 1);
        files.forEach(f => dt.items.add(f));
        imagesInput.files = dt.files;
        imagesInput.dispatchEvent(new Event('change', {bubbles: true}));
      }
    });

    videoPreview.addEventListener('click', function(e){
      if(e.target.classList.contains('preview-remove')){
        e.preventDefault();
        videoInput.value = '';
        videoInput.dispatchEvent(new Event('change', {bubbles: true}));
      }
    });

    clearBtn.addEventListener('click', function(){ 
      form.reset(); 
      updateCount(); 
      status.textContent = '';
      imagePreview.innerHTML = '';
      videoPreview.innerHTML = '';
    });

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
        const formData = new FormData();
        formData.append('content', content);
        formData.append('tags', tagsRaw);
        
        // Add images
        const imageFiles = Array.from(imagesInput.files).slice(0, 3);
        imageFiles.forEach(file => {
          formData.append('images', file);
        });
        
        // Add video
        if(videoInput.files.length > 0){
          formData.append('video', videoInput.files[0]);
        }
        
        const resp = await fetch('/api/submit', {
          method: 'POST',
          body: formData
        });
        if(resp.ok){
          status.textContent = 'Publicado (anónimo). Gracias.';
          form.reset();
          updateCount();
          imagePreview.innerHTML = '';
          videoPreview.innerHTML = '';
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
    // Also store in localStorage for better persistence
    localStorage.setItem(name, value);
  }
  function getCookie(name){
    // Try localStorage first (more reliable)
    const stored = localStorage.getItem(name);
    if(stored) return stored;
    // Fallback to document.cookie
    const v = document.cookie.match('(^|;)\\s*'+name+'\\s*=\\s*([^;]+)');
    return v ? v.pop() : '';
  }

  const consentBanner = document.getElementById('consent-banner');
  const consentAccept = document.getElementById('consent-accept');
  const consentDecline = document.getElementById('consent-decline');
  function showConsent(){ if(consentBanner) consentBanner.style.display='block'; }
  function hideConsent(){ if(consentBanner) consentBanner.style.display='none'; }
  
  // Check if user has already given consent
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
  if(consentDecline){ 
    consentDecline.addEventListener('click', function(){
      // Mark that user declined consent (don't ask again)
      localStorage.setItem('consent_declined', 'true');
      hideConsent();
    });
  }

  // --- Entries rendering, voting and reporting ---
  const entriesList = document.getElementById('entries-list');

  async function fetchEntries(){
    try{
      if(entriesList) entriesList.classList.add('loading');
      const resp = await fetch('/api/entries?limit=50');
      if(!resp.ok){ if(entriesList) entriesList.classList.remove('loading'); return; }
      const data = await resp.json();
      renderEntries(data.entries || []);
    }catch(e){ console.error('fetchEntries',e); if(entriesList) entriesList.classList.remove('loading'); }
  }

  function makeEntryNode(entry){
    const div = document.createElement('div');
    div.className = 'entry-card card';
    div.dataset.entryId = entry.id;
    const content = document.createElement('div');
    content.className = 'entry-content';
    
    // Build media HTML if present
    let mediaHtml = '';
    if(entry.images && entry.images.length > 0){
      const images = Array.isArray(entry.images) ? entry.images : [entry.images];
      mediaHtml += '<div class="entry-media">';
      images.forEach(img => {
        mediaHtml += `<img class="entry-image" src="/uploads/${img}" alt="Entry image" loading="lazy">`;
      });
      mediaHtml += '</div>';
    }
    if(entry.video){
      mediaHtml += `<video class="entry-video-player" controls><source src="/uploads/${entry.video}" type="video/mp4"></video>`;
    }
    
    content.innerHTML = `<div class="entry-title">Entrada #${entry.id}</div><div class="entry-body">${escapeHtml(entry.content).slice(0,400)}</div>${mediaHtml}`;
    const controls = document.createElement('div');
    controls.className = 'entry-controls';
    controls.innerHTML = `
      <button class="btn-vote" data-vote="1">▲</button>
      <span class="count up">${entry.upvotes||0}</span>
      <button class="btn-vote" data-vote="-1">▼</button>
      <span class="count down">${entry.downvotes||0}</span>
      <button class="btn-report">Reportar</button>
      <button class="btn-view-full">Ver entrada</button>
    `;
    div.appendChild(content);
    div.appendChild(controls);
    return div;
  }

  function renderEntries(entries){
    if(!entriesList) return;
    entriesList.classList.remove('loading');
    entriesList.innerHTML = '';
    if((entries||[]).length === 0){
      entriesList.innerHTML = '<p style="color: var(--muted); text-align: center; padding: 20px;">No hay publicaciones aún</p>';
      return;
    }
    entries.forEach(e=>{
      const node = makeEntryNode(e);
      entriesList.appendChild(node);
      // fetch vote counts for each entry
      fetch(`/api/entries?limit=1`).catch(()=>{}); // noop placeholder
    });
  }

  // Event delegation for votes and reports
  document.addEventListener('click', async function(ev){
    // View full entry
    const viewBtn = ev.target.closest && ev.target.closest('.btn-view-full');
    if(viewBtn){
      const card = viewBtn.closest('.entry-card');
      const entryId = card && card.dataset.entryId;
      if(!entryId) return;
      try{
        const res = await fetch(`/api/entries?limit=100`);
        const j = await res.json();
        const entry = j.entries && j.entries.find(e => parseInt(e.id) === parseInt(entryId));
        if(entry){
          openEntryModal(entry);
        }
      }catch(e){ console.error('view entry err',e); }
      return;
    }
    
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

  // Image lightbox modal
  const modal = document.getElementById('image-modal');
  const modalImage = document.getElementById('modal-image');
  const modalClose = document.querySelector('.modal-close');
  
  if(modal && modalClose){
    // Open image in modal
    document.addEventListener('click', function(e){
      const img = e.target.closest && e.target.closest('.entry-image');
      if(img){
        modalImage.src = img.src;
        modal.classList.add('open');
      }
    });
    
    // Close modal
    modalClose.addEventListener('click', function(){
      modal.classList.remove('open');
    });
    
    modal.addEventListener('click', function(e){
      if(e.target === modal){
        modal.classList.remove('open');
      }
    });
    
    // Close on escape
    document.addEventListener('keydown', function(e){
      if(e.key === 'Escape' && modal.classList.contains('open')){
        modal.classList.remove('open');
      }
    });
  }

  // Setup entry modal close handlers
  const entryModal = document.getElementById('entry-modal');
  if(entryModal){
    const closeBtns = entryModal.querySelectorAll('.modal-close');
    closeBtns.forEach(btn => {
      btn.addEventListener('click', function(){
        entryModal.classList.remove('open');
      });
    });
    
    entryModal.addEventListener('click', function(e){
      if(e.target === entryModal){
        entryModal.classList.remove('open');
      }
    });
    
    document.addEventListener('keydown', function(e){
      if(e.key === 'Escape' && entryModal.classList.contains('open')){
        entryModal.classList.remove('open');
      }
    });
  }
});
async function loadComments(entryId){
  try{
    const res = await fetch(`/api/comments/${entryId}`);
    if(!res.ok) return;
    const data = await res.json();
    const commentsList = document.getElementById(`comments-list-${entryId}`);
    if(!commentsList) return;
    
    commentsList.innerHTML = '';
    const comments = data.comments || [];
    
    if(comments.length === 0){
      commentsList.innerHTML = '<p style="color: var(--muted); text-align: center; padding: 20px;">Sin comentarios aún</p>';
      return;
    }
    
    comments.forEach(comment => {
      const commentEl = document.createElement('div');
      commentEl.className = 'comment-item';
      commentEl.dataset.commentId = comment.id;
      commentEl.innerHTML = `
        <div class="comment-header">
          <span class="comment-user">Usuario anónimo</span>
          <span class="comment-time">${new Date(comment.ts).toLocaleDateString()}</span>
        </div>
        <div class="comment-body">${escapeHtml(comment.content)}</div>
        <div class="comment-controls">
          <button class="comment-vote-btn" data-vote="1">▲</button>
          <span class="comment-vote-count up">${comment.upvotes || 0}</span>
          <button class="comment-vote-btn" data-vote="-1">▼</button>
          <span class="comment-vote-count down">${comment.downvotes || 0}</span>
          <button class="comment-vote-btn report-comment">🚩</button>
        </div>
      `;
      commentsList.appendChild(commentEl);
      
      // Add vote handlers
      const voteBtn1 = commentEl.querySelector('button[data-vote="1"]');
      const voteBtn2 = commentEl.querySelector('button[data-vote="-1"]');
      const reportBtn = commentEl.querySelector('.report-comment');
      
      voteBtn1.addEventListener('click', () => voteComment(comment.id, 1, commentEl));
      voteBtn2.addEventListener('click', () => voteComment(comment.id, -1, commentEl));
      reportBtn.addEventListener('click', () => reportComment(comment.id, entryId, commentEl));
    });
  }catch(e){ 
    console.error('load comments err',e);
  }
}

async function voteComment(commentId, vote, commentEl){
  try{
    const res = await fetch('/api/comment-vote', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({comment_id: commentId, vote})
    });
    if(res.ok){
      const j = await res.json();
      commentEl.querySelector('.comment-vote-count.up').textContent = j.upvotes || 0;
      commentEl.querySelector('.comment-vote-count.down').textContent = j.downvotes || 0;
    }
  }catch(e){ console.error('vote comment err',e); }
}

async function reportComment(commentId, entryId, commentEl){
  const reason = prompt('Motivo del reporte (opcional):');
  if(reason === null) return;
  
  try{
    const res = await fetch('/api/comment-report', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({comment_id: commentId, entry_id: entryId, reason})
    });
    const j = await res.json();
    if(res.ok){
      if(j.deleted){
        commentEl.remove();
        alert('Comentario eliminado por reportes de la comunidad');
      } else {
        alert('Reporte enviado. Gracias.');
      }
    } else {
      alert(j.message || 'Error al reportar');
    }
  }catch(e){
    console.error('report comment err',e);
    alert('Error de conexión');
  }
}

// Setup entry modal close handlers
const entryModal = document.getElementById('entry-modal');
if(entryModal){
  const closeBtns = entryModal.querySelectorAll('.modal-close');
  closeBtns.forEach(btn => {
    btn.addEventListener('click', function(){
      entryModal.classList.remove('open');
    });
  });
  
  entryModal.addEventListener('click', function(e){
    if(e.target === entryModal){
      entryModal.classList.remove('open');
    }
  });
  
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && entryModal.classList.contains('open')){
      entryModal.classList.remove('open');
    }
  });
}
