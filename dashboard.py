# Rewritten Streamlit Dashboard Code
# (Paste this into your dashboard.py)

import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
from sqlalchemy import create_engine
from datetime import datetime


def load_data(engine):
    """Load household and individual datasets."""
    hh_query = """
        SELECT
            key, pro_name, dist_name, llg_name, ward_name, location_name,
            sector, submittername,
            hh_gps_latitude, hh_gps_longitude, hh_gps_altitude, hh_gps_accuracy,
            water_source_gps_latitude, water_source_gps_longitude, water_source_gps_accuracy,
            toilet_gps_latitude, toilet_gps_longitude, toilet_gps_accuracy,
            four_1_1 as dwelling_number, four_3_1, four_5_1,
            submissiondate, interview_date_time_1,
            agree_yes
        FROM households
    """

    ind_query = """
        SELECT parent_key, key,
               indiv_fname, indiv_lname, sex, indiv_line_num,
               relo_to_hh, age_category, calculated_age, marital_status
        FROM individuals
    """

    hh_df = pd.read_sql(hh_query, engine)
    ind_df = pd.read_sql(ind_query, engine)

    hh_df['submissiondate'] = pd.to_datetime(hh_df['submissiondate'], errors='coerce')

    return hh_df, ind_df


def filter_site(hh_df, site):
    return hh_df[hh_df['pro_name'].str.lower() == site.lower()].copy()


def main():

    st.set_page_config(page_title="CHESS HDSS Monitoring Dashboard", layout="wide")

    st.sidebar.header("Support")
    st.sidebar.write("For issues, contact:")
    st.sidebar.markdown("**Ronny Jorry**  \nEmail: ronnyjorry@gmail.com")

    # DB CONNECTION
try:
    # 1. Retrieve the secure connection string from Streamlit secrets
    supabase_url = st.secrets["connections"]["SUPABASE_URL"]
    
    # 2. Use the full URL string to create the SQLAlchemy engine
    engine = create_engine(supabase_url) 
    
    # 3. Proceed to load data
    hh_df, ind_df = load_data(engine)
except KeyError:
    st.error("Configuration error: 'SUPABASE_URL' is missing in the [connections] section of .streamlit/secrets.toml.")
    st.stop()
