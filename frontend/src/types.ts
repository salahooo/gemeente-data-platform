export type Year={year:number;has_average_population:boolean};
export type National={year:number;municipality_count:number;population_january_1:number|null;average_population:string|null;missing_average_population_count:number};
export type Ranking={rank:number;municipality_code:string;municipality_name:string;population_january_1:number};
export type Municipality={municipality_code:string;municipality_name:string};
export type Observation={year:number;population_january_1:number;average_population:string|null;population_change_absolute:number|null;population_change_percent:string|null};
export type Lineage={processed_run_id:string;pipeline_run_id:string|null;completed_at:string};
export type AgeProfileData = {municipality_code: string; year: number; dataset_code: "70072ned"; categories: {category: string; population: number | null; share_percent: string | null; national_share_percent: string | null}[]};
export type DataQuality = {dataset_code: string; dataset_name: string; source: string; first_year: number | null; last_year: number | null; completed_at: string | null; record_count: number; validation_status: "validated" | "unavailable"; missing_values: number; warning: string};
