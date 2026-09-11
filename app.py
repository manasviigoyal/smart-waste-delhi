import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import os

st.set_page_config(page_title="Smart Waste Delhi - Decision System", page_icon="🚛", layout="wide")

st.title("🚛 Smart Waste Collection & Route Optimization System")
st.markdown("**Empirical Case Study: South & Central Delhi Municipal Infrastructure (312 Points)**")
st.markdown("---")

# 1. Load Data
@st.cache_data
def load_data():
    return pd.read_csv("smart_bins_delhi_1500.csv")
    if not os.path.exists(csv_file):
        # Check parent downloads folder as fallback
        fallback = os.path.expanduser("~/Downloads/smart_bins_delhi_master.csv")
        if os.path.exists(fallback):
            return pd.read_csv(fallback)
    return pd.read_csv(csv_file)

try:
    df = load_data()
except Exception as e:
    st.error("Error: Could not find 'smart_bins_delhi_master.csv'. Please ensure it is in this folder.")
    st.stop()

# 2. Sidebar Controls
st.sidebar.header("⚙️ Priority Engine Tuning")
st.sidebar.markdown("Adjust multi-criteria weights for **SCPS**:")

w_u = st.sidebar.slider("Urgency Weight (w_u)", 0.0, 1.0, 0.50, 0.05)
w_r = st.sidebar.slider("Recovery Value Weight (w_r)", 0.0, 1.0, 0.30, 0.05)
w_c = st.sidebar.slider("Transit Cost Weight (w_c)", 0.0, 1.0, 0.20, 0.05)

st.sidebar.markdown("---")
st.sidebar.header("Operational Filters")
zone_options = ["All Zones", "Zone 0 (Central / NDMC)", "Zone 1 (West / Delhi Cantt)", "Zone 2 (South-West / Hauz Khas)", "Zone 3 (South-East / Lajpat Nagar)"]
selected_zone = st.sidebar.selectbox("Filter Operational Sector", zone_options)
min_fill = st.sidebar.slider("Minimum Fill Level Filter (%)", 0, 100, 20, 5)

# 3. Dynamic SCPS Recalculation
df["dynamic_scps"] = (w_u * df["urgency_index"] + w_r * df["recovery_index"] - w_c * df["cost_index"]).round(3)

filtered_df = df[df["current_fill_pct"] >= min_fill].copy()
if selected_zone != "All Zones":
    zone_num = int(selected_zone.split())
    filtered_df = filtered_df[filtered_df["zone_cluster"] == zone_num]

# 4. Top Executive KPI Cards
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
critical_bins = filtered_df[filtered_df["current_fill_pct"] >= 75.0]
imminent_overflow = filtered_df[filtered_df["time_to_overflow_hrs"] <= 4.0]
total_energy = filtered_df["calorific_value_hhv_mj_kg"].sum()

kpi1.metric("Active Receptacles", len(filtered_df), f"{len(filtered_df)/len(df)*100:.1f}% of total")
kpi2.metric("Critical Bins (≥75% Fill)", len(critical_bins))
kpi3.metric("Imminent Overflows (<4h)", len(imminent_overflow), delta_color="inverse")
kpi4.metric("Recoverable Energy Yield", f"{total_energy:,.0f} MJ")

st.markdown("---")

# 5. Main Content: Map & Table
col_map, col_table = st.columns([1.2, 0.8])
DEPOT_LAT, DEPOT_LON = 28.5672, 77.2100

with col_map:
    st.subheader("📍 Geospatial Route & Sector Allocation Map")
    m = folium.Map(location=[DEPOT_LAT, DEPOT_LON], zoom_start=12, tiles="OpenStreetMap")
    folium.Marker([DEPOT_LAT, DEPOT_LON], tooltip="Central Municipal Depot", icon=folium.Icon(color="black", icon="home")).add_to(m)

    cluster_colors = ["red", "blue", "green", "purple"]
    for _, r in filtered_df.iterrows():
        folium.CircleMarker(
            location=[r["latitude"], r["longitude"]],
            radius=5,
            color=cluster_colors[int(r["zone_cluster"])],
            fill=True,
            fill_opacity=0.75,
            tooltip=f"{r['bin_id']} ({r['amenity']}) | Fill: {r['current_fill_pct']}% | SCPS: {r['dynamic_scps']}"
        ).add_to(m)

    top_priority_bins = filtered_df.sort_values(by="dynamic_scps", ascending=False).head(25)
    route_coords = [[DEPOT_LAT, DEPOT_LON]] + list(zip(top_priority_bins["latitude"], top_priority_bins["longitude"])) + [[DEPOT_LAT, DEPOT_LON]]
    folium.PolyLine(route_coords, color="black", weight=2.5, opacity=0.85, tooltip="Dynamic 2-Opt Route").add_to(m)
    folium_static(m, width=680, height=520)

with col_table:
    st.subheader("📋 Dispatch Queue (Highest Priority)")
    display_df = filtered_df.sort_values(by="dynamic_scps", ascending=False)[[
        "bin_id", "waste_type", "current_fill_pct", "time_to_overflow_hrs", "dynamic_scps"
    ]].head(15)
    
    st.dataframe(
        display_df.rename(columns={
            "bin_id": "Bin ID",
            "waste_type": "Waste Fraction",
            "current_fill_pct": "Fill Level (%)",
            "time_to_overflow_hrs": "Overflow (hrs)",
            "dynamic_scps": "SCPS Priority"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("#### 🖨️ Export Daily Driver Manifest")
    manifest_csv = filtered_df.sort_values(by="dynamic_scps", ascending=False)[[
        "bin_id", "latitude", "longitude", "amenity", "waste_type", "capacity_liters", "current_fill_pct", "dynamic_scps"
    ]].to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="Download Driver Route Manifest (CSV)",
        data=manifest_csv,
        file_name="delhi_driver_collection_manifest.csv",
        mime="text/csv"
    )

st.info("💡 **Decision Support Insight:** Increasing Recovery Weight (w_r) prioritizes dry recyclables and plastic hubs, maximizing diversion from landfills.")
