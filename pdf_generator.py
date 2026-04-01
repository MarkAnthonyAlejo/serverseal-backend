from __future__ import annotations
import base64
import io
import os
from datetime import datetime, timezone
from weasyprint import HTML
from PIL import Image
import qrcode


def _encode_image(file_path: str, max_width: int = 800) -> str | None:
    """Resize and base64-encode a local image for embedding in HTML."""
    try:
        with Image.open(file_path) as img:
            img = img.convert('RGB')
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=75)
            return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()
    except Exception:
        return None


def _fmt(ts: str | None) -> str:
    if not ts:
        return '—'
    try:
        dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        return dt.strftime('%b %d, %Y  %I:%M %p')
    except Exception:
        return str(ts)


def _generate_qr_dataurl(shipment_id: str) -> str:
    """Generate a QR code encoding the shipment URL and return as a base64 PNG data URL."""
    app_url = os.environ.get('APP_URL', 'http://localhost:5173')
    url = f"{app_url}/shipments/{shipment_id}"
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()


def _disposition_color(d: str | None) -> str:
    if not d:
        return '#666'
    return {'Pass': '#00ff88', 'Conditional': '#e8ff00',
            'Fail': '#ff3333', 'QA Hold': '#ff3333'}.get(d, '#666')


def _item_disposition_color(d: str | None) -> str:
    if not d:
        return '#666'
    return {'Pass': '#00ff88', 'Fail': '#ff3333'}.get(d, '#ff9900')


