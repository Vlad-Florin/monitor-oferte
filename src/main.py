"""
MonitorOferte v2.0 — Entry point.
Citește setările din config/setari.yaml, rulează scraper-ul Zgârcit.ro,
caută produsele urmărite și salvează rezultatele.
"""
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Adăugăm rădăcina proiectului în path pentru importuri
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.surse.zgarcit_scraper import get_toate_produsele
from src.matching.matcher import incarca_produse, cauta_in_produse, deduplica_potriviri
from src.notifications.ntfy import trimite_raport

CALE_PRODUSE = ROOT / "config" / "reguli_matching.yaml"
CALE_SETARI = ROOT / "config" / "setari.yaml"
CALE_REZULTATE = ROOT / "rezultate.csv"


# ─── SETĂRI ────────────────────────────────────────────────────────────────

def incarca_setari() -> dict:
    """Citește config/setari.yaml. Returnează valori implicite dacă lipsește."""
    default = {
        "surse": {
            "zgarcit": {
                "activ": True,
                "max_pagini": None,
                "pauza_min": 1.0,
                "pauza_max": 2.5,
            }
        },
        "comportament": {
            "trimite_notificare": True,
            "push_github": True,
            "salveaza_csv": True,
            "max_oferte_notificare": 0,
        },
    }
    if not CALE_SETARI.exists():
        print("[Config] setari.yaml lipsește — folosesc valorile implicite.")
        return default

    with open(CALE_SETARI, "r", encoding="utf-8") as f:
        setari = yaml.safe_load(f) or {}

    # Merge cu valorile implicite
    for sectiune, valori in default.items():
        if sectiune not in setari:
            setari[sectiune] = valori
        elif isinstance(valori, dict):
            for k, v in valori.items():
                setari[sectiune].setdefault(k, v)
    return setari


# ─── STOCARE CSV ───────────────────────────────────────────────────────────

def salveaza_rezultate_csv(rezultate: list, cale: Path):
    """Salvează rezultatele într-un CSV, adăugând la istoricul existent."""
    exista = cale.exists()

    with open(cale, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exista:
            writer.writerow([
                "data", "produs", "titlu_oferta", "pret_nou",
                "pret_vechi", "magazin", "categorie", "card_necesar", "gramaj"
            ])

        data_acum = datetime.now().strftime("%Y-%m-%d %H:%M")
        for r in rezultate:
            writer.writerow([
                data_acum,
                r.get("produs_cautat", ""),
                r.get("titlu_oferta", ""),
                r.get("pret_nou", ""),
                r.get("pret_vechi", ""),
                r.get("magazin", ""),
                r.get("categorie", ""),
                "DA" if r.get("card_necesar") else "NU",
                r.get("quantity", ""),
            ])

    print(f"[Storage] Rezultate salvate în {cale}")


# ─── GIT AUTO-PUSH ─────────────────────────────────────────────────────────

def try_auto_push(cale_csv: Path):
    """
    Face git add + commit + push pentru rezultate.csv.
    Nu aruncă erori dacă nu există modificări sau dacă push-ul eșuează.
    """
    try:
        # Verifică dacă fișierul e modificat
        result = subprocess.run(
            ["git", "diff", "--quiet", "--", str(cale_csv.name)],
            cwd=str(cale_csv.parent),
            capture_output=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("[Git] Niciun rezultat nou — sar peste push.")
            return

        # Add + commit + push
        data_acum = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "add", str(cale_csv.name)],
            cwd=str(cale_csv.parent),
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Actualizare oferte {data_acum}"],
            cwd=str(cale_csv.parent),
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "push"],
            cwd=str(cale_csv.parent),
            check=True,
            timeout=120,
        )
        print("[Git] ✅ Push reușit pe GitHub.")

    except subprocess.TimeoutExpired:
        print("[Git] ⚠️ Timeout la git. Verifică manual.")
    except subprocess.CalledProcessError as e:
        print(f"[Git] ⚠️ Eroare git (cod {e.returncode}). Rulează manual: git push")
    except FileNotFoundError:
        print("[Git] ⚠️ Git nu e instalat sau nu e în PATH.")
    except Exception as e:
        print(f"[Git] ⚠️ Eroare neașteptată: {e}")


# ─── RULARE PRINCIPALĂ ─────────────────────────────────────────────────────

def ruleaza():
    print("=" * 60)
    print("MonitorOferte v2.0 — Rulare")
    print("=" * 60)

    # 1. Setări
    setari = incarca_setari()
    cfg_surse = setari["surse"]["zgarcit"]
    cfg_comp = setari["comportament"]

    # 2. Produse urmărite
    if not CALE_PRODUSE.exists():
        print(f"[EROARE] Nu găsesc fișierul {CALE_PRODUSE}")
        return

    produse_urmărite = incarca_produse(str(CALE_PRODUSE))
    print(f"[Config] Am încărcat {len(produse_urmărite)} produse de urmărit:")
    for p in produse_urmărite:
        print(f"  • {p['nume']}")

    # 3. Scraper
    max_pag = cfg_surse.get("max_pagini")
    if max_pag:
        print(f"[Config] Limită pagini: {max_pag}")

    toate_produsele_oferta = get_toate_produsele(max_pagini=max_pag)
    if not toate_produsele_oferta:
        print("[EROARE] Nu am putut obține produsele de pe Zgârcit.ro.")
        if cfg_comp.get("trimite_notificare", True):
            trimite_raport([])
        return

    # 4. Matching
    potriviri = cauta_in_produse(produse_urmărite, toate_produsele_oferta)
    print(f"\n[Rezultat] Am găsit {len(potriviri)} potriviri brute.")

    rezultate = deduplica_potriviri(potriviri)
    print(f"[Rezultat] După deduplicare: {len(rezultate)} potriviri unice.")

    for r in rezultate:
        print(f"  • {r['produs_cautat']} — {r['titlu_oferta']} — "
              f"{r.get('pret_nou', '?')} lei [{r.get('magazin')}]")

    # 5. Salvare CSV
    if cfg_comp.get("salveaza_csv", True):
        salveaza_rezultate_csv(rezultate, CALE_REZULTATE)

    # 6. Notificare
    if cfg_comp.get("trimite_notificare", True):
        trimite_raport(rezultate)

    # 7. Auto-push pe GitHub
    if cfg_comp.get("push_github", True):
        try_auto_push(CALE_REZULTATE)

    print("\n[Final] Rulare completă.")


if __name__ == "__main__":
    ruleaza()