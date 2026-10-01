"""
Modul pentru extragerea produselor de pe Zgârcit.ro.
VERSIUNEA 3 — split după identityKey (robust, nu depinde de ordinea câmpurilor).
"""
_SCRAPER_VERSION = "v3-split-identityKey"
print(f"[zgarcit_scraper] Se încarcă versiunea {_SCRAPER_VERSION}")

import re
import time
import random
import requests
from typing import List, Dict, Any, Optional


# ─── CONFIGURARE ────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
}

BASE_URL = "https://zgarcit.ro/"
MAX_RETRIES = 5


# ─── HELPERS ────────────────────────────────────────────────────────────────

def _fix_mojibake(text: str) -> str:
    """Repară caracterele corupte de tipul 'Ã¢' → 'â'."""
    if not text:
        return text
    try:
        if any(c in text for c in ["Ã", "Ä", "È", "Â"]):
            return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text


def _descarca(url: str, session: requests.Session) -> Optional[str]:
    """
    Descarcă o pagină și returnează HTML-ul DE-ESCAPE-UIT
    (adică cu \\" înlocuit prin ").
    """
    for incercare in range(MAX_RETRIES):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)

            if r.status_code == 200:
                r.encoding = "utf-8"
                html_brut = r.text
                html_clean = html_brut.replace('\\"', '"')
                return html_clean

            if r.status_code == 429:
                asteapta = (2 ** incercare) + random.uniform(1, 3)
                print(f"      -> [429] Aștept {asteapta:.1f}s "
                      f"(încercarea {incercare + 1}/{MAX_RETRIES})...")
                time.sleep(asteapta)
                continue

            print(f"      -> [HTTP {r.status_code}] {url}")
            time.sleep(2)

        except requests.RequestException as e:
            print(f"      -> Eroare rețea: {e}")
            time.sleep(2)

    return None


# ─── EXTRAGERE CÂMPURI ──────────────────────────────────────────────────────

def _get_string(rest: str, key: str) -> Optional[str]:
    """Extrage un câmp de tip string: "key":"valoare" → 'valoare'."""
    m = re.search(rf'"{re.escape(key)}":"([^"]*)"', rest)
    return m.group(1) if m else None


def _get_number(rest: str, key: str) -> Optional[float]:
    """Extrage un câmp numeric: "key":12.34 → 12.34."""
    m = re.search(rf'"{re.escape(key)}":([\d.]+)', rest)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _get_nullable_number(rest: str, key: str) -> Optional[float]:
    """Extrage un câmp numeric nullable: "key":null sau "key":12.34."""
    m = re.search(rf'"{re.escape(key)}":(null|[\d.]+)', rest)
    if not m:
        return None
    if m.group(1) == "null":
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _extrage_campuri(rest: str) -> Optional[Dict[str, Any]]:
    """Extrage toate câmpurile unui produs din textul rămas după identityKey."""
    title = _get_string(rest, "title")
    if not title:
        return None

    return {
        "title": _fix_mojibake(title),
        "newPrice": _get_number(rest, "newPrice"),
        "oldPrice": _get_nullable_number(rest, "oldPrice"),
        "provider": _get_string(rest, "provider") or "",
        "quantity": _fix_mojibake(_get_string(rest, "quantity") or ""),
        "image": _get_string(rest, "image") or "",
    }


# ─── EXTRAGERE PRODUSE ──────────────────────────────────────────────────────

