'use strict';
const $ = (s,root=document)=>root.querySelector(s);
const $$ = (s,root=document)=>[...root.querySelectorAll(s)];
const toast = message=>{const box=$('#toast');if(!box)return;box.textContent=message;box.hidden=false;setTimeout(()=>box.hidden=true,4000)};
const mobileMenu=$('[data-toggle-menu]');
mobileMenu?.addEventListener('click',()=>{const nav=$('#mobile-nav');const open=nav.hidden;nav.hidden=!open;mobileMenu.setAttribute('aria-expanded',String(open))});
$$('#mobile-nav a').forEach(a=>a.addEventListener('click',()=>{$('#mobile-nav').hidden=true;mobileMenu.setAttribute('aria-expanded','false')}));
const panelButton=$('[data-panel-menu]');
panelButton?.addEventListener('click',()=>{const open=$('#panel-sidebar').classList.toggle('open');panelButton.setAttribute('aria-expanded',String(open))});
document.addEventListener('click',e=>{const sidebar=$('#panel-sidebar');if(sidebar?.classList.contains('open')&&!sidebar.contains(e.target)&&!panelButton.contains(e.target)){sidebar.classList.remove('open');panelButton.setAttribute('aria-expanded','false')}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('#panel-sidebar')?.classList.remove('open');panelButton?.setAttribute('aria-expanded','false');if(mobileMenu){$('#mobile-nav').hidden=true;mobileMenu.setAttribute('aria-expanded','false')}}});
$$('[data-date-picker]').forEach(button=>button.addEventListener('click',()=>{const input=document.getElementById(button.dataset.datePicker);try{input.showPicker()}catch{input.focus();input.click()}}));
const slides=$$('[data-slide]');let slide=0;
function showSlide(index){if(!slides.length)return;slide=(index+slides.length)%slides.length;slides.forEach((s,i)=>s.hidden=i!==slide);const count=$('[data-carousel-counter]');if(count)count.textContent=String(slide+1).padStart(2,'0')+' / '+String(slides.length).padStart(2,'0')}
$('[data-slide-next]')?.addEventListener('click',()=>showSlide(slide+1));
$('[data-slide-prev]')?.addEventListener('click',()=>showSlide(slide-1));
$$('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{const input=$(button.dataset.copy);try{await navigator.clipboard.writeText(input.value);toast('Pix copiado. Confira o valor e o recebedor no seu banco.')}catch{input.focus();input.select();toast('Selecione e copie o código Pix.')}}));
const checkout=$('[data-checkout]');if(checkout){const qty=$('[name=quantity]',checkout);const price=Number(checkout.dataset.price.replace(',','.'));const update=()=>{const value=price*Math.max(0,Number(qty.value)||0);$('#checkout-total').textContent=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(value)};qty.addEventListener('input',update);update()}
let activeForm=null;const confirmation=$('#confirm-dialog');
$$('form[data-confirm]').forEach(form=>form.addEventListener('submit',e=>{if(form.dataset.confirmed==='yes')return;e.preventDefault();activeForm=form;$('#confirm-message').textContent=form.dataset.confirm;confirmation.showModal()}));
$('[data-close-dialog]')?.addEventListener('click',()=>{confirmation.close();activeForm=null});
$('#confirm-action')?.addEventListener('click',()=>{if(!activeForm)return;const form=activeForm;activeForm=null;confirmation.close();form.dataset.confirmed='yes';form.requestSubmit()});
$$('[data-height]').forEach(bar=>bar.style.height=Math.max(1,Math.min(100,Number(bar.dataset.height)||0))+'%');
$$('input[type=file][accept*="image"]').forEach(input=>input.addEventListener('change',()=>{const field=input.closest('.field');field?.querySelectorAll('.upload-preview').forEach(x=>{URL.revokeObjectURL(x.src);x.remove()});const files=[...input.files].slice(0,3);for(const file of files){if(!['image/jpeg','image/png','image/webp'].includes(file.type))continue;const img=document.createElement('img');img.className='upload-preview';img.alt='Prévia da imagem selecionada';img.src=URL.createObjectURL(file);field?.append(img)}}));
const dateField=$('#id_event_date');if(dateField&&!dateField.value){const date=new URLSearchParams(location.search).get('dia');if(date&&/^\d{4}-\d{2}-\d{2}$/.test(date))dateField.value=date}

$$('form[data-single-submit]').forEach(form=>form.addEventListener('submit',()=>{
  if(form.dataset.submitting==='yes')return;
  form.dataset.submitting='yes';
  const button=$('button[type="submit"],button:not([type])',form);
  if(button){
    button.disabled=true;
    button.setAttribute('aria-busy','true');
    button.dataset.originalText=button.textContent;
    button.textContent='Entrando...';
  }
}));
