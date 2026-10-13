import sys

def incarca_setari() -> dict:
    """Citește config/setari.yaml. Returnează dict cu valori implicite dacă lipsește."""
    cale = ROOT / "config" / "setari.yaml"
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
    if not cale.exists():
        print("[Config] setari.yaml lipsește — folosesc valorile implicite.")
        return default
    with open(cale, "r", encoding="utf-8") as f:
        setari = yaml.safe_load(f) or {}
    # Merge cu valorile implicite
    for sectiune, valori in default.items():
        if sectiune not in setari:
            setari[sectiune] = valori
        elif isinstance(valori, dict):
            for k, v in valori.items():
                setari[sectiune].setdefault(k, v)
    return setari

from pathlib import Path
import yaml

# Adăugăm rădăcina proiectului în path pentru importuri
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.surse.zgarcit_scraper import get_toate_produsele
from src.matching.matcher import incarca_produse, cauta_in_produse, deduplica_potriviri
from src.notifications.ntfy import trimite_raport

CALE_PRODUSE = ROOT / "config" / "produse.yaml"

def salveaza_rezultate_csv(rezultate: list, cale: Path):
    """Salvează rezultatele într-un CSV, adăugând la istoricul existent."""
    import csv
    from datetime import datetime
    
    exista = cale.exists()
    
    with open(cale, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exista:
            writer.writerow([
                "data", "produs", "titlu_oferta", "pret_nou",
                "pret_vechi", "magazin", "categorie", "card_necesar"
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
            ])
    
    print(f"[Storage] Rezultate salvate în {cale}")


def ruleaza():
    print("=" * 60)
    print("MonitorOferte v2.0 — Rulare")
    print("=" * 60)

    setari = incarca_setari()
    cfg_surse = setari["surse"]["zgarcit"]
    cfg_comp = setari["comportament"]

    # ... produse ...

    # Aplică max_pagini din setari.yaml
    max_pag = cfg_surse.get("max_pagini")
    toate_produsele_oferta = get_toate_produsele(max_pagini=max_pag)

    # ... matching ...

    if cfg_comp.get("salveaza_csv", True):
        salveaza_rezultate_csv(rezultate, ROOT / "rezultate.csv")

    if cfg_comp.get("trimite_notificare", True):
        trimite_raport(rezultate)

    if cfg_comp.get("push_github", True):
        try_auto_push(ROOT / "rezultate.csv")

    print("\n[Final] Rulare completă.")

def try_auto_push(cale_csv: Path):
    """
    Face git add + commit + push pentru rezultate.csv.
    Nu aruncă erori dacă nu există modificări sau dacă push-ul eșuează.
    """
    import subprocess
    from datetime import datetime

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
        print(f"[Git] ✅ Push reușit pe GitHub.")

    except subprocess.TimeoutExpired:
        print(f"[Git] ⚠️ Timeout la git. Verifică manual.")
    except subprocess.CalledProcessError as e:
        print(f"[Git] ⚠️ Eroare git (cod {e.returncode}). Rulează manual: git push")
    except FileNotFoundError:
        print(f"[Git] ⚠️ Git nu e instalat sau nu e în PATH.")
    except Exception as e:
        print(f"[Git] ⚠️ Eroare neașteptată: {e}")

if __name__ == "__main__":
    ruleaza()