import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
import json

st.set_page_config(layout="wide")
st.title("📍 Chiangrai Outage map incident report")

# ---------- LOAD GOOGLE CREDENTIAL FROM STREAMLIT SECRET ----------
creds_dict = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets.readonly"
])

# ---------- LOAD GOOGLE SHEET ----------
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1UCjvaM8A_bgCfRRELtkssWBkb_-N1JWWX8TgTunnifo"
gc = gspread.authorize(credentials)

@st.cache_data(ttl=300)  # cache for 5 minutes
def load_data():
    sheet = gc.open_by_url(spreadsheet_url).worksheet("Report")
    df = pd.DataFrame(sheet.get_all_records())

    def convert_thai_date(date_str):
        try:
            if not date_str:
                return None
            day, month, year_time = date_str.split('/')
            year, time = year_time.strip().split(' ')
            year = str(int(year) - 543)
            return f"{day}/{month}/{year} {time}"
        except Exception:
            return None

    # Convert Thai year format
    df['Stamp_Time'] = df['Stamp_Time'].astype(str).apply(convert_thai_date)

    # Force datetime
    df['Stamp_Time'] = pd.to_datetime(
        df['Stamp_Time'],
        format="%d/%m/%Y %H:%M",
        errors='coerce'
    )

    # Drop ANY rows still broken
    df = df.dropna(subset=['Stamp_Time'])

    # Convert coordinates
    df['Lat'] = pd.to_numeric(df['Lat'], errors='coerce')
    df['Long'] = pd.to_numeric(df['Long'], errors='coerce')
    df = df.dropna(subset=['Lat', 'Long'])

    return df
    
df = load_data()
# ---------- SIDEBAR FILTERS ----------
st.sidebar.header("🔎 Filter")

#Password Protection for User Filter
ADMIN_PASSWORD = "0865356474" # Change this!
password_input = st.sidebar.text_input("Admin Password (to filter by User)", type="password")

selected_user = 'ทั้งหมด'
if password_input == ADMIN_PASSWORD:
    st.sidebar.success("Access Granted")
    user_options = ['ทั้งหมด'] + sorted(df['User'].unique().tolist())
    selected_user = st.sidebar.selectbox("Filter by User", user_options)
elif password_input != "":
    st.sidebar.error("Incorrect Password")

if not pd.api.types.is_datetime64_any_dtype(df['Stamp_Time']):
    st.error("Stamp_Time is not datetime — check data format")
    st.stop()

min_date = df['Stamp_Time'].dt.date.min()
max_date = df['Stamp_Time'].dt.date.max()

st.sidebar.write("Select Date Range")
start_dt = st.sidebar.date_input("Start Date", min_date)
end_dt = st.sidebar.date_input("End Date", max_date)

equipment_keyword = st.sidebar.text_input("อุปกรณ์ที่ใช้ contains", "ฟิว")

# ---------- FILTER DATA ----------
mask = (df['Stamp_Time'].dt.date >= start_dt) & (df['Stamp_Time'].dt.date <= end_dt)
filtered_df = df[mask].copy()

if selected_user != 'ทั้งหมด':
    filtered_df = filtered_df[filtered_df['User'] == selected_user]

if equipment_keyword.strip():
    filtered_df = filtered_df[
        filtered_df['อุปกรณ์ที่ใช้'].astype(str).str.contains(equipment_keyword, na=False)
    ]

st.write(f"📊 Results: **{len(filtered_df)}** points")

# ---------- BUILD MAP ----------
if filtered_df.empty:
    m = folium.Map(location=[19.9105, 99.8406], zoom_start=9) # Default to Chiang Rai coords
else:
    # Center map on the data
    m = folium.Map(location=[filtered_df['Lat'].mean(), filtered_df['Long'].mean()], zoom_start=10)

    # 1. Add Heatmap
    HeatMap(filtered_df[['Lat', 'Long']].values.tolist(), radius=15).add_to(m)
    
    # 2. Add Marker Cluster
    marker_cluster = MarkerCluster().add_to(m)

    for _, row in filtered_df.iterrows():
        # Constructing the HTML popup (INSIDE the loop)
        popup_html = f"""
        <div style="font-family: sans-serif; font-size: 12px; min-width: 200px;">
            <div style="font-weight: bold; color: #1f77b4; border-bottom: 2px solid #1f77b4; margin-bottom: 8px;">
                📍 {row['สถานที่']}
            </div>
            <b>👤 User:</b> {row['User']}<br>
            <b>🕒 เวลา:</b> {row['Stamp_Time'].strftime('%d/%m/%Y %H:%M')}<br>
            <b>⚠️ สาเหตุ:</b> {row['สาเหตุ']}<br>
            <b>🛠️ อุปกรณ์:</b> {row.get('อุปกรณ์ที่ใช้', '-')}
        </div>
        """
        
        # Create IFrame and Marker (INSIDE the loop)
        iframe = folium.IFrame(popup_html, width=220, height=120)
        popup = folium.Popup(iframe, max_width=250)

        folium.Marker(
            location=[row['Lat'], row['Long']],
            popup=popup
        ).add_to(marker_cluster)

# Use a unique key based on the length of filtered data to ensure refresh
st_folium(m, width=1200, height=800, key=f"map_{len(filtered_df)}",returned_objects=[])








