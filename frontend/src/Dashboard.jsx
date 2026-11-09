import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, BarChart3, RefreshCw, X } from 'lucide-react';

const API_URL = 'http://127.0.0.1:8000/api';

const FILTERS = [
  { key: 'period', label: 'Periodo' },
  { key: 'gender', label: 'Género' },
  { key: 'department', label: 'Departamento' },
  { key: 'stratum', label: 'Estrato' },
  { key: 'school_nature', label: 'Colegio' },
  { key: 'school_area', label: 'Zona' },
  { key: 'school_schedule', label: 'Jornada' },
];

// Las columnas se agrupan por tema para que el usuario pueda mostrar solo lo que necesita.
// Las barras usan escalas fijas para que sean comparables entre páginas y filtros.
const GROUPS = [
  {
    key: 'student', label: 'Estudiante',
    columns: [
      { key: 'student_code', label: 'Código', kind: 'code', sticky: true },
      { key: 'age', label: 'Edad', kind: 'num' },
      { key: 'gender', label: 'Género' },
      { key: 'period', label: 'Periodo', kind: 'num' },
      { key: 'department', label: 'Departamento' },
      { key: 'municipality', label: 'Municipio' },
    ],
  },
  {
    key: 'home', label: 'Hogar',
    columns: [
      { key: 'stratum', label: 'Estrato', kind: 'stratum' },
      { key: 'nse', label: 'NSE' },
      { key: 'mother_education', label: 'Educación madre', kind: 'long' },
      { key: 'father_education', label: 'Educación padre', kind: 'long' },
      { key: 'internet', label: 'Internet', kind: 'flag' },
      { key: 'computer', label: 'Computador', kind: 'flag' },
    ],
  },
  {
    key: 'school', label: 'Colegio',
    columns: [
      { key: 'school_name', label: 'Establecimiento', kind: 'long' },
      { key: 'school_nature', label: 'Naturaleza' },
      { key: 'school_area', label: 'Zona' },
      { key: 'school_schedule', label: 'Jornada' },
      { key: 'school_calendar', label: 'Calendario' },
      { key: 'school_bilingual', label: 'Bilingüe' },
    ],
  },
  {
    key: 'scores', label: 'Puntajes',
    columns: [
      { key: 'score_reading', label: 'Lectura', kind: 'bar', max: 100 },
      { key: 'score_math', label: 'Matemáticas', kind: 'bar', max: 100 },
      { key: 'score_science', label: 'Naturales', kind: 'bar', max: 100 },
      { key: 'score_social', label: 'Sociales', kind: 'bar', max: 100 },
      { key: 'score_english', label: 'Inglés', kind: 'bar', max: 100 },
      { key: 'score_global', label: 'Global', kind: 'bar', max: 500, strong: true },
      { key: 'percentile_global', label: 'Percentil', kind: 'bar', max: 100 },
      { key: 'english_level', label: 'Nivel inglés' },
    ],
  },
];

const INITIAL_FILTERS = { period: '', gender: '', department: '', school_nature: '', school_area: '' };
const PAGE_SIZES = [20, 50, 100];
const number = (value) => new Intl.NumberFormat('es-CO').format(value ?? 0);

function Cell({ column, value }) {
  const numeric = column.kind === 'bar' || column.kind === 'num';
  if (value == null || value === '') return <td className={numeric ? 'num muted' : 'muted'}>—</td>;
  switch (column.kind) {
    case 'bar': {
      const width = Math.max(0, Math.min(100, (value / column.max) * 100));
      return (
        <td className={`num bar-cell${column.strong ? ' strong' : ''}`}>
          <span className="bar" style={{ width: `${width}%` }} aria-hidden="true" />
          <span className="bar-value">{value}</span>
        </td>
      );
    }
    case 'num': return <td className="num">{value}</td>;
    case 'code': return <td className="code sticky">{value}</td>;
    case 'stratum': return <td>{value.replace('Estrato ', 'E')}</td>;
    case 'long': return <td className="long" title={value}>{value}</td>;
    case 'flag': return <td><span className={`flag ${value.toLowerCase().startsWith('s') ? 'yes' : 'no'}`} aria-hidden="true" />{value}</td>;
    default: return <td>{value}</td>;
  }
}

function SkeletonRows({ rows, cells }) {
  return Array.from({ length: rows }, (_, row) => (
    <tr key={row} className="skeleton-row" aria-hidden="true">
      {Array.from({ length: cells }, (_, cell) => <td key={cell}><span className="skeleton" /></td>)}
    </tr>
  ));
}

