# Page2Markdown
# streamlit run app.py
#
# REQUIREMENTS.TXT:
# streamlit, trafilatura, requests, fpdf2, beautifulsoup4, selenium, webdriver-manager

import json
import re
from urllib.parse import urlparse, urljoin
import unicodedata

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import streamlit as st
from bs4 import BeautifulSoup
from fpdf import FPDF
from fpdf.html import HTMLMixin
from urllib import robotparser

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

import trafilatura

# ---------------------
# CONFIG & PAGE HEADER
# ---------------------
st.set_page_config(page_title="Page2Markdown", page_icon="📰", layout="wide")
st.title("📰 Page2Markdown")
st.caption("Collez une URL d’article. L’app respecte `robots.txt` et détecte les paywalls **par défaut** (désactivable dans les options).")

# Initialise l'état de session pour la persistance des résultats et de l'URL
if 'result' not in st.session_state:
    st.session_state.result = None
if 'last_url' not in st.session_state:
    st.session_state.last_url = ""

# --------------
# HELPERS & CLASSES
# --------------
def _safe_filename(s: str, default="article"):
    base = (s or default).strip()
    base = re.sub(r"[\\/:*?\"<>|]+", "_", base)
    base = re.sub(r"\s+", " ", base)[:120].strip()
    return base or default

def _looks_like_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

_SANITIZE_MAP = str.maketrans({
    "–": "-", "—": "-", "−": "-", "…": "...", "“": '"', "”": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'", "•": "-", "€": "EUR", "\u00A0": " ", "\u202F": " ", "\u2009": " ", "\u200B": "",
})

def sanitize_for_pdf(s: str) -> str:
    if not s: return ""
    s = s.translate(_SANITIZE_MAP)
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("latin-1", "replace").decode("latin-1")
    return s

class PDF(FPDF, HTMLMixin):
    def header(self):
        if hasattr(self, "_header_title") and self._header_title:
            self.set_font("Helvetica", "B", 12)
            self.multi_cell(0, 10, self._header_title, 0, "L")
            self.ln(2)
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "R")

# --------------
# SIDEBAR
# --------------
with st.sidebar:
    st.header("Options d'extraction")
    render_js = st.toggle("Activer le rendu JavaScript", value=False, disabled=not SELENIUM_AVAILABLE)
    if not SELENIUM_AVAILABLE: st.caption("Selenium non trouvé.")
    ignore_robots = st.toggle("Ignorer robots.txt", value=False, help="⚠️ Fortement déconseillé.")
    ignore_paywall = st.toggle("Ignorer la détection de paywall", value=False)
    st.markdown("---")
    if st.button("♻️ Purger le cache et la session"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state.result = None
        st.session_state.last_url = ""
        st.success("Cache et session vidés.")

# ------------------------
# CORE FUNCTIONS
# ------------------------
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 30
PAYWALL_SELECTORS = [".ac-article-main__subscriber", ".subscriber-only", ".wall-content", ".paywall"]

@st.cache_resource
def get_session():
    sess = requests.Session()
    retries = Retry(total=3, connect=3, read=3, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504), allowed_methods={"GET"})
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=50)
    sess.mount("http://", adapter)
    sess.mount("https://", adapter)
    return sess

@st.cache_resource
def get_chromedriver_path():
    return ChromeDriverManager().install()

@st.cache_data(ttl=86400, max_entries=512)
def is_fetch_allowed(url: str, user_agent: str) -> bool:
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        if rp.default_entry is None and not rp.site_maps():
            return True
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True

@st.cache_data(ttl=1800, max_entries=128, show_spinner=False)
def fetch_html(url: str, execute_js: bool = False) -> str:
    if execute_js:
        if not SELENIUM_AVAILABLE: raise ImportError("Selenium n'est pas installé.")
        options = Options()
        options.page_load_strategy = "eager"
        options.add_argument("--headless=new"); options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage"); options.add_argument("--disable-gpu")
        options.add_argument(f"user-agent={USER_AGENT}")
        service = ChromeService(get_chromedriver_path())
        driver = None
        try:
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(REQUEST_TIMEOUT)
            driver.get(url)
            WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.CSS_SELECTOR, "article, main, body")))
            return driver.page_source
        except TimeoutException: return driver.page_source if driver else ""
        except WebDriverException as e: raise RuntimeError(f"Erreur Selenium/Chrome: {e}") from e
        finally:
            if driver: driver.quit()
    sess = get_session()
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "fr-FR,fr;q=0.9", "DNT": "1"}
    r = sess.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.text

