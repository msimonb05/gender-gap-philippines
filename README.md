# Mapping Gender Parity in the Philippines

A data visualizer and research report on the gender gap in the Philippines, built from public Philippine Statistics Authority (PSA) data on labor, wages, literacy, school enrollment, and poverty. The report is shown section by section on a single Flask page, with every chart drawn from the data in light or dark mode.

Live site: https://msimonb05.github.io/gender-gap-philippines/

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-11557C?style=for-the-badge&logoColor=white)
![seaborn](https://img.shields.io/badge/seaborn-4C72B0?style=for-the-badge&logoColor=white)
![SciPy](https://img.shields.io/badge/SciPy-8CAAE6?style=for-the-badge&logo=scipy&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![Jinja](https://img.shields.io/badge/Jinja-B41717?style=for-the-badge&logo=jinja&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)
![Markdown](https://img.shields.io/badge/Markdown-000000?style=for-the-badge&logo=markdown&logoColor=white)

| Category | Technology |
| :--- | :--- |
| Language | Python 3.14 |
| Data cleaning | pandas, openpyxl |
| Statistics | SciPy |
| Charts | Matplotlib, seaborn (SVG output) |
| Web app | Flask, Jinja templates |
| Styling | Bootstrap 5.3 (local copy) |
| Report | Markdown |

## What It Shows

- Where Filipino women lead men (functional literacy, wages of full-time wage workers) and where they trail (labor force participation, female-to-male ratio of 0.72 in 2025)
- How the participation gap changed from 2005 to 2026, and how much of the growth in women's labor force came from population versus participation
- Whether regional wage gaps line up with poverty or literacy (Spearman correlation, bootstrap confidence intervals, Holm correction)

## Project Structure

| Path | Contents |
| :--- | :--- |
| `csv/`, `xlsx/` | Raw PSA tables, never modified |
| `clean_psa_data.py` | Cleans and validates the raw tables into `data/` |
| `analysis.py` | Further analyses, written to `data/analysis/` |
| `app.py` | Flask app: renders the report and draws the charts |
| `templates/`, `static/` | Page template, figure card, CSS, JavaScript, Bootstrap |
| `content/` | The report in Markdown and its exported figures |

## How to Run Locally

Requires Python 3.14.

| Command | Action |
| :--- | :--- |
| `python -m venv .venv` | Create a virtual environment |
| `.venv\Scripts\python -m pip install -r requirements.txt` | Install dependencies |
| `.venv\Scripts\python clean_psa_data.py` | Rebuild the cleaned data in `data/` |
| `.venv\Scripts\python analysis.py` | Rebuild the analysis results in `data/analysis/` |
| `.venv\Scripts\python app.py` | Start the page at `localhost:5000` |
| `.venv\Scripts\python build_site.py` | Export the static site to `site/` (what GitHub Pages serves) |

On macOS or Linux, use `.venv/bin/python` in place of `.venv\Scripts\python`.

>All data come from the Philippine Statistics Authority (PSA OpenSTAT and PSA statistical tables). Full citations are in the report's reference list. This is an independent analysis, not affiliated with or endorsed by the PSA. Values such as parity ratios, the decomposition, trends, and correlations are computed from published tables and are not official statistics.
