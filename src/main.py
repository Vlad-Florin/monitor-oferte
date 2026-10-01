import sys
from pathlib import Path

# Adăugăm rădăcina proiectului în path pentru importuri
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.surse.zgarcit_scraper import get_toate_produsele
from src.matching.matcher import incarca_produse, cauta_in_produse, deduplica_potriviri
from src.notifications.ntfy import trimite_raport

CALE_PRODUSE = ROOT / "config" / "produse.yaml"

def ruleaza():
    print("=" * 60)
    print("MonitorOferte v2.0 — Rulare")
    print("=" * 60)

    # 1. Încarcă produsele urmărite
    if not CALE_PRODUSE.exists():
        print(f"[EROARE] Nu găsesc fișierul {CALE_PRODUSE}")
        return
    produse_urmărite = incarca_produse(str(CALE_PRODUSE))
    print(f"[Config] Am încărcat {len(produse_urmărite)} produse de urmărit:")
    for p in produse_urmărite:
        print(f"  • {p['nume']}")

    # 2. Extrage toate produsele de pe Zgârcit.ro
    toate_produsele_oferta = get_toate_produsele(max_pagini=20)
    if not toate_produsele_oferta:
        print("[EROARE] Nu am putut obține produsele de pe Zgârcit.ro.")
        trimite_raport([])
        return

    # 3. Caută produsele urmărite în lista de oferte
    potriviri = cauta_in_produse(produse_urmărite, toate_produsele_oferta)
    print(f"\n[Rezultat] Am găsit {len(potriviri)} potriviri brute.")

    # 4. Deduplicare (păstrează cea mai bună ofertă per produs)
    rezultate = deduplica_potriviri(potriviri)
    print(f"[Rezultat] După deduplicare: {len(rezultate)} potriviri unice.")

    for r in rezultate:
        print(f"  • {r['produs_cautat']} — {r['titlu_oferta']} — "
              f"{r.get('pret_nou', '?')} lei [{r.get('magazin')}]")

    # 5. Trimite notificare
    trimite_raport(rezultate)

    print("\n[Final] Rulare completă.")

if __name__ == "__main__":
    ruleaza()