def detect_paywall(soup: BeautifulSoup) -> bool:
    html_str = str(soup).lower()
    paywall_markers = ['article réservé aux abonnés', '"isaccessibleforfree":"false"', '"isaccessibleforfree":false', 'statut_monetisation":"payant']
    if any(m in html_str for m in paywall_markers): return True
    if soup.find("meta", attrs={"name": "restricted", "value": "true"}): return True
    for sel in PAYWALL_SELECTORS:
        if soup.select_one(sel): return True
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and str(item.get("isAccessibleForFree", "")).lower() in ("false", "0"): return True
        except (json.JSONDecodeError, AttributeError): continue
    return False

def _t_extract(html, **kwargs):
    fmt = kwargs.pop("fmt")
    try: return trafilatura.extract(html, output_format=fmt, **kwargs)
    except TypeError: return trafilatura.extract(html, output=fmt, **kwargs)

@st.cache_data(max_entries=128)
def extract_article_from_html(url: str, html_str: str) -> dict:
    soup = BeautifulSoup(html_str, "html.parser")
    title_bs, summary_bs, canonical_url = "", "", None
    try:
        title_element = soup.select_one("h1, .article-title, [itemprop='headline']")
        if title_element: title_bs = title_element.get_text(strip=True)
        summary_element = soup.select_one(".chapo, .summary, .article-chapo, .article-lede, .lede, .intro, .introduction, [itemprop='description'], h1 ~ p")
        if summary_element: summary_bs = summary_element.get_text(strip=True)
        canon = soup.find("link", rel=lambda v: v and "canonical" in v.lower())
        if canon and canon.has_attr("href"): canonical_url = urljoin(url, canon["href"].strip())
    except Exception: pass
    text_markdown = _t_extract(html_str, fmt="markdown") or ""
    data = {}
    if not title_bs or not text_markdown:
        data_json = _t_extract(html_str, url=url, fmt="json") or "{}"
        data = json.loads(data_json)
    final_text = text_markdown or data.get("text") or ""
    if summary_bs and final_text.strip().startswith(summary_bs.strip()):
        final_text = final_text.strip()[len(summary_bs.strip()):].lstrip()
    return {"title": title_bs or data.get("title"), "summary": summary_bs or data.get("excerpt"), "author": data.get("author"),
            "date": data.get("date"), "text": final_text,
            "url": canonical_url or data.get("source-url") or data.get("url") or url,
            "sitename": data.get("sitename") or urlparse(url).netloc}

def build_pdf(meta: dict) -> bytes:
    title, summary = sanitize_for_pdf(meta.get("title") or "(Sans titre)"), sanitize_for_pdf(meta.get("summary") or "")
    author, date, url, text = sanitize_for_pdf(meta.get("author") or ""), sanitize_for_pdf(meta.get("date") or ""), sanitize_for_pdf(meta.get("url") or ""), sanitize_for_pdf(meta.get("text") or "")
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.set_left_margin(15); pdf.set_right_margin(15); pdf.set_top_margin(15)
    pdf.set_title(title); pdf.set_author(author)
    pdf._header_title = title
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    meta_info = [f"Auteur : {author}" if author else "", f"Date : {date}" if date else "", f"Source : {url}" if url else ""]
    pdf.multi_cell(0, 6, "\n".join([m for m in meta_info if m])); pdf.ln(5)
    if summary:
        pdf.set_font("Helvetica", "B", 11); pdf.multi_cell(0, 6, summary); pdf.ln(3); pdf.set_font("Helvetica", size=11)
    md_body = re.sub(r"^##\s?(.*)", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    try:
        pdf.write_html(md_body)
    except Exception:
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 6, text)
    out = pdf.output(dest="S")
    if isinstance(out, str): return out.encode("latin-1", "replace")
    return bytes(out)

def build_markdown(meta: dict) -> str:
    title, summary, author, date, url, text = meta.get("title") or "(Sans titre)", meta.get("summary") or "", meta.get("author") or "", meta.get("date") or "", meta.get("url") or "", meta.get("text") or ""
    header_parts = [f"# {title}"]
    if summary: header_parts.append(f"**{summary}**")
    meta_line = " • ".join(filter(None, [author, date]))
    if meta_line: header_parts.append(meta_line)
    if url: header_parts.append(f"\nSource : {url}")
    return "\n\n".join(header_parts + ["", text.strip(), ""])

