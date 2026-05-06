# Reporte AAPP - Apuntes políticos en Google Docs

Pipeline para generar una nota interna de actualidad política en formato Google Docs, inspirada en el modelo **Apuntes políticos** de la Dirección de Relaciones Institucionales.

## Qué hace

1. Releva noticias políticas del período configurado (default: últimos 15 días).
2. Agrupa notas repetidas en **clusters de hechos políticos**. El foco no es el medio, sino la pieza de información.
3. Fusiona clusters cercanos por tema editorial para evitar desarrollos repetidos sobre el mismo hecho.
4. Prioriza entre 4 y 8 temas por recurrencia, cantidad de fuentes, centralidad política y recencia.
5. Usa Gemini para redactar una nota interna con tono politológico.
6. Genera un `.docx` local con estilo BBVA, incluyendo `assets/brand/logo_bbva_white.png` como imagen real.
7. Sube ese `.docx` a Drive y lo convierte en **Google Docs editable**.
8. Comparte el documento con Drive API y envía el enlace por SMTP.

## Contrato editorial obligatorio

El pipeline no debe publicar textos que parezcan un pegado de titulares. Antes de generar el Google Doc, se sanea y valida el contenido final para impedir:

- URLs o dominios.
- Nombres de medios usados como fuente o atribución.
- Frases como “según medios”, “relevado en medios” o “fuentes periodísticas”.
- Frases inconclusas o sin puntuación final.
- Desarrollos duplicados sobre un mismo tema político.

Si Gemini devuelve una salida con medios o texto incompleto, el sistema descarta esa salida y usa un fallback determinístico. Si el fallback tampoco cumple el contrato, la ejecución falla antes de compartir el documento.

## Formato editorial

El documento replica esta estructura:

```text
DIRECCIÓN DE RELACIONES INSTITUCIONALES        NOTA INTERNA

Apuntes políticos #X
Fecha

[Párrafo inicial de lectura política]

─ [Tesis política 1]. Desarrollo analítico.
─ [Tesis política 2]. Desarrollo analítico.
─ [Tesis política 3]. Desarrollo analítico.
─ [Tesis política 4]. Desarrollo analítico.

─ Claves prospectivas
  ○ Clave 1
  ○ Clave 2
  ○ Clave 3
  ○ Clave 4

Gracias!
DIRECCIÓN DE RELACIONES INSTITUCIONALES
```

## Secrets requeridos

### Google personal / Google Pro

Habilitar en Google Cloud:

- Google Docs API
- Google Drive API

Scopes OAuth:

```text
https://www.googleapis.com/auth/documents
https://www.googleapis.com/auth/drive.file
```

Secrets:

```text
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REFRESH_TOKEN
GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
GEMINI_API_KEY
```

Google Docs / Drive:

```text
GOOGLE_DOCS_FOLDER_ID
GOOGLE_DOCS_SHARE_WITH
```

Opcional para intentar transferencia de propiedad:

```text
GOOGLE_DOCS_TRANSFER_OWNERSHIP_TO
```

La transferencia puede fallar por restricciones de Google Workspace o por intentar transferir desde una cuenta personal hacia un dominio corporativo. En ese caso el pipeline no se cae: deja el documento compartido como editor y registra el warning.

Envío SMTP:

```text
EMAIL_FROM
EMAIL_DESTINATARIO
EMAIL_CC
EMAIL_BCC
SMTP_HOST
SMTP_PORT
EMAIL_USER
EMAIL_PASSWORD
```

Variables recomendadas:

```text
GOOGLE_DOCS_SHARE_ROLE=writer
SCHEDULE_ANCHOR_DATE=2026-05-06
RUN_EVERY_DAYS=14
AAPP_MIN_CLUSTERS=4
AAPP_MAX_CLUSTERS=8

# Numeración editorial acordada con Asuntos Públicos:
# #7 = segunda quincena de abril 2026; #8 = primera quincena de mayo 2026.
REPORT_PERIOD_MODE=half_month_current
REPORT_BASE_ISSUE_NUMBER=7
REPORT_BASE_PERIOD_YEAR=2026
REPORT_BASE_PERIOD_MONTH=4
REPORT_BASE_PERIOD_HALF=2
```

## Generar refresh token

Local:

```bash
export GOOGLE_CLIENT_ID="..."
export GOOGLE_CLIENT_SECRET="..."
python scripts/generate_oauth_token.py
```

Copiar el `refresh_token` a GitHub Secrets como `GOOGLE_REFRESH_TOKEN`.

## Ejecución local sin APIs

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p 'test*.py'
python scripts/generate_sample_report.py
```

Esto genera:

```text
output/reports/sample/sample.docx
output/reports/sample/sample_preview.txt
output/reports/sample/sample_contract.json
```

## Ejecución local real

Con variables de entorno configuradas:

```bash
python scripts/run_scheduled_report.py --period-days 15 --send-email
```

Para probar sin crear Google Doc:

```bash
python scripts/run_scheduled_report.py --period-days 15 --period-mode half_month_current --no-create-doc --disable-gemini
```

Modos de período disponibles:

```text
half_month_current    Usa la quincena vigente hasta el momento de ejecución. Ej: 06/05/2026 => primera quincena de mayo => #8.
half_month_completed  Usa la última quincena cerrada. Ej: 16/05/2026 => primera quincena de mayo => #8.
sliding               Conserva el comportamiento anterior de últimos N días, pero numera por la quincena de la fecha de cierre.
```

## Programación

El workflow corre los miércoles a la noche de Argentina mediante cron UTC:

```yaml
- cron: '0 1 * * 4'
```

Eso equivale aproximadamente a jueves 01:00 UTC / miércoles 22:00 ART. La ejecución quincenal se controla con `scripts/should_run.py`, usando:

```text
SCHEDULE_ANCHOR_DATE
RUN_EVERY_DAYS=14
```

## Memoria

El pipeline no usa memoria de noticias entre ejecuciones. Solo conserva archivos de salida para trazabilidad. El tono y formato viven en:

```text
prompts/style_apuntes_politicos.txt
prompts/political_report.txt
```
