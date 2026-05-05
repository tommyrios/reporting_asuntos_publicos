# Reporting Asuntos Públicos · BBVA

Pipeline para generar un **borrador quincenal editable** del informe de contexto político de Asuntos Públicos.

El output principal es un **PPTX de 3 slides**:

1. Portada BBVA.
2. Análisis ejecutivo de coyuntura.
3. Contraportada BBVA.

El objetivo no es reemplazar el criterio editorial del equipo, sino entregar un primer insumo ordenado para revisión, edición y ajuste de foco.

## Flujo funcional

```text
GitHub Actions
   ↓
news_collector.py
   ↓
deduplicator.py
   ↓
relevance_scorer.py
   ↓
political_analyzer.py + Gemini API
   ↓
report_contract.json
   ↓
pptx_builder.py
   ↓
send_gmail.py
```

## Stack

- Python 3.11+
- GitHub Actions para ejecución programada
- Gemini API para síntesis y visión ejecutiva
- Google News RSS / GDELT / RSS institucionales para ingesta
- Gmail API para envío
- python-pptx para generación del PPTX

## Estructura

```text
reporting_asuntos_publicos/
├─ .github/workflows/aapp-report.yml
├─ assets/
│  ├─ brand/
│  └─ templates/
├─ data/
│  ├─ config/sources.json
│  ├─ history/used_news.json
│  ├─ raw_news/
│  ├─ normalized_news/
│  └─ selected_news/
├─ output/reports/
├─ prompts/
│  ├─ political_analysis.txt
│  └─ style_gonza.txt
├─ scripts/
│  ├─ news_collector.py
│  ├─ deduplicator.py
│  ├─ relevance_scorer.py
│  ├─ political_analyzer.py
│  ├─ pptx_builder.py
│  ├─ send_gmail.py
│  └─ run_scheduled_report.py
└─ tests/
```

## Instalación local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

En Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Smoke test sin internet ni Gemini

Genera un PPTX de muestra con noticias mockeadas:

```bash
python scripts/generate_sample_report.py
```

Salida esperada:

```text
output/reports/sample/report_aapp_sample.pptx
```

## Ejecución local real

```bash
python scripts/run_scheduled_report.py --period-days 15
```

Para enviar por Gmail API:

```bash
python scripts/run_scheduled_report.py --period-days 15 --send-email
```

Para usar un set de noticias local:

```bash
python scripts/run_scheduled_report.py --input-news templates/sample_news.json --disable-gemini
```

## Secrets requeridos

```text
GEMINI_API_KEY
GEMINI_MODEL
GEMINI_FALLBACK_MODELS
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REFRESH_TOKEN
GOOGLE_TOKEN_URI
EMAIL_FROM
EMAIL_DESTINATARIO
EMAIL_CC
EMAIL_BCC
```

Variables opcionales:

```text
REPORT_TIMEZONE=America/Argentina/Buenos_Aires
AAPP_MAX_NEWS=120
AAPP_SELECTED_NEWS=12
AAPP_DISABLE_GEMINI=false
AAPP_STRICT_LLM=false
SEND_EMAIL=true
```

## Configuración de fuentes

El archivo `data/config/sources.json` define:

- búsquedas en Google News RSS;
- queries en GDELT;
- feeds RSS institucionales;
- dominios prioritarios;
- parámetros de deduplicación y selección.

Para el MVP, conviene mantener pocas queries, de alta precisión. El pipeline prioriza impacto político, regulatorio y financiero, no volumen de titulares.

## Contrato de salida

Cada ejecución genera:

```text
output/reports/<fecha>/report_aapp_<fecha>.pptx
output/reports/<fecha>/report_contract.json
output/reports/<fecha>/selected_news.json
output/reports/<fecha>/sources.json
output/reports/<fecha>/run_log.json
```

El PPTX es editable y está pensado como insumo interno. Si se requiere distribución externa, se puede exportar a PDF como paso posterior.

## Guardrails editoriales

- Gemini no inventa hechos: recibe un set de noticias seleccionado por el pipeline.
- El historial evita reutilizar URLs y clusters ya trabajados.
- La memoria de estilo está separada de la memoria de contenido.
- Si no hay suficiente información, el reporte lo explicita en vez de completar con supuestos.
- La slide prioriza lectura ejecutiva, implicancias para BBVA y focos de seguimiento.

## Tests

```bash
python -m unittest discover -s tests -p 'test*.py'
```

## GitHub Actions

El workflow corre los días 1 y 15 de cada mes, con opción manual (`workflow_dispatch`). El cron puede ajustarse cuando el equipo defina la fecha exacta de cierre editorial.
