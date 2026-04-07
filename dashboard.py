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
        engine = create_engine(st.secrets["connections"]["SUPABASE_URL"])
    
        hh_df = pd.read_sql(
            """
            SELECT
                key, pro_name, dist_name, llg_name, ward_name, location_name,
                sector, submittername,
                hh_gps_latitude, hh_gps_longitude, hh_gps_altitude, hh_gps_accuracy,
                water_source_gps_latitude, water_source_gps_longitude,
                toilet_gps_latitude, toilet_gps_longitude,
                dwelling_number as dwelling_number, four_1_1 as four_1_1, four_3_1, four_5_1,
                submissiondate, interview_date_time_1,
                agree_yes
            FROM households
            """,
            engine
        )
    
        ind_df = pd.read_sql(
            "SELECT parent_key, key FROM individuals",
            engine
        )
    
    except Exception as e:
        st.error(f"Database connection failed: {e}")
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
        if 'four_1_1' in site_hh_df.columns:
            interview_map = {
                1: "Completed",
                2: "Partially completed",
                3: "Household refused to participate",
                4: "Entire household migrated out/absent for extended period",
                5: "No competent respondent available at home",
                6: "Other (Specify)",
                96: "Don't know"
            }
            status = pd.to_numeric(site_hh_df['four_1_1'], errors='coerce').map(interview_map)
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
                dwelling_number AS "Household Number",
                four_3_1 AS "Data Collector",
                four_5_1 AS "Quality Checker",
                interview_date_time_1 AS "Interview Date/Time",
                four_1_1 AS "Interview Result",
                four_3_2 AS "Interviewer Comments and Observations",
                
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
                        ),
                        "Interview Result": st.column_config.NumberColumn(
                            "Interview Result",
                            help="Result code of the interview"
                        ),
                        "Interviewer Comments and Observations": st.column_config.TextColumn(
                            "Interviewer Comments and Observations",
                            help="Comments and observations from the interviewer"
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
                    file_name=f"missing_gps_data_{selected_site.lower()}.csv",
                    mime="text/csv"
                )
            else:
                st.success("No household member count mismatches found!")
                    
            # Missing Respondent or HH Member Information section
            st.markdown("---")
            st.subheader("Missing Respondent or HH Member Information")
            
            try:
                # Query for missing respondent information
                missing_respondent_query = """
                SELECT
                    location_name,
                    location_num,
                    dwelling_number AS dwelling_number,
                    four_3_1 AS data_collector,
                    four_5_1 AS quality_checker,
                    interview_date_time_1 AS interview_datetime,
                    four_1_1 AS interview_result,
                    four_3_2 AS interviewer_comments_observations,
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
                            "interview_result": st.column_config.NumberColumn(
                                "Interview Result",
                                help="Result code of the interview"
                            ),
                            "interviewer_comments_observations": st.column_config.TextColumn(
                                "Interviewer Comments and Observations",
                                help="Comments and observations from the interviewer"
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
            except Exception as e:
                st.error(f"Error running respondent query: {e}")

            # Household Member Count Mismatch section
            st.markdown("---")
            st.subheader("Household Member Count Mismatch")
            
            try:
                # Query for household member count mismatches
                member_count_query = """
                SELECT 
                h.location_name,
                h.location_num,
                h.dwelling_number,
                h.consent_total_hh_members AS declared_members,
                COUNT(i.key) AS recorded_members,
                h.submittername AS submitter_name,
                h.interview_date_time_1 AS interview_date
                FROM households h
                LEFT JOIN individuals i
                ON h.key = i.parent_key
                WHERE h.agree_yes = 1
                AND h.pro_name = %s
                GROUP BY h.key, h.location_name, h.location_num, h.dwelling_number, h.consent_total_hh_members, h.submittername, h.interview_date_time_1
                HAVING h.consent_total_hh_members <> COUNT(i.key);
                """
                
                # Execute the query
                member_count_df = pd.read_sql(member_count_query, engine, params=(selected_site,))
                
                if not member_count_df.empty:
                    # Count mismatches
                    total_mismatches = len(member_count_df)
                    
                    # Display summary metrics
                    st.markdown("#### Mismatch Summary")
                    st.metric("Households with Member Count Mismatches", f"{total_mismatches:,}")
                    
                    st.markdown("---")
                    st.subheader("Detailed Mismatch Information")
                    
                    # Display the detailed table
                    st.dataframe(
                        member_count_df,
                        column_config={
                            "declared_members": st.column_config.NumberColumn(
                                "Declared Members",
                                help="Number of household members declared by respondent"
                            ),
                            "recorded_members": st.column_config.NumberColumn(
                                "Recorded Members",
                                help="Number of household members actually recorded in the database"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Add download button for the data
                    csv_member = member_count_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Member Count Mismatches (CSV)",
                        data=csv_member,
                        file_name=f"member_count_mismatches_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.success("No household member count mismatches found!")
                    
            except Exception as e:
                st.error(f"Error in household member count mismatch check: {e}")
                st.exception(e)

            # Households With No Members Recorded section
            st.markdown("---")
            st.subheader("Households With No Members Recorded")
            
            try:
                # Query for households with no members recorded
                no_members_query = """
                SELECT 
                h.location_name,
                h.location_num,
                h.dwelling_number,
                h.submittername AS submitter_name,
                h.interview_date_time_1 AS interview_date
                FROM households h
                LEFT JOIN individuals i
                ON h.key = i.parent_key
                WHERE i.key IS NULL
                AND h.agree_yes = 1
                AND h.pro_name = %s;
                """
                
                # Execute the query
                no_members_df = pd.read_sql(no_members_query, engine, params=(selected_site,))
                
                if not no_members_df.empty:
                    # Count households with no members
                    total_no_members = len(no_members_df)
                    
                    # Display summary metrics
                    st.markdown("#### Summary")
                    st.metric("Households with No Members Recorded", f"{total_no_members:,}")
                    
                    st.markdown("---")
                    st.subheader("Detailed Information")
                    
                    # Display the detailed table
                    st.dataframe(
                        no_members_df,
                        column_config={
                            "location_name": st.column_config.TextColumn(
                                "Village",
                                help="Location name"
                            ),
                            "location_num": st.column_config.NumberColumn(
                                "Location Number",
                                help="Location number"
                            ),
                            "dwelling_number": st.column_config.NumberColumn(
                                "Dwelling Number",
                                help="Household dwelling number"
                            ),
                            "submitter_name": st.column_config.TextColumn(
                                "Submitter Name",
                                help="Name of the data submitter"
                            ),
                            "interview_date": st.column_config.DatetimeColumn(
                                "Interview Date",
                                format="DD/MM/YYYY HH:mm"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Add download button for the data
                    csv_no_members = no_members_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Households with No Members (CSV)",
                        data=csv_no_members,
                        file_name=f"households_no_members_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.success("No households with no members recorded found!")
                    
            except Exception as e:
                st.error(f"Error in households with no members check: {e}")
                st.exception(e)
            # Multiple Household Heads Table section
            st.markdown("---")
            st.subheader("Multiple Household Heads Table")
            
            try:
                # Query for households with multiple heads
                multiple_heads_query = """
                SELECT
                h.location_name,
                h.dwelling_number,
                h.submittername AS submitter,
                COUNT(*) AS head_count
                FROM individuals i
                JOIN households h
                ON h.key = i.parent_key
                WHERE i.relo_to_hh = 1
                AND h.agree_yes = 1
                AND h.pro_name = %s
                GROUP BY h.key, h.location_name, h.dwelling_number, h.submittername
                HAVING COUNT(*) > 1;
                """
                
                # Execute the query
                multiple_heads_df = pd.read_sql(multiple_heads_query, engine, params=(selected_site,))
                
                if not multiple_heads_df.empty:
                    # Count households with multiple heads
                    total_multiple_heads = len(multiple_heads_df)
                    
                    # Display summary metrics
                    st.markdown("#### Summary")
                    st.metric("Households with Multiple Heads", f"{total_multiple_heads:,}")
                    
                    st.markdown("---")
                    st.subheader("Detailed Information")
                    
                    # Display the detailed table
                    st.dataframe(
                        multiple_heads_df,
                        column_config={
                            "location_name": st.column_config.TextColumn(
                                "Village",
                                help="Location name"
                            ),
                            "dwelling_number": st.column_config.NumberColumn(
                                "Dwelling Number",
                                help="Household dwelling number"
                            ),
                            "submitter": st.column_config.TextColumn(
                                "Submitter",
                                help="Name of the data submitter"
                            ),
                            "head_count": st.column_config.NumberColumn(
                                "Number of Heads",
                                help="Number of household heads recorded"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Add download button for the data
                    csv_multiple_heads = multiple_heads_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Multiple Heads Households (CSV)",
                        data=csv_multiple_heads,
                        file_name=f"multiple_heads_households_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.success("No households with multiple heads found!")
                    
            except Exception as e:
                st.error(f"Error in multiple household heads check: {e}")
                st.exception(e)

        # Households With No Head Table section
            st.markdown("---")
            st.subheader("Households With No Head Table")
            
            try:
                # Query for households with no head
                no_head_query = """
                SELECT 
                h.location_name,
                h.dwelling_number,
                h.submittername AS submitter
                FROM households h
                LEFT JOIN individuals i ON h.key = i.parent_key AND i.relo_to_hh = 1
                WHERE h.agree_yes = 1
                AND h.pro_name = %s
                AND i.key IS NULL;
                """
                
                # Execute the query
                no_head_df = pd.read_sql(no_head_query, engine, params=(selected_site,))
                
                if not no_head_df.empty:
                    # Count households with no head
                    total_no_head = len(no_head_df)
                    
                    # Display summary metrics
                    st.markdown("#### Summary")
                    st.metric("Households with No Head", f"{total_no_head:,}")
                    
                    st.markdown("---")
                    st.subheader("Detailed Information")
                    
                    # Display the detailed table
                    st.dataframe(
                        no_head_df,
                        column_config={
                            "location_name": st.column_config.TextColumn(
                                "Village",
                                help="Location name"
                            ),
                            "dwelling_number": st.column_config.NumberColumn(
                                "Dwelling Number",
                                help="Household dwelling number"
                            ),
                            "submitter": st.column_config.TextColumn(
                                "Submitter",
                                help="Name of the data submitter"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Add download button for the data
                    csv_no_head = no_head_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Households with No Head (CSV)",
                        data=csv_no_head,
                        file_name=f"households_no_head_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.success("No households with no head found!")
                    
            except Exception as e:
                st.error(f"Error in households with no head check: {e}")
                st.exception(e)

        # Duplicate Households (Same dwelling_number) section
            st.markdown("---")
            st.subheader("Duplicate Households (Same dwelling_number)")
            
            try:
                # Query for duplicate households with same dwelling_number
                duplicate_households_query = """
                SELECT 
                    h.location_name,
                    h.location_num,
                    h.dwelling_number,
                    i.indiv_fname AS first_name_hh,
                    i.indiv_lname AS last_name_hh,
                    COUNT(DISTINCT h.key) AS household_count,
                    COUNT(i.key) AS total_individuals
                FROM households h
                LEFT JOIN individuals i 
                    ON h.key = i.parent_key 
                    AND i.relo_to_hh = 1
                WHERE h.agree_yes = 1
                AND h.pro_name = %s
                GROUP BY 
                    h.location_name,
                    h.location_num,
                    h.dwelling_number,
                    i.indiv_fname,
                    i.indiv_lname
                HAVING COUNT(DISTINCT h.key) > 1;
                """
                
                # Execute the query
                duplicate_households_df = pd.read_sql(duplicate_households_query, engine, params=(selected_site,))
                
                if not duplicate_households_df.empty:
                    # Count duplicate dwelling numbers
                    total_duplicates = len(duplicate_households_df)
                    
                    # Display summary metrics
                    st.markdown("#### Summary")
                    st.metric("Duplicate Dwelling Numbers", f"{total_duplicates:,}")
                    
                    st.markdown("---")
                    st.subheader("Detailed Information")
                    
                    # Display the detailed table
                    st.dataframe(
                        duplicate_households_df,
                        column_config={
                            "location_name": st.column_config.TextColumn(
                                "Village",
                                help="Location name"
                            ),
                            "location_num": st.column_config.NumberColumn(
                                "Location Number",
                                help="Location number"
                            ),
                            "dwelling_number": st.column_config.NumberColumn(
                                "Dwelling Number",
                                help="Household dwelling number"
                            ),
                            "first_name_hh": st.column_config.TextColumn(
                                "First Name HH",
                                help="First name of household head"
                            ),
                            "last_name_hh": st.column_config.TextColumn(
                                "Last Name HH",
                                help="Last name of household head"
                            ),
                            "household_count": st.column_config.NumberColumn(
                                "Household Count",
                                help="Number of households with this dwelling number"
                            ),
                            "total_individuals": st.column_config.NumberColumn(
                                "Total Individuals",
                                help="Total individuals in these households"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Add download button for the data
                    csv_duplicates = duplicate_households_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Duplicate Households (CSV)",
                        data=csv_duplicates,
                        file_name=f"duplicate_households_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.success("No duplicate households found!")
                    
            except Exception as e:
                st.error(f"Error in duplicate households check: {e}")
                st.exception(e)

        # Duplicate Households (Same dwelling_number) section
            st.markdown("---")
            st.subheader("Missing Sex Table")
            
            try:
                # Query for individuals with missing sex
                missing_sex_query = """
                SELECT 
                    h.location_name,
                    h.location_num,
                    h.dwelling_number,
                    h.four_3_1 AS data_collector,
                    h.interview_date_time_1 AS interview_datetime,
                    i.key AS individual_id,
                    CONCAT(i.indiv_fname, ' ', i.indiv_lname) AS full_name,
                    i.relo_to_hh AS relationship_to_head,
                    i.sex
                FROM households h
                JOIN individuals i 
                    ON h.key = i.parent_key
                WHERE h.agree_yes = 1
                AND h.pro_name = %s
                AND (
                    i.sex IS NULL 
                    OR i.sex = ''
                );
                """
                
                # Execute the query
                missing_sex_df = pd.read_sql(missing_sex_query, engine, params=(selected_site,))
                
                if not missing_sex_df.empty:
                    # Count individuals with missing sex
                    total_missing_sex = len(missing_sex_df)
                    
                    # Display summary metrics
                    st.markdown("#### Summary")
                    st.metric("Individuals with Missing Sex", f"{total_missing_sex:,}")
                    
                    st.markdown("---")
                    st.subheader("Detailed Information")
                    
                    # Display the detailed table
                    st.dataframe(
                        missing_sex_df,
                        column_config={
                            "location_name": st.column_config.TextColumn(
                                "Village",
                                help="Location name"
                            ),
                            "location_num": st.column_config.NumberColumn(
                                "Location Number",
                                help="Location number"
                            ),
                            "dwelling_number": st.column_config.NumberColumn(
                                "Dwelling Number",
                                help="Household dwelling number"
                            ),
                            "data_collector": st.column_config.TextColumn(
                                "Data Collector",
                                help="Name of the data collector"
                            ),
                            "interview_datetime": st.column_config.DatetimeColumn(
                                "Interview Date/Time",
                                format="DD/MM/YYYY HH:mm"
                            ),
                            "individual_id": st.column_config.TextColumn(
                                "Individual ID",
                                help="Individual identifier"
                            ),
                            "full_name": st.column_config.TextColumn(
                                "Full Name",
                                help="Individual's full name"
                            ),
                            "relationship_to_head": st.column_config.NumberColumn(
                                "Relationship to Head",
                                help="Relationship code to household head"
                            ),
                            "sex": st.column_config.TextColumn(
                                "Sex",
                                help="Individual's sex (missing)"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Add download button for the data
                    csv_missing_sex = missing_sex_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Missing Sex Data (CSV)",
                        data=csv_missing_sex,
                        file_name=f"missing_sex_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.success("No individuals with missing sex found!")
                    
            except Exception as e:
                st.error(f"Error in missing sex check: {e}")
                st.exception(e)
        except Exception as e:
            st.error(f"Error running GPS quality query: {e}")

# Call the main function to actually run the app
if __name__ == "__main__":
    main()
