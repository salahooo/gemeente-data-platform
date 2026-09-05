export function annualChanges<T extends {year: number; population_january_1: number | null}>(data: T[]) {
  return [...data].sort((a, b) => a.year - b.year).map((item) => {
    const previous = data.find((candidate) => candidate.year === item.year - 1);
    return {...item, change: item.population_january_1 !== null && previous?.population_january_1 != null
      ? item.population_january_1 - previous.population_january_1 : null};
  });
}
