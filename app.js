let mode='deposit';
function openModal(m){mode=m;document.getElementById('mtitle').textContent=m==='deposit'?'Recharge / Deposit':'Withdraw';document.getElementById('modal').classList.remove('hidden')}
function closeModal(){document.getElementById('modal').classList.add('hidden')}
function submitRequest(){let a=Number(document.getElementById('amount').value),r=document.getElementById('reference').value.trim();if(!a||a<=0)return toast('Enter a valid demo amount.');if(!r)return toast('Enter a demo reference code.');closeModal();toast((mode==='deposit'?'Deposit':'Withdrawal')+' demo request recorded. Payment gateway is not connected.')}
function selectPlan(n){document.getElementById('selected').textContent=n;toast(n+' selected. Real payment is disabled in this demo.')}
function copyRef(){navigator.clipboard?.writeText(document.getElementById('ref').value).then(()=>toast('Referral link copied.')).catch(()=>toast('Copy unavailable.'))}
function topPage(){scrollTo({top:0,behavior:'smooth'})}
function toast(s){let t=document.getElementById('toast');t.textContent=s;t.style.display='block';clearTimeout(window.tt);window.tt=setTimeout(()=>t.style.display='none',2600)}