def _extrage_produse(html_clean: str, debug: bool = False) -> List[Dict[str, Any]]:
    """
    Extrage produsele din HTML-ul deja de-escape-uit.
    Folosim split după '"identityKey":"' pentru robustețe maximă.
    """
    produse: List[Dict[str, Any]] = []
    vazute: set = set()

    chunks = html_clean.split('"identityKey":"')

    if debug:
        print(f"      [DEBUG] Split a produs {len(chunks)} chunks")

    # chunks[0] e textul dinainte de primul identityKey — îl ignorăm
    for chunk in chunks[1:]:
        # Limităm chunk-ul la 3000 caractere ca să nu depășim în produsul următor
        chunk = chunk[:3000]

        # Extragem identityKey-ul (până la primul ")
        if '"' not in chunk:
            continue
        identity_key, rest = chunk.split('"', 1)

        # Validare: identityKey trebuie să fie hash hex, lungime >= 20
        if len(identity_key) < 20:
            continue
        if not all(c in '0123456789abcdef' for c in identity_key):
            continue

        # Deduplicare
        if identity_key in vazute:
            continue
        vazute.add(identity_key)

        # Extragem câmpurile
        produs = _extrage_campuri(rest)
        if produs and produs.get("title"):
            produs["identityKey"] = identity_key
            produse.append(produs)

    # Debug: dacă am găsit chunks dar 0 produse, arată primul chunk
    if debug and not produse and len(chunks) > 1:
        print(f"      [DEBUG] ⚠️  {len(chunks) - 1} chunks găsite dar 0 produse extrase!")
        print(f"      [DEBUG] Primul chunk (primele 500 car.):")
        print(f"      {repr(chunks[1][:500])}")

    return produse


def _extrage_total_pagini(html_clean: str) -> int:
    """Extrage totalPages din HTML deja de-escape-uit."""
    m = re.search(r'"totalPages":(\d+)', html_clean)
    if m:
        return int(m.group(1))
    print("[Zgârcit] ATENȚIE: Nu am putut detecta totalPages. Presupun 456.")
    return 456


# ─── FUNCȚIA PRINCIPALĂ ─────────────────────────────────────────────────────

def get_toate_produsele(max_pagini: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Funcția principală: descarcă paginile și extrage produsele.

    Args:
        max_pagini: dacă e setat, limitează numărul de pagini procesate.
    """
    session = requests.Session()

    # Pagina 1 — descărcare cu debug
    print("[Zgârcit] Descarc pagina 1...")
    html1 = _descarca(f"{BASE_URL}?page=1", session)
    if not html1:
        print("[Zgârcit] Nu am putut descărca pagina 1.")
        return []

    print(f"[Zgârcit] Lungime HTML clean: {len(html1):,} caractere")
    print(f"[Zgârcit] Conține identityKey: {'identityKey' in html1}")
    print(f"[Zgârcit] Conține newPrice: {'newPrice' in html1}")
    print()

    total_pagini = _extrage_total_pagini(html1)
    print(f"[Zgârcit] Total pagini: {total_pagini}")

    if max_pagini:
        total_pagini = min(total_pagini, max_pagini)
        print(f"[Zgârcit] Limită testare: {total_pagini} pagini")

    # Procesăm pagina 1 cu debug activat
    produse_p1 = _extrage_produse(html1, debug=True)
    print(f"[Zgârcit] Pagina 1/{total_pagini}: {len(produse_p1)} produse")

    toate = list(produse_p1)

    # Restul paginilor
    pagini_reusite = 1 if produse_p1 else 0
    pagini_esuate = 0

    for pagina in range(2, total_pagini + 1):
        print(f"[Zgârcit] Pagina {pagina}/{total_pagini}...")
        html = _descarca(f"{BASE_URL}?page={pagina}", session)
        if not html:
            pagini_esuate += 1
            print(f"      -> Sărită (eșec la descărcare)")
            continue

        produse_p = _extrage_produse(html, debug=False)
        toate.extend(produse_p)
        pagini_reusite += 1
        print(f"      -> {len(produse_p)} produse")

        time.sleep(random.uniform(1.0, 2.5))

    print()
    print(f"[Zgârcit] ═══════════════════════════════════════════")
    print(f"[Zgârcit] TOTAL produse extrase: {len(toate)}")
    print(f"[Zgârcit] Pagini reușite: {pagini_reusite}/{total_pagini}")
    print(f"[Zgârcit] Pagini eșuate: {pagini_esuate}/{total_pagini}")
    print(f"[Zgârcit] ═══════════════════════════════════════════")

    return toate