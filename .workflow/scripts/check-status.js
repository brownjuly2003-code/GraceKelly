const https=require('https'),fs=require('fs'),F='.workflow/status.json';
try{const c=JSON.parse(fs.readFileSync(F,'utf8'));
if(Date.now()-new Date(c.checked_at).getTime()<3e5){
console.log(JSON.stringify(c));process.exit(c.all_ok?0:1)}}catch{}
const get=u=>new Promise(r=>https.get(u,{timeout:5e3},s=>{let d='';
s.on('data',c=>d+=c);s.on('end',()=>{try{r(JSON.parse(d))}catch{r(null)}})}).on('error',()=>r(null)));
(async()=>{
const[aS,oS]=await Promise.all([
get('https://status.anthropic.com/api/v2/status.json'),
get('https://status.openai.com/api/v2/status.json')]);
const aOk=aS?.status?.indicator==='none'||aS?.status?.indicator==='minor';
const oOk=oS?.status?.indicator==='none'||oS?.status?.indicator==='minor';
const r={checked_at:new Date().toISOString(),
anthropic:{ok:aOk,indicator:aS?.status?.indicator||'unknown'},
openai:{ok:oOk,indicator:oS?.status?.indicator||'unknown'},
all_ok:aOk&&oOk};
fs.writeFileSync(F,JSON.stringify(r,null,2));
console.log(JSON.stringify(r));
process.exit(r.all_ok?0:1)})();
