import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
from sqlalchemy import create_engine
from datetime import datetime


# ----------------------------------------
# Load Data
# ----------------------------------------
def load_data(engine):
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


# ----------------------------------------
# MAIN DASHBOARD FUNCTION
# ----------------------------------------
def main():

    st.markdown("## 📊 CHESS HDSS Monitoring Dashboard")
    st.sidebar.header("Support")
    st.sidebar.markdown("**Ronny Jorry**  \n📧 ronnyjorry@gmail.com")

    # ------------------------------
    # DATABASE CONNECTION
    # ------------------------------
    try:
        supabase_url = st.secrets["connections"]["SUPABASE_URL"]
        engine = create_engine(supabase_url)
        hh_df, ind_df = load_data(engine)

    except KeyError:
        st.error("❗ Missing SUPABASE_URL in secrets.toml under [connections].")
        st.stop()
    except Exception as e:
        st.error(f"❗ Database connection failed: {e}")
        st.stop()

    # ------------------------------
    # SITE LIST
    # ------------------------------
    sites = ['central', 'east_new_britian', 'eastern_highlands', 'ncd', 'east_sepik']

    hh_df["sector_name"] = pd.to_numeric(hh_df["sector"], errors="coerce").map({
        1: "Urban",
        2: "Peri-Urban",
        3: "Settlement",
        4: "Rural"
    })

    # ------------------------------
    # SIDEBAR
    # ------------------------------
    st.sidebar.header("Site Selection")
    selected_site = st.sidebar.selectbox("Select Site", sites, index=0)

    site_hh_df = filter_site(hh_df, selected_site)

    # ------------------------------
    # TOP METRICS
    # ------------------------------
    total_hh_all = len(hh_df)
    total_ind_all = len(ind_df)

    col1, col2 = st.columns(2)
    col1.metric("Total Households (All Sites)", total_hh_all)
    col2.metric("Total Individuals (All Sites)", total_ind_all)

    total_hh_site = len(site_hh_df)
    total_ind_site = len(ind_df[ind_df["parent_key"].isin(site_hh_df["key"])])

    st.caption(
        f"**{selected_site.replace('_',' ').title()}** → {total_hh_site:,} households | {total_ind_site:,} individuals"
    )

    # ------------------------------
    # TABS
    # ------------------------------
    tab_overview, tab_sector, tab_collectors, tab_map, tab_quality, tab_report = st.tabs([
        "Overview", "Sector Analysis", "Data Collectors", "GPS Mapping", "Data Quality", "Report"
    ])

    # ---- OVERVIEW TAB ----
    with tab_overview:
        st.header("Overview")

        c1, c2, c3 = st.columns(3)
        c1.metric("Households", total_hh_site)
        c2.metric("Individuals", total_ind_site)
        c3.metric("Avg Household Size", round(total_ind_site / total_hh_site, 2) if total_hh_site > 0 else 0)

        if "dwelling_number" in site_hh_df:
            interview_map = {
                1: "Completed",
                2: "Partially completed",
                3: "Refused",
                4: "Migrated/Absent",
                5: "No competent respondent",
                6: "Other",
                96: "Don't know"
            }

            status = pd.to_numeric(site_hh_df["dwelling_number"], errors="coerce").map(interview_map)
            status_counts = status.value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]

            fig = px.pie(status_counts, names="Status", values="Count", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

    # ---- SECTOR TAB ----
    with tab_sector:
        st.header("Sector Analysis")
        if site_hh_df["sector_name"].notna().any():
            sector_counts = site_hh_df["sector_name"].value_counts().reset_index()
            colA, colB = st.columns(2)
            colA.plotly_chart(px.pie(sector_counts, names="sector_name", values="count"), use_container_width=True)
            colB.plotly_chart(px.bar(sector_counts, x="sector_name", y="count"), use_container_width=True)

    # ---- COLLECTORS TAB ----
    with tab_collectors:
        st.header("Data Collectors")
        if "submittername" in site_hh_df:
            collector = site_hh_df["submittername"].value_counts().reset_index()
            collector.columns = ["submittername", "count"]
            st.plotly_chart(px.bar(collector, x="submittername", y="count"), use_container_width=True)

    # ---- GPS MAP ----
    with tab_map:
        st.header("GPS Mapping")
        gps_df = site_hh_df.dropna(subset=["hh_gps_latitude", "hh_gps_longitude"])
        if not gps_df.empty:
            m = folium.Map(
                location=[gps_df["hh_gps_latitude"].mean(), gps_df["hh_gps_longitude"].mean()],
                zoom_start=11
            )
            for _, r in gps_df.iterrows():
                folium.Marker([r["hh_gps_latitude"], r["hh_gps_longitude"]]).add_to(m)
            st_folium(m, width=1100, height=600)

    # ---- QUALITY TAB ----
    with tab_quality:
        st.header("Data Quality")
        st.info("Quality checks coming soon.")

    # ---- REPORT TAB ----
    with tab_report:
        st.header("Daily Tally Report")
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
            WHERE h.pro_name = %s
            GROUP BY h.four_3_1, h.location_name, DATE(h.interview_date_time_1)
        """
        try:
            df_daily = pd.read_sql(daily_query, engine, params=[selected_site])
            st.dataframe(df_daily, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading report: {e}")


if __name__ == "__main__":
    main()
