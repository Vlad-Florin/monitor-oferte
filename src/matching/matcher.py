import re
from typing import List, Dict, Any

LUNGIME_MINIMA_SINONIM = 3

def normalizeaza(text: str) -> str:
    """Normalizează textul: lowercase, elimină diacritice, elimină punctuație."""
    if not text:
        return ""
    inlocuiri = {
        "ă": "a", "â": "a", "î": "i", "ș": "s", "ț": "t",
        "ş": "s", "ţ": "t", "á": "a", "é": "e", "í": "i",
        "ó": "o", "ú": "u",
    }
    text = text.lower()
    for k, v in inlocuiri.items():
        text = text.replace(k, v)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def incarca_produse(cale_yaml: str) -> List[Dict[str, Any]]:
    """Citește fișierul YAML cu produsele urmărite."""
    import yaml
    with open(cale_yaml, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("produse", [])

def cauta_in_produse(produse_urmărite: List[Dict[str, Any]], lista_produse_oferta: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Caută produsele urmărite în lista de produse de la ofertă.

    Reguli aplicate:
    1. Word boundary (evită potriviri în mijlocul altor cuvinte)
    2. Excluderi per produs (exclude_daca_contine)
    3. Regulă inteligentă "cu":
       - Se aplică DOAR dacă sinonimul NU conține deja "cu"
       - Userul poate controla explicit cu `exclude_daca_precedat_de`
       - Exemplu: "Mazăre cu piept de pui" → exclus când cauți "piept de pui"
       - Exemplu: "Pâine cu semințe" → păstrat când cauți "pâine cu semințe"
    """
    potriviri = []

    for produs_oferta in lista_produse_oferta:
        titlu = produs_oferta.get("title", "")
        if not titlu:
            continue
        titlu_norm = normalizeaza(titlu)

        for produs_urmărit in produse_urmărite:
            nume_produs = produs_urmărit.get("nume", "")
            sinonime = produs_urmărit.get("sinonime", [nume_produs])
            exclude = produs_urmărit.get("exclude_daca_contine", [])
            exclude_norm = [normalizeaza(e) for e in exclude]

            # Prepoziții excluse: implicit ["cu"]; userul poate seta [] ca să dezactiveze
            prepozitii = produs_urmărit.get("exclude_daca_precedat_de", ["cu"])

            for sinonim in sinonime:
                sinonim_norm = normalizeaza(sinonim)
                if len(sinonim_norm) < LUNGIME_MINIMA_SINONIM:
                    continue

                # 1. Căutare cu word boundary
                pattern = r"\b" + re.escape(sinonim_norm) + r"\b"
                if not re.search(pattern, titlu_norm):
                    continue

                # 2. Regula prepozițiilor (ex: "cu")
                blocat = False
                for prep in prepozitii:
                    # Dacă sinonimul conține deja prepoziția → nu blocăm
                    if prep in sinonim_norm.split():
                        continue
                    # Verifică "<prep> <sinonim>" în titlu
                    pattern_prep = r"\b" + re.escape(prep) + r"\s+" + re.escape(sinonim_norm) + r"\b"
                    if re.search(pattern_prep, titlu_norm):
                        blocat = True
                        break
                if blocat:
                    continue

                # 3. Excluderi pe listă
                exclus = False
                for ex_norm in exclude_norm:
                    if ex_norm and ex_norm in titlu_norm:
                        exclus = True
                        break
                if exclus:
                    continue

                potriviri.append({
                    "produs_cautat": nume_produs,
                    "titlu_oferta": titlu,
                    "cuvant_gasit": sinonim,   # ← asigură-te că e prezent
                    "pret_nou": produs_oferta.get("newPrice"),
                    "pret_vechi": produs_oferta.get("oldPrice"),
                    "magazin": produs_oferta.get("provider"),
                    "categorie": produs_oferta.get("category"),
                    "card_necesar": produs_oferta.get("requiresVendorCard", False),
                    "imagine": produs_oferta.get("image", ""),
                })
                break

    return potriviri

def deduplica_potriviri(potriviri: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicare în două etape:
    1. Grupare pe titlu de ofertă: dacă același titlu se potrivește cu mai multe
       produse urmărite, păstrăm doar potrivirea cea mai specifică (produsul
       urmărit cu cel mai lung sinonim găsit).
    2. Grupare pe produs urmărit: păstrăm cea mai bună ofertă (preț minim).
    """
    if not potriviri:
        return []

    # ─── Etapa 1: pentru fiecare titlu, păstrează cel mai specific match ───
    per_titlu: Dict[str, Dict[str, Any]] = {}
    for p in potriviri:
        titlu = p.get("titlu_oferta", "")
        if not titlu:
            continue

        lungime_nou = len(p.get("cuvant_gasit", ""))
        existing = per_titlu.get(titlu)

        if existing is None:
            per_titlu[titlu] = p
        else:
            # Compară lungimea cuvântului găsit — cel mai lung câștigă
            lungime_existing = len(existing.get("cuvant_gasit", ""))
            if lungime_nou > lungime_existing:
                per_titlu[titlu] = p

    # ─── Etapa 2: grupare pe produs urmărit, preț minim ───
    per_produs: Dict[str, List[Dict[str, Any]]] = {}
    for p in per_titlu.values():
        nume = p["produs_cautat"]
        per_produs.setdefault(nume, []).append(p)

    rezultat = []
    for nume, lista in per_produs.items():
        cu_pret = [x for x in lista if x.get("pret_nou") is not None]
        if cu_pret:
            cu_pret.sort(key=lambda x: x["pret_nou"])
            rezultat.append(cu_pret[0])
        elif lista:
            rezultat.append(lista[0])

    return rezultat