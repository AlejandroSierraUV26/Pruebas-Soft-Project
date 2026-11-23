# Explorador de resultados ICFES

Prototipo con API FastAPI y dashboard React para consultar el archivo `icfes_data.csv`.

## Requisitos

- Python 3.10 o superior.
- Node.js 22.12 o superior.
- El archivo `icfes_data.csv` en la raíz del proyecto.

El archivo de origen ocupa aproximadamente 1,2 GB y está separado por tabulaciones. La API lo lee directamente como archivo plano, conserva las variables usadas por la tabla, limpia espacios y descarta filas sin datos esenciales. No utiliza una base de datos ni genera copias en disco. La primera consulta muestra el progreso de lectura y prepara una caché compacta en memoria; filtros y páginas posteriores reutilizan esos datos. La caché se libera tras 15 minutos sin actividad o al cerrar la API.

## Iniciar

En una terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn file_api:app --reload
```

En otra terminal:

```powershell
cd frontend
npm install
npm run dev
```

Abre la URL que indique Vite, normalmente `http://localhost:5173`. La API responde en `http://127.0.0.1:8000/api/records` y su documentación está en `http://127.0.0.1:8000/docs`.

La tabla permite filtrar por periodo, género, departamento, naturaleza del colegio y zona, y paginar los resultados. El navegador conserva las últimas 40 páginas consultadas mientras la pestaña permanece abierta.

## Pruebas

Las pruebas del backend usan `pytest` y exigen al menos 90 % de cobertura de `file_api.py`:

```powershell
cd backend
pip install -r requirements-dev.txt
python -m pytest tests -q --cov=file_api --cov-report=term-missing --cov-fail-under=90
```

Las pruebas del frontend usan `Vitest` y `Testing Library`:

```powershell
cd frontend
npm install
npm test
```

El flujo de GitHub Actions (`.github/workflows/ci.yml`) ejecuta ambas suites en Python 3.10 y 3.12, y el build del frontend, en cada push a `main` y en cada pull request.

El dashboard incluye además un panel de promedios (`/api/stats?group_by=...`) que agrupa los puntajes por año, departamento, estrato y educación de los padres, con barras comparables, diferencia respecto al promedio general y tamaño de muestra (n) de cada grupo.