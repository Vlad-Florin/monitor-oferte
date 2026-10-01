import requests
from typing import List, Dict, Any

NTFY_TOPIC = "Monitor-Oferte-ROK"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

def trimite_notificare(titlu: str, mesaj: str, prioritate: str = "high") -> bool:
    """Trimite o notificare push prin ntfy.sh."""
    try:
        r = requests.post(
            NTFY_URL,
            data=mesaj.encode("utf-8"),
            headers={
                "Title": titlu.encode("utf-8"),
                "Priority": prioritate,
                "Tags": "shopping_cart,rotating_light",
            },
            timeout=15,
        )
        r.raise_for_status()
        print(f"[ntfy] Notificare trimisă: {titlu}")
        return True
    except requests.RequestException as e:
        print(f"[ntfy] Eroare la trimitere: {e}")
        return False

def trimite_raport(oferte: List[Dict[str, Any]]) -> bool:
    """Trimite un raport formatat cu toate ofertele găsite."""
    if not oferte:
        return trimite_notificare(
            titlu="Monitor Oferte: nicio ofertă",
            mesaj="Niciun produs urmărit nu a fost găsit în ofertele actuale.",
            prioritate="default",
        )

    linii = []
    # Sortăm alfabetic după produsul căutat
    oferte_sortate = sorted(oferte, key=lambda x: x["produs_cautat"])

    for o in oferte_sortate:
        produs = o["produs_cautat"]
        pret_nou = o.get("pret_nou")
        pret_vechi = o.get("pret_vechi")
        magazin = o.get("magazin", "")
        card = " (card)" if o.get("card_necesar") else ""

        if pret_nou is not None and pret_vechi is not None:
            reducere = round((1 - pret_nou / pret_vechi) * 100)
            linie = f"• {produs} — {pret_nou:.2f} lei (-{reducere}%) [{magazin}{card}]"
        elif pret_nou is not None:
            linie = f"• {produs} — {pret_nou:.2f} lei [{magazin}{card}]"
        else:
            linie = f"• {produs} — preț nedetectat [{magazin}{card}]"
        linii.append(linie)

    mesaj = "\n".join(linii)
    titlu = f"🛒 Monitor Oferte: {len(oferte)} produse la ofertă"

    return trimite_notificare(titlu, mesaj)