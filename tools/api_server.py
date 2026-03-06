#!/usr/bin/env python3
"""
Serenity Yoga — Backend API Server
Serves the website + stores leads and tracks clicks in SQLite.

Run:  python3 tools/api_server.py
Admin: http://localhost:3000/admin
"""

import json
import os
import sqlite3

from flask import Flask, jsonify, render_template_string, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, '.tmp', 'serenity.db')

app = Flask(__name__, static_folder=BASE_DIR)
app.config['JSON_SORT_KEYS'] = False


# ─── DATABASE ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS signups (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL,
            source     TEXT DEFAULT 'lead_magnet',
            ip         TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            event_type TEXT,
            element    TEXT,
            section    TEXT,
            ip         TEXT,
            metadata   TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
    ''')
    conn.commit()
    conn.close()


# ─── STATIC FILES ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'oldwebsite.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(BASE_DIR, path)


# ─── API ENDPOINTS ─────────────────────────────────────────────────────────────

@app.route('/api/signup', methods=['POST'])
def signup():
    data  = request.get_json() or {}
    name  = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    source = data.get('source', 'lead_magnet')

    if not name or not email or '@' not in email:
        return jsonify({'error': 'Valid name and email required'}), 400

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO signups (name, email, source, ip) VALUES (?, ?, ?, ?)',
            (name, email, source, request.remote_addr)
        )
        conn.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        # Duplicate email — still treat as success
        return jsonify({'success': True, 'note': 'already_registered'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/track', methods=['POST'])
def track():
    data = request.get_json() or {}
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO events (session_id, event_type, element, section, ip, metadata) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (
                data.get('session_id', ''),
                data.get('event_type', 'click'),
                data.get('element', ''),
                data.get('section', ''),
                request.remote_addr,
                json.dumps(data.get('metadata', {})),
            )
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ─── ADMIN DASHBOARD ──────────────────────────────────────────────────────────

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Serenity Admin</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #FAF5EE; color: #2C1A10; min-height: 100vh; }
  header { background: #3D2B1F; padding: 1.2rem 2.5rem;
           display: flex; align-items: center; justify-content: space-between; }
  header h1 { color: #C9A96E; font-size: 1.25rem; font-weight: 600; letter-spacing: 0.04em; }
  header span { color: rgba(255,255,255,0.4); font-size: 0.8rem; }
  .main { padding: 2rem 2.5rem; max-width: 1300px; margin: 0 auto; }
  .stats { display: flex; gap: 1.2rem; margin-bottom: 2.5rem; flex-wrap: wrap; }
  .stat-box { background: white; border-radius: 8px; padding: 1.4rem 1.8rem;
              box-shadow: 0 2px 12px rgba(44,26,16,0.07); flex: 1; min-width: 140px;
              border-top: 3px solid #C4614A; }
  .stat-box.gold { border-top-color: #C9A96E; }
  .stat-box.green { border-top-color: #7A9E7E; }
  .stat-box .num { font-size: 2.4rem; color: #C4614A; font-weight: 700; line-height: 1; }
  .stat-box.gold .num { color: #C9A96E; }
  .stat-box.green .num { color: #7A9E7E; }
  .stat-box .lbl { font-size: 0.72rem; color: #9A7A65; text-transform: uppercase;
                   letter-spacing: 0.12em; margin-top: 5px; }
  .section-hdr { display: flex; align-items: center; justify-content: space-between;
                 margin: 2.2rem 0 0.9rem; }
  .section-hdr h2 { font-size: 0.78rem; color: #8B6547; text-transform: uppercase;
                    letter-spacing: 0.2em; font-weight: 700; }
  .refresh-btn { background: #C4614A; color: white; border: none; padding: 0.45rem 1rem;
                 border-radius: 4px; cursor: pointer; font-size: 0.78rem; font-weight: 600; }
  .refresh-btn:hover { background: #A34A36; }
  .export-btn { background: #C9A96E; color: white; border: none; padding: 0.45rem 1rem;
                border-radius: 4px; cursor: pointer; font-size: 0.78rem; font-weight: 600; text-decoration: none; }
  table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px;
          overflow: hidden; box-shadow: 0 2px 12px rgba(44,26,16,0.07); margin-bottom: 2rem; }
  th { background: #3D2B1F; color: rgba(255,255,255,0.85); padding: 0.8rem 1rem;
       text-align: left; font-size: 0.72rem; letter-spacing: 0.1em; text-transform: uppercase;
       font-weight: 600; }
  td { padding: 0.72rem 1rem; border-bottom: 1px solid #F5EDE0; font-size: 0.87rem; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #FAF5EE; }
  .badge { display: inline-block; padding: 0.22rem 0.65rem; border-radius: 20px;
           font-size: 0.7rem; font-weight: 700; }
  .bg-green { background: #E8F5E9; color: #2E7D32; }
  .bg-gold  { background: #FFF8E1; color: #B8860B; }
  .bg-red   { background: #FFF0F0; color: #C62828; }
  .empty { color: #9A7A65; font-style: italic; text-align: center; padding: 2rem; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  @media (max-width: 768px) { .grid2 { grid-template-columns: 1fr; } .main { padding: 1.5rem; } }
</style>
</head>
<body>
<header>
  <h1>🌿 Serenity Admin Dashboard</h1>
  <span>localhost:3000/admin</span>
</header>
<div class="main">

  <div class="stats">
    <div class="stat-box">
      <div class="num">{{ total_signups }}</div>
      <div class="lbl">Total Leads</div>
    </div>
    <div class="stat-box gold">
      <div class="num">{{ total_clicks }}</div>
      <div class="lbl">Total Clicks</div>
    </div>
    <div class="stat-box green">
      <div class="num">{{ total_sessions }}</div>
      <div class="lbl">Unique Sessions</div>
    </div>
    <div class="stat-box gold">
      <div class="num">{{ whatsapp_clicks }}</div>
      <div class="lbl">WhatsApp Taps</div>
    </div>
  </div>

  <!-- LEADS TABLE -->
  <div class="section-hdr">
    <h2>📋 Leads / Signups</h2>
    <div style="display:flex;gap:0.5rem;">
      <a href="/api/export/signups" class="export-btn">⬇ Export CSV</a>
      <button class="refresh-btn" onclick="location.reload()">↻ Refresh</button>
    </div>
  </div>
  <table>
    <thead><tr><th>#</th><th>Name</th><th>Email</th><th>Source</th><th>Date &amp; Time</th></tr></thead>
    <tbody>
    {% for s in signups %}
    <tr>
      <td>{{ s['id'] }}</td>
      <td><strong>{{ s['name'] }}</strong></td>
      <td>{{ s['email'] }}</td>
      <td><span class="badge bg-green">{{ s['source'] }}</span></td>
      <td>{{ s['created_at'] }}</td>
    </tr>
    {% else %}
    <tr><td colspan="5" class="empty">No signups yet — share the page!</td></tr>
    {% endfor %}
    </tbody>
  </table>

  <div class="grid2">
    <!-- CLICK SUMMARY -->
    <div>
      <div class="section-hdr"><h2>🖱️ Click Analytics</h2></div>
      <table>
        <thead><tr><th>Button / CTA</th><th>Section</th><th>Clicks</th></tr></thead>
        <tbody>
        {% for c in click_summary %}
        <tr>
          <td>{{ c['element'] }}</td>
          <td>{{ c['section'] or '—' }}</td>
          <td><span class="badge bg-gold">{{ c['count'] }}</span></td>
        </tr>
        {% else %}
        <tr><td colspan="3" class="empty">No clicks tracked yet</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>

    <!-- RECENT ACTIVITY -->
    <div>
      <div class="section-hdr"><h2>⏱️ Recent Activity</h2></div>
      <table>
        <thead><tr><th>Time</th><th>Event</th><th>Element</th></tr></thead>
        <tbody>
        {% for e in recent_events %}
        <tr>
          <td style="font-size:0.78rem;color:#9A7A65;">{{ e['created_at'] }}</td>
          <td><span class="badge {% if e['event_type']=='signup' %}bg-green{% else %}bg-gold{% endif %}">
            {{ e['event_type'] }}</span></td>
          <td>{{ e['element'] or '—' }}</td>
        </tr>
        {% else %}
        <tr><td colspan="3" class="empty">No activity yet</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

</div>
</body>
</html>"""


@app.route('/admin')
def admin():
    conn = get_db()
    signups      = conn.execute('SELECT * FROM signups ORDER BY created_at DESC').fetchall()
    click_summary = conn.execute('''
        SELECT element, section, COUNT(*) as count
        FROM events WHERE event_type = 'click'
        GROUP BY element, section ORDER BY count DESC
    ''').fetchall()
    recent_events = conn.execute(
        'SELECT * FROM events ORDER BY created_at DESC LIMIT 60'
    ).fetchall()
    total_signups  = conn.execute('SELECT COUNT(*) FROM signups').fetchone()[0]
    total_clicks   = conn.execute("SELECT COUNT(*) FROM events WHERE event_type='click'").fetchone()[0]
    total_sessions = conn.execute('SELECT COUNT(DISTINCT session_id) FROM events WHERE session_id != ""').fetchone()[0]
    whatsapp_clicks = conn.execute(
        "SELECT COUNT(*) FROM events WHERE element LIKE '%whatsapp%'"
    ).fetchone()[0]
    conn.close()

    return render_template_string(
        ADMIN_HTML,
        signups=signups, click_summary=click_summary, recent_events=recent_events,
        total_signups=total_signups, total_clicks=total_clicks,
        total_sessions=total_sessions, whatsapp_clicks=whatsapp_clicks
    )


@app.route('/api/export/signups')
def export_signups():
    conn = get_db()
    rows = conn.execute('SELECT id, name, email, source, created_at FROM signups ORDER BY created_at DESC').fetchall()
    conn.close()
    lines = ['id,name,email,source,created_at']
    for r in rows:
        lines.append(f'{r["id"]},"{r["name"]}",{r["email"]},{r["source"]},{r["created_at"]}')
    from flask import Response
    return Response('\n'.join(lines), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=serenity_leads.csv'})


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print('\n🌿  Serenity Yoga — Server started')
    print('    Website  →  http://localhost:3000')
    print('    Admin    →  http://localhost:3000/admin\n')
    app.run(host='0.0.0.0', port=3000, debug=False)