def build_txt(meta: dict) -> str:
    title, author, date, url, text = meta.get("title") or "(Sans titre)", meta.get("author") or "", meta.get("date") or "", meta.get("url") or "", meta.get("text") or ""
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = text.replace('**', ''); text = text.replace('*', '')
    text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'`{3,}.*?`{3,}', '', text, flags=re.DOTALL)
    text = re.sub(r'`(.+?)`', r'\1', text)
    header_parts = [title, "=" * len(title)]
    meta_info = list(filter(None, [f"Auteur : {author}", f"Date : {date}", f"Source : {url}"]))
    header_parts.extend(meta_info)
    txt = "\n\n".join(header_parts) + "\n\n" + "="*40 + "\n\n" + text.strip()
    return txt.replace("\r\n", "\n").replace("\r", "\n")

# -------------
# MAIN UI
# -------------
url = st.text_input(
    "URL de l’article",
    value=st.session_state.last_url,
    placeholder="https://exemple.com/article"
)

if run := st.button("Afficher l’article", type="primary"):
    st.session_state.last_url = url
    st.session_state.result = None
    if not _looks_like_url(url):
        st.error("URL invalide. Pensez à inclure http(s)://"); st.stop()
    try:
        with st.spinner("Analyse de la page…"):
            if not ignore_robots and not is_fetch_allowed(url, USER_AGENT):
                st.warning("Le site interdit l'extraction de cette URL via robots.txt.")
                st.link_button("Ouvrir l’article original", url); st.stop()
            html = fetch_html(url, execute_js=render_js)
            soup = BeautifulSoup(html, "html.parser")
            if not ignore_paywall and detect_paywall(soup):
                st.warning("Cet article semble réservé aux abonnés (option désactivable).")
                st.link_button("Ouvrir l’article original", url); st.stop()
            meta = extract_article_from_html(url, html)
            if not meta or not meta.get("text"):
                st.warning("Impossible d'extraire le contenu principal."); st.stop()
            st.session_state.result = {"meta": meta, "html": html}
    except requests.RequestException as e: st.error(f"Erreur réseau : {e}")
    except Exception as e: st.error(f"Erreur inattendue : {e}", icon="🔥")

if st.session_state.result:
    meta, html = st.session_state.result["meta"], st.session_state.result["html"]
    title = meta.get("title") or "(Sans titre)"
    st.subheader(title)
    
    if summary := meta.get("summary"): st.markdown(f"**{summary}**")
    info_bits = filter(None, [meta.get("sitename"), meta.get("author"), meta.get("date")])
    st.caption(" • ".join(info_bits))
    if article_url := meta.get("url"): st.link_button("Ouvrir l’article original ↗️", article_url)
    st.divider()

    full_markdown_content = build_markdown(meta)
    tabs = st.tabs(["Article", "Markdown", "Métadonnées", "HTML brut"])
    with tabs[0]: st.markdown(meta.get("text", ""))
    with tabs[1]: st.code(full_markdown_content, language="markdown")
    with tabs[2]: st.json({k: v for k, v in meta.items() if k != "text"})
    with tabs[3]:
        st.caption(f"Taille HTML ≈ {len(html):,} octets".replace(",", " "))
        st.text_area("Source HTML (aperçu)", html[:150000], height=240, disabled=True)
    st.divider()

    fname = _safe_filename(title)
    pdf_bytes = build_pdf(meta)
    txt_content = build_txt(meta)
    
    dl_col1, dl_col2, dl_col3 = st.columns(3)
    with dl_col1: st.download_button("⬇️ Télécharger en Markdown", full_markdown_content.encode("utf-8"), f"{fname}.md", "text/markdown", use_container_width=True)
    with dl_col2: st.download_button("⬇️ Télécharger en PDF", pdf_bytes, f"{fname}.pdf", "application/pdf", use_container_width=True)
    with dl_col3:
        st.download_button(
            "⬇️ Télécharger en TXT",
            txt_content.encode("utf-8"),
            f"{fname}.txt",
            "text/plain; charset=utf-8",
            use_container_width=True
        )

    if st.button("Nouvelle recherche"):
        st.session_state.result = None
        st.session_state.last_url = ""
        st.rerun()