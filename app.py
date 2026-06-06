"""
app.py — Big Mac Index Interactive Dashboard
Cải tiến so với dashboard gốc:
  1. KPI Summary  – Most Over/Undervalued, Global Average
  2. Glossary     – Tooltip giải thích PPP, overvalued, undervalued
  3. Filters      – Bộ lọc theo khu vực, mức GDP, khoảng năm
  4. Animation    – Choropleth animated theo năm

Chạy:  streamlit run app.py
"""

import glob
import os

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Big Mac Index Dashboard",
    page_icon="🍔",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
REGION_MAP = {
    "ARG": "Nam Mỹ",    "BRA": "Nam Mỹ",    "CHL": "Nam Mỹ",
    "COL": "Nam Mỹ",    "PER": "Nam Mỹ",    "URY": "Nam Mỹ",
    "CAN": "Bắc Mỹ",   "MEX": "Bắc Mỹ",   "USA": "Bắc Mỹ",
    "CRI": "Trung Mỹ", "GTM": "Trung Mỹ", "HND": "Trung Mỹ", "NIC": "Trung Mỹ",
    "GBR": "Châu Âu",  "DNK": "Châu Âu",  "EUZ": "Châu Âu",
    "HRV": "Châu Âu",  "CZE": "Châu Âu",  "HUN": "Châu Âu",
    "MDA": "Châu Âu",  "NOR": "Châu Âu",  "POL": "Châu Âu",
    "ROU": "Châu Âu",  "RUS": "Châu Âu",  "SWE": "Châu Âu",
    "CHE": "Châu Âu",  "TUR": "Châu Âu",  "UKR": "Châu Âu",
    "AUS": "Châu Đại Dương", "NZL": "Châu Đại Dương",
    "AZE": "Châu Á",   "CHN": "Châu Á",   "HKG": "Châu Á",
    "IDN": "Châu Á",   "IND": "Châu Á",   "JPN": "Châu Á",
    "KOR": "Châu Á",   "LKA": "Châu Á",   "MYS": "Châu Á",
    "PAK": "Châu Á",   "PHL": "Châu Á",   "SGP": "Châu Á",
    "TWN": "Châu Á",   "THA": "Châu Á",   "VNM": "Châu Á",
    "BHR": "Trung Đông", "ARE": "Trung Đông", "ISR": "Trung Đông",
    "JOR": "Trung Đông", "KWT": "Trung Đông", "LBN": "Trung Đông",
    "OMN": "Trung Đông", "QAT": "Trung Đông", "SAU": "Trung Đông",
    "EGY": "Châu Phi",  "ZAF": "Châu Phi",
}

GDP_BINS   = [float("-inf"), 5_000, 20_000, float("inf")]
GDP_LABELS = ["Thấp (< $5k)", "Trung bình ($5k–$20k)", "Cao (> $20k)"]

GLOSSARY = {
    "Big Mac Index": (
        "Chỉ số do tạp chí **The Economist** phát minh năm 1986. "
        "Dùng giá của một chiếc Big Mac tại các quốc gia để so sánh "
        "sức mua của đồng tiền – một cách đơn giản hóa lý thuyết PPP."
    ),
    "PPP (Purchasing Power Parity)": (
        "**Ngang bằng sức mua** – lý thuyết kinh tế cho rằng tỷ giá hối đoái "
        "dài hạn sẽ cân bằng ở mức mà cùng một lượng hàng hóa có giá như nhau "
        "ở tất cả các quốc gia (sau khi quy đổi sang cùng đơn vị tiền tệ)."
    ),
    "USD_raw (Overvalued / Undervalued)": (
        "Chỉ số định giá thô so với USD. "
        "**> 0** (đỏ): đồng tiền được định giá **cao hơn** USD – Big Mac đắt hơn ở Mỹ. "
        "**< 0** (xanh): đồng tiền được định giá **thấp hơn** USD – Big Mac rẻ hơn ở Mỹ."
    ),
    "Adj. Price (Adjusted Big Mac Price)": (
        "Giá Big Mac **điều chỉnh theo GDP per capita**. "
        "Phiên bản 'công bằng' hơn của USD_raw, tính đến mức thu nhập của từng quốc gia "
        "– các nước nghèo hơn thường có giá thấp hơn một cách tự nhiên."
    ),
    "Dollar Price": (
        "Giá Big Mac quy đổi sang **USD** theo tỷ giá hối đoái thị trường tại thời điểm khảo sát."
    ),
}


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data() -> pd.DataFrame:
    base = os.path.dirname(__file__)
    pattern = os.path.join(base, "outputs", "enriched_snapshot.csv", "part-*.csv")
    files = glob.glob(pattern)
    if files:
        df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    else:
        df = pd.read_csv(os.path.join(base, "data", "big mac.csv"))

    df["date"] = pd.to_datetime(df["date"])
    if "year" not in df.columns:
        df["year"] = df["date"].dt.year

    # Loại bỏ entry trùng iso_a3 (UAE vs United Arab Emirates, Britain vs GBR)
    df = df[~df["name"].isin(["UAE", "Britain"])]

    df["region"] = df["iso_a3"].map(REGION_MAP).fillna("Khác")
    df["gdp_level"] = pd.cut(
        df["GDP_dollar"], bins=GDP_BINS, labels=GDP_LABELS, right=False
    ).astype("object").fillna("Không có dữ liệu")

    return df


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_pct(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}{val * 100:.1f}%"


