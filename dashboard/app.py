"""
MonitorOferte — Dashboard Streamlit.
Citește rezultate.csv din rădăcina proiectului și afișează ofertele.
"""
import pandas as pd
import streamlit as st
from pathlib import Path

# ─── CONFIGURARE PAGINĂ ───
st.set_page_config(
    page_title="Monitor Oferte",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# CSS personalizat pentru un look mai curat pe telefon
st.markdown("""
<style>
    .main { padding-top: 1rem; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 8px; }
    @media (max-width: 768px) {
        h1 { font-size: 1.5rem !important; }
        .stMetric label { font-size: 0.8rem !important; }
    }
</style>
""", unsafe_allow_html=True)

st.title("🛒 Monitor Oferte")
st.caption("Ofertele săptămânale, centralizate")

# ─── CITIRE DATE ───
CALE_CSV = Path(__file__).resolve().parent.parent / "rezultate.csv"

if not CALE_CSV.exists():
    st.warning("⚠️ Nu există încă rezultate. Rulează mai întâi scriptul de monitorizare.")
    st.stop()

df = pd.read_csv(CALE_CSV)

# Convertim coloanele numerice
df["pret_nou"] = pd.to_numeric(df["pret_nou"], errors="coerce")
df["pret_vechi"] = pd.to_numeric(df["pret_vechi"], errors="coerce")

# Sortăm descrescător după data
df = df.sort_values("data", ascending=False).reset_index(drop=True)

# ─── SIDEBAR FILTRE ───
st.sidebar.header("🔎 Filtre")

# Magazine
magazine = sorted(df["magazin"].dropna().unique().tolist())
magazine_selectate = st.sidebar.multiselect(
    "Magazin",
    magazine,
    default=magazine,
)

# Produse
produse = sorted(df["produs"].dropna().unique().tolist())
produse_selectate = st.sidebar.multiselect(
    "Produs",
    produse,
    default=produse,
)

# Preț maxim
if not df["pret_nou"].dropna().empty:
    pret_min = float(df["pret_nou"].min())
    pret_max = float(df["pret_nou"].max())
    interval_pret = st.sidebar.slider(
        "Preț (lei)",
        min_value=pret_min,
        max_value=pret_max,
        value=(pret_min, pret_max),
    )
else:
    interval_pret = (0, 9999)

# Card fidelitate
doar_card = st.sidebar.checkbox("Doar oferte cu card fidelitate", value=False)

# Sortare
sortare = st.sidebar.selectbox(
    "Sortează după",
    ["Data (recent)", "Preț crescător", "Preț descrescător", "Produs (A-Z)"],
)

# ─── APLICARE FILTRE ───
df_filtrat = df[
    (df["magazin"].isin(magazine_selectate)) &
    (df["produs"].isin(produse_selectate)) &
    (df["pret_nou"].fillna(0).between(interval_pret[0], interval_pret[1]))
].copy()

if doar_card:
    df_filtrat = df_filtrat[df_filtrat["card_necesar"] == "DA"]

# Sortare
if sortare == "Preț crescător":
    df_filtrat = df_filtrat.sort_values("pret_nou", ascending=True)
elif sortare == "Preț descrescător":
    df_filtrat = df_filtrat.sort_values("pret_nou", ascending=False)
elif sortare == "Produs (A-Z)":
    df_filtrat = df_filtrat.sort_values("produs", ascending=True)

# ─── METRICI ───
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

col1.metric("Total oferte", len(df_filtrat))
col2.metric("Produse", df_filtrat["produs"].nunique())
col3.metric("Magazine", df_filtrat["magazin"].nunique())
if not df_filtrat["pret_nou"].dropna().empty:
    col4.metric("Preț mediu", f"{df_filtrat['pret_nou'].mean():.2f} lei")

st.markdown("---")

# ─── TABEL PRINCIPAL ───
st.subheader("📋 Oferte găsite")

if df_filtrat.empty:
    st.info("Nicio ofertă nu corespunde filtrelor selectate.")
else:
    df_afisare = df_filtrat[["data", "produs", "titlu_oferta", "pret_nou", "pret_vechi", "magazin", "card_necesar"]].copy()
    df_afisare.columns = ["Data", "Produs", "Ofertă", "Preț nou", "Preț vechi", "Magazin", "Card"]
    df_afisare = df_afisare.reset_index(drop=True)

    st.dataframe(
        df_afisare,
        width="stretch",
        hide_index=True,
        column_config={
            "Preț nou": st.column_config.NumberColumn(format="%.2f lei"),
            "Preț vechi": st.column_config.NumberColumn(format="%.2f lei"),
        },
    )

# ─── GRAFICE ───
if not df_filtrat.empty:
    st.markdown("---")
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("📊 Oferte pe magazin")
        counts = df_filtrat["magazin"].value_counts()
        st.bar_chart(counts)

    with col_g2:
        st.subheader("📊 Oferte pe produs")
        counts_prod = df_filtrat["produs"].value_counts()
        st.bar_chart(counts_prod)

    # ─── CEA MAI BUNĂ OFERTĂ PER PRODUS ───
    st.markdown("---")
    st.subheader("🏆 Cea mai bună ofertă per produs")

    for produs in sorted(df_filtrat["produs"].dropna().unique()):
        sub = df_filtrat[df_filtrat["produs"] == produs].copy()
        sub = sub.dropna(subset=["pret_nou"]).sort_values("pret_nou")
        if sub.empty:
            continue

        best = sub.iloc[0]
        with st.expander(f"**{produs}** — {best['pret_nou']:.2f} lei la {best['magazin']}"):
            for _, row in sub.iterrows():
                linie = f"- **{row['titlu_oferta']}** — {row['pret_nou']:.2f} lei"
                if pd.notna(row['pret_vechi']) and row['pret_vechi'] > 0:
                    reducere = round((1 - row['pret_nou'] / row['pret_vechi']) * 100)
                    linie += f" (redus de la {row['pret_vechi']:.2f} lei, **-{reducere}%**)"
                linie += f" — *{row['magazin']}*"
                if row['card_necesar'] == "DA":
                    linie += " 💳"
                st.markdown(linie)

# ─── FOOTER ───
st.markdown("---")
st.caption(f"Ultima actualizare: {df['data'].max() if not df.empty else 'N/A'}")