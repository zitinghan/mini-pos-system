export const money=(sen:number)=>`RM ${(sen/100).toFixed(2)}`;
export function parseSen(value:string):number|null {if(!/^\d+(\.\d{0,2})?$/.test(value))return null;const [whole,fraction='']=value.split('.');const sen=Number(whole)*100+Number(fraction.padEnd(2,'0'));return Number.isSafeInteger(sen)?sen:null;}
export const localTime=(value:string)=>new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Kuala_Lumpur',hour12:false});
export const elapsed=(value:string|null)=>value?`${Math.max(0,Math.floor((Date.now()-Date.parse(value))/60000))} 分钟`:'尚未开桌';
export const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kuala_Lumpur',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