def generate_report(shipment_data: dict, inspection_data: dict | None) -> bytes:
    """Renders the chain-of-custody PDF and returns raw bytes."""
    shipment       = shipment_data['shipment']
    events         = shipment_data['history']
    status_history = shipment_data['status_history']
    generated_at   = datetime.now(timezone.utc).strftime('%b %d, %Y  %I:%M %p UTC')
    qr_dataurl     = _generate_qr_dataurl(str(shipment.get('shipment_id', '')))

    # ── Status timeline rows ─────────────────────────────────────────
    timeline_rows = ''.join(
        f'<tr>'
        f'<td class="mono">{e["status"].upper().replace(" ", "_")}</td>'
        f'<td class="mono muted">{_fmt(e.get("changed_at"))}</td>'
        f'</tr>'
        for e in status_history
    )

    # ── QA Inspection section ────────────────────────────────────────
    qa_section = ''
    if inspection_data:
        verdict_color = _disposition_color(inspection_data.get('overall_disposition'))
        checklist_rows = ''.join(
            f'<tr>'
            f'<td class="mono">{item.get("serial_number") or "—"}</td>'
            f'<td class="mono muted">{item.get("manufacturer") or "—"}</td>'
            f'<td class="mono muted">{item.get("model") or "—"}</td>'
            f'<td class="mono" style="text-align:center">{item.get("quantity", 1)}</td>'
            f'<td class="mono" style="color:{"#00ff88" if item.get("visual_condition") == "Pass" else "#ff3333" if item.get("visual_condition") == "Fail" else "#666"}">'
            f'{item.get("visual_condition") or "—"}</td>'
            f'<td class="mono" style="color:{"#00ff88" if item.get("packaging_condition") == "Pass" else "#ff3333" if item.get("packaging_condition") == "Fail" else "#666"}">'
            f'{item.get("packaging_condition") or "—"}</td>'
            f'<td class="mono" style="color:{_item_disposition_color(item.get("disposition"))}">'
            f'{item.get("disposition") or "—"}</td>'
            f'<td class="mono muted small">{item.get("damage_notes") or "—"}</td>'
            f'</tr>'
            for item in (inspection_data.get('items') or [])
        )

        checklist_table = f'''
        <table>
          <thead>
            <tr>
              <th>SERIAL #</th><th>MANUFACTURER</th><th>MODEL</th>
              <th>QTY</th><th>VISUAL</th><th>PACKAGING</th><th>DISPOSITION</th><th>NOTES</th>
            </tr>
          </thead>
          <tbody>{checklist_rows if checklist_rows else '<tr><td colspan="8" class="muted mono" style="text-align:center;padding:12px">No checklist items recorded.</td></tr>'}</tbody>
        </table>
        ''' if True else ''

        qa_notes = f'<p class="mono muted small" style="margin-top:8px">{inspection_data["notes"]}</p>' if inspection_data.get('notes') else ''

        qa_section = f'''
        <div class="section">
          <div class="section-header">QA_INSPECTION</div>
          <div class="info-grid">
            <div class="info-item">
              <div class="info-label">ASSIGNED INSPECTOR</div>
              <div class="info-value mono">{inspection_data.get("assigned_qa_email", "—")}</div>
            </div>
            <div class="info-item">
              <div class="info-label">INSPECTION STATUS</div>
              <div class="info-value mono">{inspection_data.get("status", "—").upper()}</div>
            </div>
            <div class="info-item">
              <div class="info-label">VERDICT</div>
              <div class="info-value mono" style="color:{verdict_color}; font-weight:bold">
                {(inspection_data.get("overall_disposition") or "PENDING").upper()}
              </div>
            </div>
            <div class="info-item">
              <div class="info-label">COMPLETED</div>
              <div class="info-value mono">{_fmt(inspection_data.get("completed_at"))}</div>
            </div>
          </div>
          {qa_notes}
          <div style="margin-top:16px">
            <div class="subsection-label">CHECKLIST // {len(inspection_data.get("items") or [])} UNIT(S)</div>
            {checklist_table}
          </div>
        </div>
        '''

    # ── Event log ────────────────────────────────────────────────────
    event_blocks = []
    for idx, event in enumerate(events):
        all_media = event.get('evidence_photos') or []
        signatures = [p for p in all_media if p.get('type') == 'signature']
        photos = [p for p in all_media if p.get('type') != 'signature']

        photos_html = ''
        encoded = []
        for p in photos:
            src = _encode_image(p.get('path', ''))
            if src:
                encoded.append(f'<img src="{src}" class="photo" />')
        if encoded:
            photos_html = f'<div class="photo-grid">{"".join(encoded)}</div>'

        sig_html = ''
        if signatures:
            sig_src = _encode_image(signatures[0].get('path', ''))
            if sig_src:
                sig_html = f'''
                <div class="signature-block">
                  <div class="subsection-label" style="margin-bottom:6px">DELIVERY_SIGNATURE</div>
                  <img src="{sig_src}" class="signature-img" />
                </div>'''

        event_blocks.append(f'''
        <div class="event-card {"page-break-before" if idx > 0 and idx % 4 == 0 else ""}">
          <div class="event-header">
            <span class="mono event-type">{event.get("event_type", "").upper()}</span>
            <span class="mono muted small">{_fmt(event.get("created_at"))}</span>
          </div>
          <div class="event-meta">
            {"<span class='meta-item'><span class='meta-label'>LOCATION</span> " + str(event.get("location") or "") + "</span>" if event.get("location") else ""}
            {"<span class='meta-item'><span class='meta-label'>HARDWARE</span> " + str(event.get("hardware_details") or "") + "</span>" if event.get("hardware_details") else ""}
          </div>
          {"<p class='event-notes mono muted small'>" + str(event.get("notes") or "") + "</p>" if event.get("notes") else ""}
          {sig_html}
          {photos_html}
        </div>
        ''')

    events_html = ''.join(event_blocks) if event_blocks else '<p class="mono muted" style="padding:16px">No events recorded.</p>'

    # ── Full HTML document ───────────────────────────────────────────
    html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;600&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: #ffffff;
    color: #111111;
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 11px;
    line-height: 1.5;
  }}

  .mono  {{ font-family: 'IBM Plex Mono', monospace; }}
  .muted {{ color: #666666; }}
  .small {{ font-size: 9px; }}

  /* ── Page header ── */
  .page-header {{
    background: #0a0a0a;
    color: #e8ff00;
    padding: 20px 32px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }}
  .page-header .brand {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 22px;
    font-weight: 500;
    letter-spacing: 0.15em;
  }}
  .page-header .report-meta {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 8px;
    color: #888;
    text-align: right;
    line-height: 1.8;
  }}

  /* ── Shipment title bar ── */
  .shipment-bar {{
    background: #f5f5f5;
    border-bottom: 2px solid #e8ff00;
    padding: 16px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .shipment-bar .bol {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 28px;
    font-weight: 500;
    color: #0a0a0a;
    letter-spacing: -0.02em;
  }}
  .shipment-bar .route {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: #444;
    margin-top: 4px;
  }}
  .status-badge {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    border: 1px solid #0a0a0a;
    padding: 4px 10px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
  }}

  /* ── Content area ── */
  .content {{ padding: 24px 32px; }}

  /* ── Sections ── */
  .section {{ margin-bottom: 28px; }}
  .section-header {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 8px;
    font-weight: 500;
    letter-spacing: 0.25em;
    color: #ffffff;
    background: #0a0a0a;
    padding: 5px 10px;
    margin-bottom: 12px;
    text-transform: uppercase;
  }}
  .subsection-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 8px;
    letter-spacing: 0.2em;
    color: #666;
    text-transform: uppercase;
    margin-bottom: 8px;
  }}

  /* ── Info grid ── */
  .info-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 4px;
  }}
  .info-item {{ padding: 8px 0; border-top: 1px solid #e0e0e0; }}
  .info-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 7px;
    color: #999;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 3px;
  }}
  .info-value {{
    font-size: 11px;
    color: #111;
  }}

  /* ── Tables ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 9px;
  }}
  th {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 7px;
    letter-spacing: 0.15em;
    color: #999;
    text-transform: uppercase;
    text-align: left;
    padding: 6px 8px;
    border-bottom: 1px solid #ddd;
    background: #fafafa;
  }}
  td {{
    padding: 6px 8px;
    border-bottom: 1px solid #f0f0f0;
    vertical-align: top;
  }}
  tr:last-child td {{ border-bottom: none; }}

  /* ── Event cards ── */
  .event-card {{
    border: 1px solid #e0e0e0;
    margin-bottom: 12px;
    padding: 12px 14px;
  }}
  .event-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }}
  .event-type {{
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.1em;
    color: #0a0a0a;
  }}
  .event-meta {{
    display: flex;
    gap: 16px;
    margin-bottom: 4px;
  }}
  .meta-item {{ font-size: 9px; color: #444; }}
  .meta-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 7px;
    letter-spacing: 0.15em;
    color: #999;
    text-transform: uppercase;
    margin-right: 4px;
  }}
  .event-notes {{ margin-top: 4px; color: #555; }}

  /* ── Photos ── */
  .photo-grid {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
  }}
  .photo {{
    width: 180px;
    height: 135px;
    object-fit: cover;
    border: 1px solid #e0e0e0;
  }}

  /* ── Signature ── */
  .signature-block {{
    margin-top: 10px;
    padding: 8px;
    border: 1px solid #ccc;
    display: inline-block;
  }}
  .signature-img {{
    height: 60px;
    width: auto;
    display: block;
  }}

  /* ── Footer ── */
  .page-footer {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #f5f5f5;
    border-top: 1px solid #ddd;
    padding: 6px 32px;
    display: flex;
    justify-content: space-between;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 7px;
    color: #999;
    letter-spacing: 0.1em;
  }}

  .page-break-before {{ page-break-before: always; }}

  @page {{
    margin: 0 0 28px 0;
    size: A4;
  }}
