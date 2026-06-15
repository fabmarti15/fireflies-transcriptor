#!/usr/bin/env python3
"""
Fireflies – Descargador de Transcripción Completa
Uso: python3 fireflies_transcripcion.py
"""

import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime

# ──────────────────────────────────────────
# CONFIGURACIÓN  (podés editar estos valores)
# ──────────────────────────────────────────
API_KEY     = ""          # Dejá vacío para que te la pida al ejecutar
MEETING_URL = ""          # Dejá vacío para que te lo pida al ejecutar
OUTPUT_FILE = ""          # Dejá vacío para generar nombre automático
# ──────────────────────────────────────────


GRAPHQL_ENDPOINT = "https://api.fireflies.ai/graphql"

QUERY = """
query GetTranscript($id: String!) {
  transcript(id: $id) {
    id
    title
    date
    duration
    organizer_email
    sentences {
      index
      speaker_name
      text
      start_time
      end_time
    }
  }
}
"""


def extract_id(url: str) -> str | None:
    """Extrae el ID de la reunión desde la URL de Fireflies."""
    match = re.search(r"::([A-Za-z0-9]+)$", url)
    if match:
        return match.group(1)
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts[-1] else None


def format_time(ms: int | None) -> str:
    if ms is None:
        return ""
    total_sec = ms // 1000
    m, s = divmod(total_sec, 60)
    return f"{m:02d}:{s:02d}"


def fetch_transcript(api_key: str, transcript_id: str) -> dict:
    payload = json.dumps({"query": QUERY, "variables": {"id": transcript_id}}).encode()
    req = urllib.request.Request(
        GRAPHQL_ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def build_text(transcript: dict) -> str:
    lines = []

    title = transcript.get("title") or "Reunión sin título"
    date_raw = transcript.get("date")
    duration = transcript.get("duration")
    organizer = transcript.get("organizer_email", "")

    # Encabezado
    lines.append("=" * 60)
    lines.append(f"  {title}")
    lines.append("=" * 60)

    if date_raw:
        try:
            dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
            lines.append(f"Fecha:      {dt.strftime('%d/%m/%Y %H:%M')}")
        except Exception:
            lines.append(f"Fecha:      {date_raw}")

    if duration:
        lines.append(f"Duración:   {duration // 60} min")
    if organizer:
        lines.append(f"Organizador: {organizer}")

    lines.append("")

    sentences = sorted(transcript.get("sentences") or [], key=lambda s: s.get("index", 0))
    if not sentences:
        lines.append("(No hay oraciones en esta transcripción.)")
    else:
        for s in sentences:
            speaker = s.get("speaker_name") or "Desconocido"
            t = format_time(s.get("start_time"))
            text = s.get("text", "")
            lines.append(f"[{t}] {speaker}")
            lines.append(f"  {text}")
            lines.append("")

    return "\n".join(lines)


def main():
    api_key = API_KEY.strip()
    if not api_key:
        api_key = input("API Key de Fireflies: ").strip()

    meeting_url = MEETING_URL.strip()
    if not meeting_url:
        meeting_url = input("URL de la reunión: ").strip()

    transcript_id = extract_id(meeting_url)
    if not transcript_id:
        print("❌ No se pudo extraer el ID de la reunión desde la URL.")
        sys.exit(1)

    print(f"🔍 Obteniendo transcripción (ID: {transcript_id})...")

    try:
        data = fetch_transcript(api_key, transcript_id)
    except urllib.error.HTTPError as e:
        print(f"❌ Error HTTP {e.code}: {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        sys.exit(1)

    if "errors" in data and data["errors"]:
        msgs = "; ".join(e.get("message", str(e)) for e in data["errors"])
        print(f"❌ Error de API: {msgs}")
        sys.exit(1)

    transcript = data.get("data", {}).get("transcript")
    if not transcript:
        print("❌ No se encontró la transcripción. Verificá el ID o los permisos de la API key.")
        sys.exit(1)

    text = build_text(transcript)

    # Determinar nombre del archivo
    output = OUTPUT_FILE.strip()
    if not output:
        safe_title = re.sub(r"[^\w\s-]", "", transcript.get("title") or "transcripcion")
        safe_title = re.sub(r"\s+", "_", safe_title.strip())[:50]
        output = f"{safe_title}.txt"

    with open(output, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"✅ Transcripción guardada en: {output}")
    print(f"   {len(transcript.get('sentences') or [])} oraciones encontradas.")


if __name__ == "__main__":
    main()
