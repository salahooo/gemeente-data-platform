export const number=(value:number|null)=>value===null?"Niet beschikbaar":new Intl.NumberFormat("nl-NL").format(value);
export const percent=(value:string|null)=>value===null?"Niet beschikbaar":`${new Intl.NumberFormat("nl-NL",{maximumFractionDigits:1}).format(Number(value))}%`;
