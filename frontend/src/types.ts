export type Year={year:number;has_average_population:boolean};
export type National={year:number;municipality_count:number;population_january_1:number|null;average_population:string|null;missing_average_population_count:number};
export type Ranking={rank:number;municipality_code:string;municipality_name:string;population_january_1:number};
export type Municipality={municipality_code:string;municipality_name:string};
export type Observation={year:number;population_january_1:number;average_population:string|null;population_change_absolute:number|null;population_change_percent:string|null};