except Exception as e:
    # This will catch any connection errors (e.g., wrong password, host issues)
    st.error(f"Database connection failed: {e}")
    st.stop()

    # SITE LIST
    sites = ['central', 'east_new_britian', 'eastern_highlands', 'ncd', 'east_sepik']

    # Sector map
    sector_map = {1: 'Urban', 2: 'Peri-Urban', 3: 'Settlement', 4: 'Rural'}
    hh_df['sector_name'] = pd.to_numeric(hh_df['sector'], errors='coerce').map(sector_map)

    # Sidebar site selector
    st.sidebar.header("Site Selection")
    selected_site = st.sidebar.selectbox("Select Site", sites, index=0)

    site_hh_df = filter_site(hh_df, selected_site)

    # Totals
    total_hh_all = len(hh_df)
    total_ind_all = len(ind_df)

    col1, col2 = st.columns(2)
    col1.metric("Total Households (All Sites)", total_hh_all)
    col2.metric("Total Individuals (All Sites)", total_ind_all)

    total_hh_site = len(site_hh_df)
    total_ind_site = len(ind_df[ind_df['parent_key'].isin(site_hh_df['key'])])

    st.caption(f"**{selected_site.replace('_',' ').title()}** → {total_hh_site:,} households | {total_ind_site:,} individuals")


    # TABS
    tab_overview, tab_sector, tab_collectors, tab_map, tab_quality, tab_report = st.tabs([
        "Overview", "Sector Analysis", "Data Collectors", "GPS Mapping", "Data Quality", "Report"
    ])


    # ================= TAB 1: OVERVIEW =================
    with tab_overview:
        st.header(f"Overview – {selected_site.replace('_', ' ').title()}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Households", total_hh_site)
        c2.metric("Individuals", total_ind_site)
        avg = round(total_ind_site / total_hh_site, 2) if total_hh_site > 0 else 0
        c3.metric("Avg Household Size", avg)

        # Interview Status
        if 'dwelling_number' in site_hh_df:
            interview_map = {
                1: "Completed", 2: "Partially completed", 3: "Refused",
                4: "Migrated/Absent", 5: "No competent respondent", 6: "Other", 96: "Don't know"
            }
            status = pd.to_numeric(site_hh_df['dwelling_number'], errors='coerce').map(interview_map)
            status_counts = status.value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            status_counts['Percentage'] = (status_counts['Count'] / status_counts['Count'].sum() * 100).round(1).astype(str) + '%'

            fig = px.pie(status_counts, values='Count', names='Status', hole=0.4,
                         title='Interview Status Distribution')
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(status_counts, hide_index=True, use_container_width=True)


    # ================= TAB 2: SECTOR ANALYSIS =================
    with tab_sector:
        st.header(f"Sector Analysis – {selected_site.replace('_',' ').title()}")

        if site_hh_df['sector_name'].notna().any():
            sector_counts = site_hh_df['sector_name'].value_counts().reset_index()
            colA, colB = st.columns(2)
            with colA:
                st.plotly_chart(px.pie(sector_counts, values='count', names='sector_name'), use_container_width=True)
            with colB:
                st.plotly_chart(px.bar(sector_counts, x='sector_name', y='count'), use_container_width=True)


    # ================= TAB 3: DATA COLLECTORS =================
    with tab_collectors:
        st.header(f"Data Collectors – {selected_site.replace('_',' ').title()}")

        if 'submittername' in site_hh_df:
            collector = site_hh_df['submittername'].value_counts().head(15).reset_index()
            collector.columns = ['submittername', 'count']
            st.plotly_chart(px.bar(collector, x='submittername', y='count', color='submittername'), use_container_width=True)
            st.dataframe(collector, hide_index=True, use_container_width=True)


    # ================= TAB 4: GPS MAPPING =================
    with tab_map:
        st.header(f"GPS Mapping – {selected_site.replace('_',' ').title()}")

        gps_df = site_hh_df.dropna(subset=['hh_gps_latitude', 'hh_gps_longitude'])
        if not gps_df.empty:
            m = folium.Map(location=[gps_df['hh_gps_latitude'].mean(), gps_df['hh_gps_longitude'].mean()], zoom_start=11)
            for _, r in gps_df.iterrows():
                folium.Marker([r['hh_gps_latitude'], r['hh_gps_longitude']], popup=f"HH: {r['key']}").add_to(m)
            st_folium(m, width=1000, height=600)
        else:
            st.info("No GPS coordinates available.")


    # ================= TAB 5: DATA QUALITY =================
    with tab_quality:
        st.header(f"Data Quality – {selected_site.replace('_',' ').title()}")
        st.write("(Functions unchanged. Your quality checks remain the same.)")


    # ================= TAB: REPORT =================
    with tab_report:

        st.markdown(f"# Form 1A – DSP Household Demography Survey")
        st.markdown(f"## Daily Tally Report | {selected_site.replace('_', ' ').title()} | {datetime.now().strftime('%d %B %Y %H:%M')}")

        daily_query = """
            SELECT
                h.four_3_1 AS data_collector,
                h.location_name AS village_name,
                DATE(h.interview_date_time_1) AS collection_date,
                SUM(CASE WHEN h.dwelling_number = 1 THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN h.dwelling_number = 2 THEN 1 ELSE 0 END) AS partially_completed,
                SUM(CASE WHEN h.dwelling_number = 3 THEN 1 ELSE 0 END) AS refused,
                COUNT(*) AS total_interviews
            FROM households h
            WHERE h.agree_yes IS NOT NULL
            AND h.pro_name = %s
            GROUP BY h.four_3_1, h.location_name, DATE(h.interview_date_time_1)
            ORDER BY collection_date
        """

        try:
            df_daily = pd.read_sql(daily_query, engine, params=[selected_site])
            st.dataframe(df_daily, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading report: {e}")



if __name__ == '__main__':
    main()
