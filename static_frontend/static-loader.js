'use strict';

const BACKEND='https://resenha-morumbi.onrender.com';

function cacheDescriptor(){
  const page=document.body.dataset.page||'home';
  const current=new URL(location.href);
  const api=new URL(BACKEND+'/api/public/render.json');
  api.searchParams.set('page',page);

  if(page==='home'){
    const category=current.searchParams.get('categoria');
    if(category) api.searchParams.set('categoria',category);
  }else if(page==='agenda'){
    for(const key of ['ano','mes','categoria']){
      const value=current.searchParams.get(key);
      if(value) api.searchParams.set(key,value);
    }
  }else if(page==='event'){
    const id=current.searchParams.get('id');
    if(id) api.searchParams.set('id',id);
  }

  return {
    page,
    apiUrl:api.toString(),
    cacheKey:'resenha-static:'+page+':'+current.searchParams.toString()
  };
}

function rewriteHref(raw){
  if(!raw) return raw;
  if(raw.startsWith('#')||raw.startsWith('mailto:')||raw.startsWith('tel:')||raw.startsWith('javascript:')) return raw;
  if(/^https?:\/\//i.test(raw)) return raw;

  const u=new URL(raw,'https://static.local');
  const path=u.pathname;
  const suffix=u.search+u.hash;

  if(path==='/') return '/'+suffix;
  if(path==='/agenda/') return '/agenda.html'+suffix;

  const eventMatch=path.match(/^\/evento\/([0-9a-f-]{36})\/$/i);
  if(eventMatch) return '/evento.html?id='+encodeURIComponent(eventMatch[1])+u.hash;

  if(path.startsWith('/static/')) return path.slice('/static'.length)+suffix;
  if(path.startsWith('/media/')) return BACKEND+path+suffix;

  return '/wake.html?to='+encodeURIComponent(path+u.search+u.hash);
}

function rewriteAsset(raw){
  if(!raw) return raw;
  if(/^https?:\/\//i.test(raw)||raw.startsWith('data:')||raw.startsWith('blob:')) return raw;
  if(raw.startsWith('/static/')) return raw.slice('/static'.length);
  if(raw.startsWith('/media/')) return BACKEND+raw;
  return raw;
}

function transformHtml(html,descriptor){
  const doc=new DOMParser().parseFromString(html,'text/html');

  doc.querySelectorAll('a[href]').forEach(el=>el.setAttribute('href',rewriteHref(el.getAttribute('href'))));
  doc.querySelectorAll('form[action]').forEach(el=>{
    const raw=el.getAttribute('action');
    if(raw&&raw.startsWith('/')) el.setAttribute('action',BACKEND+raw);
  });

  doc.querySelectorAll('img[src],script[src],source[src]').forEach(el=>el.setAttribute('src',rewriteAsset(el.getAttribute('src'))));
  doc.querySelectorAll('link[href]').forEach(el=>el.setAttribute('href',rewriteAsset(el.getAttribute('href'))));
  doc.querySelectorAll('source[srcset]').forEach(el=>{
    const value=el.getAttribute('srcset');
    if(value) el.setAttribute('srcset',value.split(',').map(part=>{
      const bits=part.trim().split(/\s+/);
      bits[0]=rewriteAsset(bits[0]);
      return bits.join(' ');
    }).join(', '));
  });

  const canonical=doc.querySelector('link[rel="canonical"]');
  if(canonical) canonical.setAttribute('href',location.href.split('#')[0]);
  const ogUrl=doc.querySelector('meta[property="og:url"]');
  if(ogUrl) ogUrl.setAttribute('content',location.href.split('#')[0]);

  const marker=doc.createElement('meta');
  marker.setAttribute('name','resenha-static-frontend');
  marker.setAttribute('content','1');
  doc.head.appendChild(marker);

  const refresh=doc.createElement('script');
  refresh.src='/static-refresh.js';
  refresh.defer=true;
  refresh.dataset.apiUrl=descriptor.apiUrl;
  refresh.dataset.cacheKey=descriptor.cacheKey;
  doc.body.appendChild(refresh);

  return '<!doctype html>\n'+doc.documentElement.outerHTML;
}

function showError(message){
  const status=document.querySelector('[data-bridge-status]');
  if(status) status.textContent=message;
  const retry=document.querySelector('[data-bridge-retry]');
  if(retry) retry.hidden=false;
}

async function fetchFresh(descriptor){
  let lastError;
  for(let attempt=0;attempt<32;attempt++){
    try{
      const response=await fetch(descriptor.apiUrl,{headers:{Accept:'application/json'},cache:'no-store',mode:'cors'});
      if(response.ok){
        const data=await response.json();
        if(data.ok&&data.html) return data.html;
      }
      lastError=new Error('HTTP '+response.status);
    }catch(error){
      lastError=error;
    }
    const status=document.querySelector('[data-bridge-status]');
    if(status){
      status.textContent=attempt<3
        ? 'Carregando a agenda e os ingressos...'
        : 'O sistema de eventos está iniciando. O site continua online.';
    }
    await new Promise(resolve=>setTimeout(resolve,2200));
  }
  throw lastError||new Error('Falha ao carregar');
}

async function start(){
  const descriptor=cacheDescriptor();
  const retry=document.querySelector('[data-bridge-retry]');
  if(retry) retry.addEventListener('click',()=>location.reload());

  const cached=localStorage.getItem(descriptor.cacheKey);
  if(cached){
    document.open();
    document.write(transformHtml(cached,descriptor));
    document.close();
    return;
  }

  try{
    const html=await fetchFresh(descriptor);
    try{localStorage.setItem(descriptor.cacheKey,html)}catch{}
    document.open();
    document.write(transformHtml(html,descriptor));
    document.close();
  }catch{
    showError('Não foi possível atualizar os eventos agora. Tente novamente em instantes.');
  }
}

start();