def color_delta(val: float) -> str:
    return "inverse" if val >= 0 else "normal"


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar(df: pd.DataFrame):
    st.sidebar.title("🎛️ Bộ lọc")

    years = sorted(df["year"].unique())
    year_range = st.sidebar.slider(
        "Khoảng năm",
        min_value=int(years[0]),
        max_value=int(years[-1]),
        value=(int(years[0]), int(years[-1])),
        step=1,
    )

    regions = sorted(df["region"].unique())
    sel_regions = st.sidebar.multiselect(
        "Khu vực",
        options=regions,
        default=regions,
        help="Chọn một hoặc nhiều khu vực địa lý",
    )

    gdp_levels = [l for l in GDP_LABELS + ["Không có dữ liệu"] if l in df["gdp_level"].unique()]
    sel_gdp = st.sidebar.multiselect(
        "Mức GDP per capita",
        options=gdp_levels,
        default=gdp_levels,
        help="Phân loại dựa trên GDP bình quân đầu người (USD)",
    )

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Reset bộ lọc & xóa cache", help="Xóa cache dữ liệu và tải lại từ đầu"):
        load_data.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Nguồn dữ liệu**: [The Economist – Big Mac Index](https://www.kaggle.com/datasets/mrmorj/big-mac-index-data)  \n"
        "Năm 2000 – 2020 · 57 quốc gia"
    )

    return year_range, sel_regions, sel_gdp


# ── KPI Cards ─────────────────────────────────────────────────────────────────
def render_kpis(df: pd.DataFrame):
    st.subheader("📊 Tổng quan nhanh")

    avg_by_country = (
        df.groupby(["name", "iso_a3"])["USD_raw"]
        .mean()
        .reset_index()
        .dropna(subset=["USD_raw"])
    )

    most_over   = avg_by_country.loc[avg_by_country["USD_raw"].idxmax()]
    most_under  = avg_by_country.loc[avg_by_country["USD_raw"].idxmin()]
    global_avg  = df["USD_raw"].mean()
    n_countries = df["name"].nunique()
    avg_price   = df["dollar_price"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "🔴 Định giá cao nhất",
        most_over["name"],
        f"USD_raw {fmt_pct(most_over['USD_raw'])}",
        delta_color="inverse",
        help="Quốc gia có đồng tiền được định giá cao hơn USD nhiều nhất (trung bình toàn kỳ)",
    )
    c2.metric(
        "🔵 Định giá thấp nhất",
        most_under["name"],
        f"USD_raw {fmt_pct(most_under['USD_raw'])}",
        delta_color="normal",
        help="Quốc gia có đồng tiền được định giá thấp hơn USD nhiều nhất (trung bình toàn kỳ)",
    )
    c3.metric(
        "🌐 TB Định giá toàn cầu",
        fmt_pct(global_avg),
        help="Trung bình USD_raw của tất cả quốc gia trong kỳ được lọc",
    )
    c4.metric(
        "💵 Giá Big Mac TB",
        f"${avg_price:.2f}",
        help="Giá Big Mac trung bình toàn cầu (USD) trong kỳ được lọc",
    )
    c5.metric(
        "🗺️ Số quốc gia",
        n_countries,
        help="Số quốc gia trong bộ lọc hiện tại",
    )


# ── Glossary ──────────────────────────────────────────────────────────────────
def render_glossary():
    with st.expander("📖 Giải thích thuật ngữ (PPP, Overvalued, USD_raw...)", expanded=False):
        cols = st.columns(len(GLOSSARY))
        for col, (term, explanation) in zip(cols, GLOSSARY.items()):
            col.markdown(f"**{term}**")
            col.markdown(explanation)


