import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
from sqlalchemy import create_engine
from datetime import datetime

def main():
    # Page config
    st.set_page_config(page_title="CHESS HDSS Monitoring Dashboard", layout="wide")

    # Sidebar - Support
    st.sidebar.header("Support")
    st.sidebar.write("For issues, contact:")
    st.sidebar.markdown("**Ronny Jorry**  \nEmail: [ronnyjorry@gmail.com](mailto:ronnyjorry@gmail.com)")

    # Database connection
    try:
        supabase_url = st.secrets["connections"]["SUPABASE_URL"]
        engine = create_engine(supabase_url)

        hh_df = pd.read_sql(
            """
            SELECT
                key, pro_name, dist_name, llg_name, ward_name, location_name,
                sector, submittername,
                hh_gps_latitude, hh_gps_longitude, hh_gps_altitude, hh_gps_accuracy,
                water_source_gps_latitude, water_source_gps_longitude,
                toilet_gps_latitude, toilet_gps_longitude,
                four_1_1 as dwelling_number, four_3_1, four_5_1,
                submissiondate, interview_date_time_1,
                agree_yes
            FROM households
            """,
            engine
        )

        ind_df = pd.read_sql("SELECT parent_key, key FROM individuals", engine)

    except KeyError:
        st.error("❗ Missing SUPABASE_URL in secrets.toml under [connections].")
        st.stop()
    except Exception as e:
        st.error(f"❗ Database connection failed: {e}")
        st.stop()

    # Site list & sector mapping
    sites = ['central', 'east_new_britian', 'eastern_highlands', 'ncd', 'east_sepik']
    sector_map = {1: 'Urban', 2: 'Peri-Urban', 3: 'Settlement', 4: 'Rural'}
    hh_df['sector_name'] = pd.to_numeric(hh_df['sector'], errors='coerce').map(sector_map)
    
    # Convert submissiondate to datetime
    hh_df['submissiondate'] = pd.to_datetime(hh_df['submissiondate'], errors='coerce')

    # Sidebar - Site selection
    st.sidebar.header("Site Selection")
    selected_site = st.sidebar.selectbox("Select Site", sites, index=0)

    # Filter for selected site
    site_hh_df = hh_df[hh_df['pro_name'].str.lower() == selected_site.lower()].copy()

    # Overall totals (all sites)
    total_hh_all = len(hh_df)
    total_ind_all = len(ind_df)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Households (All Sites)", total_hh_all)
    with col2:
        st.metric("Total Individuals (All Sites)", total_ind_all)

    # Site-specific totals
    total_hh_site = len(site_hh_df)
    total_ind_site = len(ind_df[ind_df['parent_key'].isin(site_hh_df['key'])])
    st.caption(f"**{selected_site.replace('_', ' ').title()}** → {total_hh_site:,} households | {total_ind_site:,} individuals")

    # ==================== TABS (including new Report tab) ====================
    tab1, tab2, tab3, tab4, tab5, tab_report = st.tabs([
        "Overview", "Sector Analysis", "Data Collectors", "GPS Mapping", "Data Quality", "Report"
    ])

    # <-- NEW "Report" tab added here

    # ==================== TAB 1: Overview ====================
    with tab1:
        st.header(f"Overview – {selected_site.replace('_', ' ').title()}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Households", total_hh_site)
        with c2:
            st.metric("Individuals", total_ind_site)
        with c3:
            avg = round(total_ind_site / total_hh_site, 2) if total_hh_site > 0 else 0
            st.metric("Avg Household Size", avg)

        st.subheader("Interview Status")
        if 'dwelling_number' in site_hh_df.columns:
            interview_map = {
                1: "Completed",
                2: "Partially completed",
                3: "Household refused to participate",
                4: "Entire household migrated out/absent for extended period",
                5: "No competent respondent available at home",
                6: "Other (Specify)",
                96: "Don't know"
            }
            status = pd.to_numeric(site_hh_df['dwelling_number'], errors='coerce').map(interview_map)
            status_counts = status.value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            status_counts['Percentage'] = (status_counts['Count'] / status_counts['Count'].sum() * 100).round(1).astype(str) + '%'
            
            # Display pie chart
            fig = px.pie(status_counts, values='Count', names='Status', hole=0.4,
                        title='Interview Status Distribution')
            st.plotly_chart(fig, use_container_width=True)
            
            # Display the table with counts and percentages
            st.subheader('Interview Status Counts')
            st.dataframe(
                status_counts.sort_values('Count', ascending=False),
                column_config={
                    'Status': 'Interview Status',
                    'Count': st.column_config.NumberColumn('Count', format='%d'),
                    'Percentage': 'Percentage'
                },
                hide_index=True,
                use_container_width=True
            )

    # ==================== TAB 2: Sector Analysis ====================
    with tab2:
        st.header(f"Sector Analysis – {selected_site.replace('_', ' ').title()}")
        if 'sector_name' in site_hh_df.columns and site_hh_df['sector_name'].notna().any():
            sector_counts = site_hh_df['sector_name'].value_counts().reset_index()
            col1, col2 = st.columns(2)
            with col1:
                fig = px.pie(sector_counts, values='count', names='sector_name', title="By Sector")
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.bar(sector_counts, x='sector_name', y='count', title="Households per Sector")
                st.plotly_chart(fig, use_container_width=True)

    # ==================== TAB 3: Data Collectors ====================
    with tab3:
        st.header(f"Data Collectors – {selected_site.replace('_', ' ').title()}")
        if 'submittername' in site_hh_df.columns:
            collector = site_hh_df['submittername'].value_counts().head(15).reset_index()
            fig = px.bar(collector, x='submittername', y='count', color='submittername',
                         title="Households per Data Collector")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(collector, hide_index=True, use_container_width=True)

    # ==================== TAB 4: GPS Mapping ====================
    with tab4:
        st.header(f"GPS Mapping – {selected_site.replace('_', ' ').title()}")
        gps_df = site_hh_df.dropna(subset=['hh_gps_latitude', 'hh_gps_longitude'])
        if not gps_df.empty:
            m = folium.Map(location=[gps_df['hh_gps_latitude'].mean(),
                                    gps_df['hh_gps_longitude'].mean()], zoom_start=11)
            for _, r in gps_df.iterrows():
                folium.Marker([r['hh_gps_latitude'], r['hh_gps_longitude']],
                              popup=f"HH: {r['key']}").add_to(m)
            st_folium(m, width=1000, height=600)
        else:
            st.info("No GPS coordinates available.")

    # ==================== TAB 5: Data Quality ====================
    with tab5:
        st.header(f"Data Quality – {selected_site.replace('_', ' ').title()}")
        
        # Run the missing GPS query
        try:
            missing_gps_query = """
            SELECT 
                location_name AS "Village",
                location_num AS "Location Number",
                four_1_1 AS "Household Number",
                four_3_1 AS "Data Collector",
                four_5_1 AS "Quality Checker",
                interview_date_time_1 AS "Interview Date/Time",
                
                -- Original GPS Status Columns
                CASE 
                    WHEN hh_gps_latitude IS NULL OR hh_gps_longitude IS NULL OR hh_gps_altitude IS NULL 
                    THEN 'Missing' 
                    ELSE 'Complete' 
                END AS "Household GPS",
                
                CASE 
                    WHEN water_source_gps_latitude IS NULL OR water_source_gps_longitude IS NULL OR water_source_gps_altitude IS NULL 
                    THEN 'Missing' 
                    ELSE 'Complete' 
                END AS "Water Source GPS",
                
                CASE 
                    WHEN toilet_gps_latitude IS NULL OR toilet_gps_longitude IS NULL OR toilet_gps_altitude IS NULL 
                    THEN 'Missing' 
                    ELSE 'Complete' 
                END AS "Toilet GPS",
                
                -- New Accuracy Columns
                CASE 
                    WHEN hh_gps_accuracy IS NULL THEN 'N/A'
                    WHEN hh_gps_accuracy > 5 THEN CONCAT('Inaccurate (', hh_gps_accuracy::int, 'm)')
                    ELSE CONCAT('Accurate (', hh_gps_accuracy::int, 'm)')
                END AS "Household GPS Accuracy",
                
                CASE 
                    WHEN water_source_gps_accuracy IS NULL THEN 'N/A'
                    WHEN water_source_gps_accuracy > 5 THEN CONCAT('Inaccurate (', water_source_gps_accuracy::int, 'm)')
                    ELSE CONCAT('Accurate (', water_source_gps_accuracy::int, 'm)')
                END AS "Water Source GPS Accuracy",
                
                CASE 
                    WHEN toilet_gps_accuracy IS NULL THEN 'N/A'
                    WHEN toilet_gps_accuracy > 5 THEN CONCAT('Inaccurate (', toilet_gps_accuracy::int, 'm)')
                    ELSE CONCAT('Accurate (', toilet_gps_accuracy::int, 'm)')
                END AS "Toilet GPS Accuracy"

            FROM households
            WHERE 
                agree_yes = 1
                AND pro_name = %s
                AND (
                    -- Missing or Inaccurate Household GPS
                    (hh_gps_latitude IS NULL 
                    OR hh_gps_longitude IS NULL 
                    OR hh_gps_altitude IS NULL
                    OR hh_gps_accuracy > 5
                    OR hh_gps_accuracy IS NULL)

                    OR

                    -- Missing or Inaccurate Water Source GPS
                    (water_source_gps_latitude IS NULL
                    OR water_source_gps_longitude IS NULL
                    OR water_source_gps_altitude IS NULL
                    OR water_source_gps_accuracy > 5
                    OR water_source_gps_accuracy IS NULL)

                    OR

                    -- Missing or Inaccurate Toilet GPS
                    (toilet_gps_latitude IS NULL
                    OR toilet_gps_longitude IS NULL
                    OR toilet_gps_altitude IS NULL
                    OR toilet_gps_accuracy > 5
                    OR toilet_gps_accuracy IS NULL)
                )
            ORDER BY location_name, location_num, four_1_1;
            """
            
            # Execute the query with the selected site parameter
            missing_gps_df = pd.read_sql(missing_gps_query, engine, params=(selected_site,))
            
            # Display summary statistics
            st.subheader("GPS Data Quality Summary")
            
            if not missing_gps_df.empty:
                # Count GPS status by type
                hh_missing = (missing_gps_df['Household GPS'] == 'Missing').sum()
                hh_inaccurate = (missing_gps_df['Household GPS Accuracy'].str.startswith('Inaccurate')).sum()
                water_missing = (missing_gps_df['Water Source GPS'] == 'Missing').sum()
                water_inaccurate = (missing_gps_df['Water Source GPS Accuracy'].str.startswith('Inaccurate')).sum()
                toilet_missing = (missing_gps_df['Toilet GPS'] == 'Missing').sum()
                toilet_inaccurate = (missing_gps_df['Toilet GPS Accuracy'].str.startswith('Inaccurate')).sum()
                
                # Display summary metrics
                st.markdown("#### Household GPS")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Missing GPS Data", f"{hh_missing:,}")
                with col2:
                    st.metric("Inaccurate GPS (>5m)", f"{hh_inaccurate:,}")
                
                st.markdown("#### Water Source GPS")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Missing GPS Data", f"{water_missing:,}")
                with col2:
                    st.metric("Inaccurate GPS (>5m)", f"{water_inaccurate:,}")
                
                st.markdown("#### Toilet GPS")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Missing GPS Data", f"{toilet_missing:,}")
                with col2:
                    st.metric("Inaccurate GPS (>5m)", f"{toilet_inaccurate:,}")
                
                st.markdown("---")
                st.subheader("Detailed GPS Data")
                
                # Display the detailed table
                st.dataframe(
                    missing_gps_df,
                    column_config={
                        "Interview Date/Time": st.column_config.DatetimeColumn(
                            "Interview Date/Time",
                            format="DD/MM/YYYY HH:mm"
                        )
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Add download button for the data
                csv = missing_gps_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Missing GPS Data (CSV)",
                    data=csv,
                    file_name=f"missing_gps_{selected_site.lower()}.csv",
                    mime="text/csv"
                )
            else:
                st.success("No missing GPS data found for the selected site!")
                
            # Add Missing Respondent or HH Member Information section
            st.markdown("---")
            st.subheader("Missing Respondent or HH Member Information")
            
            try:
                # Query for missing respondent information
                missing_respondent_query = """
                SELECT
                    location_name,
                    location_num,
                    four_1_1 AS dwelling_number,
                    four_3_1 AS data_collector,
                    four_5_1 AS quality_checker,
                    interview_date_time_1 AS interview_datetime,
                    consent_respondent_name,
                    consent_respondent_relo,
                    consent_total_hh_members
                FROM households
                WHERE 
                    agree_yes = 1
                    AND pro_name = %s
                    AND (
                        consent_respondent_name IS NULL
                        OR consent_respondent_relo IS NULL
                        OR consent_total_hh_members IS NULL
                    )
                ORDER BY location_name, location_num, four_1_1;
                """
                
                # Execute the query
                missing_respondent_df = pd.read_sql(missing_respondent_query, engine, params=(selected_site,))
                
                if not missing_respondent_df.empty:
                    # Count missing values by field
                    missing_name = missing_respondent_df['consent_respondent_name'].isna().sum()
                    missing_relo = missing_respondent_df['consent_respondent_relo'].isna().sum()
                    missing_members = missing_respondent_df['consent_total_hh_members'].isna().sum()
                    
                    # Display summary metrics
                    st.markdown("#### Missing Data Summary")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Missing Respondent Name", f"{missing_name:,}")
                    with col2:
                        st.metric("Missing Relationship", f"{missing_relo:,}")
                    with col3:
                        st.metric("Missing HH Members", f"{missing_members:,}")
                    
                    st.markdown("---")
                    st.subheader("Detailed Missing Information")
                    
                    # Display the detailed table
                    st.dataframe(
                        missing_respondent_df,
                        column_config={
                            "interview_datetime": st.column_config.DatetimeColumn(
                                "Interview Date/Time",
                                format="DD/MM/YYYY HH:mm"
                            ),
                            "consent_respondent_name": st.column_config.TextColumn(
                                "Respondent Name",
                                help="Name of the household respondent"
                            ),
                            "consent_respondent_relo": st.column_config.TextColumn(
                                "Relationship to HH Head",
                                help="Respondent's relationship to household head"
                            ),
                            "consent_total_hh_members": st.column_config.NumberColumn(
                                "Total HH Members",
                                help="Total number of household members"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Add download button for the data
                    csv_resp = missing_respondent_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Missing Respondent Data (CSV)",
                        data=csv_resp,
                        file_name=f"missing_respondent_info_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.success("No missing respondent or household member information found!")
                
            except Exception as e:
                st.error(f"Error retrieving missing respondent information: {e}")
                st.exception(e)
            
            # Add Missing Individual Name and Sex section
            st.markdown("---")
            st.subheader("Missing Individual Name and Sex")
                
            try:
                # Query for missing individual information
                missing_individual_query = """
                    SELECT
                        h.location_name,
                        h.location_num,
                        h.four_1_1 AS dwelling_number,
                        h.four_3_1 AS data_collector,
                        h.four_5_1 AS quality_checker,
                        h.interview_date_time_1,

                        -- Individual fields
                        i.indiv_fname,
                        i.indiv_lname,
                        i.sex,
                        i.indiv_line_num,
                        i.relo_to_hh,
                        i.age_category,
                        i.calculated_age,
                        i.marital_status,

                        -- Keys
                        i.parent_key,
                        h.key AS household_key

                    FROM individuals i
                    JOIN households h 
                        ON i.parent_key = h.key

                    WHERE
                        h.agree_yes = 1
                        AND h.pro_name = %s
                        AND i.indiv_line_num IS NOT NULL
                        AND (
                            i.indiv_fname IS NULL
                            OR i.indiv_lname IS NULL
                            OR i.sex IS NULL
                        )
                    ORDER BY h.location_name, h.location_num, h.four_1_1, i.indiv_line_num;
                    """
                # Execute the query
                try:
                    missing_individual_df = pd.read_sql(missing_individual_query, engine, params=(selected_site,))
                except Exception as e:
                    st.error(f"Error retrieving missing individual information: {e}")
                    st.exception(e)
                    missing_individual_df = pd.DataFrame()
                
                if not missing_individual_df.empty:
                    try:
                        # Count missing values by field
                        missing_fname = missing_individual_df['indiv_fname'].isna().sum()
                        missing_lname = missing_individual_df['indiv_lname'].isna().sum()
                        missing_sex = missing_individual_df['sex'].isna().sum()
                        
                        # Display summary metrics
                        st.markdown("#### Missing Data Summary")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Missing First Name", f"{missing_fname:,}")
                        with col2:
                            st.metric("Missing Last Name", f"{missing_lname:,}")
                        with col3:
                            st.metric("Missing Sex", f"{missing_sex:,}")
                        
                        st.markdown("---")
                        st.subheader("Detailed Missing Information")
                        
                        # Display the detailed table
                        st.dataframe(
                            missing_individual_df.drop(columns=['parent_key', 'household_key']),  # Expose only necessary columns
                            column_config={
                                "interview_date_time_1": st.column_config.DatetimeColumn(
                                    "Interview Date/Time",
                                    format="DD/MM/YYYY HH:mm"
                                ),
                                "indiv_fname": st.column_config.TextColumn(
                                    "First Name",
                                    help="Individual's first name"
                                ),
                                "indiv_lname": st.column_config.TextColumn(
                                    "Last Name",
                                    help="Individual's last name"
                                ),
                                "sex": st.column_config.TextColumn(
                                    "Sex",
                                    help="Individual's sex"
                                ),
                                "indiv_line_num": st.column_config.NumberColumn(
                                    "Line #",
                                    help="Line number in household roster"
                                ),
                                "relo_to_hh": st.column_config.TextColumn(
                                    "Relationship to HH",
                                    help="Relationship to household head"
                                ),
                                "age_category": st.column_config.TextColumn(
                                    "Age Category",
                                    help="Age category of the individual"
                                ),
                                "calculated_age": st.column_config.NumberColumn(
                                    "Age",
                                    help="Calculated age of the individual"
                                )
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                        
                        # Add download button for the data
                        csv_indiv = missing_individual_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Download Missing Individual Data (CSV)",
                            data=csv_indiv,
                            file_name=f"missing_individual_info_{selected_site.lower()}.csv",
                            mime="text/csv"
                        )
                    except Exception as e:
                        st.error(f"Error processing individual information: {e}")
                        st.exception(e)
                else:
                    st.success("No individuals with missing name or sex information found!")
                    
            except Exception as e:
                st.error(f"Error in data quality section: {e}")
                st.exception(e)
                
            st.success("Data quality check completed. See above for any data quality issues.")

        except Exception as e:
            st.error(f"Error in data quality section: {e}")
            st.exception(e)

     # ==================== TAB: Report ====================
    with tab_report:
        # Form 1A - Daily Tally Report
        st.markdown(f"# Form 1A – DSP Household Demography Survey")
        st.markdown(f"## Daily Tally Report | {selected_site.replace('_', ' ').title()} | {datetime.now().strftime('%d %B %Y %H:%M')}")
        
        try:
            # Execute the daily tally query
            daily_tally_query = """
            SELECT
                h.four_3_1 AS data_collector,
                h.location_name AS village_name,
                DATE(h.interview_date_time_1) AS collection_date,
                SUM(CASE WHEN h.four_1_1 = 1 THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN h.four_1_1 = 2 THEN 1 ELSE 0 END) AS partially_completed,
                SUM(CASE WHEN h.four_1_1 = 3 THEN 1 ELSE 0 END) AS refused,
                SUM(CASE WHEN h.four_1_1 = 4 THEN 1 ELSE 0 END) AS could_not_be_located,
                SUM(CASE WHEN h.four_1_1 = 5 THEN 1 ELSE 0 END) AS other,
                SUM(CASE WHEN h.four_1_1 = 6 THEN 1 ELSE 0 END) AS dont_know,
                COUNT(*) AS total_interviews
            FROM households h
            WHERE h.agree_yes IS NOT NULL
            AND h.pro_name = %s
            GROUP BY
                h.four_3_1,
                h.location_name,
                DATE(h.interview_date_time_1)
            ORDER BY
                collection_date,
                data_collector,
                village_name;
            """
            
            # Execute the query with the selected site parameter
            daily_tally_df = pd.read_sql(daily_tally_query, engine, params=(selected_site,))
            
            if not daily_tally_df.empty:
                st.dataframe(
                    daily_tally_df,
                    column_config={
                        "collection_date": st.column_config.DateColumn("Collection Date", format="DD/MM/YYYY"),
                        "data_collector": "Data Collector",
                        "village_name": "Village Name",
                        "completed": "Completed",
                        "partially_completed": "Partially Completed",
                        "refused": "Refused",
                        "could_not_be_located": "Could Not Be Located",
                        "other": "Other",
                        "dont_know": "Don't Know",
                        "total_interviews": "Total Interviews"
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Download button for daily tally
                csv = daily_tally_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Daily Tally Report (CSV)",
                    data=csv,
                    file_name=f"daily_tally_report_{selected_site.lower()}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No interview data available for the selected site.")
                
        except Exception as e:
            st.error(f"Error generating daily tally report: {e}")
            st.exception(e)

        st.markdown("---")
        
        # Form 1B - Progressive Monthly Tally
        st.markdown("## Form 1B – DSP Household Demography Survey")
        st.markdown("### Progressive Monthly Tally")
        
        try:
            # Monthly tally query with monthly breakdown
            monthly_tally_query = """
            WITH monthly_sector_data AS (
                SELECT
                    DATE_TRUNC('month', TO_DATE(SUBSTRING(h.interview_date_time_1, 1, 10), 'YYYY-MM-DD')) AS month,
                    h.sector,
                    h.four_1_1 AS interview_result,
                    COUNT(DISTINCT h.key) AS households,
                    COUNT(i.key) AS population
                FROM households h
                LEFT JOIN individuals i ON i.parent_key = h.key
                WHERE h.pro_name = %s
                AND h.interview_date_time_1 ~ '^\\d{4}-\\d{2}-\\d{2}'
                AND h.four_1_1 = 1  -- Only completed interviews
                GROUP BY DATE_TRUNC('month', TO_DATE(SUBSTRING(h.interview_date_time_1, 1, 10), 'YYYY-MM-DD')), h.sector, h.four_1_1
            ),
            monthly_totals AS (
                SELECT 
                    month,
                    SUM(households) AS total_households,
                    SUM(population) AS total_population
                FROM monthly_sector_data
                GROUP BY month
            )
            SELECT
                TO_CHAR(msd.month, 'Mon YYYY') AS month_display,
                msd.month,
                -- Urban
                COALESCE(MAX(CASE WHEN msd.sector = 1 THEN msd.households END), 0) AS urban_households,
                COALESCE(MAX(CASE WHEN msd.sector = 1 THEN msd.population END), 0) AS urban_population,
                -- Peri-Urban
                COALESCE(MAX(CASE WHEN msd.sector = 2 THEN msd.households END), 0) AS periurban_households,
                COALESCE(MAX(CASE WHEN msd.sector = 2 THEN msd.population END), 0) AS periurban_population,
                -- Settlement
                COALESCE(MAX(CASE WHEN msd.sector = 3 THEN msd.households END), 0) AS settlement_households,
                COALESCE(MAX(CASE WHEN msd.sector = 3 THEN msd.population END), 0) AS settlement_population,
                -- Rural
                COALESCE(MAX(CASE WHEN msd.sector = 4 THEN msd.households END), 0) AS rural_households,
                COALESCE(MAX(CASE WHEN msd.sector = 4 THEN msd.population END), 0) AS rural_population,
                -- Totals
                mt.total_households,
                mt.total_population
            FROM monthly_sector_data msd
            JOIN monthly_totals mt ON msd.month = mt.month
            GROUP BY msd.month, mt.total_households, mt.total_population, month_display
            ORDER BY msd.month;
            """
            
            monthly_tally_df = pd.read_sql(monthly_tally_query, engine, params=(selected_site,))
            
            if not monthly_tally_df.empty:
                # Create a styled dataframe with monthly breakdown
                st.markdown("#### Progressive Monthly Tally by Sector")
                
                # Create a list to hold all monthly data
                all_months_data = []
                
                # Process each month's data
                for _, row in monthly_tally_df.iterrows():
                    month_data = {
                        'Month': row['month_display'],
                        'Urban (HH)': row['urban_households'],
                        'Urban (Pop)': row['urban_population'],
                        'Peri-Urban (HH)': row['periurban_households'],
                        'Peri-Urban (Pop)': row['periurban_population'],
                        'Settlement (HH)': row['settlement_households'],
                        'Settlement (Pop)': row['settlement_population'],
                        'Rural (HH)': row['rural_households'],
                        'Rural (Pop)': row['rural_population'],
                        'Total (HH)': row['total_households'],
                        'Total (Pop)': row['total_population']
                    }
                    all_months_data.append(month_data)
                
                # Create a dataframe with all months
                display_df = pd.DataFrame(all_months_data)
                
                # Add a grand total row
                if not display_df.empty:
                    total_row = {
                        'Month': 'GRAND TOTAL',
                        'Urban (HH)': display_df['Urban (HH)'].sum(),
                        'Urban (Pop)': display_df['Urban (Pop)'].sum(),
                        'Peri-Urban (HH)': display_df['Peri-Urban (HH)'].sum(),
                        'Peri-Urban (Pop)': display_df['Peri-Urban (Pop)'].sum(),
                        'Settlement (HH)': display_df['Settlement (HH)'].sum(),
                        'Settlement (Pop)': display_df['Settlement (Pop)'].sum(),
                        'Rural (HH)': display_df['Rural (HH)'].sum(),
                        'Rural (Pop)': display_df['Rural (Pop)'].sum(),
                        'Total (HH)': display_df['Total (HH)'].sum(),
                        'Total (Pop)': display_df['Total (Pop)'].sum()
                    }
                    display_df = pd.concat([display_df, pd.DataFrame([total_row])], ignore_index=True)
                
                # Display the dataframe with proper formatting
                st.dataframe(
                    display_df,
                    column_config={
                        "Month": st.column_config.TextColumn("Month"),
                        "Urban (HH)": st.column_config.NumberColumn("Urban (HH)"),
                        "Urban (Pop)": st.column_config.NumberColumn("Urban (Pop)"),
                        "Peri-Urban (HH)": st.column_config.NumberColumn("Peri-Urban (HH)"),
                        "Peri-Urban (Pop)": st.column_config.NumberColumn("Peri-Urban (Pop)"),
                        "Settlement (HH)": st.column_config.NumberColumn("Settlement (HH)"),
                        "Settlement (Pop)": st.column_config.NumberColumn("Settlement (Pop)"),
                        "Rural (HH)": st.column_config.NumberColumn("Rural (HH)"),
                        "Rural (Pop)": st.column_config.NumberColumn("Rural (Pop)"),
                        "Total (HH)": st.column_config.NumberColumn("Total (HH)", help="Cumulative total of households"),
                        "Total (Pop)": st.column_config.NumberColumn("Total (Pop)", help="Cumulative total of population")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Download button for monthly tally
                csv_monthly = monthly_tally_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Monthly Tally Report (CSV)",
                    data=csv_monthly,
                    file_name=f"monthly_tally_report_{selected_site.lower()}.csv",
                    mime="text/csv"
                )
                
            else:
                st.info("No monthly data available for the selected site.")
                
        except Exception as e:
            st.error(f"Error generating monthly tally report: {e}")
            
        st.markdown("---")
        
        # Interview Outcomes
        st.markdown("## Interview Outcomes")
        
        try:
            # Interview outcomes query with household and population counts
            outcomes_query = """
            WITH outcomes AS (
                SELECT
                    h.key AS household_key,
                    h.four_1_1 AS status_code,
                    COUNT(DISTINCT i.key) AS population
                FROM households h
                LEFT JOIN individuals i ON i.parent_key = h.key
                WHERE h.pro_name = %s
                GROUP BY h.key, h.four_1_1
            )
            SELECT
                'Completed' AS outcome_type,
                COUNT(DISTINCT CASE WHEN status_code = 1 THEN household_key END) AS households,
                COALESCE(SUM(CASE WHEN status_code = 1 THEN population ELSE 0 END), 0) AS population
            FROM outcomes
            
            UNION ALL
            
            SELECT
                'Partially completed' AS outcome_type,
                COUNT(DISTINCT CASE WHEN status_code = 2 THEN household_key END) AS households,
                COALESCE(SUM(CASE WHEN status_code = 2 THEN population ELSE 0 END), 0) AS population
            FROM outcomes
            
            UNION ALL
            
            SELECT
                'Refusal' AS outcome_type,
                COUNT(DISTINCT CASE WHEN status_code = 3 THEN household_key END) AS households,
                COALESCE(SUM(CASE WHEN status_code = 3 THEN population ELSE 0 END), 0) AS population
            FROM outcomes
            
            UNION ALL
            
            SELECT
                'No competent respondent' AS outcome_type,
                COUNT(DISTINCT CASE WHEN status_code = 4 THEN household_key END) AS households,
                COALESCE(SUM(CASE WHEN status_code = 4 THEN population ELSE 0 END), 0) AS population
            FROM outcomes
            
            UNION ALL
            
            SELECT
                'Absent for extended period' AS outcome_type,
                COUNT(DISTINCT CASE WHEN status_code = 5 THEN household_key END) AS households,
                COALESCE(SUM(CASE WHEN status_code = 5 THEN population ELSE 0 END), 0) AS population
            FROM outcomes;
            """
            
            outcomes_df = pd.read_sql(outcomes_query, engine, params=(selected_site,))
            
            if not outcomes_df.empty:
                # Pivot the data for the desired format
                pivot_df = outcomes_df.pivot_table(
                    index='outcome_type',
                    values=['households', 'population'],
                    aggfunc='sum'
                ).reset_index()
                
                # Create a list to hold all rows
                table_data = []
                
                # Add header row
                header = [''] + ['House', 'Pop.'] * 5
                table_data.append(header)
                
                # Add data rows
                for _, row in outcomes_df.iterrows():
                    table_data.append([
                        row['outcome_type'],
                        int(row['households']),
                        int(row['population'])
                    ])
                
                # Convert to DataFrame for display
                display_df = pd.DataFrame(table_data[1:], columns=['Outcome', 'House', 'Pop.'])
                
                # Display the table
                st.dataframe(
                    display_df,
                    column_config={
                        'Outcome': st.column_config.TextColumn('Outcome'),
                        'House': st.column_config.NumberColumn('House'),
                        'Pop.': st.column_config.NumberColumn('Pop.')
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Download button for outcomes
                csv_outcomes = outcomes_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Interview Outcomes (CSV)",
                    data=csv_outcomes,
                    file_name=f"interview_outcomes_{selected_site.lower()}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No interview outcomes data available for the selected site.")
                
        except Exception as e:
            st.error(f"Error generating interview outcomes report: {e}")
            st.exception(e)
            
        st.markdown("---")
        
        # Mortality Data - Number of Deaths by Sector
        st.markdown("## Mortality Data – Number of Deaths by Sector")
        
        try:
            # Mortality by sector query with household consent data
            mortality_query = """
            SELECT * FROM (
                SELECT
                    CASE 
                        WHEN sector = 1 THEN 'Urban'
                        WHEN sector = 2 THEN 'Peri-Urban'
                        WHEN sector = 3 THEN 'Settlement'
                        WHEN sector = 4 THEN 'Rural'
                        ELSE 'Unknown'
                    END AS sector,
                    COUNT(CASE WHEN consent_three_7_1 = 1 THEN key END) AS households_with_death,
                    SUM(CASE 
                            WHEN consent_three_7_1 = 1 
                            THEN consent_death_three_7_2 
                            ELSE 0 
                        END) AS total_deaths
                FROM households
                WHERE pro_name = %s
                GROUP BY sector

                UNION ALL

                -- TOTAL ROW
                SELECT
                    'TOTAL' AS sector,
                    COUNT(CASE WHEN consent_three_7_1 = 1 THEN key END),
                    SUM(CASE 
                            WHEN consent_three_7_1 = 1 
                            THEN consent_death_three_7_2 
                            ELSE 0 
                        END)
                FROM households
                WHERE pro_name = %s
            ) AS subquery
            ORDER BY 
                CASE 
                    WHEN sector='Urban' THEN 1
                    WHEN sector='Peri-Urban' THEN 2
                    WHEN sector='Settlement' THEN 3
                    WHEN sector='Rural' THEN 4
                    WHEN sector='TOTAL' THEN 5
                    ELSE 6
                END;
            """
            
            mortality_df = pd.read_sql(mortality_query, engine, params=(selected_site, selected_site))
            
            if not mortality_df.empty:
                # Display the mortality data in the requested format
                st.markdown("""
                | Sector | Households with Death | Total Deaths |
                |--------|----------------------|--------------|
                | **Urban** | | |
                | | {urban_households:,} | {urban_deaths:,} |
                | **Peri-Urban** | | |
                | | {periurban_households:,} | {periurban_deaths:,} |
                | **Settlement** | | |
                | | {settlement_households:,} | {settlement_deaths:,} |
                | **Rural** | | |
                | | {rural_households:,} | {rural_deaths:,} |
                | **TOTAL** | | |
                | | {total_households:,} | {total_deaths:,} |
                """.format(
                    urban_households=mortality_df[mortality_df['sector'] == 'Urban']['households_with_death'].values[0] if not mortality_df[mortality_df['sector'] == 'Urban'].empty else 0,
                    urban_deaths=mortality_df[mortality_df['sector'] == 'Urban']['total_deaths'].values[0] if not mortality_df[mortality_df['sector'] == 'Urban'].empty else 0,
                    periurban_households=mortality_df[mortality_df['sector'] == 'Peri-Urban']['households_with_death'].values[0] if not mortality_df[mortality_df['sector'] == 'Peri-Urban'].empty else 0,
                    periurban_deaths=mortality_df[mortality_df['sector'] == 'Peri-Urban']['total_deaths'].values[0] if not mortality_df[mortality_df['sector'] == 'Peri-Urban'].empty else 0,
                    settlement_households=mortality_df[mortality_df['sector'] == 'Settlement']['households_with_death'].values[0] if not mortality_df[mortality_df['sector'] == 'Settlement'].empty else 0,
                    settlement_deaths=mortality_df[mortality_df['sector'] == 'Settlement']['total_deaths'].values[0] if not mortality_df[mortality_df['sector'] == 'Settlement'].empty else 0,
                    rural_households=mortality_df[mortality_df['sector'] == 'Rural']['households_with_death'].values[0] if not mortality_df[mortality_df['sector'] == 'Rural'].empty else 0,
                    rural_deaths=mortality_df[mortality_df['sector'] == 'Rural']['total_deaths'].values[0] if not mortality_df[mortality_df['sector'] == 'Rural'].empty else 0,
                    total_households=mortality_df[mortality_df['sector'] == 'TOTAL']['households_with_death'].values[0] if not mortality_df[mortality_df['sector'] == 'TOTAL'].empty else 0,
                    total_deaths=mortality_df[mortality_df['sector'] == 'TOTAL']['total_deaths'].values[0] if not mortality_df[mortality_df['sector'] == 'TOTAL'].empty else 0
                ))
                
                # Download button for mortality data
                csv_mortality = mortality_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Mortality Data (CSV)",
                    data=csv_mortality,
                    file_name=f"mortality_by_sector_{selected_site.lower()}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No mortality data available for the selected site.")
                
        except Exception as e:
            st.error(f"Error generating mortality report: {e}")
            st.exception(e)
        
        st.caption("CHESS HDSS Monitoring Dashboard – Report generated automatically")

if __name__ == "__main__":
    main()
