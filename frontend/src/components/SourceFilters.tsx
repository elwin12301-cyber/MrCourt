import { ACT_LABEL, type SourceFilterValues, TYPE_LABEL, useFilterOptions } from '../services/knowledge';

/** Filters by document details (feature 008). Options come only from documents this person may see. */
export function SourceFilters({
  value,
  onChange,
  idPrefix,
}: {
  value: SourceFilterValues;
  onChange: (next: SourceFilterValues) => void;
  idPrefix: string;
}) {
  const options = useFilterOptions().data;
  const set = (key: keyof SourceFilterValues, v: string) => onChange({ ...value, [key]: v || undefined });
  const any = Object.values(value).some(Boolean);
  return (
    <fieldset className="filters" aria-label="Filter sources by details">
      <legend className="sr-only">Filter sources by details</legend>
      <label className="field" htmlFor={`${idPrefix}-type`}>
        Type
        <select id={`${idPrefix}-type`} value={value.type ?? ''} onChange={(e) => set('type', e.target.value)}>
          <option value="">Any</option>
          {(options?.types ?? []).map((t) => (
            <option key={t} value={t}>
              {TYPE_LABEL[t] ?? t}
            </option>
          ))}
        </select>
      </label>
      <label className="field" htmlFor={`${idPrefix}-court`}>
        Court
        <select id={`${idPrefix}-court`} value={value.court ?? ''} onChange={(e) => set('court', e.target.value)}>
          <option value="">Any</option>
          {(options?.courts ?? []).map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
      <label className="field" htmlFor={`${idPrefix}-year`}>
        Year
        <select id={`${idPrefix}-year`} value={value.year ?? ''} onChange={(e) => set('year', e.target.value)}>
          <option value="">Any</option>
          {(options?.years ?? []).map((y) => (
            <option key={y} value={String(y)}>
              {y}
            </option>
          ))}
        </select>
      </label>
      <label className="field" htmlFor={`${idPrefix}-act`}>
        Act
        <select id={`${idPrefix}-act`} value={value.act ?? ''} onChange={(e) => set('act', e.target.value)}>
          <option value="">Any</option>
          {(options?.acts ?? []).map((a) => (
            <option key={a} value={a}>
              {ACT_LABEL[a] ?? a}
            </option>
          ))}
        </select>
      </label>
      <label className="field" htmlFor={`${idPrefix}-section`}>
        Section or article
        <input
          id={`${idPrefix}-section`}
          value={value.section ?? ''}
          onChange={(e) => set('section', e.target.value.trim())}
          maxLength={20}
          placeholder="e.g. 21"
        />
      </label>
      <label className="field" htmlFor={`${idPrefix}-case`}>
        Case number
        <input
          id={`${idPrefix}-case`}
          value={value.case ?? ''}
          onChange={(e) => set('case', e.target.value)}
          maxLength={60}
          placeholder="e.g. W.P. 11944/2013"
        />
      </label>
      {any && (
        <button type="button" className="btn small ghost" onClick={() => onChange({})}>
          Clear filters
        </button>
      )}
    </fieldset>
  );
}