# ── Tab 1: Animated Choropleth ────────────────────────────────────────────────
def render_map_tab(df: pd.DataFrame):
    st.markdown("### 🗺️ Bản đồ Định giá Big Mac theo Năm")
    st.caption(
        "Màu **đỏ** = đồng tiền định giá cao hơn USD  ·  "
        "Màu **xanh** = định giá thấp hơn USD  ·  "
        "Nhấn ▶ để xem animation theo năm"
    )

    map_df = (
        df.groupby(["year", "iso_a3", "name"])
        .agg(USD_raw=("USD_raw", "mean"), dollar_price=("dollar_price", "mean"))
        .reset_index()
        .dropna(subset=["USD_raw"])
    )
    map_df["USD_raw_pct"] = (map_df["USD_raw"] * 100).round(1)
    map_df["hover"] = (
        map_df["name"] + "<br>"
        + "Định giá: " + map_df["USD_raw_pct"].apply(lambda v: f"{'+'if v>=0 else''}{v:.1f}%") + "<br>"
        + "Giá Big Mac: $" + map_df["dollar_price"].round(2).astype(str)
    )

    fig = px.choropleth(
        map_df,
        locations="iso_a3",
        color="USD_raw_pct",
        hover_name="name",
        hover_data={"iso_a3": False, "USD_raw_pct": ":.1f", "dollar_price": ":.2f"},
        animation_frame="year",
        color_continuous_scale=px.colors.diverging.RdBu_r,
        color_continuous_midpoint=0,
        range_color=[-80, 80],
        title="",
        labels={"USD_raw_pct": "Định giá (%)", "dollar_price": "Giá USD"},
        height=500,
    )
    fig.update_layout(
        coloraxis_colorbar=dict(
            title="Định giá (%)",
            tickvals=[-80, -40, 0, 40, 80],
            ticktext=["−80% (rẻ)", "−40%", "0 (ngang bằng)", "+40%", "+80% (đắt)"],
        ),
        geo=dict(showframe=False, showcoastlines=True, projection_type="natural earth"),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    # Tăng tốc animation
    fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 600
    fig.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 300

    st.plotly_chart(fig, width="stretch")


# ── Tab 2: Ranking Bar Chart ──────────────────────────────────────────────────
def render_ranking_tab(df: pd.DataFrame):
    st.markdown("### 📊 Xếp hạng Định giá so với USD")

    col_metric, col_top_n = st.columns([3, 1])
    metric = col_metric.radio(
        "Chỉ số",
        ["USD_raw (định giá thô)", "dollar_price (giá USD)", "adj_price (giá điều chỉnh GDP)"],
        horizontal=True,
    )
    top_n = col_top_n.slider("Số quốc gia", 10, df["name"].nunique(), 20, 5)

    col_map = {
        "USD_raw (định giá thô)": "USD_raw",
        "dollar_price (giá USD)": "dollar_price",
        "adj_price (giá điều chỉnh GDP)": "adj_price",
    }
    col = col_map[metric]

    avg = (
        df.groupby("name")[col]
        .mean()
        .reset_index()
        .dropna()
        .sort_values(col, ascending=True)
    )
    top_half  = avg.tail(top_n // 2)
    bot_half  = avg.head(top_n // 2)
    plot_df   = pd.concat([bot_half, top_half])

    if col == "USD_raw":
        plot_df["color"] = plot_df[col].apply(lambda v: "Overvalued" if v >= 0 else "Undervalued")
        color_map = {"Overvalued": "#e74c3c", "Undervalued": "#3498db"}
        x_label = "USD_raw (> 0: đắt hơn USD; < 0: rẻ hơn)"
        plot_df["display"] = (plot_df[col] * 100).round(1).astype(str) + "%"
    else:
        plot_df["color"] = "neutral"
        color_map = {"neutral": "#5d6d7e"}
        x_label = f"Giá trung bình (USD)"
        plot_df["display"] = "$" + plot_df[col].round(2).astype(str)

    fig = px.bar(
        plot_df,
        x=col,
        y="name",
        orientation="h",
        color="color",
        color_discrete_map=color_map,
        text="display",
        labels={col: x_label, "name": "Quốc gia"},
        height=max(450, top_n * 22),
    )
    fig.update_traces(textposition="outside")
    if col == "USD_raw":
        fig.add_vline(x=0, line_dash="dash", line_color="black", line_width=1.5)
    fig.update_layout(showlegend=True, margin=dict(l=0, r=60, t=10, b=0))
    st.plotly_chart(fig, width="stretch")


# ── Tab 3: Timeline ───────────────────────────────────────────────────────────
def render_timeline_tab(df: pd.DataFrame):
    st.markdown("### 📈 Diễn biến theo Thời gian")

    all_countries = sorted(df["name"].unique())
    default_pick = [c for c in ["United States", "Switzerland", "China", "Japan", "Vietnam"]
                    if c in all_countries][:5]

    selected = st.multiselect(
        "Chọn quốc gia để so sánh",
        options=all_countries,
        default=default_pick,
        max_selections=12,
    )
    metric = st.radio(
        "Chỉ số",
        ["dollar_price", "USD_raw"],
        format_func=lambda x: "Giá Big Mac (USD)" if x == "dollar_price" else "Định giá USD_raw",
        horizontal=True,
    )

    if not selected:
        st.info("Chọn ít nhất 1 quốc gia.")
        return

    timeline = (
        df[df["name"].isin(selected)]
        .groupby(["name", "year"])[metric]
        .mean()
        .reset_index()
    )

    fig = px.line(
        timeline,
        x="year",
        y=metric,
        color="name",
        markers=True,
        labels={"year": "Năm", metric: "Giá (USD)" if metric == "dollar_price" else "Định giá (USD_raw)", "name": "Quốc gia"},
        height=450,
    )
    if metric == "USD_raw":
        fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1.5,
                      annotation_text="Ngang bằng USD", annotation_position="bottom right")
    fig.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")


# ── Tab 4: GDP Scatter ────────────────────────────────────────────────────────
def render_scatter_tab(df: pd.DataFrame):
    st.markdown("### 💰 GDP per capita vs Định giá Big Mac")
    st.caption("Quốc gia giàu hơn có xu hướng có giá Big Mac đắt hơn — kiểm chứng lý thuyết PPP")

    scatter_df = df.dropna(subset=["GDP_dollar", "USD_raw"]).copy()

    if scatter_df.empty:
        st.info("Không có dữ liệu GDP với bộ lọc hiện tại. Thử bỏ chọn 'Không có dữ liệu' hoặc mở rộng bộ lọc.")
        return

    scatter_df["USD_raw_pct"] = (scatter_df["USD_raw"] * 100).round(1)
    years = sorted(scatter_df["year"].unique())

    year_sel = st.select_slider(
        "Chọn năm snapshot",
        options=years,
        value=years[-1],
    )
    snap = scatter_df[scatter_df["year"] == year_sel]

    if snap.empty:
        st.info(f"Không có dữ liệu cho năm {year_sel} với bộ lọc hiện tại.")
        return

    fig = px.scatter(
        snap,
        x="GDP_dollar",
        y="USD_raw_pct",
        color="region",
        size="dollar_price",
        size_max=22,
        hover_name="name",
        hover_data={"GDP_dollar": ":,.0f", "USD_raw_pct": ":.1f", "dollar_price": ":.2f", "region": False},
        trendline="ols",
        trendline_scope="overall",
        trendline_color_override="black",
        labels={
            "GDP_dollar": "GDP per capita (USD)",
            "USD_raw_pct": "Định giá so với USD (%)",
            "region": "Khu vực",
            "dollar_price": "Giá USD",
        },
        height=500,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    df_raw = load_data()

    # ── Sidebar & filters ─────────────────────────────────────────────────────
    year_range, sel_regions, sel_gdp = render_sidebar(df_raw)

    # pandas isin() không match NaN → xử lý riêng khi "Không có dữ liệu" được chọn
    gdp_mask = df_raw["gdp_level"].isin(sel_gdp)
    if "Không có dữ liệu" in sel_gdp:
        gdp_mask = gdp_mask | df_raw["gdp_level"].isna()

    df = df_raw[
        (df_raw["year"] >= year_range[0])
        & (df_raw["year"] <= year_range[1])
        & (df_raw["region"].isin(sel_regions))
        & gdp_mask
    ]

    # ── Header ────────────────────────────────────────────────────────────────
    st.title("🍔 Big Mac Index Dashboard")
    st.markdown(
        "Dashboard phân tích **Big Mac Index** – chỉ số so sánh sức mua đồng tiền "
        "của 57 quốc gia từ năm **2000 đến 2020** dựa trên giá của một chiếc Big Mac. "
        f"*Đang hiển thị: {year_range[0]}–{year_range[1]}, "
        f"{len(sel_regions)} khu vực, {df['name'].nunique()} quốc gia.*"
    )

    # ── Cải tiến 2: Glossary ──────────────────────────────────────────────────
    render_glossary()

    st.divider()

    # ── Cải tiến 1: KPI Summary ───────────────────────────────────────────────
    if df.empty:
        st.warning("Không có dữ liệu với bộ lọc hiện tại.")
        return
    render_kpis(df)

    st.divider()

    # ── Cải tiến 3 & 4: Charts với tabs ──────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "🗺️ Bản đồ (Animation)",
        "📊 Xếp hạng",
        "📈 Timeline",
        "💰 GDP & Định giá",
    ])
    with tab1:
        render_map_tab(df)
    with tab2:
        render_ranking_tab(df)
    with tab3:
        render_timeline_tab(df)
    with tab4:
        render_scatter_tab(df)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.divider()
    st.caption(
        "📌 **Đề xuất cải tiến được thực hiện**: "
        "KPI Summary · Giải thích thuật ngữ (Glossary) · "
        "Bộ lọc theo khu vực / GDP / năm · Animation choropleth theo năm"
    )


if __name__ == "__main__":
    main()
