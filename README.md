# Reporte AAPP - Apuntes políticos en Google Docs

Pipeline para generar una nota interna de actualidad política en formato Google Docs, inspirada en el modelo **Apuntes políticos** de la Dirección de Relaciones Institucionales.

## Qué hace

1. Releva noticias políticas del período configurado (default: últimos 15 días).
2. Agrupa notas repetidas en **clusters de hechos políticos**. El foco no es el medio, sino la pieza de información.
3. Prioriza entre 4 y 8 clusters por recurrencia, centralidad política y recencia.
4. Usa Gemini para redactar una nota interna con tono politológico.
5. Crea un Google Doc editable con Google Docs API.
6. Comparte el archivo con Drive API.
7. Envía el enlace por Gmail API o SMTP.

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
- Gmail API, solo si `EMAIL_DELIVERY_MODE=gmail_api`

Scopes OAuth:

```text
https://www.googleapis.com/auth/documents
https://www.googleapis.com/auth/drive.file
https://www.googleapis.com/auth/gmail.send
```

Secrets:

```text
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REFRESH_TOKEN
GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
GEMINI_API_KEY
```

Opcionales:

```text
GOOGLE_DOCS_FOLDER_ID
GOOGLE_DOCS_SHARE_WITH
EMAIL_FROM
EMAIL_DESTINATARIO
EMAIL_CC
EMAIL_BCC
```

Variables recomendadas:

```text
GOOGLE_DOCS_SHARE_ROLE=writer
EMAIL_DELIVERY_MODE=gmail_api
SCHEDULE_ANCHOR_DATE=2026-05-06
RUN_EVERY_DAYS=14
AAPP_MIN_CLUSTERS=4
AAPP_MAX_CLUSTERS=8
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

Esto genera un preview local en:

```text
output/reports/sample/sample_preview.txt
```

## Ejecución local real

Con variables de entorno configuradas:

```bash
python scripts/run_scheduled_report.py --period-days 15 --send-email
```

Para probar sin crear Google Doc:

```bash
python scripts/run_scheduled_report.py --period-days 15 --no-create-doc --disable-gemini
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
