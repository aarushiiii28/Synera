import { describe, expect, it } from 'vitest';
import { filterCities } from '../components/india/CityPicker';

const C = [
  { id: 'delhi', name: 'Delhi', state: 'Delhi' }, { id: 'amritsar', name: 'Amritsar', state: 'Punjab' }, { id: 'agra', name: 'Agra', state: 'Uttar Pradesh' },
  { id: 'chandigarh', name: 'Chandigarh', state: 'Chandigarh' }, { id: 'ludhiana', name: 'Ludhiana', state: 'Punjab' },
];

describe('city dropdown filter', () => {
  it('lists every city A to Z when nothing is typed', () => {
    expect(filterCities(C, '').map((c) => c.name)).toEqual(['Agra', 'Amritsar', 'Chandigarh', 'Delhi', 'Ludhiana']);
  });
  it('narrows to matching cities as you type, case-insensitively', () => {
    expect(filterCities(C, 'Amr').map((c) => c.id)).toEqual(['amritsar']);
    expect(filterCities(C, 'AMR').map((c) => c.id)).toEqual(['amritsar']);
  });
  it('ranks names that start with the text above names that merely contain it, then state matches', () => {
    expect(filterCities(C, 'd').map((c) => c.id)).toEqual(['delhi', 'chandigarh', 'ludhiana', 'agra']);   // starts with d, contains d, only the state (Uttar Pradesh) contains d
    expect(filterCities(C, 'punjab').map((c) => c.id)).toEqual(['amritsar', 'ludhiana']);
  });
  it('returns nothing when nothing matches', () => {
    expect(filterCities(C, 'zzz')).toEqual([]);
  });
});
