import sys
from pathlib import Path

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

    if not CALE_PRODUSE.exists():
        print(f"[EROARE] Nu găsesc fișierul {CALE_PRODUSE}")
        return
    
    produse_urmărite = incarca_produse(str(CALE_PRODUSE))
    print(f"[Config] Am încărcat {len(produse_urmărite)} produse de urmărit:")
    for p in produse_urmărite:
        print(f"  • {p['nume']}")

    toate_produsele_oferta = get_toate_produsele()
    if not toate_produsele_oferta:
        print("[EROARE] Nu am putut obține produsele de pe Zgârcit.ro.")
        trimite_raport([])
        return

    potriviri = cauta_in_produse(produse_urmărite, toate_produsele_oferta)
    print(f"\n[Rezultat] Am găsit {len(potriviri)} potriviri brute.")

    rezultate = deduplica_potriviri(potriviri)
    print(f"[Rezultat] După deduplicare: {len(rezultate)} potriviri unice.")

    for r in rezultate:
        print(f"  • {r['produs_cautat']} — {r['titlu_oferta']} — "
              f"{r.get('pret_nou', '?')} lei [{r.get('magazin')}]")

    # Salvare în CSV
    CALE_REZULTATE = ROOT / "rezultate.csv"
    salveaza_rezultate_csv(rezultate, CALE_REZULTATE)

    # Notificare
    trimite_raport(rezultate)

    print("\n[Final] Rulare completă.")

if __name__ == "__main__":
    ruleaza()