import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import Dashboard from './Dashboard';

const AVERAGES = {
  score_reading: 50,
  score_math: 52,
  score_science: 50,
  score_social: 48,
  score_english: 51,
  score_global: 250,
};

const STATS = {
  group_by: 'period',
  total_records: 2,
  overall_average_global: 250,
  groups: [
    { value: '20194', count: 2, share: 100, averages: AVERAGES, diff_global: 0 },
    { value: null, count: 0, share: 0, averages: { ...AVERAGES, score_global: null }, diff_global: null },
  ],
};

const DEPARTMENT_STATS = {
  ...STATS,
  group_by: 'department',
  groups: [{ value: 'VALLE', count: 2, share: 100, averages: AVERAGES, diff_global: 0 }],
};

const RECORDS = {
  total_records: 45,
  filtered_records: 45,
  page: 1,
  page_size: 20,
  records: [{
    student_code: 'ALUMNO-1',
    age: 17,
    gender: 'F',
    period: '20194',
    department: 'VALLE',
    municipality: 'TULUA',
    stratum: 'Estrato 2',
    nse: 'NSE2',
    mother_education: 'Secundaria',
    father_education: 'Primaria',
    internet: 'Si',
    computer: 'No',
    school_name: 'IE JULIA RESTREPO',
    school_nature: 'OFICIAL',
    school_area: 'URBANO',
    school_schedule: 'MANANA',
    school_calendar: 'A',
    school_bilingual: 'N',
    score_reading: 55,
    score_math: 52,
    score_science: 50,
    score_social: 48,
    score_english: 51,
    score_global: 260,
    percentile_global: 55,
    english_level: 'A1',
  }],
  filters: {
    period: ['20194'],
    gender: ['F'],
    department: ['VALLE', 'CAUCA'],
    stratum: ['Estrato 2'],
    school_nature: ['OFICIAL'],
    school_area: ['URBANO'],
    school_schedule: ['MANANA'],
  },
};

const response = (payload) => ({ ok: true, status: 200, json: async () => payload });

function mockApi() {
  const fetchMock = vi.fn(async (url) => {
    const target = String(url);
    if (target.includes('/api/stats')) {
      return response(target.includes('group_by=department') ? DEPARTMENT_STATS : STATS);
    }
    if (target.includes('/api/records')) return response(RECORDS);
    throw new Error(`URL inesperada: ${target}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('Dashboard', () => {
  it('muestra los promedios y el promedio general', async () => {
    mockApi();
    render(<Dashboard />);

    expect(await screen.findByText('Promedios de puntaje global')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/Promedio general:/)).toHaveTextContent('250'));
    expect(screen.getAllByText('20194').length).toBeGreaterThan(0);
    expect(screen.getByText('Sin dato')).toBeInTheDocument();
  });

  it('reutiliza los promedios ya consultados por grupo', async () => {
    const fetchMock = mockApi();
    render(<Dashboard />);

    await screen.findByText('Promedios de puntaje global');
    const periodCalls = () => fetchMock.mock.calls
      .filter(([url]) => String(url).includes('/stats?group_by=period')).length;
    await waitFor(() => expect(periodCalls()).toBe(1));

    fireEvent.click(screen.getByRole('button', { name: 'Por departamento' }));
    await waitFor(() => expect(fetchMock.mock.calls
      .some(([url]) => String(url).includes('/stats?group_by=department'))).toBe(true));

    fireEvent.click(screen.getByRole('button', { name: 'Por año' }));
    expect(periodCalls()).toBe(1);
  });

  it('consulta los registros y aplica filtros', async () => {
    const fetchMock = mockApi();
    render(<Dashboard />);
    fireEvent.click(screen.getByRole('tab', { name: /Datos/ }));

    expect(await screen.findByText('ALUMNO-1')).toBeInTheDocument();
    expect(fetchMock.mock.calls
      .some(([url]) => String(url).includes('/records?page=1&page_size=20'))).toBe(true);

    fireEvent.change(screen.getByLabelText('Departamento'), { target: { value: 'VALLE' } });

    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => {
      const target = String(url);
      return target.includes('/records?') && target.includes('department=VALLE') && target.includes('page=1');
    })).toBe(true));
    expect(screen.getByTitle('Quitar Departamento')).toBeInTheDocument();
  });

  it('navega entre paginas', async () => {
    const fetchMock = mockApi();
    render(<Dashboard />);
    fireEvent.click(screen.getByRole('tab', { name: /Datos/ }));
    await screen.findByText('ALUMNO-1');

    expect(screen.getByText('Página 1 de 3')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Página siguiente' }));

    await waitFor(() => expect(fetchMock.mock.calls
      .some(([url]) => String(url).includes('page=2'))).toBe(true));
  });

  it('muestra el error y permite reintentar', async () => {
    let fail = true;
    const fetchMock = vi.fn(async (url) => {
      if (String(url).includes('/api/stats')) return response(STATS);
      if (fail) throw new Error('fallo de red');
      return response(RECORDS);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<Dashboard />);
    fireEvent.click(screen.getByRole('tab', { name: /Datos/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('fallo de red');

    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByText('ALUMNO-1')).toBeInTheDocument();
  });
});
