import json, os, socket
PORT = int(os.environ.get('PORT', 8080))
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, unquote

ROUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rounds")
DASHBOARD_KEY = "bs2026"

def get_round_dir(round_name):
    d = os.path.join(ROUNDS_DIR, round_name)
    return d if os.path.isdir(d) else None

def load_subs(round_name):
    f = os.path.join(ROUNDS_DIR, round_name, "data", "submissions.json")
    if os.path.exists(f):
        with open(f, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return []

def save_subs(round_name, data):
    d = os.path.join(ROUNDS_DIR, round_name, "data")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "submissions.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_skin_images(round_name):
    img_dir = os.path.join(ROUNDS_DIR, round_name, "images")
    if not os.path.isdir(img_dir):
        return {}
    imgs = {}
    for f in sorted(os.listdir(img_dir)):
        if f.lower().endswith(('.png','.jpg','.jpeg','.gif','.webp')):
            name = f.rsplit('-', 1)[0]
            if name not in imgs:
                imgs[name] = f
    return imgs

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f0f2f5;display:flex;align-items:center;justify-content:center;min-height:100vh}
.box{background:#fff;padding:40px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.1);text-align:center;max-width:360px;width:90%}
.box h2{font-size:20px;font-weight:500;margin-bottom:8px}
.box p{font-size:14px;color:#5f6368;margin-bottom:20px}
.box input{width:100%;padding:12px 16px;font-size:16px;border:1px solid #dadce0;border-radius:8px;outline:none;text-align:center;margin-bottom:16px}
.box input:focus{border-color:#1a73e8;box-shadow:0 0 0 3px rgba(26,115,232,.12)}
.box button{background:#1a73e8;color:#fff;border:none;padding:12px 32px;font-size:15px;border-radius:8px;cursor:pointer}
.box button:hover{background:#1557b0}
.err{color:#d93025;font-size:13px;margin-top:8px;display:none}
</style>
</head>
<body>
<div class="box">
<h2>Dashboard Access</h2>
<p>Enter the access key</p>
<input type="password" id="pw" placeholder="Access key" autofocus>
<button onclick="go()">View Dashboard</button>
<p class="err" id="err">Incorrect access key</p>
</div>
<script>
document.getElementById("pw").addEventListener("keydown",function(e){if(e.key==="Enter")go()});
function go(){var p=document.getElementById("pw").value;if(p)window.location.href=window.location.pathname+"?k="+encodeURIComponent(p)}
(function(){if(location.search.indexOf("k=wrong")>-1)document.getElementById("err").style.display="block"})();
</script>
</body>
</html>"""

class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2 and parts[1] == "api" and parts[2] == "submit":
            round_name = parts[0]
            if not get_round_dir(round_name):
                self.send_response(404); self.end_headers(); return
            cl = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(cl)
            sub = json.loads(body)
            subs = load_subs(round_name)
            subs.append(sub)
            save_subs(round_name, subs)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "total": len(subs)}).encode())
        else:
            self.send_response(404); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")

        # Dashboard
        if len(parts) >= 2 and parts[1] == "dashboard":
            round_name = parts[0]
            if not get_round_dir(round_name):
                self.send_response(404); self.end_headers(); return
            qs = parse_qs(parsed.query)
            key = qs.get("k", [""])[0]
            if key != DASHBOARD_KEY:
                if key:
                    self.send_response(302)
                    self.send_header("Location", "/" + round_name + "/dashboard?k=wrong")
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(LOGIN_PAGE.encode("utf-8"))
                return
            html = build_dashboard(round_name, key)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        # API: submissions
        elif len(parts) >= 2 and parts[1] == "api" and parts[2] == "submissions":
            round_name = parts[0]
            subs = load_subs(round_name)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(subs, ensure_ascii=False).encode())

        # Root: show round list linking to dashboards
        elif parsed.path == "/" or parsed.path == "":
            rlist = sorted([d for d in os.listdir(ROUNDS_DIR) if os.path.isdir(os.path.join(ROUNDS_DIR, d))], reverse=True)
            links = ""
            for r in rlist:
                links += '<a href="/{0}/dashboard?k={1}">{0} &rarr; Dashboard</a>'.format(r, DASHBOARD_KEY)
            if not links:
                links = "<p>No rounds yet</p>"
            html = '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Survey Rounds</title><style>body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f0f2f5;padding:40px;text-align:center}h1{font-weight:500;margin-bottom:24px}a{display:inline-block;margin:8px;padding:16px 32px;background:#fff;border-radius:12px;text-decoration:none;color:#1a73e8;font-size:18px;box-shadow:0 1px 3px rgba(0,0,0,.08)}a:hover{box-shadow:0 4px 12px rgba(0,0,0,.12)}</style></head><body><h1>Survey Rounds</h1>' + links + '</body></html>'
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        # Serve static files
        else:
            round_name = parts[0]
            rd = get_round_dir(round_name)
            if rd:
                file_path = unquote("/".join(parts[1:])) or "index.html"
                full = os.path.join(rd, file_path)
                if os.path.isfile(full) and os.path.commonpath([rd, os.path.abspath(full)]) == os.path.abspath(rd):
                    if file_path == "index.html":
                        with open(full, "r", encoding="utf-8") as f:
                            content = f.read()
                        content = content.replace('"/api/submit"', '"/' + round_name + '/api/submit"')
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(content.encode("utf-8"))
                        return
                    ct = "application/octet-stream"
                    if full.endswith(".png"): ct = "image/png"
                    elif full.endswith((".jpg",".jpeg")): ct = "image/jpeg"
                    elif full.endswith(".gif"): ct = "image/gif"
                    elif full.endswith(".webp"): ct = "image/webp"
                    elif full.endswith(".css"): ct = "text/css"
                    elif full.endswith(".js"): ct = "application/javascript"
                    elif full.endswith(".html"): ct = "text/html"
                    with open(full, "rb") as fimg:
                        data = fimg.read()
                    self.send_response(200)
                    self.send_header("Content-Type", ct)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
            super().do_GET()

def build_dashboard(round_name, key):
    subs = load_subs(round_name)
    skin_imgs = get_skin_images(round_name)
    total = len(subs)
    if total == 0:
        return '<html><body style="font-family:sans-serif;padding:40px;text-align:center"><h2>No submissions yet</h2><p>Waiting for survey responses for <b>' + round_name + '</b>...</p><meta http-equiv="refresh" content="20"></body></html>'

    skin_scores = {}; skin_counts = {}
    countries = {}; playtimes = {}; spendings = {}
    for s in subs:
        for r in s.get("ratings", []):
            n = r["theme"]
            skin_scores[n] = skin_scores.get(n, 0) + r["rating"]
            skin_counts[n] = skin_counts.get(n, 0) + 1
        c = s.get("country", "Unknown"); countries[c] = countries.get(c, 0) + 1
        p = s.get("playtime", "Unknown"); playtimes[p] = playtimes.get(p, 0) + 1
        sp = s.get("spending", "Unknown"); spendings[sp] = spendings.get(sp, 0) + 1

    pl = {"less-1m":"<1m","1-3m":"1-3m","3-6m":"3-6m","6-12m":"6-12m","1-2y":"1-2y","2y-plus":">2y"}
    sl = {"0":"$0","1-10":"$1-10","11-50":"$11-50","51-100":"$51-100","101-500":"$101-500","500-plus":">$500"}

    ranked = sorted(skin_scores.items(), key=lambda x: -skin_scores[x[0]]/skin_counts[x[0]])
    
    def thumb_cell(name):
        img = skin_imgs.get(name, "")
        if not img:
            for k, v in skin_imgs.items():
                if k.lower() == name.lower():
                    img = v
                    break
        if img:
            return '<td><img src="/{0}/images/{1}" style="width:60px;height:40px;object-fit:contain;border-radius:4px" alt=""></td>'.format(round_name, img)
        return '<td></td>'

    rank_rows = ""
    for i, (n, _) in enumerate(ranked):
        rank_rows += '<tr>' + thumb_cell(n) + '<td>{0}</td><td>{1}</td><td><b>{2:.2f}</b></td><td>{3}</td></tr>'.format(i+1, n, skin_scores[n]/skin_counts[n], skin_counts[n])

    detail_rows = ""
    for n in sorted(skin_scores):
        avg = skin_scores[n]/skin_counts[n]
        stars = "&#9733;"*round(avg) + "&#9734;"*(5-round(avg))
        detail_rows += '<tr>' + thumb_cell(n) + '<td>{0}</td><td><b>{1:.2f}</b></td><td class="stars">{2}</td><td>{3}</td></tr>'.format(n, avg, stars, skin_counts[n])

    country_rows = ""
    for c, n in sorted(countries.items(), key=lambda x: -x[1]):
        country_rows += '<tr><td>{0}</td><td>{1}</td><td>{2:.1f}%</td></tr>'.format(c, n, n/total*100)

    pt_rows = ""
    for k in pl:
        n = playtimes.get(k, 0)
        pt_rows += '<tr><td>{0}</td><td>{1}</td><td>{2:.1f}%</td></tr>'.format(pl[k], n, n/total*100 if total else 0)

    sp_rows = ""
    for k in sl:
        n = spendings.get(k, 0)
        sp_rows += '<tr><td>{0}</td><td>{1}</td><td>{2:.1f}%</td></tr>'.format(sl[k], n, n/total*100 if total else 0)

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard — {round}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f0f2f5;color:#202124;padding:24px}}
h1{{font-size:24px;font-weight:500;margin-bottom:4px}}
.sub{{color:#5f6368;font-size:14px;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;max-width:1100px}}
.card{{background:#fff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);overflow:hidden}}
.card h2{{font-size:16px;font-weight:500;padding:16px 20px;border-bottom:1px solid #e0e0e0}}
.card table{{width:100%;border-collapse:collapse}}
.card th,.card td{{padding:10px 12px;text-align:left;font-size:14px;border-bottom:1px solid #f0f0f0}}
.card th{{font-weight:500;color:#5f6368;font-size:12px;text-transform:uppercase;letter-spacing:.5px}}
.full{{grid-column:1/-1}}
.stars{{color:#f9ab00;font-size:16px;letter-spacing:2px}}
@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}
</style>
<meta http-equiv="refresh" content="30">
</head>
<body>
<h1>Dashboard — {round}</h1>
<p class="sub">Total submissions: <strong>{total}</strong> | Auto-refreshes every 30s</p>
<div class="grid">
<div class="card full"><h2>Skin Rankings</h2><table><tr><th></th><th>#</th><th>Theme</th><th>Avg</th><th>N</th></tr>{rank_rows}</table></div>
<div class="card full"><h2>Detailed Ratings</h2><table><tr><th></th><th>Theme</th><th>Avg</th><th>Distribution</th><th>N</th></tr>{detail_rows}</table></div>
<div class="card"><h2>Country / Region</h2><table><tr><th>Country</th><th>Count</th><th>%</th></tr>{country_rows}</table></div>
<div class="card"><h2>Playtime</h2><table><tr><th>Duration</th><th>Count</th><th>%</th></tr>{pt_rows}</table></div>
<div class="card"><h2>Spending</h2><table><tr><th>Amount</th><th>Count</th><th>%</th></tr>{sp_rows}</table></div>
</div></body></html>""".format(round=round_name, total=total, rank_rows=rank_rows, detail_rows=detail_rows, country_rows=country_rows, pt_rows=pt_rows, sp_rows=sp_rows)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    srv.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print(f"http://0.0.0.0:{PORT}/")
    srv.serve_forever()