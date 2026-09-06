export const number=(value:number|null)=>value===null?"Niet beschikbaar":new Intl.NumberFormat("nl-NL").format(value);
export const percent=(value:string|null)=>value===null?"Niet beschikbaar":`${new Intl.NumberFormat("nl-NL",{maximumFractionDigits:1}).format(Number(value))}%`;

export const municipalityDisplayName = (name: string) => name.endsWith(" (gemeente)") ? name.slice(0, -11) : name;
