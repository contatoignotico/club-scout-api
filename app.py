import os, uuid, time, re, random
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, send_from_directory
import pandas as pd

app = Flask(__name__)

EXPORT_DIR = "/tmp/exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+(?:\s*\[at\]\s*|\s*@\s*|\s*AT\s*|@)"
    r"[a-zA-Z0-9.-]+(?:\s*\[dot\]\s*|\s*\.\s*|\s*DOT\s*|\.)[a-zA-Z]{2,}",
    re.IGNORECASE
)
CONTACT_HINTS = ["contact", "contato", "kontakt", "kontakte", "contacto", "impressum", "contatti", "fale", "about"]
PRIORITY = ["marketing", "media", "press", "comunic", "comercial", "secretaria", "geral", "info", "contato"]

def normalize_email(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"\[at\]|\(at\)|\sat\s|AT", "@", s, flags=re.I)
    s = re.sub(r"\[dot\]|\(dot\)|\sdot\s|DOT", ".", s, flags=re.I)
    return s

def fetch(url, timeout=15):
    for _ in range(2):
        try:
            r = SESSION.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            time.sleep(1.2)
    return None

def absolute(base, href):
    try:
        return urljoin(base, href)
    except Exception:
        return href

def unique(seq):
    seen = set(); out = []
    for x in seq:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out

def list_club_urls(league_url: str):
    html = fetch(league_url)
    if not html: return []
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.select("a[href*='/verein/']"):
        href = a.get("href")
        if href and "/verein/" in href:
            full = absolute(league_url, href)
            if "transfermarkt" in urlparse(full).netloc.lower():
                links.append(full.split("?")[0])
    return unique(links)

def get_club_info_from_tm(club_url: str):
    """Return (club_name, country, official_site) from Transfermarkt club page."""
    html = fetch(club_url)
    if not html: return (None, None, None)
    soup = BeautifulSoup(html, "lxml")

    # club name
    club_name = None
    h1 = soup.find("h1")
    if h1: club_name = h1.get_text(strip=True)

    # country (best effort)
    country = None
    ctry_anchor = soup.select_one("a[data-country]")
    if ctry_anchor:
        country = ctry_anchor.get_text(strip=True)

    # official site: heuristic — link with text 'website'/'official' OR first external link
    official = None
    for a in soup.select("a[href^='http']"):
        href = a.get("href", "")
        host = urlparse(href).netloc.lower()
        if "transfermarkt" in host: 
            continue
        text = (a.get_text() or "").lower()
        if "website" in text or "official" in text or "site" in text:
            official = href; break
    if not official:
        for a in soup.select("a[href^='http']"):
            href = a.get("href", "")
            host = urlparse(href).netloc.lower()
            if "transfermarkt" not in host:
                official = href; break

    return (club_name, country, official)

def find_contact_page(base_url: str, soup: BeautifulSoup):
    # 1) anchors with hint
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = (a.get_text() or "").strip().lower()
        if any(h in text for h in CONTACT_HINTS) or any(h in href.lower() for h in CONTACT_HINTS):
            return absolute(base_url, href)
    # 2) common paths
    parsed = urlparse(base_url)
    roots = [f"{parsed.scheme}://{parsed.netloc}/{h}" for h in CONTACT_HINTS]
    for r in roots:
        if fetch(r):
            return r
    return None

def extract_emails_and_ig(url: str):
    html = fetch(url)
    if not html: 
        return [], None, None
    soup = BeautifulSoup(html, "lxml")

    # emails in the page text
    raw = EMAIL_RE.findall(html)
    emails = unique([normalize_email(e) for e in raw])

    # instagram
    ig = None
    for a in soup.select("a[href*='instagram.com']"):
        ig = a.get("href")
        break

    # best contact page
    contact = find_contact_page(url, soup)
    if contact and contact != url:
        html2 = fetch(contact)
        if html2:
            raw2 = EMAIL_RE.findall(html2)
            emails += [normalize_email(e) for e in raw2]
            emails = unique(emails)
            if not ig:
                soup2 = BeautifulSoup(html2, "lxml")
                a2 = soup2.select_one("a[href*='instagram.com']")
                if a2: ig = a2.get("href")

    # sort by priority
    def score(e):
        le = e.lower()
        return min([le.find(k) if k in le else 99 for k in PRIORITY])
    emails = sorted(emails, key=score)

    return emails, ig, contact

@app.route("/")
def home():
    return "Club Scout API is running!"

@app.route("/coletar", methods=["POST"])
def coletar():
    data = request.get_json(force=True) if request.data else {}
    league_name = data.get("league_name", "Liga Desconhecida")
    league_url  = data.get("league_url")
    max_clubs   = int(data.get("max_clubs", 20))  # limite para testes

    if not league_url:
        return jsonify({"error": "Forneça 'league_url' do Transfermarkt para coleta real."}), 400

    clubs_urls = list_club_urls(league_url)[:max_clubs]
    rows = []
    for i, club_url in enumerate(clubs_urls, 1):
        time.sleep(random.uniform(0.6, 1.2))  # respeito básico aos sites
        club_name, country, official = get_club_info_from_tm(club_url)

        emails_joined, ig, contact_url = ([], None, None)
        if official:
            emails, ig, contact_url = extract_emails_and_ig(official)
            emails_joined = ", ".join(emails) if emails else "N/A"

        rows.append({
            "league": league_name,
            "club_name": club_name or "N/A",
            "country": country or "N/A",
            "official_website": official or "N/A",
            "contact_page": contact_url or "N/A",
            "emails_found": emails_joined if emails_joined else "N/A",
            "instagram": ig or "N/A",
        })

    df = pd.DataFrame(rows).fillna("N/A")

    token = uuid.uuid4().hex[:10]
    safe_league = (league_name or "liga").replace(" ", "_").lower()
    filename = f"leads_{safe_league}_{token}.xlsx"
    filepath = os.path.join(EXPORT_DIR, filename)
    df.to_excel(filepath, index=False)

    base = request.url_root.rstrip("/")
    download_url = f"{base}/download/{filename}"
    summary = f"Processados {len(df)} clubes para {league_name}. (Limite atual: {max_clubs})"
    return jsonify({"summary": summary, "download_url": download_url})

@app.route("/download/<path:fname>", methods=["GET"])
def download(fname):
    return send_from_directory(EXPORT_DIR, fname, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
