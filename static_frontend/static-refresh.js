'use strict';
(()=>{
  const script=document.currentScript;
  if(!script) return;
  const apiUrl=script.dataset.apiUrl;
  const cacheKey=script.dataset.cacheKey;
  if(!apiUrl||!cacheKey) return;

  const update=async()=>{
    try{
      const response=await fetch(apiUrl,{headers:{Accept:'application/json'},cache:'no-store',mode:'cors'});
      if(!response.ok) return;
      const data=await response.json();
      if(data.ok&&data.html){
        try{localStorage.setItem(cacheKey,data.html)}catch{}
      }
    }catch{}
  };

  if('requestIdleCallback' in window) requestIdleCallback(update,{timeout:3000});
  else setTimeout(update,1200);
})();
