let balance=0, rewards=0, refcount=0;
const history=[];
function login(){
 const name=document.getElementById("name").value.trim();
 if(!name){alert("ስም ያስገቡ");return;}
 document.getElementById("auth").hidden=true;
 document.getElementById("dashboard").hidden=false;
 document.getElementById("welcome").textContent="ሰላም "+name+" 👋";
 document.getElementById("refLink").textContent=location.href+"?ref="+encodeURIComponent(name);
 renderPackages(); render();
}
function renderPackages(){
 let html="";
 for(let a=500;a<=50000;a+=500){
   const demoReward=a*0.20;
   html+=`<div class="pkg"><b>${a.toLocaleString()} ETB</b><small>Demo reward display: ${demoReward.toLocaleString()} ETB</small><button onclick="depositDemo(${a})">Demo Deposit</button></div>`;
 }
 document.getElementById("packages").innerHTML=html;
}
function depositDemo(a){
 balance+=a; rewards+=a*.20;
 history.unshift({type:"Demo Deposit",amount:a});
 render(); msg("Demo deposit "+a.toLocaleString()+" ETB ተጨምሯል።");
}
function withdrawDemo(){
 const a=Number(document.getElementById("withdrawAmount").value);
 if(a<200){alert("Minimum withdrawal is 200 ETB");return;}
 const fee=a*.10,total=a+fee;
 if(total>balance){alert("Insufficient demo balance");return;}
 balance-=total; history.unshift({type:"Demo Withdrawal",amount:-a,fee});
 render(); msg("Demo withdrawal "+a.toLocaleString()+" ETB · fee "+fee.toLocaleString()+" ETB");
}
function render(){
 document.getElementById("balance").textContent=balance.toLocaleString(undefined,{maximumFractionDigits:2})+" ETB";
 document.getElementById("rewards").textContent=rewards.toLocaleString(undefined,{maximumFractionDigits:2})+" ETB";
 document.getElementById("refcount").textContent=refcount;
 document.getElementById("history").innerHTML=history.length?history.map(x=>`<div class="item"><span>${x.type}</span><b>${Math.abs(x.amount).toLocaleString()} ETB</b></div>`).join(""):"ምንም ግብይት የለም።";
}
function msg(t){document.getElementById("message").textContent=t}
async function copyRef(){try{await navigator.clipboard.writeText(document.getElementById("refLink").textContent);msg("Referral link copied.");}catch(e){msg("Link: "+document.getElementById("refLink").textContent)}}
