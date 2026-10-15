"""
MonitorOferte — Dashboard Streamlit.
Citește rezultate.csv din rădăcina proiectului și afișează ofertele
cu grafice interactive Plotly, filtre și detalii complete (inclusiv gramaj).
"""
import pandas as pd
import plotly.express as px
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
    [data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        padding: 12px;
        border-radius: 8px;
        border-left: 4px solid #ff4b4b;
    }
    [data-testid="stMetric"] label {
        color: var(--text-color) !important;
    }
    [data-testid="stMetricValue"] {
        color: var(--text-color) !important;
    }
    @media (max-width: 768px) {
        h1 { font-size: 1.5rem !important; }
        [data-testid="stMetric"] label { font-size: 0.8rem !important; }
    }
</style>
""", unsafe_allow_html=True)

st.title("🛒 Monitor Oferte")
st.caption("Ofertele săptămânale din supermarketurile românești")

# ─── CITIRE DATE ───
CALE_CSV = Path(__file__).resolve().parent.parent / "rezultate.csv"

if not CALE_CSV.exists():
    st.warning("⚠️ Nu există încă rezultate. Rulează mai întâi scriptul de monitorizare.")
    st.stop()

# Citire robustă: tratăm posibilele inconsistențe de coloane
try:
    df = pd.read_csv(CALE_CSV)
except pd.errors.ParserError:
    # CSV cu număr inconsistent de coloane — citim cu engine python (mai lent dar tolerant)
    df = pd.read_csv(
        CALE_CSV,
        engine="python",
        on_bad_lines="skip",
    )

# Verificăm că avem coloanele minime necesare
coloane_necesare = ["data", "produs", "titlu_oferta", "pret_nou", "magazin"]
coloane_lipsa = [c for c in coloane_necesare if c not in df.columns]
if coloane_lipsa:
    st.error(f"❌ CSV-ul nu are coloanele necesare: {coloane_lipsa}")
    st.info("Rulează din nou scraper-ul pentru a regenera `rezultate.csv` cu formatul corect.")
    st.stop()

# Adăugăm coloanele opționale lipsă
for col in ["pret_vechi", "categorie", "card_necesar", "gramaj"]:
    if col not in df.columns:
        df[col] = ""

# Convertim coloanele numerice (valorile lipsă → NaN)
df["pret_nou"] = pd.to_numeric(df["pret_nou"], errors="coerce")
df["pret_vechi"] = pd.to_numeric(df["pret_vechi"], errors="coerce")

# Sortăm descrescător după data
df = df.sort_values("data", ascending=False).reset_index(drop=True)

# Curăță coloanele text: NaN → string gol
for col in df.select_dtypes(include="object").columns:
    df[col] = df[col].fillna("").astype(str)
    df[col] = df[col].replace({"None": "", "nan": "", "NaN": "", "null": ""})

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
    if pret_min < pret_max:
        interval_pret = st.sidebar.slider(
            "Preț (lei)",
            min_value=pret_min,
            max_value=pret_max,
            value=(pret_min, pret_max),
        )
    else:
        interval_pret = (pret_min, pret_max)
else:
    interval_pret = (0, 9999)

# Card fidelitate
doar_card = st.sidebar.checkbox("Doar oferte cu card fidelitate", value=False)

# Reducere minimă
doar_reduceri = st.sidebar.checkbox("Doar oferte cu reducere", value=False)

# Sortare
sortare = st.sidebar.selectbox(
    "Sortează după",
    ["Data (recent)", "Preț crescător", "Preț descrescător", "Produs (A-Z)", "Magazin (A-Z)"],
)

# ─── APLICARE FILTRE ───
df_filtrat = df[
    (df["magazin"].isin(magazine_selectate)) &
    (df["produs"].isin(produse_selectate)) &
    (df["pret_nou"].fillna(0).between(interval_pret[0], interval_pret[1]))
].copy()

if doar_card:
    df_filtrat = df_filtrat[df_filtrat["card_necesar"] == "DA"]

if doar_reduceri:
    df_filtrat = df_filtrat[
        df_filtrat["pret_vechi"].notna() &
        (df_filtrat["pret_vechi"] > df_filtrat["pret_nou"])
    ]

# Sortare
if sortare == "Preț crescător":
    df_filtrat = df_filtrat.sort_values("pret_nou", ascending=True)
elif sortare == "Preț descrescător":
    df_filtrat = df_filtrat.sort_values("pret_nou", ascending=False)
elif sortare == "Produs (A-Z)":
    df_filtrat = df_filtrat.sort_values("produs", ascending=True)
elif sortare == "Magazin (A-Z)":
    df_filtrat = df_filtrat.sort_values("magazin", ascending=True)

# ─── METRICI ───
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

col1.metric("Total oferte", len(df_filtrat))
col2.metric("Produse", df_filtrat["produs"].nunique())
col3.metric("Magazine", df_filtrat["magazin"].nunique())

if not df_filtrat["pret_nou"].dropna().empty:
    # Calculează reducerea medie acolo unde există preț vechi
    cu_reducere = df_filtrat[
        df_filtrat["pret_vechi"].notna() &
        (df_filtrat["pret_vechi"] > df_filtrat["pret_nou"])
    ]
    if not cu_reducere.empty:
        reduceri = (1 - cu_reducere["pret_nou"] / cu_reducere["pret_vechi"]) * 100
        col4.metric("Reducere medie", f"{reduceri.mean():.1f}%")
    else:
        col4.metric("Preț mediu", f"{df_filtrat['pret_nou'].mean():.2f} lei")

st.markdown("---")

# ─── TABEL PRINCIPAL ───
st.subheader("📋 Oferte găsite")

if df_filtrat.empty:
    st.info("Nicio ofertă nu corespunde filtrelor selectate.")
else:
    # Pregătim datele pentru afișare
    df_afisare = df_filtrat[[
        "data", "produs", "titlu_oferta", "gramaj",
        "pret_nou", "pret_vechi", "magazin", "card_necesar"
    ]].copy()
    df_afisare.columns = [
        "Data", "Produs", "Ofertă", "Gramaj",
        "Preț nou", "Preț vechi", "Magazin", "Card"
    ]

    # Formatare manuală: prețurile devin string-uri frumoase, NaN → ""
    df_afisare["Preț nou"] = df_afisare["Preț nou"].apply(
        lambda x: f"{x:.2f} lei" if pd.notna(x) else ""
    )
    df_afisare["Preț vechi"] = df_afisare["Preț vechi"].apply(
        lambda x: f"{x:.2f} lei" if pd.notna(x) else ""
    )
    df_afisare = df_afisare.fillna("").reset_index(drop=True)

    st.dataframe(
        df_afisare,
        width="stretch",
        hide_index=True,
    )

# ─── GRAFICE ───
if not df_filtrat.empty:
    st.markdown("---")

    # ─── Grafice rând 1: distribuție magazin + produs ───
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("🏪 Oferte pe magazin")
        counts = df_filtrat["magazin"].value_counts().reset_index()
        counts.columns = ["Magazin", "Număr oferte"]
        fig = px.bar(
            counts,
            x="Magazin",
            y="Număr oferte",
            color="Magazin",
            text="Număr oferte",
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            showlegend=False,
            height=400,
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_g2:
        st.subheader("🎯 Distribuție pe produse urmărite")
        counts_prod = df_filtrat["produs"].value_counts().reset_index()
        counts_prod.columns = ["Produs", "Număr oferte"]
        fig = px.pie(
            counts_prod,
            names="Produs",
            values="Număr oferte",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ─── Grafice rând 2: prețuri + reduceri ───
    col_g3, col_g4 = st.columns(2)

    with col_g3:
        st.subheader("💰 Distribuția prețurilor")
        df_pret = df_filtrat[df_filtrat["pret_nou"].notna()].copy()
        if not df_pret.empty:
            fig = px.histogram(
                df_pret,
                x="pret_nou",
                nbins=20,
                color="magazin",
                labels={"pret_nou": "Preț (lei)", "count": "Număr oferte"},
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig.update_layout(
                height=400,
                margin=dict(l=10, r=10, t=30, b=10),
                xaxis_title="Preț (lei)",
                yaxis_title="Număr oferte",
                legend_title="Magazin",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nu există prețuri pentru a afișa distribuția.")

    with col_g4:
        st.subheader("📉 Top reduceri")
        df_red = df_filtrat[
            df_filtrat["pret_vechi"].notna() &
            (df_filtrat["pret_vechi"] > df_filtrat["pret_nou"])
        ].copy()
        if not df_red.empty:
            df_red["reducere"] = ((1 - df_red["pret_nou"] / df_red["pret_vechi"]) * 100).round(1)
            df_red = df_red.sort_values("reducere", ascending=False).head(10)
            df_red["eticheta"] = df_red["produs"] + " - " + df_red["titlu_oferta"].str[:30]

            fig = px.bar(
                df_red,
                x="reducere",
                y="eticheta",
                orientation="h",
                text="reducere",
                color="reducere",
                color_continuous_scale="RdYlGn_r",
                labels={"reducere": "Reducere (%)", "eticheta": ""},
            )
            fig.update_traces(texttemplate="%{text}%", textposition="outside")
            fig.update_layout(
                height=400,
                margin=dict(l=10, r=10, t=30, b=10),
                showlegend=False,
                coloraxis_showscale=False,
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nu există reduceri (prețuri vechi) pentru a calcula topul.")

    # ─── GRAFIC EVOLUȚIE ÎN TIMP ───
    st.markdown("---")
    st.subheader("📈 Evoluția prețurilor în timp")

    produs_selectat = st.selectbox(
        "Alege produs pentru evoluție:",
        sorted(df_filtrat["produs"].unique()),
        key="evolutie_produs",
    )

    df_evolutie = df_filtrat[df_filtrat["produs"] == produs_selectat].copy()
    df_evolutie["data_dt"] = pd.to_datetime(df_evolutie["data"], errors="coerce")

    if not df_evolutie["data_dt"].isna().all() and len(df_evolutie) > 1:
        df_evolutie = df_evolutie.sort_values("data_dt")
        fig = px.line(
            df_evolutie,
            x="data_dt",
            y="pret_nou",
            color="magazin",
            markers=True,
            labels={"data_dt": "Data", "pret_nou": "Preț (lei)", "magazin": "Magazin"},
            title=f"Evoluția prețului pentru {produs_selectat}",
        )
        fig.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nu există suficiente date istorice pentru a afișa evoluția (rulează scraper-ul de mai multe ori).")

    # ─── CEA MAI BUNĂ OFERTĂ PER PRODUS ───
    st.markdown("---")
    st.subheader("🏆 Cea mai bună ofertă per produs")

    for produs in sorted(df_filtrat["produs"].dropna().unique()):
        sub = df_filtrat[df_filtrat["produs"] == produs].copy()
        sub = sub.dropna(subset=["pret_nou"]).sort_values("pret_nou")
        if sub.empty:
            continue

        best = sub.iloc[0]
        gramaj_best = f" ({best['gramaj']})" if best['gramaj'] else ""
        titlu_expander = (
            f"**{produs}** — {best['pret_nou']:.2f} lei "
            f"la {best['magazin']}{gramaj_best}"
        )

        with st.expander(titlu_expander):
            for _, row in sub.iterrows():
                gramaj = f" ({row['gramaj']})" if row['gramaj'] else ""
                linie = f"- **{row['titlu_oferta']}**{gramaj} — {row['pret_nou']:.2f} lei"
                if pd.notna(row['pret_vechi']) and row['pret_vechi'] > 0:
                    reducere = round((1 - row['pret_nou'] / row['pret_vechi']) * 100)
                    linie += f" ~~{row['pret_vechi']:.2f} lei~~ **-{reducere}%**"
                linie += f" — *{row['magazin']}*"
                if row['card_necesar'] == "DA":
                    linie += " 💳"
                st.markdown(linie)

# ─── FOOTER ───
st.markdown("---")
if not df.empty:
    st.caption(f"📅 Ultima actualizare: {df['data'].max()}")
    st.caption(f"📊 Total oferte în istoric: {len(df)}")