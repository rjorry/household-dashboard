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
                # Display the table with proper formatting
                st.dataframe(
                    daily_tally_df,
                    column_config={
                        "collection_date": st.column_config.DateColumn(
                            "Collection Date",
                            format="DD/MM/YYYY"
                        ),
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
                
                # Add download button for the data
                csv = daily_tally_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Daily Tally Report (CSV)",
                    data=csv,
                    file_name=f"daily_tally_report_{selected_site.lower()}.csv",
                    mime="text/csv"
                )
                
                # Display summary statistics
                st.markdown("### Summary Statistics")
                
                # Calculate totals
                total_completed = daily_tally_df['completed'].sum()
                total_refused = daily_tally_df['refused'].sum()
                total_other = daily_tally_df['other'].sum()
                total_dont_know = daily_tally_df['dont_know'].sum()
                total_interviews = daily_tally_df['total_interviews'].sum()
                
                # Display in columns
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Total Completed", f"{total_completed:,}")
                with col2:
                    st.metric("Total Refused", f"{total_refused:,}")
                with col3:
                    st.metric("Total Other", f"{total_other:,}")
                with col4:
                    st.metric("Total Don't Know", f"{total_dont_know:,}")
                with col5:
                    st.metric("Total Interviews", f"{total_interviews:,}")
                
            else:
                st.info("No interview data available for the selected site.")
                
        except Exception as e:
            st.error(f"Error generating daily tally report: {e}")
            st.exception(e)

        
        st.caption("CHESS HDSS Monitoring Dashboard – Report generated automatically")

if __name__ == "__main__":
    main()
