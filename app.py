import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials

# 1. Page Config and Title (Requirement 3)
st.set_page_config(layout="wide")
st.title("📍 Chiangrai Outage map incident report")

# ---------- LOAD GOOGLE CREDENTIAL ----------
creds_dict = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets.readonly"
])

# ---------- LOAD DATA ----------
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1UCjvaM8A_bgCfRRELtkssWBkb_-N1JWWX8TgTunnifo"
gc = gspread.authorize(credentials)

@st.cache_data(ttl=300)
def load_data():
    sheet = gc.open_by_url(spreadsheet_url).worksheet("Report")
    df = pd.DataFrame(sheet.get_all_records())

    def convert_thai_date(date_str):
        try:
            if not date_str: return None
            day, month, year_time = date_str.split('/')
            year, time = year_time.strip().split(' ')
            year = str(int(year) - 543) # Convert Buddhist year to Gregorian
            return f"{day}/{month}/{year} {time}"
        except:
            return None

    df['Stamp_Time'] = df['Stamp_Time'].astype(str).apply(convert_thai_date)
    df['Stamp_Time'] = pd.to_datetime(df['Stamp_Time'], format="%d/%m/%Y %H:%M", errors='coerce')
    df = df.dropna(subset=['Stamp_Time'])
    df['Lat'] = pd.to_numeric(df['Lat'], errors='coerce')
    df['Long'] = pd.to_numeric(df['Long'], errors='coerce')
    df = df.dropna(subset=['Lat', 'Long'])
    return df

df = load_data()

# ---------- SIDEBAR FILTERS ----------
st.sidebar.header("🔎 Filter")

# Requirement 2: Separate Date Blocks with DD/MM/YYYY format
min_date = df['Stamp_Time'].dt.date.min()
max_date = df['Stamp_Time'].dt.date.max()

st.sidebar.write("Select Date Range")
start_dt = st.sidebar.date_input("Start Date", min_date, format="DD/MM/YYYY")
end_dt = st.sidebar.date_input("End Date", max_date, format="DD/MM/YYYY")

user_options = ['ทั้งหมด'] + sorted(df['User'].unique())
selected_user = st.sidebar.selectbox("User", user_options)

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

# ---------- REQUIREMENT 1: ACCUMULATE FREQUENCY ----------
# Group by exact coordinates to count how many incidents happened at that point
freq_df = filtered_df.groupby(['Lat', 'Long', 'สถานที่']).size().reset_index(name='incident_count')

st.write(f"📊 Total Incidents Found: **{len(filtered_df)}** across **{len(freq_df)}** unique locations.")

# ---------- BUILD MAP (Requirement 4: Large Display) ----------
if freq_df.empty:
    m = folium.Map(location=[19.9105, 99.8406], zoom_start=9) # Centered on Chiang Rai
else:
    m = folium.Map(location=[freq_df['Lat'].mean(), freq_df['Long'].mean()], zoom_start=9)

    for _, row in freq_df.iterrows():
        # Create a label with the count
        # We use a DivIcon to show the number on the map
        folium.Marker(
            location=[row['Lat'], row['Long']],
            icon=folium.DivIcon(
                html=f"""<div style="font-family: sans-serif; color: white; background-color: red; 
                        border-radius: 50%; width: 25px; height: 25px; display: flex; 
                        align-items: center; justify-content: center; font-weight: bold; 
                        border: 2px solid white; box-shadow: 0px 0px 5px black;">
                        {row['incident_count']}</div>"""
            ),
            popup=f"<b>Location:</b> {row['สถานที่']}<br><b>Incidents:</b> {row['incident_count']}"
        ).add_to(m)

# Display map at ~80% width/height
st_folium(m, width=1400, height=800, use_container_width=True)
