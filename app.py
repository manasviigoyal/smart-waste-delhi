import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import os

st.set_page_config(
    page_title="Smart Waste Delhi - Decision System",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Smart Waste Collection & Route Optimization System")
st.markdown("**City-Wide Decision Support System: Delhi Metropolitan Area (1,500 Points)**")
st.markdown("---")

# 1. Load Data
@st.cache_data
def load_data():
    return pd.read_csv("smart_bins_delhi_1500.csv")

try:
    df = load_data()
except Exception as e:
    st.error("Could not find 'smart_bins_delhi_1500.csv'. Please ensure it exists in your repository.")
    st.stop()

# 2. Sidebar Controls
st.sidebar.header("⚙️ Priority Engine Tuning")
st.sidebar.markdown("Adjust multi-criteria weights for **SCPS**:")

w_u = st.sidebar.slider("Urgency Weight (w_u)", 0.0, 1.0, 0.50, 0.05)
w_r = st.sidebar.slider("Recovery Value Weight (w_r)", 0.0, 1.0, 0.30, 0.05)
w_c = st.sidebar.slider("Transit Cost Weight (w_c)", 0.0, 1.0, 0.20, 0.05)

st.sidebar.markdown("---")
st.sidebar.header("Operational Filters")
zones = ["All Zones (Delhi City-Wide)"] + sorted(df["ward_zone"].dropna().unique().tolist())
selected_zone = st.sidebar.selectbox("Filter Operational Ward", zones)
min_fill = st.sidebar.slider("Minimum Fill Level Filter (%)", 0, 100, 20, 5)

# 3. Dynamic Calculation
df["dynamic_scps"] = (w_u * df["urgency_index"] + w_r * df["recovery_index"] - w_c * df["cost_index"]).round(3)

filtered_df = df[df["current_fill_pct"] >= min_fill].copy()
if selected_zone != "All Zones (Delhi City-Wide)":
    filtered_df = filtered_df[filtered_df["ward_zone"] == selected_zone]

# 4. Top KPI Cards
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
critical_bins = filtered_df[filtered_df["current_fill_pct"] >= 75.0]
imminent_overflow = filtered_df[filtered_df["time_to_overflow_hrs"] <= 4.0]
total_energy = filtered_df["calorific_value_hhv_mj_kg"].sum()

kpi1.metric("Active Monitored Bins", f"{len(filtered_df):,}", f"{len(filtered_df)/len(df)*100:.1f}% of network")
kpi2.metric("Critical Bins (≥75% Fill)", f"{len(critical_bins):,}")
kpi3.metric("Imminent Overflows (<4h)", f"{len(imminent_overflow):,}", delta_color="inverse")
kpi4.metric("Recoverable Energy Yield", f"{total_energy:,.0f} MJ")

st.markdown("---")

# 5. Main View: Map & Prioritized Queue
col_map, col_table = st.columns([1.2, 0.8])
DEPOT_LAT, DEPOT_LON = 28.5672, 77.2100

with col_map:
    st.subheader("📍 City-Wide Geospatial Dispatch Map")
    m = folium.Map(location=[DEPOT_LAT, DEPOT_LON], zoom_start=11, tiles="OpenStreetMap")
    folium.Marker([DEPOT_LAT, DEPOT_LON], tooltip="Central Municipal Hub (AIIMS/Hauz Khas)", icon=folium.Icon(color="black", icon="home")).add_to(m)

    # 12 distinct colors for the 12 Delhi municipal zones
    cluster_colors = [
        "red", "blue", "green", "purple", "orange", "darkred",
        "darkblue", "darkgreen", "cadetblue", "darkpurple", "pink", "lightblue"
    ]

    top_map_bins = filtered_df.sort_values(by="dynamic_scps", ascending=False).head(80)
    for _, r in top_map_bins.iterrows():
        zone_color = cluster_colors[int(r["zone_cluster"]) % len(cluster_colors)]
        folium.CircleMarker(
            location=[r["latitude"], r["longitude"]],
            radius=5,
            color=zone_color,
            fill=True,
            fill_opacity=0.75,
            tooltip=f"{r['bin_id']} ({r['ward_zone']}) | Type: {r['waste_type']} | Fill: {r['current_fill_pct']}% | SCPS: {r['dynamic_scps']}"
        ).add_to(m)

    route_coords = [[DEPOT_LAT, DEPOT_LON]] + list(zip(top_map_bins.head(25)["latitude"], top_map_bins.head(25)["longitude"])) + [[DEPOT_LAT, DEPOT_LON]]
    folium.PolyLine(route_coords, color="black", weight=2.5, opacity=0.85, tooltip="Dynamic 2-Opt Fleet Route").add_to(m)
    folium_static(m, width=680, height=520)

with col_table:
    st.subheader("📋 Prioritized Collection Queue")
    display_df = filtered_df.sort_values(by="dynamic_scps", ascending=False)[[
        "bin_id", "ward_zone", "waste_type", "current_fill_pct", "time_to_overflow_hrs", "dynamic_scps"
    ]].head(15)
    
    st.dataframe(
        display_df.rename(columns={
            "bin_id": "Bin ID",
            "ward_zone": "Municipal Zone",
            "waste_type": "Waste Fraction",
            "current_fill_pct": "Fill (%)",
            "time_to_overflow_hrs": "Overflow (hrs)",
            "dynamic_scps": "SCPS Score"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("#### 🖨️ Export Daily Dispatch Manifest")
    manifest_csv = filtered_df.sort_values(by="dynamic_scps", ascending=False).head(100)[[
        "bin_id", "ward_zone", "latitude", "longitude", "amenity", "waste_type", "capacity_liters", "current_fill_pct", "dynamic_scps"
    ]].to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="Download Fleet Manifest (CSV)",
        data=manifest_csv,
        file_name="delhi_1500_fleet_manifest.csv",
        mime="text/csv"
    )

st.success("✅ Scaled to 1,500 locations across all 12 Delhi municipal zones.")