</style>
</head>
<body>

<!-- Page header -->
<div class="page-header">
  <div>
    <div class="brand">SERVERSEAL</div>
    <div class="mono small" style="color:#666;margin-top:3px;letter-spacing:0.15em">
      CHAIN_OF_CUSTODY_REPORT
    </div>
  </div>
  <div class="report-meta">
    GENERATED: {generated_at}<br/>
    DOC_TYPE: CHAIN_OF_CUSTODY<br/>
    STATUS: OFFICIAL_RECORD
  </div>
</div>

<!-- Shipment title bar -->
<div class="shipment-bar">
  <div>
    <div class="bol">{shipment.get("bol_number", "")}</div>
    <div class="route">
      {shipment.get("origin", "")} &nbsp;›&nbsp; {shipment.get("destination", "")}
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <div class="status-badge">{shipment.get("status", "").upper().replace(" ", "_")}</div>
    <div style="text-align:center">
      <img src="{qr_dataurl}" style="width:64px;height:64px;display:block;border:1px solid #ddd" />
      <div style="font-family:'IBM Plex Mono',monospace;font-size:6px;color:#999;letter-spacing:0.1em;margin-top:2px">SCAN_TO_VIEW</div>
    </div>
  </div>
</div>

<!-- Content -->
<div class="content">

  <!-- Shipment info -->
  <div class="section">
    <div class="section-header">SHIPMENT_DETAILS</div>
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">BOL NUMBER</div>
        <div class="info-value mono">{shipment.get("bol_number", "—")}</div>
      </div>
      <div class="info-item">
        <div class="info-label">ORIGIN</div>
        <div class="info-value">{shipment.get("origin", "—")}</div>
      </div>
      <div class="info-item">
        <div class="info-label">DESTINATION</div>
        <div class="info-value">{shipment.get("destination", "—")}</div>
      </div>
      <div class="info-item">
        <div class="info-label">INITIATED</div>
        <div class="info-value mono">{_fmt(shipment.get("created_at"))}</div>
      </div>
    </div>
  </div>

  <!-- Status timeline -->
  <div class="section">
    <div class="section-header">STATUS_TIMELINE</div>
    <table>
      <thead>
        <tr><th>STATUS</th><th>TIMESTAMP</th></tr>
      </thead>
      <tbody>{timeline_rows}</tbody>
    </table>
  </div>

  <!-- QA Inspection (if exists) -->
  {qa_section}

  <!-- Chain of custody events -->
  <div class="section">
    <div class="section-header">CHAIN_OF_CUSTODY // EVENT_LOG</div>
    {events_html}
  </div>

</div>

<!-- Footer -->
<div class="page-footer">
  <span>SERVERSEAL // CHAIN_OF_CUSTODY_REPORT // {shipment.get("bol_number", "")}</span>
  <span>CONFIDENTIAL — FOR AUTHORIZED USE ONLY</span>
</div>

</body>
</html>'''

    return HTML(string=html).write_pdf()