function Dashboard() {
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [dense, setDense] = useState(true);
  const [hiddenGroups, setHiddenGroups] = useState([]);
  const [retryKey, setRetryKey] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState(null);
  const pageCache = useRef(new Map());

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    Object.entries(filters).forEach(([key, value]) => value && params.set(key, value));
    const cacheKey = JSON.stringify([filters, page, pageSize]);
    const cachedPage = pageCache.current.get(cacheKey);
    if (cachedPage) {
      setData(cachedPage);
      setError('');
      setLoadProgress(null);
      setLoading(false);
      return () => controller.abort();
    }

    setLoading(true);
    setLoadProgress(null);
    setError('');

    async function fetchPage() {
      try {
        let response = await fetch(`${API_URL}/records?${params}`, { signal: controller.signal });
        if (response.status === 202) {
          let status = await response.json();
          setLoadProgress(status);
          while (status.status === 'loading' && !controller.signal.aborted) {
            await new Promise((resolve) => window.setTimeout(resolve, 700));
            const statusResponse = await fetch(`${API_URL}/load-status`, { signal: controller.signal });
            if (!statusResponse.ok) throw new Error('No fue posible consultar el progreso de lectura');
            status = await statusResponse.json();
            setLoadProgress(status);
          }
          if (status.status === 'error') throw new Error(status.error || 'No fue posible leer el archivo');
          if (controller.signal.aborted) return;
          response = await fetch(`${API_URL}/records?${params}`, { signal: controller.signal });
        }
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || `Error ${response.status}: no fue posible consultar la API`);
        }
        const result = await response.json();
        pageCache.current.set(cacheKey, result);
        if (pageCache.current.size > 40) pageCache.current.delete(pageCache.current.keys().next().value);
        setData(result);
        setLoadProgress(null);
      } catch (requestError) {
        if (requestError.name !== 'AbortError') setError(requestError.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    fetchPage();
    return () => controller.abort();
  }, [filters, page, pageSize, retryKey]);

  const updateFilter = (key, value) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  };
  const clearFilters = () => { setFilters({ ...INITIAL_FILTERS }); setPage(1); };
  const toggleGroup = (key) => setHiddenGroups((current) => (
    current.includes(key) ? current.filter((item) => item !== key) : [...current, key]
  ));

  const visibleGroups = GROUPS.filter((group) => !hiddenGroups.includes(group.key));
  const visibleColumns = visibleGroups.flatMap((group) => group.columns);
  const activeFilters = useMemo(
    () => FILTERS.filter((filter) => filters[filter.key]).map((filter) => ({ ...filter, value: filters[filter.key] })),
    [filters],
  );
  const total = data?.total_records ?? 0;
  const filtered = data?.filtered_records ?? 0;
  const share = total ? (filtered / total) * 100 : 0;
  const totalPages = Math.max(1, Math.ceil(filtered / pageSize));
  const firstRow = filtered ? (page - 1) * pageSize + 1 : 0;
  const lastRow = Math.min(page * pageSize, filtered);
  const initialLoad = loading && !data;

  return (
    <main className="shell">
      <header className="topbar">
        <span className="brand"><span className="brand-mark"><BarChart3 size={16} /></span>ICFES · Saber 11</span>
        <span className={`status ${loading ? 'busy' : 'ready'}`} role="status" aria-live="polite">
          <span className="status-dot" />
          {loading ? (loadProgress ? `Leyendo archivo ${loadProgress.percent}%` : 'Actualizando…') : 'Datos al día'}
        </span>
      </header>

      <section className="kpis" aria-label="Resumen">
        <div className="kpi">
          <span className="kpi-label">Registros depurados</span>
          <strong className="kpi-value">{data ? number(total) : '—'}</strong>
        </div>
        <div className="kpi kpi-main">
          <span className="kpi-label">Coinciden con los filtros</span>
          <strong className="kpi-value">{data ? number(filtered) : '—'}</strong>
          <span className="share" aria-hidden="true"><span className="share-fill" style={{ width: `${share}%` }} /></span>
          <span className="kpi-note">{data ? `${share.toFixed(share < 10 && share > 0 ? 1 : 0)}% del total` : ' '}</span>
        </div>
      </section>

      <section className="filters" aria-label="Filtros">
        <div className="filter-row">
          {FILTERS.map((filter) => (
            <label className="field" key={filter.key}>
              <span>{filter.label}</span>
              <select value={filters[filter.key]} onChange={(event) => updateFilter(filter.key, event.target.value)} disabled={!data}>
                <option value="">Todos</option>
                {(data?.filters?.[filter.key] ?? []).map((option) => <option value={option} key={option}>{option}</option>)}
              </select>
            </label>
          ))}
        </div>
        <div className="chips" aria-live="polite">
          {activeFilters.length === 0 && <span className="chips-empty">Sin filtros: se muestran todos los registros</span>}
          {activeFilters.map((filter) => (
            <button type="button" className="chip" key={filter.key} onClick={() => updateFilter(filter.key, '')} title={`Quitar ${filter.label}`}>
              <small>{filter.label}</small>{filter.value}<X size={12} />
            </button>
          ))}
          {activeFilters.length > 0 && (
            <button type="button" className="link-button" onClick={clearFilters}><RefreshCw size={12} />Limpiar todo</button>
          )}
        </div>
      </section>

      {loadProgress && !error && (
        <section className="progress" role="status">
          <div className="progress-head">
            <strong>Preparando los datos por primera vez</strong>
            <span>{loadProgress.percent}% · {number(loadProgress.rows_loaded)} registros</span>
          </div>
          <progress max="100" value={loadProgress.percent} aria-label="Progreso de lectura del dataset" />
          <small>Se guardan en memoria mientras la sesión esté activa; las siguientes consultas serán inmediatas.</small>
        </section>
      )}

      {error ? (
        <div className="error" role="alert">
          <strong>No se pudo consultar el archivo</strong>
          <span>{error}</span>
          <button type="button" onClick={() => setRetryKey((current) => current + 1)}>Reintentar</button>
        </div>
      ) : (
        <section className="table-block" aria-busy={loading}>
          <div className="table-tools">
            <span className="range">{filtered ? `${number(firstRow)}–${number(lastRow)} de ${number(filtered)}` : 'Sin resultados'}</span>
            <div className="tool-group">
              <div className="segmented groups" role="group" aria-label="Columnas visibles">
                {GROUPS.map((group) => {
                  const on = !hiddenGroups.includes(group.key);
                  return (
                    <button type="button" key={group.key} className={on ? 'on' : ''} aria-pressed={on}
                      disabled={on && visibleGroups.length === 1} onClick={() => toggleGroup(group.key)}>
                      {group.label}
                    </button>
                  );
                })}
              </div>
              <label className="inline-field">
                <span>Filas</span>
                <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}>
                  {PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
                </select>
              </label>
              <div className="segmented" role="group" aria-label="Densidad de la tabla">
                <button type="button" className={dense ? 'on' : ''} aria-pressed={dense} onClick={() => setDense(true)}>Compacta</button>
                <button type="button" className={!dense ? 'on' : ''} aria-pressed={!dense} onClick={() => setDense(false)}>Cómoda</button>
              </div>
            </div>
          </div>

          <div className={`table-scroll${loading && data ? ' stale' : ''}`}>
            <table className={`grid${dense ? ' dense' : ''}`}>
              <thead>
                <tr className="group-row">
                  {visibleGroups.map((group) => (
                    <th key={group.key} colSpan={group.columns.length} className={`group group-${group.key}`}>{group.label}</th>
                  ))}
                </tr>
                <tr>
                  {visibleColumns.map((column) => (
                    <th key={column.key} className={`${column.kind === 'bar' || column.kind === 'num' ? 'num' : ''}${column.sticky ? ' sticky' : ''}`}>
                      {column.label}{column.max && <small>/{column.max}</small>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {initialLoad && <SkeletonRows rows={12} cells={visibleColumns.length} />}
                {(data?.records ?? []).map((row) => (
                  <tr key={`${row.student_code}-${row.period}`}>
                    {visibleColumns.map((column) => <Cell key={column.key} column={column} value={row[column.key]} />)}
                  </tr>
                ))}
                {!loading && !data?.records?.length && (
                  <tr><td colSpan={visibleColumns.length} className="empty">
                    Ningún registro cumple esta combinación.
                    <button type="button" className="link-button" onClick={clearFilters}>Limpiar filtros</button>
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="table-foot">
            <span className="legend"><span className="legend-bar" />Barra = puntaje respecto a su máximo</span>
            <div className="pager">
              <span>Página {page} de {number(totalPages)}</span>
              <button type="button" aria-label="Primera página" disabled={page <= 1 || loading} onClick={() => setPage(1)}>1</button>
              <button type="button" aria-label="Página anterior" disabled={page <= 1 || loading} onClick={() => setPage((current) => current - 1)}><ArrowLeft size={15} /></button>
              <button type="button" aria-label="Página siguiente" disabled={page >= totalPages || loading} onClick={() => setPage((current) => current + 1)}><ArrowRight size={15} /></button>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}

export default Dashboard;
