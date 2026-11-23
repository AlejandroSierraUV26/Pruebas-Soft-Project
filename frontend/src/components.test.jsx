import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Cell, TrendChart } from './Dashboard';

function renderCell(column, value) {
  return render(<table><tbody><tr><Cell column={column} value={value} /></tr></tbody></table>);
}

describe('Cell', () => {
  it('muestra un guion para valores ausentes', () => {
    const { container } = renderCell({ key: 'score', kind: 'num' }, null);
    expect(container.textContent).toBe('—');
  });

  it('limita el ancho de la barra al maximo de la columna', () => {
    const { container } = renderCell({ key: 'score_global', kind: 'bar', max: 100, strong: true }, 250);
    expect(container.querySelector('.bar')).toHaveStyle({ width: '100%' });
    expect(container.textContent).toContain('250');
  });

  it('abrevia el estrato', () => {
    const { container } = renderCell({ key: 'stratum', kind: 'stratum' }, 'Estrato 2');
    expect(container.textContent).toBe('E2');
  });

  it('distingue las banderas si y no', () => {
    const yes = renderCell({ key: 'internet', kind: 'flag' }, 'Si');
    expect(yes.container.querySelector('.flag.yes')).toBeInTheDocument();
    yes.unmount();

    const no = renderCell({ key: 'computer', kind: 'flag' }, 'No');
    expect(no.container.querySelector('.flag.no')).toBeInTheDocument();
  });
});

describe('TrendChart', () => {
  it('no dibuja la tendencia con menos de dos puntos', () => {
    const { container } = render(
      <TrendChart groups={[{ value: '20194', count: 1, averages: { score_global: 250 } }]} overall={250} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('dibuja la tendencia y la linea del promedio general', () => {
    const { container } = render(
      <TrendChart
        groups={[
          { value: '20191', count: 1, averages: { score_global: 240 } },
          { value: '20194', count: 2, averages: { score_global: 260 } },
        ]}
        overall={250}
      />,
    );
    expect(container.querySelector('.trend-line')).toBeInTheDocument();
    expect(container.querySelector('.trend-overall')).toBeInTheDocument();
    expect(container.querySelectorAll('.trend-dot')).toHaveLength(2);
  });
});
