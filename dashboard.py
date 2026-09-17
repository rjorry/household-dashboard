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

    # ==================== TAB: Report ====================
    with tab_report:
        st.header(f"Domain 1: Population & Demography – {selected_site.replace('_', ' ').title()}")
        
        # Load full individual and household data with required demographic fields
        try:
            hh_full_df = pd.read_sql(
                """
                SELECT key, pro_name, dist_name, llg_name, ward_name, sector, dwelling_number
                FROM households
                """,
                engine
            )
            
            ind_full_df = pd.read_sql(
                """
                SELECT parent_key, indiv_line_num, sex, age_year, est_age_years
                FROM individuals
                """,
                engine
            )
            
            # Convert age columns to numeric
            ind_full_df['age_year'] = pd.to_numeric(ind_full_df['age_year'], errors='coerce')
            ind_full_df['est_age_years'] = pd.to_numeric(ind_full_df['est_age_years'], errors='coerce')
            
            # Use age_year if available, otherwise fall back to est_age_years
            ind_full_df['final_age'] = ind_full_df['age_year'].fillna(ind_full_df['est_age_years'])
            
            # Filter for selected site
            site_hh_full = hh_full_df[hh_full_df['pro_name'].str.lower() == selected_site.lower()].copy()
            site_ind_full = ind_full_df[ind_full_df['parent_key'].isin(site_hh_full['key'])].copy()
            
            # Robust sex code normalization
            def normalize_sex(val):
                if pd.isna(val):
                    return '99'
                s = str(val).strip().upper()
                # Remove trailing .0 from floats
                if s.endswith('.0'):
                    s = s[:-2]
                if s in ('01', '1', 'M', 'MALE', 'BOY', 'M.'):
                    return '01'
                elif s in ('02', '2', 'F', 'FEMALE', 'GIRL', 'F.'):
                    return '02'
                else:
                    return '99'
            
            site_ind_full['sex_norm'] = site_ind_full['sex'].apply(normalize_sex)
            
            # Calculate site-wide demographic indicators
            total_hh = site_hh_full['key'].nunique()
            total_pop = len(site_ind_full)
            avg_hh_size = round(total_pop / total_hh, 2) if total_hh > 0 else 0
            
            males = (site_ind_full['sex_norm'] == '01').sum()
            females = (site_ind_full['sex_norm'] == '02').sum()
            sex_ratio = round((males / females * 100), 2) if females > 0 else 0
            
            children = (site_ind_full['final_age'] < 15).sum()
            working_age = ((site_ind_full['final_age'] >= 15) & (site_ind_full['final_age'] <= 64)).sum()
            elderly = (site_ind_full['final_age'] >= 65).sum()
            dependency_ratio = round(((children + elderly) / working_age * 100), 2) if working_age > 0 else 0
            
            # Display site-wide summary
            st.subheader("Site-Wide Demographic Summary")
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
            with col1:
                st.metric("Total Population", f"{total_pop:,}")
            with col2:
                st.metric("Total Households", f"{total_hh:,}")
            with col3:
                st.metric("Avg HH Size", f"{avg_hh_size:.2f}")
            with col4:
                st.metric("Males", f"{males:,}")
            with col5:
                st.metric("Females", f"{females:,}")
            with col6:
                st.metric("Sex Ratio", f"{sex_ratio:.2f}")
            with col7:
                st.metric("Dependency Ratio", f"{dependency_ratio:.2f}%")
            
            # Population Pyramid
            st.markdown("---")
            st.subheader("Age-Sex Distribution (Population Pyramid)")
            
            if not site_ind_full.empty:
                # Create 5-year age cohorts for individuals with valid age and sex
                valid_pyramid = site_ind_full.dropna(subset=['final_age']).copy()
                valid_pyramid = valid_pyramid[valid_pyramid['sex_norm'].isin(['01', '02'])]
                
                if not valid_pyramid.empty:
                    bins = list(range(0, 81, 5)) + [np.inf]
                    labels = [f"{i}-{i+4}" for i in range(0, 80, 5)] + ["80+"]
                    valid_pyramid['age_group'] = pd.cut(valid_pyramid['final_age'], bins=bins, labels=labels, right=False)
                    
                    pyramid_data = valid_pyramid.groupby(['age_group', 'sex_norm'], observed=True).size().reset_index(name='count')
                    pyramid_data['count'] = pyramid_data['count'].fillna(0)
                    
                    # Pivot for pyramid
                    male_counts = pyramid_data[pyramid_data['sex_norm'] == '01'].set_index('age_group')['count'].reindex(labels).fillna(0)
                    female_counts = pyramid_data[pyramid_data['sex_norm'] == '02'].set_index('age_group')['count'].reindex(labels).fillna(0)
                    
                    # Build pyramid chart data in long form
                    max_count = max(male_counts.max(), female_counts.max())
                    step = round(max_count / 2 / 100) * 100 if max_count > 200 else round(max_count / 2 / 10) * 10
                    if step == 0:
                        step = 1
                    top = step * 2
                    tickvals = [-top, -step, 0, step, top]
                    ticktext = [f"{top:,}", f"{step:,}", "0", f"{step:,}", f"{top:,}"]
                    
                    pyramid_chart = pd.DataFrame({
                        'Age Group': labels * 2,
                        'Population': list(-male_counts.values) + list(female_counts.values),
                        'Sex': ['Male'] * len(labels) + ['Female'] * len(labels)
                    })
                    
                    fig = px.bar(
                        pyramid_chart,
                        y='Age Group',
                        x='Population',
                        color='Sex',
                        orientation='h',
                        barmode='overlay',
                        title=f"Population Pyramid – {selected_site.replace('_', ' ').title()}",
                        color_discrete_map={'Male': '#3b6e9b', 'Female': '#c45c7a'}
                    )
                    fig.update_layout(
                        xaxis_title="Population",
                        yaxis_title="Age Group",
                        bargap=0.1,
                        plot_bgcolor='white',
                        xaxis=dict(tickvals=tickvals, ticktext=ticktext),
                        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No valid age and sex data available to build the population pyramid.")
            
            # Key indicators explanation
            st.markdown("---")
            st.subheader("Key Indicators Captured")
            st.markdown("""
            **Total Population:** Sum of registered individuals in the surveillance roster.
            
            **Total Households & Avg HH Size:** Count of unique households; average size is total population divided by total households.
            
            **Sex Ratio:** Males per 100 females; identifies gender imbalances.
            
            **Dependency Ratio:** Percentage of dependents (children under 15 + elderly 65+) relative to working-age population (15–64); a critical indicator of economic burden.
            
            **Age-Sex Distribution / Pyramid:** Disaggregation into 5-year age cohorts by sex, showing population structure.
            """)
            
            # District and Sector breakdown
            st.markdown("---")
            st.subheader("Demographic Indicators by District & Sector")
            
            # SQL aggregation by district and sector using correct parent_key join
            demographic_sql = """
            SELECT 
                h.pro_name AS province,
                h.dist_name AS district,
                h.sector AS sector_code,
                CASE 
                    WHEN h.sector = '01' THEN 'Urban'
                    WHEN h.sector = '02' THEN 'Peri-Urban'
                    WHEN h.sector = '03' THEN 'Settlement'
                    WHEN h.sector = '04' THEN 'Rural'
                    ELSE 'Unclassified'
                END AS sector_label,
                COUNT(DISTINCT h.key) AS total_households,
                COUNT(i.indiv_line_num) AS total_population,
                ROUND(COUNT(i.indiv_line_num) * 1.0 / NULLIF(COUNT(DISTINCT h.key), 0), 2) AS avg_household_size,
                SUM(CASE WHEN LPAD(COALESCE(i.sex::text, ''), 2, '0') = '01' THEN 1 ELSE 0 END) AS total_males,
                SUM(CASE WHEN LPAD(COALESCE(i.sex::text, ''), 2, '0') = '02' THEN 1 ELSE 0 END) AS total_females,
                ROUND(
                    (SUM(CASE WHEN LPAD(COALESCE(i.sex::text, ''), 2, '0') = '01' THEN 1 ELSE 0 END) * 100.0) / 
                    NULLIF(SUM(CASE WHEN LPAD(COALESCE(i.sex::text, ''), 2, '0') = '02' THEN 1 ELSE 0 END), 0), 2
                ) AS sex_ratio,
                SUM(CASE WHEN COALESCE(i.age_year, i.est_age_years) < 15 THEN 1 ELSE 0 END) AS children_0_14,
                SUM(CASE WHEN COALESCE(i.age_year, i.est_age_years) BETWEEN 15 AND 64 THEN 1 ELSE 0 END) AS working_age_15_64,
                SUM(CASE WHEN COALESCE(i.age_year, i.est_age_years) >= 65 THEN 1 ELSE 0 END) AS elderly_65_plus,
                ROUND(
                    ((SUM(CASE WHEN COALESCE(i.age_year, i.est_age_years) < 15 OR COALESCE(i.age_year, i.est_age_years) >= 65 THEN 1 ELSE 0 END)) * 100.0) / 
                    NULLIF(SUM(CASE WHEN COALESCE(i.age_year, i.est_age_years) BETWEEN 15 AND 64 THEN 1 ELSE 0 END), 0), 2
                ) AS dependency_ratio
            FROM households h
            LEFT JOIN individuals i ON h.key = i.parent_key
            WHERE h.pro_name = %s
            GROUP BY h.pro_name, h.dist_name, h.sector
            ORDER BY h.dist_name, h.sector;
            """
            
            demographic_df = pd.read_sql(demographic_sql, engine, params=(selected_site,))
            
            if not demographic_df.empty:
                # Display the data table
                st.dataframe(
                    demographic_df,
                    column_config={
                        "province": st.column_config.TextColumn("Province"),
                        "district": st.column_config.TextColumn("District"),
                        "sector_code": st.column_config.TextColumn("Sector Code"),
                        "sector_label": st.column_config.TextColumn("Sector"),
                        "total_households": st.column_config.NumberColumn("Total Households", format="%d"),
                        "total_population": st.column_config.NumberColumn("Total Population", format="%d"),
                        "avg_household_size": st.column_config.NumberColumn("Avg HH Size", format="%.2f"),
                        "total_males": st.column_config.NumberColumn("Males", format="%d"),
                        "total_females": st.column_config.NumberColumn("Females", format="%d"),
                        "sex_ratio": st.column_config.NumberColumn("Sex Ratio (M/F*100)", format="%.2f"),
                        "children_0_14": st.column_config.NumberColumn("Children 0-14", format="%d"),
                        "working_age_15_64": st.column_config.NumberColumn("Working Age 15-64", format="%d"),
                        "elderly_65_plus": st.column_config.NumberColumn("Elderly 65+", format="%d"),
                        "dependency_ratio": st.column_config.NumberColumn("Dependency Ratio (%)", format="%.2f")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Add download button
                csv_demo = demographic_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Demographic Analysis (CSV)",
                    data=csv_demo,
                    file_name=f"domain1_demography_{selected_site.lower()}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No district/sector data available for this site.")
                
        except Exception as e:
            st.error(f"Error running demographic analysis: {e}")
            st.exception(e)

    st.markdown("---")
    st.header(f"Domain 2: Education & Human Capital – {selected_site.replace('_', ' ').title()}")

    try:
        # Load individual education records for the selected site
        edu_df = pd.read_sql(
            """
            SELECT 
                h.pro_name, h.dist_name, h.sector,
                i.indiv_line_num, i.sex, i.age_year, i.est_age_years,
                i.edu_info_currently_school AS currently_school,
                i.edu_info_highest_level_edu AS highest_level_edu,
                i.edu_info_main_reason_not_sch AS main_reason_not_sch,
                i.edu_info_reason_not_furth_edu AS reason_not_furth_edu
            FROM households h
            LEFT JOIN individuals i ON h.key = i.parent_key
            WHERE h.pro_name = %s
            """,
            engine,
            params=(selected_site,)
        )

        # Convert age columns to numeric
        edu_df['age_year'] = pd.to_numeric(edu_df['age_year'], errors='coerce')
        edu_df['est_age_years'] = pd.to_numeric(edu_df['est_age_years'], errors='coerce')
        edu_df['final_age'] = edu_df['age_year'].fillna(edu_df['est_age_years'])

        # Normalize sex codes
        def edu_normalize_sex(val):
            if pd.isna(val):
                return '99'
            s = str(val).strip().upper()
            if s.endswith('.0'):
                s = s[:-2]
            if s in ('01', '1', 'M', 'MALE', 'BOY', 'M.'):
                return '01'
            elif s in ('02', '2', 'F', 'FEMALE', 'GIRL', 'F.'):
                return '02'
            else:
                return '99'

        edu_df['sex_norm'] = edu_df['sex'].apply(edu_normalize_sex)

        # Normalize coded string variables to two-digit strings
        for col in ['currently_school', 'highest_level_edu', 'main_reason_not_sch', 'reason_not_furth_edu']:
            edu_df[col + '_norm'] = (
                edu_df[col]
                .astype('string')
                .fillna('')
                .str.strip()
                .str.replace(r'\.0$', '', regex=True)
                .str.zfill(2)
            )

        # Subsets
        edu_5plus = edu_df[edu_df['final_age'] >= 5].copy()
        edu_15plus = edu_df[edu_df['final_age'] >= 15].copy()

        # Site-wide metrics
        pop_5plus = len(edu_5plus)
        pop_15plus = len(edu_15plus)

        attending = (edu_5plus['currently_school_norm'] == '01').sum()
        attendance_rate = round(attending * 100.0 / pop_5plus, 2) if pop_5plus > 0 else 0

        male_5plus = edu_5plus[edu_5plus['sex_norm'] == '01']
        female_5plus = edu_5plus[edu_5plus['sex_norm'] == '02']
        male_rate = round(
            (male_5plus['currently_school_norm'] == '01').sum() * 100.0 / len(male_5plus), 2
        ) if len(male_5plus) > 0 else 0
        female_rate = round(
            (female_5plus['currently_school_norm'] == '01').sum() * 100.0 / len(female_5plus), 2
        ) if len(female_5plus) > 0 else 0
        gpi = round(female_rate / male_rate, 2) if male_rate > 0 else 0

        # Educational attainment (adults 15+)
        primary_codes = {'02', '03', '04', '05', '06', '07', '08', '09', '10'}
        secondary_codes = {'04', '07', '08', '09', '10'}
        tertiary_tvet_codes = {'06', '08', '10'}

        primary_rate = round(
            edu_15plus['highest_level_edu_norm'].isin(primary_codes).sum() * 100.0 / pop_15plus, 2
        ) if pop_15plus > 0 else 0
        secondary_rate = round(
            edu_15plus['highest_level_edu_norm'].isin(secondary_codes).sum() * 100.0 / pop_15plus, 2
        ) if pop_15plus > 0 else 0
        tertiary_rate = round(
            edu_15plus['highest_level_edu_norm'].isin(tertiary_tvet_codes).sum() * 100.0 / pop_15plus, 2
        ) if pop_15plus > 0 else 0

        # Display site-wide metrics
        st.subheader("Site-Wide Education & Human Capital Summary")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Pop Aged 5+", f"{pop_5plus:,}")
            st.metric("Attendance Rate", f"{attendance_rate:.2f}%")
        with c2:
            st.metric("Male Attendance", f"{male_rate:.2f}%")
            st.metric("Female Attendance", f"{female_rate:.2f}%")
            st.metric("GPI", f"{gpi:.2f}")
        with c3:
            st.metric("Adult Pop 15+", f"{pop_15plus:,}")
            st.metric("Primary+", f"{primary_rate:.2f}%")
        with c4:
            st.metric("Secondary+", f"{secondary_rate:.2f}%")
            st.metric("Tertiary/TVET+", f"{tertiary_rate:.2f}%")

        # Barriers and drop-out drivers
        st.markdown("---")
        st.subheader("Barriers to Schooling and Drop-out Drivers")

        main_reason_map = {
            '00': 'Not Applicable / People Attending School',
            '01': 'No school nearby',
            '02': 'School fees',
            '03': 'Disability',
            '04': 'Cultural / traditional',
            '05': 'Lack of interest',
            '06': 'Other Reasons'
        }
        further_reason_map = {
            '00': 'Not Applicable / People Attending School',
            '01': 'Academic drop-out',
            '02': 'School fees',
            '03': 'Forced marriage / cultural',
            '04': 'Pregnancy',
            '05': 'Disability',
            '06': 'Other Reasons'
        }

        barrier_counts = edu_5plus.loc[edu_5plus['main_reason_not_sch_norm'].ne(''), 'main_reason_not_sch_norm'].value_counts()
        barrier_data = pd.DataFrame([
            {'Reason': main_reason_map.get(k, f'Code {k}'), 'Count': int(v)}
            for k, v in barrier_counts.items()
        ])

        further_counts = edu_5plus.loc[edu_5plus['reason_not_furth_edu_norm'].ne(''), 'reason_not_furth_edu_norm'].value_counts()
        further_data = pd.DataFrame([
            {'Reason': further_reason_map.get(k, f'Code {k}'), 'Count': int(v)}
            for k, v in further_counts.items()
        ])

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Barriers to Schooling (never attended)**")
            if not barrier_data.empty:
                st.dataframe(barrier_data, hide_index=True, use_container_width=True)
                fig_b = px.bar(
                    barrier_data.sort_values('Count', ascending=True),
                    y='Reason',
                    x='Count',
                    orientation='h',
                    title='Barriers to Schooling',
                    color_discrete_sequence=['#3b6e9b']
                )
                fig_b.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_b, use_container_width=True)
            else:
                st.info("No barrier data available.")

        with col2:
            st.markdown("**Drop-out / Non-Furtherance Drivers**")
            if not further_data.empty:
                st.dataframe(further_data, hide_index=True, use_container_width=True)
                fig_d = px.bar(
                    further_data.sort_values('Count', ascending=True),
                    y='Reason',
                    x='Count',
                    orientation='h',
                    title='Drop-out / Non-Furtherance Drivers',
                    color_discrete_sequence=['#c45c7a']
                )
                fig_d.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_d, use_container_width=True)
            else:
                st.info("No drop-out driver data available.")

        # District and sector breakdown
        st.markdown("---")
        st.subheader("Education Indicators by District & Sector")

        edu_district_data = []
        for (district, sector), group in edu_df.groupby(['dist_name', 'sector']):
            g_5plus = group[group['final_age'] >= 5]
            g_15plus = group[group['final_age'] >= 15]

            pop_5 = len(g_5plus)
            pop_15 = len(g_15plus)

            att_rate = round(
                (g_5plus['currently_school_norm'] == '01').sum() * 100.0 / pop_5, 2
            ) if pop_5 > 0 else 0

            m_5 = g_5plus[g_5plus['sex_norm'] == '01']
            f_5 = g_5plus[g_5plus['sex_norm'] == '02']
            m_rate = round(
                (m_5['currently_school_norm'] == '01').sum() * 100.0 / len(m_5), 2
            ) if len(m_5) > 0 else 0
            f_rate = round(
                (f_5['currently_school_norm'] == '01').sum() * 100.0 / len(f_5), 2
            ) if len(f_5) > 0 else 0
            gpi_val = round(f_rate / m_rate, 2) if m_rate > 0 else 0

            p_rate = round(
                g_15plus['highest_level_edu_norm'].isin(primary_codes).sum() * 100.0 / pop_15, 2
            ) if pop_15 > 0 else 0
            s_rate = round(
                g_15plus['highest_level_edu_norm'].isin(secondary_codes).sum() * 100.0 / pop_15, 2
            ) if pop_15 > 0 else 0
            t_rate = round(
                g_15plus['highest_level_edu_norm'].isin(tertiary_tvet_codes).sum() * 100.0 / pop_15, 2
            ) if pop_15 > 0 else 0

            sector_map = {
                '01': 'Urban', '02': 'Peri-Urban', '03': 'Settlement', '04': 'Rural'
            }
            edu_district_data.append({
                'District': district,
                'Sector Code': sector,
                'Sector': sector_map.get(str(sector).zfill(2), 'Unclassified'),
                'Pop 5+': pop_5,
                'Attendance Rate (%)': att_rate,
                'Male Attendance (%)': m_rate,
                'Female Attendance (%)': f_rate,
                'GPI': gpi_val,
                'Pop 15+': pop_15,
                'Primary+ (%)': p_rate,
                'Secondary+ (%)': s_rate,
                'Tertiary/TVET+ (%)': t_rate
            })

        edu_district_df = pd.DataFrame(edu_district_data)

        if not edu_district_df.empty:
            st.dataframe(
                edu_district_df,
                column_config={
                    'District': st.column_config.TextColumn('District'),
                    'Sector Code': st.column_config.TextColumn('Sector Code'),
                    'Sector': st.column_config.TextColumn('Sector'),
                    'Pop 5+': st.column_config.NumberColumn('Pop 5+', format='%d'),
                    'Attendance Rate (%)': st.column_config.NumberColumn('Attendance Rate (%)', format='%.2f'),
                    'Male Attendance (%)': st.column_config.NumberColumn('Male Attendance (%)', format='%.2f'),
                    'Female Attendance (%)': st.column_config.NumberColumn('Female Attendance (%)', format='%.2f'),
                    'GPI': st.column_config.NumberColumn('GPI', format='%.2f'),
                    'Pop 15+': st.column_config.NumberColumn('Pop 15+', format='%d'),
                    'Primary+ (%)': st.column_config.NumberColumn('Primary+ (%)', format='%.2f'),
                    'Secondary+ (%)': st.column_config.NumberColumn('Secondary+ (%)', format='%.2f'),
                    'Tertiary/TVET+ (%)': st.column_config.NumberColumn('Tertiary/TVET+ (%)', format='%.2f')
                },
                hide_index=True,
                use_container_width=True
            )

            csv_edu = edu_district_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label='Download Education Analysis (CSV)',
                data=csv_edu,
                file_name=f'domain2_education_{selected_site.lower()}.csv',
                mime='text/csv'
            )
        else:
            st.info("No district/sector education data available for this site.")

        # Key indicators explanation
        st.markdown("---")
        st.subheader("Key Indicators Captured")
        st.markdown("""
        **School Attendance Rate (Aged 5+):** Percentage of the population aged 5 years and older currently attending school. A key indicator of school participation.

        **Educational Attainment (Aged 15+):** Percentage of adults (15+) who have completed at least primary, secondary, or tertiary/TVET education. Captures the stock of human capital in the adult population.

        **Gender Parity Index (GPI):** Ratio of female to male school attendance rates. A value of 1.0 indicates parity; values below 1.0 suggest male advantage, while values above 1.0 suggest female advantage.

        **Barriers to Schooling (never attended):** Distribution of primary reasons reported for never enrolling in school, such as distance, cost, disability, cultural reasons, or lack of interest.

        **Drop-out / Non-Furtherance Drivers:** Distribution of main causes for discontinuing studies beyond the highest level completed, including academic drop-out, fees, forced marriage/cultural pressures, pregnancy, and disability.
        """)

    except Exception as e:
        if 'currently_school' in str(e) or 'highest_level_edu' in str(e) or 'main_reason_not_sch' in str(e) or 'reason_not_furth_edu' in str(e):
            st.info("Education data columns (currently_school, highest_level_edu, main_reason_not_sch, reason_not_furth_edu) are not available in the current dataset. Domain 2 analysis is not possible.")
        else:
            st.error(f"Error running education analysis: {e}")

    st.markdown("---")
    st.header(f"Domain 3: Employment & Livelihoods – {selected_site.replace('_', ' ').title()}")

    try:
        # Discover actual employment column names from the database
        cols_df = pd.read_sql(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'individuals'
            """,
            engine
        )
        cols = cols_df['column_name'].tolist()

        def find_col(keywords):
            for c in cols:
                c_lower = c.lower()
                if all(k in c_lower for k in keywords):
                    return c
            return None

        app_col = find_col(['employ', 'app'])
        status_col = find_col(['employ', 'status'])
        job_col = find_col(['employ', 'job', 'type'])

        if not app_col or not status_col or not job_col:
            raise Exception(
                f"Could not find one or more employment columns. "
                f"Columns found: {', '.join(cols[:30])}"
            )

        # Load individual employment data using the discovered column names
        emp_sql = f'''
            SELECT 
                h.pro_name, h.dist_name, h.sector,
                i.indiv_line_num, i.sex, i.age_year, i.est_age_years,
                i."{app_col}" AS employment_app,
                i."{status_col}" AS employment_status,
                i."{job_col}" AS job_type
            FROM households h
            LEFT JOIN individuals i ON h.key = i.parent_key
            WHERE h.pro_name = %s
        '''
        emp_df = pd.read_sql(emp_sql, engine, params=(selected_site,))

        # Load household income data at household level (optional)
        try:
            hh_income_df = pd.read_sql(
                """
                SELECT pro_name, dist_name, sector,
                       consent_hhses_three_5_1 AS three_5_1,
                       consent_hhses_three_5_4 AS three_5_4,
                       consent_hhses_three_5_5 AS three_5_5
                FROM households
                WHERE pro_name = %s
                """,
                engine,
                params=(selected_site,)
            )
        except Exception:
            st.info("Household income columns (three_5_1, three_5_4, three_5_5) were not found; income and expenditure charts will be skipped.")
            hh_income_df = pd.DataFrame(columns=['pro_name', 'dist_name', 'sector', 'three_5_1', 'three_5_4', 'three_5_5'])

        # Convert age columns to numeric
        emp_df['age_year'] = pd.to_numeric(emp_df['age_year'], errors='coerce')
        emp_df['est_age_years'] = pd.to_numeric(emp_df['est_age_years'], errors='coerce')
        emp_df['final_age'] = emp_df['age_year'].fillna(emp_df['est_age_years'])

        # Normalize sex codes
        def emp_normalize_sex(val):
            if pd.isna(val):
                return '99'
            s = str(val).strip().upper()
            if s.endswith('.0'):
                s = s[:-2]
            if s in ('01', '1', 'M', 'MALE', 'BOY', 'M.'):
                return '01'
            elif s in ('02', '2', 'F', 'FEMALE', 'GIRL', 'F.'):
                return '02'
            else:
                return '99'

        emp_df['sex_norm'] = emp_df['sex'].apply(emp_normalize_sex)

        # Normalize coded string variables
        for col in ['employment_app', 'employment_status', 'job_type']:
            emp_df[col + '_norm'] = (
                emp_df[col]
                .astype('string')
                .fillna('')
                .str.strip()
                .str.replace(r'\.0$', '', regex=True)
                .str.zfill(2)
            )

        for col in ['three_5_1']:
            hh_income_df[col + '_norm'] = (
                hh_income_df[col]
                .astype('string')
                .fillna('')
                .str.strip()
                .str.replace(r'\.0$', '', regex=True)
                .str.zfill(2)
            )

        hh_income_df['three_5_4'] = pd.to_numeric(hh_income_df['three_5_4'], errors='coerce')
        hh_income_df['three_5_5'] = pd.to_numeric(hh_income_df['three_5_5'], errors='coerce')

        # Working-age subset (15+)
        emp_15plus = emp_df[emp_df['final_age'] >= 15].copy()

        # Site-wide metrics
        working_age_pop = len(emp_15plus)
        eligible = emp_15plus[emp_15plus['employment_app_norm'] == '01']
        labor_eligible = len(eligible)

        in_labor_force = eligible[eligible['employment_status_norm'].isin(['01', '02', '03'])]
        employed = eligible[eligible['employment_status_norm'] == '01']
        self_employed = eligible[eligible['employment_status_norm'] == '02']
        unemployed = eligible[eligible['employment_status_norm'] == '03']
        students = eligible[eligible['employment_status_norm'] == '04']

        lfpr = round(len(in_labor_force) * 100.0 / labor_eligible, 2) if labor_eligible > 0 else 0
        wage_rate = round(len(employed) * 100.0 / labor_eligible, 2) if labor_eligible > 0 else 0
        informal_rate = round(len(self_employed) * 100.0 / labor_eligible, 2) if labor_eligible > 0 else 0
        unemp_rate = round(len(unemployed) * 100.0 / len(in_labor_force), 2) if len(in_labor_force) > 0 else 0
        student_rate = round(len(students) * 100.0 / labor_eligible, 2) if labor_eligible > 0 else 0

        # Display site-wide metrics
        st.subheader("Site-Wide Employment & Livelihoods Summary")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Working-Age Pop 15+", f"{working_age_pop:,}")
            st.metric("Labour Eligible", f"{labor_eligible:,}")
        with c2:
            st.metric("Labour Force Participation", f"{lfpr:.2f}%")
            st.metric("Wage Employment Rate", f"{wage_rate:.2f}%")
        with c3:
            st.metric("Informal / Subsistence Rate", f"{informal_rate:.2f}%")
            st.metric("Open Unemployment Rate", f"{unemp_rate:.2f}%")

        # Income source and earnings
        st.markdown("---")
        st.subheader("Household Income & Livelihoods")

        income_source_map = {
            '00': 'No Response',
            '01': 'Paid employment',
            '02': 'Selling cash crops / fishing',
            '03': 'Informal sector',
            '888': "Don't Know"
        }

        income_counts = hh_income_df.loc[hh_income_df['three_5_1_norm'].ne(''), 'three_5_1_norm'].value_counts()
        income_data = pd.DataFrame([
            {'Source': income_source_map.get(k, f'Code {k}'), 'Count': int(v)}
            for k, v in income_counts.items()
        ])

        avg_income = hh_income_df['three_5_4'].mean()
        avg_food = hh_income_df['three_5_5'].mean()
        food_ratio = round(avg_food * 100.0 / avg_income, 2) if avg_income and avg_income > 0 else 0

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Avg. Fortnightly Income (PGK)", f"{avg_income:.2f}" if pd.notna(avg_income) else "n/a")
            st.metric("Avg. Food Expenditure (PGK)", f"{avg_food:.2f}" if pd.notna(avg_food) else "n/a")
            st.metric("Food / Income Ratio", f"{food_ratio:.2f}%" if pd.notna(avg_income) and pd.notna(avg_food) else "n/a")

        with col2:
            if not income_data.empty:
                st.dataframe(income_data, hide_index=True, use_container_width=True)
                fig_inc = px.bar(
                    income_data.sort_values('Count', ascending=True),
                    y='Source',
                    x='Count',
                    orientation='h',
                    title='Main Household Income Source',
                    color_discrete_sequence=['#3b6e9b']
                )
                fig_inc.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_inc, use_container_width=True)
            else:
                st.info("No household income source data available.")

        # Occupation breakdown
        st.markdown("---")
        st.subheader("Occupation Breakdown")

        job_type_map = {
            '00': 'No Response',
            '01': 'Subsistence / Fishing',
            '02': 'Street / Market Vendor',
            '03': 'SME Owner',
            '04': 'SME Owner (04)',
            '05': 'Labourer',
            '06': 'Hospitality',
            '07': 'Construction',
            '08': 'Skilled Trade',
            '09': 'Professional',
            '10': 'Religious Leaders',
            '888': "Don't Know"
        }

        job_counts = emp_15plus.loc[emp_15plus['job_type_norm'].ne(''), 'job_type_norm'].value_counts()
        job_data = pd.DataFrame([
            {'Occupation': job_type_map.get(k, f'Code {k}'), 'Count': int(v)}
            for k, v in job_counts.items()
        ])

        if not job_data.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(job_data, hide_index=True, use_container_width=True)
            with col2:
                fig_job = px.bar(
                    job_data.sort_values('Count', ascending=True),
                    y='Occupation',
                    x='Count',
                    orientation='h',
                    title='Occupation Distribution',
                    color_discrete_sequence=['#3b6e9b']
                )
                fig_job.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_job, use_container_width=True)
        else:
            st.info("No occupation data available.")

        # District and sector breakdown
        st.markdown("---")
        st.subheader("Employment & Livelihoods by District & Sector")

        emp_district_data = []
        for (district, sector), group in emp_15plus.groupby(['dist_name', 'sector']):
            eligible_g = group[group['employment_app_norm'] == '01']
            labor_eligible_g = len(eligible_g)
            in_lf = eligible_g[eligible_g['employment_status_norm'].isin(['01', '02', '03'])]
            employed_g = eligible_g[eligible_g['employment_status_norm'] == '01']
            self_g = eligible_g[eligible_g['employment_status_norm'] == '02']
            unemp_g = eligible_g[eligible_g['employment_status_norm'] == '03']

            lfpr_g = round(len(in_lf) * 100.0 / labor_eligible_g, 2) if labor_eligible_g > 0 else 0
            wage_g = round(len(employed_g) * 100.0 / labor_eligible_g, 2) if labor_eligible_g > 0 else 0
            informal_g = round(len(self_g) * 100.0 / labor_eligible_g, 2) if labor_eligible_g > 0 else 0
            unemp_g_rate = round(len(unemp_g) * 100.0 / len(in_lf), 2) if len(in_lf) > 0 else 0

            sector_map = {
                '01': 'Urban', '02': 'Peri-Urban', '03': 'Settlement', '04': 'Rural'
            }
            emp_district_data.append({
                'District': district,
                'Sector Code': sector,
                'Sector': sector_map.get(str(sector).zfill(2), 'Unclassified'),
                'Working-Age 15+': len(group),
                'Labour Eligible': labor_eligible_g,
                'LFPR (%)': lfpr_g,
                'Wage Rate (%)': wage_g,
                'Informal Rate (%)': informal_g,
                'Unemployment (%)': unemp_g_rate
            })

        emp_district_df = pd.DataFrame(emp_district_data)

        # Merge household income by district/sector
        income_district = hh_income_df.groupby(['dist_name', 'sector']).agg(
            avg_income_pgk=('three_5_4', 'mean'),
            avg_food_pgk=('three_5_5', 'mean')
        ).reset_index()
        income_district['avg_income_pgk'] = income_district['avg_income_pgk'].round(2)
        income_district['avg_food_pgk'] = income_district['avg_food_pgk'].round(2)

        if not emp_district_df.empty:
            emp_district_df = emp_district_df.merge(
                income_district,
                left_on=['District', 'Sector Code'],
                right_on=['dist_name', 'sector'],
                how='left'
            )
            emp_district_df['Avg Income (PGK)'] = emp_district_df['avg_income_pgk'].fillna(0)
            emp_district_df['Avg Food Spend (PGK)'] = emp_district_df['avg_food_pgk'].fillna(0)
            emp_district_df = emp_district_df.drop(columns=['dist_name', 'sector', 'avg_income_pgk', 'avg_food_pgk'])

            st.dataframe(
                emp_district_df,
                column_config={
                    'District': st.column_config.TextColumn('District'),
                    'Sector Code': st.column_config.TextColumn('Sector Code'),
                    'Sector': st.column_config.TextColumn('Sector'),
                    'Working-Age 15+': st.column_config.NumberColumn('Working-Age 15+', format='%d'),
                    'Labour Eligible': st.column_config.NumberColumn('Labour Eligible', format='%d'),
                    'LFPR (%)': st.column_config.NumberColumn('LFPR (%)', format='%.2f'),
                    'Wage Rate (%)': st.column_config.NumberColumn('Wage Rate (%)', format='%.2f'),
                    'Informal Rate (%)': st.column_config.NumberColumn('Informal Rate (%)', format='%.2f'),
                    'Unemployment (%)': st.column_config.NumberColumn('Unemployment (%)', format='%.2f'),
                    'Avg Income (PGK)': st.column_config.NumberColumn('Avg Income (PGK)', format='%.2f'),
                    'Avg Food Spend (PGK)': st.column_config.NumberColumn('Avg Food Spend (PGK)', format='%.2f')
                },
                hide_index=True,
                use_container_width=True
            )

            csv_emp = emp_district_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label='Download Employment & Livelihoods Analysis (CSV)',
                data=csv_emp,
                file_name=f'domain3_employment_{selected_site.lower()}.csv',
                mime='text/csv'
            )
        else:
            st.info("No district/sector employment data available for this site.")

        # Key indicators explanation
        st.markdown("---")
        st.subheader("Key Indicators Captured")
        st.markdown("""
        **Labour Force Participation Rate (15+):** Share of the working-age population that is either employed, self-employed, or unemployed and seeking work. Eligible individuals exclude those not in the labour force due to old age, disability, or sickness.

        **Formal Wage Employment Rate:** Percentage of the labour-eligible population that is in paid wage employment.

        **Informal / Subsistence Rate:** Percentage of the labour-eligible population engaged in self-employment or subsistence production.

        **Open Unemployment Rate:** Share of the labour force that is unemployed and actively looking for work, among those in the labour force.

        **Main Household Income Source:** Distribution of households by their primary income generation channel: paid employment, cash crops/fishing, or the informal sector.

        **Fortnightly Income & Food Expenditure:** Average household cash income and food expenditure per fortnight, and the share of income spent on food.

        **Occupation Breakdown:** Distribution of working adults across specific economic activities, including subsistence/fishing, vending, SME ownership, labouring, hospitality, construction, skilled trades, and professional occupations.
        """)

    except Exception as e:
        if any(col in str(e) for col in ['employment_app', 'employment_status', 'job_type', 'three_5_1', 'three_5_4', 'three_5_5']):
            st.info("Employment or livelihood columns (employment_app, employment_status, job_type, three_5_1, three_5_4, three_5_5) are not available in the current dataset. Domain 3 analysis is not possible.")
        else:
            st.error(f"Error running employment analysis: {e}")

    st.markdown("---")
    st.header(f"Domain 4: Housing Conditions – {selected_site.replace('_', ' ').title()}")

    try:
        # Discover actual household column names from the database
        hh_cols_df = pd.read_sql(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'households'
            """,
            engine
        )
        hh_cols = hh_cols_df['column_name'].tolist()

        def find_col_hh(keywords):
            for c in hh_cols:
                c_lower = c.lower()
                if all(k in c_lower for k in keywords):
                    return c
            return None

        t41 = find_col_hh(['three_4_1'])
        t44 = find_col_hh(['three_4_4'])
        t45 = find_col_hh(['three_4_5'])
        t46 = find_col_hh(['three_4_6'])
        t47 = find_col_hh(['three_4_7'])
        t49 = find_col_hh(['three_4_9'])
        t410 = find_col_hh(['three_4_10'])
        t415 = find_col_hh(['three_4_15'])
        ttm = find_col_hh(['total', 'hh', 'member'])

        missing = [n for n, c in zip(
            ['three_4_1', 'three_4_4', 'three_4_5', 'three_4_6', 'three_4_7',
             'three_4_9', 'three_4_10', 'three_4_15'],
            [t41, t44, t45, t46, t47, t49, t410, t415]
        ) if c is None]

        if missing:
            raise Exception(
                f"Could not find one or more housing columns. Missing: {', '.join(missing)}. "
                f"Columns found: {', '.join(hh_cols[:30])}"
            )

        total_expr = f'h."{ttm}" AS total_hh_members' if ttm else 'NULL AS total_hh_members'

        # Load household-level housing data using the discovered column names
        housing_sql = f'''
            SELECT 
                h.key, h.pro_name, h.dist_name, h.sector,
                h."{t41}" AS three_4_1,
                h."{t44}" AS three_4_4,
                h."{t45}" AS three_4_5,
                h."{t46}" AS three_4_6,
                h."{t47}" AS three_4_7,
                h."{t49}" AS three_4_9,
                h."{t410}" AS three_4_10,
                h."{t415}" AS three_4_15,
                {total_expr}
            FROM households h
            WHERE h.pro_name = %s
        '''
        housing_df = pd.read_sql(housing_sql, engine, params=(selected_site,))

        # If total_hh_members is missing, compute from individuals
        if housing_df['total_hh_members'].isna().all():
            hh_size = pd.read_sql(
                """
                SELECT h.key, COUNT(i.parent_key) AS total_hh_members
                FROM households h
                LEFT JOIN individuals i ON h.key = i.parent_key
                WHERE h.pro_name = %s
                GROUP BY h.key
                """,
                engine,
                params=(selected_site,)
            )
            housing_df = housing_df.drop(columns=['total_hh_members']).merge(
                hh_size, on='key', how='left'
            )

        # Convert numeric structural columns
        for col in ['three_4_4', 'three_4_5', 'three_4_6', 'three_4_7', 'total_hh_members']:
            housing_df[col] = pd.to_numeric(housing_df[col], errors='coerce')

        # Treat Don't Know / No Response as missing for quality ratings
        for col in ['three_4_5', 'three_4_6', 'three_4_7']:
            housing_df.loc[housing_df[col] >= 888, col] = np.nan

        # Normalize categorical string codes
        for col in ['three_4_1', 'three_4_9', 'three_4_10', 'three_4_15']:
            housing_df[col + '_norm'] = (
                housing_df[col]
                .astype('string')
                .fillna('')
                .str.strip()
                .str.replace(r'\.0$', '', regex=True)
                .str.zfill(2)
            )

        # Housing Quality Index (HQI) classification
        finished_wall = housing_df['three_4_5'] >= 10
        finished_floor = housing_df['three_4_6'] >= 4
        finished_roof = housing_df['three_4_7'] >= 7
        valid_hqi = housing_df[['three_4_5', 'three_4_6', 'three_4_7']].notna().all(axis=1)

        permanent = valid_hqi & finished_wall & finished_floor & finished_roof
        semi = valid_hqi & finished_roof & (finished_wall | finished_floor) & ~permanent
        traditional = valid_hqi & ~permanent & ~semi

        hqi_counts = pd.Series([
            permanent.sum(),
            semi.sum(),
            traditional.sum()
        ], index=['Permanent / Finished', 'Semi-Permanent', 'Traditional / Rudimentary'])

        # Overcrowding
        housing_df['persons_per_room'] = (
            housing_df['total_hh_members'] / housing_df['three_4_4']
        ).where(housing_df['three_4_4'] > 0)
        overcrowded = housing_df['persons_per_room'] > 2.0
        total_hh = len(housing_df)
        overcrowded_count = overcrowded.sum()
        overcrowding_rate = round(overcrowded_count * 100.0 / total_hh, 2) if total_hh > 0 else 0
        avg_ppr = housing_df['persons_per_room'].mean()

        # Tenure
        tenure_map = {
            '01': 'Own',
            '02': 'Rent',
            '03': 'Other'
        }
        tenure_counts = housing_df.loc[housing_df['three_4_15_norm'].ne(''), 'three_4_15_norm'].value_counts()

        # Structural type
        structural_map = {
            '00': 'No Response',
            '01': 'Traditional (Bush materials)',
            '02': 'Semi-permanent house',
            '03': 'Permanent house',
            '04': 'Other',
            '10': 'Other (10)',
            '888': "Don't Know"
        }
        structural_counts = housing_df.loc[housing_df['three_4_1_norm'].ne(''), 'three_4_1_norm'].value_counts()

        # Kitchen
        has_dedicated_kitchen = (housing_df['three_4_9_norm'] == '01').sum()
        kitchen_pct = round(has_dedicated_kitchen * 100.0 / total_hh, 2) if total_hh > 0 else 0
        kitchen_type_map = {
            '00': 'No Response',
            '01': 'Separate room',
            '02': 'Elsewhere in house',
            '03': 'Separate building',
            '04': 'Outdoors',
            '05': 'Other',
            '888': "Don't Know"
        }
        kitchen_counts = housing_df.loc[
            (housing_df['three_4_9_norm'] == '01') & (housing_df['three_4_10_norm'].ne('')),
            'three_4_10_norm'
        ].value_counts()

        # Site-wide metrics
        st.subheader("Site-Wide Housing Conditions Summary")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Permanent / Finished (HQI)", f"{permanent.sum():,}")
            st.metric("Semi-Permanent (HQI)", f"{semi.sum():,}")
            st.metric("Traditional / Rudimentary (HQI)", f"{traditional.sum():,}")
        with c2:
            st.metric("Overcrowding Rate", f"{overcrowding_rate:.2f}%")
            st.metric("Avg. Persons per Sleeping Room", f"{avg_ppr:.2f}" if pd.notna(avg_ppr) else "n/a")
        with c3:
            st.metric("Dedicated Kitchen (%)", f"{kitchen_pct:.2f}%")

        # Visualizations
        st.markdown("---")
        st.subheader("Housing Quality & Tenure")

        col1, col2 = st.columns(2)
        with col1:
            hqi_data = pd.DataFrame({'Housing Quality': hqi_counts.index, 'Count': hqi_counts.values})
            fig_hqi = px.pie(
                hqi_data,
                values='Count',
                names='Housing Quality',
                title='Housing Quality Index',
                color_discrete_sequence=['#2a9d8f', '#e9c46a', '#e76f51']
            )
            st.plotly_chart(fig_hqi, use_container_width=True)

        with col2:
            tenure_data = pd.DataFrame([
                {'Tenure': tenure_map.get(k, f'Code {k}'), 'Count': int(v)}
                for k, v in tenure_counts.items()
            ])
            if not tenure_data.empty:
                fig_tenure = px.bar(
                    tenure_data,
                    x='Tenure',
                    y='Count',
                    title='Dwelling Tenure Arrangement',
                    color_discrete_sequence=['#3b6e9b']
                )
                st.plotly_chart(fig_tenure, use_container_width=True)
            else:
                st.info("No tenure data available.")

        st.markdown("---")
        st.subheader("Structural Type & Kitchen Facilities")

        col1, col2 = st.columns(2)
        with col1:
            struct_data = pd.DataFrame([
                {'Structural Type': structural_map.get(k, f'Code {k}'), 'Count': int(v)}
                for k, v in structural_counts.items()
            ])
            if not struct_data.empty:
                fig_struct = px.bar(
                    struct_data,
                    x='Structural Type',
                    y='Count',
                    title='Structural Type Classification',
                    color_discrete_sequence=['#3b6e9b']
                )
                st.plotly_chart(fig_struct, use_container_width=True)
            else:
                st.info("No structural type data available.")

        with col2:
            kitchen_data = pd.DataFrame([
                {'Kitchen Location': kitchen_type_map.get(k, f'Code {k}'), 'Count': int(v)}
                for k, v in kitchen_counts.items()
            ])
            if not kitchen_data.empty:
                fig_kitchen = px.bar(
                    kitchen_data,
                    x='Kitchen Location',
                    y='Count',
                    title='Dedicated Kitchen Location',
                    color_discrete_sequence=['#3b6e9b']
                )
                st.plotly_chart(fig_kitchen, use_container_width=True)
            else:
                st.info("No kitchen location data available.")

        # District and sector breakdown
        st.markdown("---")
        st.subheader("Housing Conditions by District & Sector")

        housing_district_data = []
        for (district, sector), group in housing_df.groupby(['dist_name', 'sector']):
            total = len(group)
            valid = group[['three_4_5', 'three_4_6', 'three_4_7']].notna().all(axis=1)
            permanent_g = (valid & (group['three_4_5'] >= 10) & (group['three_4_6'] >= 4) & (group['three_4_7'] >= 7)).sum()
            semi_g = (valid & (group['three_4_7'] >= 7) & ((group['three_4_5'] >= 10) | (group['three_4_6'] >= 4)) & (permanent_g == False)).sum()
            trad_g = (valid & (permanent_g == False) & (semi_g == False)).sum()
            overcrowded_g = (group['persons_per_room'] > 2.0).sum()
            ppr_g = group['persons_per_room'].mean()

            sector_map = {'01': 'Urban', '02': 'Peri-Urban', '03': 'Settlement', '04': 'Rural'}
            housing_district_data.append({
                'District': district,
                'Sector Code': sector,
                'Sector': sector_map.get(str(sector).zfill(2), 'Unclassified'),
                'Households': total,
                'Permanent (HQI)': int(permanent_g),
                'Semi-Permanent (HQI)': int(semi_g),
                'Traditional (HQI)': int(trad_g),
                'Overcrowding Rate (%)': round(overcrowded_g * 100.0 / total, 2) if total > 0 else 0,
                'Avg PPR': round(ppr_g, 2) if pd.notna(ppr_g) else 0
            })

        housing_district_df = pd.DataFrame(housing_district_data)
        if not housing_district_df.empty:
            st.dataframe(
                housing_district_df,
                column_config={
                    'District': st.column_config.TextColumn('District'),
                    'Sector Code': st.column_config.TextColumn('Sector Code'),
                    'Sector': st.column_config.TextColumn('Sector'),
                    'Households': st.column_config.NumberColumn('Households', format='%d'),
                    'Permanent (HQI)': st.column_config.NumberColumn('Permanent (HQI)', format='%d'),
                    'Semi-Permanent (HQI)': st.column_config.NumberColumn('Semi-Permanent (HQI)', format='%d'),
                    'Traditional (HQI)': st.column_config.NumberColumn('Traditional (HQI)', format='%d'),
                    'Overcrowding Rate (%)': st.column_config.NumberColumn('Overcrowding Rate (%)', format='%.2f'),
                    'Avg PPR': st.column_config.NumberColumn('Avg PPR', format='%.2f')
                },
                hide_index=True,
                use_container_width=True
            )

            csv_housing = housing_district_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label='Download Housing Conditions Analysis (CSV)',
                data=csv_housing,
                file_name=f'domain4_housing_{selected_site.lower()}.csv',
                mime='text/csv'
            )
        else:
            st.info("No district/sector housing data available for this site.")

        # Key indicators explanation
        st.markdown("---")
        st.subheader("Key Indicators Captured")
        st.markdown("""
        **Housing Quality Index (HQI):** Classifies dwellings into Permanent/Finished, Semi-Permanent, and Traditional/Rudimentary based on wall, floor, and roof material codes. Permanent requires finished walls, floor, and roof.

        **Overcrowding Rate:** The share of households with more than 2 persons per sleeping room, and the average persons-per-room across all households.

        **Dwelling Tenure Arrangement:** Distribution of households by ownership status: own, rent, or other.

        **Structural Type Classification:** Proportion of households in traditional bush-material, semi-permanent, or permanent houses.

        **Dedicated Kitchen Infrastructure:** Percentage of households with a dedicated kitchen and the location of that kitchen (separate room, elsewhere in house, separate building, outdoors).
        """)

    except Exception as e:
        if any(col in str(e) for col in ['three_4_1', 'three_4_4', 'three_4_5', 'three_4_6', 'three_4_7', 'three_4_9', 'three_4_10', 'three_4_15', 'total_hh_members']):
            st.info("Housing condition columns (three_4_1, three_4_4/5/6/7/9/10/15, total_hh_members) are not available in the current dataset. Domain 4 analysis is not possible.")
        else:
            st.error(f"Error running housing analysis: {e}")

    st.markdown("---")
    st.header(f"Domain 5: Water, Sanitation & Hygiene (WASH) – {selected_site.replace('_', ' ').title()}")

    try:
        # Discover actual household WASH column names from the database
        wash_cols_df = pd.read_sql(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'households'
            """,
            engine
        )
        wash_cols = wash_cols_df['column_name'].tolist()

        def find_col_wash(keywords):
            for c in wash_cols:
                c_lower = c.lower()
                if all(k in c_lower for k in keywords):
                    return c
            return None

        wthree_1_1 = find_col_wash(['three_1_1'])
        wthree_1_4 = find_col_wash(['three_1_4'])
        wthree_1_6 = find_col_wash(['three_1_6'])
        wthree_1_7 = find_col_wash(['three_1_7'])
        wthree_1_8 = find_col_wash(['three_1_8'])
        wthree_1_9 = find_col_wash(['three_1_9'])
        wthree_1_10 = find_col_wash(['three_1_10'])
        wthree_2_2 = find_col_wash(['three_2_2'])
        wthree_2_3 = find_col_wash(['three_2_3'])
        wthree_2_4 = find_col_wash(['three_2_4'])

        required = [
            ('three_1_1', wthree_1_1),
            ('three_1_9', wthree_1_9),
            ('three_1_10', wthree_1_10)
        ]
        missing = [n for n, c in required if c is None]

        if missing:
            raise Exception(
                f"Could not find one or more WASH columns. Missing: {', '.join(missing)}. "
                f"Columns found: {', '.join(wash_cols[:30])}"
            )

        def sel_expr(col, alias):
            return f'h."{col}" AS {alias}' if col else f'NULL AS {alias}'

        # Load household-level WASH data using the discovered column names
        wash_sql = f'''
            SELECT 
                h.key, h.pro_name, h.dist_name, h.sector,
                {sel_expr(wthree_1_1, 'three_1_1')},
                {sel_expr(wthree_1_4, 'three_1_4')},
                {sel_expr(wthree_1_6, 'three_1_6')},
                {sel_expr(wthree_1_7, 'three_1_7')},
                {sel_expr(wthree_1_8, 'three_1_8')},
                {sel_expr(wthree_1_9, 'three_1_9')},
                {sel_expr(wthree_1_10, 'three_1_10')},
                {sel_expr(wthree_2_2, 'three_2_2')},
                {sel_expr(wthree_2_3, 'three_2_3')},
                {sel_expr(wthree_2_4, 'three_2_4')}
            FROM households h
            WHERE h.pro_name = %s
        '''
        wash_df = pd.read_sql(wash_sql, engine, params=(selected_site,))

        # Normalize categorical codes
        for col in ['three_1_1', 'three_1_6', 'three_1_7', 'three_1_8', 'three_1_9', 'three_1_10',
                    'three_2_2', 'three_2_3', 'three_2_4']:
            wash_df[col] = (
                wash_df[col]
                .astype('string')
                .fillna('')
                .str.strip()
                .str.replace(r'\.0$', '', regex=True)
                .str.zfill(2)
            )

        # Convert numeric columns
        wash_df['three_1_4'] = pd.to_numeric(wash_df['three_1_4'], errors='coerce')
        wash_df.loc[wash_df['three_1_4'] >= 888, 'three_1_4'] = np.nan

        total_hh = len(wash_df)

        # Improved drinking water
        improved_water_codes = {'01', '02', '03', '04', '05', '06', '08', '11', '12', '13'}
        improved_water = wash_df['three_1_1'].isin(improved_water_codes)
        improved_water_rate = round(improved_water.sum() * 100.0 / total_hh, 2) if total_hh > 0 else 0
        surface_water = wash_df['three_1_1'] == '10'
        surface_water_rate = round(surface_water.sum() * 100.0 / total_hh, 2) if total_hh > 0 else 0

        # Improved sanitation (unshared)
        improved_san_codes = {'01', '02', '03', '04', '05', '06', '07'}
        improved_san_unshared = wash_df['three_1_9'].isin(improved_san_codes) & (wash_df['three_1_10'] == '02')
        improved_san_rate = round(improved_san_unshared.sum() * 100.0 / total_hh, 2) if total_hh > 0 else 0
        open_defecation = wash_df['three_1_9'].isin({'10', '11'})
        open_defecation_rate = round(open_defecation.sum() * 100.0 / total_hh, 2) if total_hh > 0 else 0

        # Basic handwashing
        basic_handwashing = (wash_df['three_2_2'] == '01') & (wash_df['three_2_3'] == '01') & (wash_df['three_2_4'] == '01')
        handwashing_rate = round(basic_handwashing.sum() * 100.0 / total_hh, 2) if total_hh > 0 else 0

        # Water fetching time and burden
        avg_fetch_time = wash_df['three_1_4'].mean()
        female_collectors = wash_df['three_1_6'].isin({'01', '03'})
        all_collectors = wash_df['three_1_6'].isin({'01', '02', '03', '04'})
        female_burden = round(female_collectors.sum() * 100.0 / all_collectors.sum(), 2) if all_collectors.sum() > 0 else 0

        # Water treatment
        any_treatment = wash_df['three_1_7'] == '01'
        treatment_rate = round(any_treatment.sum() * 100.0 / total_hh, 2) if total_hh > 0 else 0

        # Site-wide metrics
        st.subheader("Site-Wide WASH Summary")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Improved Water Access", f"{improved_water_rate:.2f}%")
            st.metric("Surface Water Reliance", f"{surface_water_rate:.2f}%")
        with c2:
            st.metric("Improved Sanitation (Unshared)", f"{improved_san_rate:.2f}%")
            st.metric("Open Defecation Rate", f"{open_defecation_rate:.2f}%")
        with c3:
            st.metric("Basic Handwashing", f"{handwashing_rate:.2f}%")
            st.metric("Water Treatment Rate", f"{treatment_rate:.2f}%")

        st.metric("Avg. Water Fetching Time (min)", f"{avg_fetch_time:.1f}" if pd.notna(avg_fetch_time) else "n/a")
        st.metric("Female/Girl Water Collection Burden", f"{female_burden:.2f}%" if all_collectors.sum() > 0 else "n/a")

        # Visualizations
        st.markdown("---")
        st.subheader("Drinking Water & Sanitation")

        water_source_map = {
            '01': 'Piped into dwelling',
            '02': 'Piped into yard/plot',
            '03': 'Piped to public tap',
            '04': 'Piped to neighbor',
            '05': 'Tube well',
            '06': 'Protected well',
            '07': 'Unprotected well',
            '08': 'Protected spring',
            '09': 'Unprotected spring',
            '10': 'Surface water',
            '11': 'Rainwater tank',
            '12': 'Tanker-truck',
            '13': 'Bottled water'
        }
        water_counts = wash_df.loc[wash_df['three_1_1'].ne(''), 'three_1_1'].value_counts()
        water_data = pd.DataFrame([
            {'Source': water_source_map.get(k, f'Code {k}'), 'Count': int(v)}
            for k, v in water_counts.items()
        ])

        sanitation_map = {
            '01': 'Flush to sewer',
            '02': 'Flush to septic',
            '03': 'Flush to pit',
            '04': 'Flush elsewhere',
            '05': 'VIP latrine',
            '06': 'Pit with slab',
            '07': 'Composting toilet',
            '08': 'Pit without slab',
            '09': 'Overhung toilet',
            '10': 'Open defecation',
            '11': 'No facility'
        }
        san_counts = wash_df.loc[wash_df['three_1_9'].ne(''), 'three_1_9'].value_counts()
        san_data = pd.DataFrame([
            {'Facility': sanitation_map.get(k, f'Code {k}'), 'Count': int(v)}
            for k, v in san_counts.items()
        ])

        col1, col2 = st.columns(2)
        with col1:
            if not water_data.empty:
                fig_water = px.bar(
                    water_data.sort_values('Count', ascending=True),
                    y='Source',
                    x='Count',
                    orientation='h',
                    title='Drinking Water Source',
                    color_discrete_sequence=['#3b6e9b']
                )
                fig_water.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_water, use_container_width=True)
            else:
                st.info("No drinking water source data available.")

        with col2:
            if not san_data.empty:
                fig_san = px.bar(
                    san_data.sort_values('Count', ascending=True),
                    y='Facility',
                    x='Count',
                    orientation='h',
                    title='Sanitation Facility',
                    color_discrete_sequence=['#3b6e9b']
                )
                fig_san.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_san, use_container_width=True)
            else:
                st.info("No sanitation facility data available.")

        st.markdown("---")
        st.subheader("Handwashing, Treatment & Water Collection")

        treatment_map = {
            '01': 'Boil',
            '02': 'Bleach / Chlorine',
            '03': 'Cloth filter',
            '04': 'Ceramic / Sand filter',
            '05': 'Solar'
        }
        treatment_counts = wash_df.loc[wash_df['three_1_8'].ne(''), 'three_1_8'].value_counts()
        treatment_data = pd.DataFrame([
            {'Method': treatment_map.get(k, f'Code {k}'), 'Count': int(v)}
            for k, v in treatment_counts.items()
        ])

        collector_map = {
            '01': 'Adult woman',
            '02': 'Adult man',
            '03': 'Female child',
            '04': 'Male child'
        }
        collector_counts = wash_df.loc[wash_df['three_1_6'].ne(''), 'three_1_6'].value_counts()
        collector_data = pd.DataFrame([
            {'Collector': collector_map.get(k, f'Code {k}'), 'Count': int(v)}
            for k, v in collector_counts.items()
        ])

        col1, col2 = st.columns(2)
        with col1:
            if not treatment_data.empty:
                fig_treat = px.bar(
                    treatment_data,
                    x='Method',
                    y='Count',
                    title='Water Treatment Method',
                    color_discrete_sequence=['#3b6e9b']
                )
                st.plotly_chart(fig_treat, use_container_width=True)
            else:
                st.info("No water treatment data available.")

        with col2:
            if not collector_data.empty:
                fig_coll = px.bar(
                    collector_data,
                    x='Collector',
                    y='Count',
                    title='Primary Water Collector',
                    color_discrete_sequence=['#3b6e9b']
                )
                st.plotly_chart(fig_coll, use_container_width=True)
            else:
                st.info("No water collector data available.")

        # District and sector breakdown
        st.markdown("---")
        st.subheader("WASH by District & Sector")

        wash_district_data = []
        for (district, sector), group in wash_df.groupby(['dist_name', 'sector']):
            total = len(group)
            improved_w = group['three_1_1'].isin(improved_water_codes)
            surface_w = group['three_1_1'] == '10'
            improved_s = (group['three_1_9'].isin(improved_san_codes)) & (group['three_1_10'] == '02')
            open_d = group['three_1_9'].isin({'10', '11'})
            handw = (group['three_2_2'] == '01') & (group['three_2_3'] == '01') & (group['three_2_4'] == '01')
            treated = group['three_1_7'] == '01'
            avg_ft = group['three_1_4'].mean()

            sector_map = {'01': 'Urban', '02': 'Peri-Urban', '03': 'Settlement', '04': 'Rural'}
            wash_district_data.append({
                'District': district,
                'Sector Code': sector,
                'Sector': sector_map.get(str(sector).zfill(2), 'Unclassified'),
                'Households': total,
                'Improved Water (%)': round(improved_w.sum() * 100.0 / total, 2) if total > 0 else 0,
                'Surface Water (%)': round(surface_w.sum() * 100.0 / total, 2) if total > 0 else 0,
                'Improved Sanitation (%)': round(improved_s.sum() * 100.0 / total, 2) if total > 0 else 0,
                'Open Defecation (%)': round(open_d.sum() * 100.0 / total, 2) if total > 0 else 0,
                'Basic Handwashing (%)': round(handw.sum() * 100.0 / total, 2) if total > 0 else 0,
                'Water Treatment (%)': round(treated.sum() * 100.0 / total, 2) if total > 0 else 0,
                'Avg Fetch Time (min)': round(avg_ft, 1) if pd.notna(avg_ft) else 0
            })

        wash_district_df = pd.DataFrame(wash_district_data)
        if not wash_district_df.empty:
            st.dataframe(
                wash_district_df,
                column_config={
                    'District': st.column_config.TextColumn('District'),
                    'Sector Code': st.column_config.TextColumn('Sector Code'),
                    'Sector': st.column_config.TextColumn('Sector'),
                    'Households': st.column_config.NumberColumn('Households', format='%d'),
                    'Improved Water (%)': st.column_config.NumberColumn('Improved Water (%)', format='%.2f'),
                    'Surface Water (%)': st.column_config.NumberColumn('Surface Water (%)', format='%.2f'),
                    'Improved Sanitation (%)': st.column_config.NumberColumn('Improved Sanitation (%)', format='%.2f'),
                    'Open Defecation (%)': st.column_config.NumberColumn('Open Defecation (%)', format='%.2f'),
                    'Basic Handwashing (%)': st.column_config.NumberColumn('Basic Handwashing (%)', format='%.2f'),
                    'Water Treatment (%)': st.column_config.NumberColumn('Water Treatment (%)', format='%.2f'),
                    'Avg Fetch Time (min)': st.column_config.NumberColumn('Avg Fetch Time (min)', format='%.1f')
                },
                hide_index=True,
                use_container_width=True
            )

            csv_wash = wash_district_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label='Download WASH Analysis (CSV)',
                data=csv_wash,
                file_name=f'domain5_wash_{selected_site.lower()}.csv',
                mime='text/csv'
            )
        else:
            st.info("No district/sector WASH data available for this site.")

        # Key indicators explanation
        st.markdown("---")
        st.subheader("Key Indicators Captured")
        st.markdown("""
        **Improved Drinking Water Access:** Percentage of households using an improved drinking water source, including piped water, tube wells, protected wells, protected springs, rainwater, tanker-trucks, and bottled water.

        **Surface Water Reliance:** Percentage of households depending on unprotected surface water such as rivers, streams, or lakes.

        **Improved Sanitation (Unshared):** Percentage of households using an improved sanitation facility that is not shared with other households.

        **Open Defecation Rate:** Percentage of households reporting open defecation or no sanitation facility.

        **Basic Handwashing Facility:** Percentage of households with an observed handwashing station that has both water and soap/detergent available.

        **Water Treatment Rate:** Percentage of households that treat their drinking water before consumption.

        **Water Fetching Time & Gender Burden:** Average round-trip time (minutes) to collect water, and the share of households where water is collected by women or girls.
        """)

    except Exception as e:
        if any(col in str(e) for col in ['three_1_1', 'three_1_4', 'three_1_6', 'three_1_7', 'three_1_8', 'three_1_9', 'three_1_10', 'three_2_2', 'three_2_3', 'three_2_4']):
            st.info("WASH columns (three_1_1/4/6/7/8/9/10, three_2_2/3/4) are not available in the current dataset. Domain 5 analysis is not possible.")
        else:
            st.error(f"Error running WASH analysis: {e}")

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

        st.markdown("---")
        st.subheader("Data Collected by Ward")
        if 'ward_name' in site_hh_df.columns:
            ward_counts = site_hh_df['ward_name'].value_counts().reset_index()
            ward_counts.columns = ['Ward', 'Households']

            fig_ward = px.bar(ward_counts, x='Ward', y='Households', color='Ward',
                              title="Households Collected per Ward")
            st.plotly_chart(fig_ward, use_container_width=True)

            st.dataframe(
                ward_counts.sort_values('Households', ascending=False),
                column_config={
                    'Ward': st.column_config.TextColumn("Ward"),
                    'Households': st.column_config.NumberColumn("Households", format='%d')
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
            collector = site_hh_df['submittername'].value_counts().reset_index()
            collector.columns = ['submittername', 'count']
    
            fig = px.bar(
                collector,
                x='submittername',
                y='count',
                color='submittername',
                title="Households per Data Collector (submittername)"
            )
    
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(collector, hide_index=True, use_container_width=True)

        st.markdown("---")
        if 'four_3_1' in site_hh_df.columns:
            collector_431 = site_hh_df['four_3_1'].value_counts().reset_index()
            fig_431 = px.bar(
                collector_431,
                x='four_3_1',
                y='count',
                color='four_3_1',
                title="Households per Data Collector (Interviews Name)"
            )
            st.plotly_chart(fig_431, use_container_width=True)
            st.dataframe(collector_431, hide_index=True, use_container_width=True)

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
                ward_name,
                location_name AS "Village",
                location_num AS "Location Number",
                dwelling_number AS "Household Number",
                CASE consent_hhses_three_4_1
                    WHEN 1 THEN 'Traditional (Bush materials)'
                    WHEN 2 THEN 'Semi-permanent house'
                    WHEN 3 THEN 'Permanent house'
                    ELSE CAST(consent_hhses_three_4_1 AS TEXT)
                END AS "Type of Household",

                CASE consent_hhses_three_1_1
                    WHEN 1 THEN 'Piped into dwelling'
                    WHEN 2 THEN 'Piped into compound, yard or plot'
                    WHEN 3 THEN 'Piped to neighbour'
                    WHEN 4 THEN 'Public tap / standpipe'
                    WHEN 5 THEN 'Tube/drill well'
                    WHEN 6 THEN 'Protected well'
                    WHEN 7 THEN 'Unprotected well'
                    WHEN 8 THEN 'Protected spring'
                    WHEN 9 THEN 'Unprotected spring'
                    WHEN 10 THEN 'Surface water (river, stream, dam, lake, pond, or canal)'
                    WHEN 11 THEN 'Rainwater tank'
                    WHEN 12 THEN 'Tanker-truck'
                    WHEN 13 THEN 'Bottled water'
                    WHEN 14 THEN 'Container'
                    WHEN 15 THEN 'Other (specify)'
                    ELSE CAST(consent_hhses_three_1_1 AS TEXT)
                END AS "Main source of Drinking Water",

                CASE consent_hhses_three_1_3
                    WHEN 1 THEN 'Piped into dwelling'
                    WHEN 2 THEN 'Piped into compound, yard or plot'
                    WHEN 3 THEN 'Piped to neighbour'
                    WHEN 4 THEN 'Public tap / standpipe'
                    WHEN 5 THEN 'Tube/drill well'
                    WHEN 6 THEN 'Protected well'
                    WHEN 7 THEN 'Unprotected well'
                    WHEN 8 THEN 'Protected spring'
                    WHEN 9 THEN 'Unprotected spring'
                    WHEN 10 THEN 'Surface water (river, stream, dam, lake, pond, or canal)'
                    WHEN 11 THEN 'Rainwater tank'
                    WHEN 12 THEN 'Tanker-truck'
                    WHEN 13 THEN 'Bottled water'
                    WHEN 14 THEN 'Container'
                    WHEN 15 THEN 'Other (specify)'
                    ELSE CAST(consent_hhses_three_1_3 AS TEXT)
                END AS "cooking and hand washing water source",

                CASE consent_hhses_three_1_9
                    WHEN 1 THEN 'Flush to piped sewer system'
                    WHEN 2 THEN 'Flush to septic tank'
                    WHEN 3 THEN 'Flush to pit (latrine)'
                    WHEN 4 THEN 'Flush to somewhere else'
                    WHEN 5 THEN 'Pit latrine with ventilation'
                    WHEN 6 THEN 'Pit latrine with slab'
                    WHEN 7 THEN 'Composting toilet'
                    WHEN 8 THEN 'Pit latrine without slab / Open pit'
                    WHEN 9 THEN 'Overhung toilet on sea'
                    WHEN 10 THEN 'Open defecation (No facility/ Bush/ Field)'
                    WHEN 11 THEN 'Open defecation (No facility/ Sea/River)'
                    WHEN 12 THEN 'Other (specify)'
                    WHEN 888 THEN 'Don''t know'
                    ELSE CAST(consent_hhses_three_1_9 AS TEXT)
                END AS "Types of Toilet",
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
                        "ward_name": st.column_config.TextColumn(
                            "Ward Name",
                            help="Ward name"
                        ),
                        "Village": st.column_config.TextColumn(
                            "Village",
                            help="Location name"
                        ),
                        "Location Number": st.column_config.NumberColumn(
                            "Location Number",
                            help="Location number"
                        ),
                        "Household Number": st.column_config.NumberColumn(
                            "Household Number",
                            help="Household dwelling number"
                        ),
                        "Type of Household": st.column_config.TextColumn(
                            "Type of Household",
                            help="Type of household"
                        ),
                        "Main source of Drinking Water": st.column_config.TextColumn(
                            "Main source of Drinking Water",
                            help="Main source of drinking water"
                        ),
                        "cooking and hand washing water source": st.column_config.TextColumn(
                            "cooking and hand washing water source",
                            help="Water source for cooking and hand washing"
                        ),
                        "Types of Toilet": st.column_config.TextColumn(
                            "Types of Toilet",
                            help="Types of toilet facility"
                        ),
                        "Data Collector": st.column_config.TextColumn(
                            "Data Collector",
                            help="Name of the data collector"
                        ),
                        "Quality Checker": st.column_config.TextColumn(
                            "Quality Checker",
                            help="Name of the quality checker"
                        ),
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
                st.success("No GPS Queries found!")
                    
           # Table Check Missing Consent section
            st.markdown("---")
            st.subheader("Table Check Missing Consent")

            try:
                # Query for households with missing consent
                missing_consent_query = """
                SELECT
                    h.ward_name,
                    h.location_name,
                    h.location_num,
                    h.dwelling_number,
                    CONCAT(head.indiv_fname, ' ', head.indiv_lname) AS household_head_name,
                    h.four_3_1 AS data_collector,
                    h.interview_date_time_1 AS interview_datetime,
                    h.consent_consent_pic
                FROM households h
                LEFT JOIN individuals head
                    ON h.key = head.parent_key
                    AND head.relo_to_hh = 1
                WHERE h.agree_yes = 1
                AND h.pro_name = %s
                AND (
                    h.consent_consent_pic IS NULL
                    OR h.consent_consent_pic = ''
                );
                """

                # Execute the query
                missing_consent_df = pd.read_sql(missing_consent_query, engine, params=(selected_site,))

                if not missing_consent_df.empty:
                    # Count households with missing consent
                    total_missing_consent = len(missing_consent_df)

                    # Display summary metrics
                    st.markdown("#### Summary")
                    st.metric("Households with Missing Consent", f"{total_missing_consent:,}")

                    st.markdown("---")
                    st.subheader("Detailed Information")
                    # Display the detailed table
                    st.dataframe(
                        missing_consent_df,
                        column_config={
                            "ward_name": st.column_config.TextColumn(
                                "Ward Name",
                                help="Ward name"
                            ),
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
                            "household_head_name": st.column_config.TextColumn(
                                "Household Head Name",
                                help="Name of the household head"
                            ),
                            "data_collector": st.column_config.TextColumn(
                                "Data Collector",
                                help="Name of the data collector"
                            ),
                            "interview_datetime": st.column_config.DatetimeColumn(
                                "Interview Date/Time",
                                format="DD/MM/YYYY HH:mm"
                            ),
                            "consent_consent_pic": st.column_config.TextColumn(
                                "Consent Picture",
                                help="Consent picture (missing)"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )

                    # Add download button for the data
                    csv_missing_consent = missing_consent_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Missing Consent Data (CSV)",
                        data=csv_missing_consent,
                        file_name=f"missing_consent_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.success("No households with missing consent found!")

            except Exception as e:
                st.error(f"Error in missing consent check: {e}")
                st.exception(e)
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
            st.subheader("Household Member Count Mismatch (For Data Managers ONLY!)")
            
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
                h.ward_name,
                h.location_name,
                h.location_num,
                h.dwelling_number,
                CONCAT(head.indiv_fname, ' ', head.indiv_lname) AS household_head_name,
                h.submittername AS submitter_name,
                h.interview_date_time_1 AS interview_date
                FROM households h
                LEFT JOIN individuals i
                ON h.key = i.parent_key
                LEFT JOIN individuals head
                ON h.key = head.parent_key
                AND head.relo_to_hh = 1
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
                            "ward_name": st.column_config.TextColumn(
                                "Ward Name",
                                help="Ward name"
                            ),
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
                            "household_head_name": st.column_config.TextColumn(
                                "Household Head Name",
                                help="Name of the household head"
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
                h.ward_name,
                h.location_name,
                h.dwelling_number,
                STRING_AGG(CONCAT(i.indiv_fname, ' ', i.indiv_lname), ', ') AS household_head_name,
                h.submittername AS submitter,
                COUNT(*) AS head_count
                FROM individuals i
                JOIN households h
                ON h.key = i.parent_key
                WHERE i.relo_to_hh = 1
                AND h.agree_yes = 1
                AND h.pro_name = %s
                GROUP BY h.key, h.ward_name, h.location_name, h.dwelling_number, h.submittername
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
                            "ward_name": st.column_config.TextColumn(
                                "Ward Name",
                                help="Ward name"
                            ),
                            "location_name": st.column_config.TextColumn(
                                "Village",
                                help="Location name"
                            ),
                            "dwelling_number": st.column_config.NumberColumn(
                                "Dwelling Number",
                                help="Household dwelling number"
                            ),
                            "household_head_name": st.column_config.TextColumn(
                                "Household Head Name",
                                help="Names of household heads (multiple heads)"
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
                h.ward_name,
                h.location_name,
                h.dwelling_number,
                h.consent_respondent_name,
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
                duplicate_households_query = """
                SELECT 
                    h.ward_name,
                    h.location_name,
                    h.location_num,
                    h.dwelling_number,
                    i.indiv_fname AS head_first_name,
                    i.indiv_lname AS head_last_name,
            
                    -- Number of households sharing same dwelling
                    COUNT(*) OVER (
                        PARTITION BY h.location_name, h.dwelling_number
                    ) AS household_count,
            
                    -- Total individuals per household
                    (
                        SELECT COUNT(*) 
                        FROM individuals i2 
                        WHERE i2.parent_key = h.key
                    ) AS total_individuals
            
                FROM households h
                LEFT JOIN individuals i 
                    ON h.key = i.parent_key 
                    AND i.relo_to_hh = 1
            
                WHERE h.agree_yes = 1
                AND h.pro_name = %s
            
                -- Keep only duplicates
                AND (h.location_name, h.dwelling_number) IN (
                    SELECT location_name, dwelling_number
                    FROM households
                    WHERE agree_yes = 1
                    AND pro_name = %s
                    GROUP BY location_name, dwelling_number
                    HAVING COUNT(*) > 1
                )
            
                ORDER BY 
                    h.location_name,
                    h.dwelling_number,
                    h.key;
                """
            
                # ✅ IMPORTANT: pass parameter twice
                duplicate_households_df = pd.read_sql(
                    duplicate_households_query,
                    engine,
                    params=(selected_site, selected_site)
                )
            
                if not duplicate_households_df.empty:
            
                    # ✅ Correct duplicate count (unique dwelling duplicates)
                    total_duplicates = duplicate_households_df[
                        ["location_name", "dwelling_number"]
                    ].drop_duplicates().shape[0]
            
                    # Summary
                    st.markdown("#### Summary")
                    st.metric("Duplicate Dwelling Numbers", f"{total_duplicates:,}")
            
                    st.markdown("---")
                    st.subheader("Detailed Information")
            
                    # ✅ Optional highlighting for duplicates
                    styled_df = duplicate_households_df.style.apply(
                        lambda row: ['background-color: #ffcccc' if row.household_count > 1 else '' for _ in row],
                        axis=1
                    )
            
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
                            "head_first_name": st.column_config.TextColumn(
                                "First Name HH",
                                help="First name of household head"
                            ),
                            "head_last_name": st.column_config.TextColumn(
                                "Last Name HH",
                                help="Last name of household head"
                            ),
                            "household_count": st.column_config.NumberColumn(
                                "Household Count",
                                help="Number of households sharing this dwelling"
                            ),
                            "total_individuals": st.column_config.NumberColumn(
                                "Total Individuals",
                                help="Total individuals in the household"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
                    # Download button
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

            # Duplicate Names Table section
            st.markdown("---")
            st.subheader("Duplicate Names Table")
            
            try:
                # Query for duplicate names in households
                duplicate_names_query = """
                SELECT 
                    h.location_name,
                    h.location_num,
                    h.dwelling_number,
                    CONCAT(i.indiv_fname, ' ', i.indiv_lname) AS full_name,
                    COUNT(*) AS name_count
                FROM households h
                JOIN individuals i 
                    ON h.key = i.parent_key
                    AND i.relo_to_hh = 1
                WHERE h.agree_yes = 1
                AND h.pro_name = %s
                GROUP BY 
                    h.key,
                    h.location_name,
                    h.location_num,
                    h.dwelling_number,
                    CONCAT(i.indiv_fname, ' ', i.indiv_lname)
                HAVING COUNT(*) > 1
                ORDER BY 
                    h.location_name,
                    h.dwelling_number;
                """
                
                # Execute the query
                duplicate_names_df = pd.read_sql(duplicate_names_query, engine, params=(selected_site,))
                
                if not duplicate_names_df.empty:
                    # Count duplicate names
                    total_duplicate_names = len(duplicate_names_df)
                    
                    # Display summary metrics
                    st.markdown("#### Summary")
                    st.metric("Duplicate Names (Household Heads)", f"{total_duplicate_names:,}")
                    
                    st.markdown("---")
                    st.subheader("Detailed Information")
                    
                    # Display the detailed table
                    st.dataframe(
                        duplicate_names_df,
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
                            "full_name": st.column_config.TextColumn(
                                "Full Name",
                                help="Full name of household head"
                            ),
                            "name_count": st.column_config.NumberColumn(
                                "Name Count",
                                help="Number of times this name appears"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Add download button for the data
                    csv_duplicate_names = duplicate_names_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Duplicate Names (CSV)",
                        data=csv_duplicate_names,
                        file_name=f"duplicate_names_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.success("No duplicate names found!")
                    
            except Exception as e:
                st.error(f"Error in duplicate names check: {e}")
                st.exception(e)

            # Missing Sex Query
            st.markdown("---")
            st.subheader("Missing Sex Table")
            
            try:
                # Query for individuals with missing sex
                missing_sex_query = """
                SELECT
                    h.ward_name,
                    h.location_name,
                    h.location_num,
                    h.dwelling_number,
                    h.consent_respondent_name,
                    h.four_3_1 AS data_collector,
                    h.interview_date_time_1 AS interview_datetime,
                    CONCAT(i.indiv_fname, ' ', i.indiv_lname) AS full_name,
                    i.relo_to_hh AS relationship_to_head,
                    i.sex
                FROM households h
                JOIN individuals i
                    ON h.key = i.parent_key
                WHERE h.agree_yes = 1
                AND h.pro_name = %s
                AND i.sex IS NULL;
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
        
            # Missing Age Table section
            st.markdown("---")
            st.subheader("Missing Age Table")

            try:
                # Query for individuals with missing or invalid age data
                missing_age_query = """
                SELECT
                    h.ward_name,
                    h.location_name,
                    h.dwelling_number,

                    h.four_3_1 AS data_collector,
                    h.four_5_1 AS data_quality_check_by,
                    h.four_1_1 AS result_of_interview,
                    h.four_3_2 AS interview_comment_observation,
                    h.submittername,

                    -- Household head
                    CONCAT(head.indiv_fname, ' ', head.indiv_lname) AS household_head_name,

                    -- Individual
                    CONCAT(i.indiv_fname, ' ', i.indiv_lname) AS individual_name,
                    i.indiv_line_num,
                    i.age_category,

                    i.age_year,
                    i.age_month,
                    i.age_days,
                    i.est_age_years,
                    i.est_age_month,
                    i.est_age_days,

                    CASE
                        -- ❌ Years selected but missing
                        WHEN i.age_category = 'mb1a_age_years'
                             AND (i.age_year IS NULL OR i.age_year = 888)
                        THEN 'Year selected but age_year missing or invalid'

                        -- ❌ Months selected but missing
                        WHEN i.age_category = 'mb1a_age_months'
                             AND (i.age_month IS NULL OR i.age_month = 888)
                        THEN 'Month selected but age_month missing or invalid'

                        -- ❌ Days selected but missing
                        WHEN i.age_category = 'mb1a_age_days'
                             AND (i.age_days IS NULL OR i.age_days = 888)
                        THEN 'Day selected but age_days missing or invalid'

                        -- ❌ 888 used but no estimate
                        WHEN i.age_year = 888
                             AND i.est_age_years IS NULL
                        THEN 'Year unknown but estimate missing'

                        WHEN i.age_month = 888
                             AND i.est_age_month IS NULL
                        THEN 'Month unknown but estimate missing'

                        WHEN i.age_days = 888
                             AND i.est_age_days IS NULL
                        THEN 'Day unknown but estimate missing'

                        -- ❌ All empty
                        WHEN
                            (i.age_year IS NULL) AND
                            (i.age_month IS NULL) AND
                            (i.age_days IS NULL) AND
                            (i.est_age_years IS NULL) AND
                            (i.est_age_month IS NULL) AND
                            (i.est_age_days IS NULL)
                        THEN 'All age fields missing'

                    END AS issue

                FROM households h

                JOIN individuals i
                    ON h.key = i.parent_key

                LEFT JOIN individuals head
                    ON h.key = head.parent_key
                    AND head.relo_to_hh = 1

                WHERE h.agree_yes = 1
                AND h.pro_name = %s
                AND (
                    -- Only show problematic records
                    (
                        i.age_category = 'mb1a_age_years'
                        AND (i.age_year IS NULL OR i.age_year = 888)
                    )
                    OR
                    (
                        i.age_category = 'mb1a_age_months'
                        AND (i.age_month IS NULL OR i.age_month = 888)
                    )
                    OR
                    (
                        i.age_category = 'mb1a_age_days'
                        AND (i.age_days IS NULL OR i.age_days = 888)
                    )
                    OR
                    (i.age_year = 888 AND (i.est_age_years IS NULL))
                    OR
                    (i.age_month = 888 AND (i.est_age_month IS NULL))
                    OR
                    (i.age_days = 888 AND (i.est_age_days IS NULL))
                    OR
                    (
                        (i.age_year IS NULL) AND
                        (i.age_month IS NULL) AND
                        (i.age_days IS NULL) AND
                        (i.est_age_years IS NULL) AND
                        (i.est_age_month IS NULL) AND
                        (i.est_age_days IS NULL)
                    )
                )

                ORDER BY
                    h.location_name,
                    h.dwelling_number;
                """

                # Execute the query
                missing_age_df = pd.read_sql(missing_age_query, engine, params=(selected_site,))

                if not missing_age_df.empty:
                    # Count individuals with missing age data
                    total_missing_age = len(missing_age_df)

                    # Display summary metrics
                    st.markdown("#### Summary")
                    st.metric("Individuals with Missing Age Data", f"{total_missing_age:,}")

                    st.markdown("---")
                    st.subheader("Detailed Information")

                    # Display the detailed table
                    st.dataframe(
                        missing_age_df,
                        column_config={
                            "ward_name": st.column_config.TextColumn(
                                "Ward",
                                help="Ward name"
                            ),
                            "location_name": st.column_config.TextColumn(
                                "Village",
                                help="Location name"
                            ),
                            "dwelling_number": st.column_config.NumberColumn(
                                "Dwelling Number",
                                help="Household dwelling number"
                            ),
                            "data_collector": st.column_config.TextColumn(
                                "Data Collector",
                                help="Name of the data collector"
                            ),
                            "data_quality_check_by": st.column_config.TextColumn(
                                "Quality Check By",
                                help="Person who performed data quality check"
                            ),
                            "result_of_interview": st.column_config.TextColumn(
                                "Interview Result",
                                help="Result of the interview"
                            ),
                            "interview_comment_observation": st.column_config.TextColumn(
                                "Interview Comments",
                                help="Comments or observations from interview"
                            ),
                            "submittername": st.column_config.TextColumn(
                                "Submitter",
                                help="Name of the submitter"
                            ),
                            "household_head_name": st.column_config.TextColumn(
                                "Household Head",
                                help="Name of the household head"
                            ),
                            "individual_name": st.column_config.TextColumn(
                                "Individual Name",
                                help="Name of the individual"
                            ),
                            "indiv_line_num": st.column_config.NumberColumn(
                                "Line Number",
                                help="Individual line number in household"
                            ),
                            "age_category": st.column_config.TextColumn(
                                "Age Category",
                                help="Age category selected (years/months/days)"
                            ),
                            "age_year": st.column_config.TextColumn(
                                "Age (Years)",
                                help="Age in years"
                            ),
                            "age_month": st.column_config.TextColumn(
                                "Age (Months)",
                                help="Age in months"
                            ),
                            "age_days": st.column_config.TextColumn(
                                "Age (Days)",
                                help="Age in days"
                            ),
                            "est_age_years": st.column_config.TextColumn(
                                "Est. Age (Years)",
                                help="Estimated age in years"
                            ),
                            "est_age_month": st.column_config.TextColumn(
                                "Est. Age (Months)",
                                help="Estimated age in months"
                            ),
                            "est_age_days": st.column_config.TextColumn(
                                "Est. Age (Days)",
                                help="Estimated age in days"
                            ),
                            "issue": st.column_config.TextColumn(
                                "Issue Description",
                                help="Description of the age data issue"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )

                    # Add download button for the data
                    csv_missing_age = missing_age_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Missing Age Data (CSV)",
                        data=csv_missing_age,
                        file_name=f"missing_age_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
                else:
                    st.success("No individuals with missing age data found!")

            except Exception as e:
                st.error(f"Error in missing age check: {e}")
                st.exception(e)

            # Age Checks Table section
            st.markdown("---")
            st.subheader("Age Checks Table")
            
            try:
                age_checks_query = """
                SELECT
                    h.ward_name,
                    h.location_name,
                    h.dwelling_number,
            
                    h.four_3_1 AS data_collector,
                    h.four_5_1 AS data_quality_check_by,
                    h.four_1_1 AS result_of_interview,
                    h.submittername,
            
                    CONCAT(head.indiv_fname, ' ', head.indiv_lname) AS household_head_name,
            
                    CONCAT(i.indiv_fname, ' ', i.indiv_lname) AS individual_name,
                    i.indiv_line_num,
                    i.relo_to_hh,
            
                    -- DOB fields
                    i.day_birth,
                    i.month_birth,
                    i.year_birth,
            
                    -- Age fields
                    i.age_category,
                    i.age_year,
                    i.age_month,
                    i.age_days,
            
                    -- Estimated ages
                    i.est_age_years,
                    i.est_age_month,
                    i.est_age_days,
            
                    CASE
            
                        -- 🚨 Missing DOB
                        WHEN (
                            i.day_birth IS NULL
                            OR i.month_birth IS NULL
                            OR i.year_birth IS NULL
                        )
                        THEN 'Missing Date of Birth'
            
                        -- 🚨 Underage household head/spouse
                        WHEN i.relo_to_hh IN (1,2,3)
                             AND i.age_category = 'mb1a_age_years'
                             AND (
                                (i.age_year <> 888 AND i.age_year <= 13)
                                OR
                                (
                                    i.age_year = 888
                                    AND i.est_age_years IS NOT NULL
                                    AND i.est_age_years <> 888
                                    AND i.est_age_years <= 13
                                )
                             )
                        THEN 'Head/Spouse age ≤ 13 (Invalid)'
            
                        -- 🚨 Invalid months
                        WHEN i.age_category = 'mb1a_age_months'
                             AND (
                                (i.age_month <> 888 AND i.age_month >= 12)
                                OR
                                (
                                    i.age_month = 888
                                    AND i.est_age_month IS NOT NULL
                                    AND i.est_age_month <> 888
                                    AND i.est_age_month >= 12
                                )
                             )
                        THEN 'Age in months should be < 12'
            
                        -- 🚨 Invalid days
                        WHEN i.age_category = 'mb1a_age_days'
                             AND (
                                (i.age_days <> 888 AND i.age_days >= 31)
                                OR
                                (
                                    i.age_days = 888
                                    AND i.est_age_days IS NOT NULL
                                    AND i.est_age_days <> 888
                                    AND i.est_age_days >= 31
                                )
                             )
                        THEN 'Age in days should be < 31'
            
                        -- 🚨 Unknown age without estimate
                        WHEN i.age_category = 'mb1a_age_years'
                             AND i.age_year = 888
                             AND i.est_age_years IS NULL
                        THEN 'Unknown years but no estimate'
            
                        WHEN i.age_category = 'mb1a_age_months'
                             AND i.age_month = 888
                             AND i.est_age_month IS NULL
                        THEN 'Unknown months but no estimate'
            
                        WHEN i.age_category = 'mb1a_age_days'
                             AND i.age_days = 888
                             AND i.est_age_days IS NULL
                        THEN 'Unknown days but no estimate'
            
                    END AS issue
            
                FROM households h
            
                JOIN individuals i
                    ON h.key = i.parent_key
            
                LEFT JOIN individuals head
                    ON h.key = head.parent_key
                    AND head.relo_to_hh = 1
            
                WHERE h.agree_yes = 1
                AND h.pro_name = %s
            
                -- Exclude blank names
                AND TRIM(COALESCE(i.indiv_fname, '')) <> ''
                AND TRIM(COALESCE(i.indiv_lname, '')) <> ''
            
                AND (
            
                    -- 🚨 Missing DOB
                    (
                        i.day_birth IS NULL
                        OR i.month_birth IS NULL
                        OR i.year_birth IS NULL
                    )
            
                    -- 🚨 Underage head/spouse
                    OR (
                        i.relo_to_hh IN (1,2,3)
                        AND i.age_category = 'mb1a_age_years'
                        AND (
                            (i.age_year <> 888 AND i.age_year <= 13)
                            OR
                            (
                                i.age_year = 888
                                AND i.est_age_years IS NOT NULL
                                AND i.est_age_years <> 888
                                AND i.est_age_years <= 13
                            )
                        )
                    )
            
                    -- 🚨 Invalid months
                    OR (
                        i.age_category = 'mb1a_age_months'
                        AND (
                            (i.age_month <> 888 AND i.age_month >= 12)
                            OR
                            (
                                i.age_month = 888
                                AND i.est_age_month IS NOT NULL
                                AND i.est_age_month <> 888
                                AND i.est_age_month >= 12
                            )
                        )
                    )
            
                    -- 🚨 Invalid days
                    OR (
                        i.age_category = 'mb1a_age_days'
                        AND (
                            (i.age_days <> 888 AND i.age_days >= 31)
                            OR
                            (
                                i.age_days = 888
                                AND i.est_age_days IS NOT NULL
                                AND i.est_age_days <> 888
                                AND i.est_age_days >= 31
                            )
                        )
                    )
            
                    -- 🚨 Unknown without estimate
                    OR (
                        i.age_category = 'mb1a_age_years'
                        AND i.age_year = 888
                        AND i.est_age_years IS NULL
                    )
            
                    OR (
                        i.age_category = 'mb1a_age_months'
                        AND i.age_month = 888
                        AND i.est_age_month IS NULL
                    )
            
                    OR (
                        i.age_category = 'mb1a_age_days'
                        AND i.age_days = 888
                        AND i.est_age_days IS NULL
                    )
            
                )
            
                ORDER BY h.location_name, h.dwelling_number;
                """
            
                age_checks_df = pd.read_sql(
                    age_checks_query,
                    engine,
                    params=(selected_site,)
                )
            
                if not age_checks_df.empty:
            
                    total_age_checks = len(age_checks_df)
            
                    st.markdown("#### Summary")
                    st.metric(
                        "Individuals with Age Validation Issues",
                        f"{total_age_checks:,}"
                    )
            
                    st.markdown("---")
                    st.subheader("Detailed Information")
            
                    st.dataframe(
                        age_checks_df,
                        hide_index=True,
                        use_container_width=True
                    )
            
                    csv_age_checks = age_checks_df.to_csv(index=False).encode('utf-8')
            
                    st.download_button(
                        label="Download Age Checks Data (CSV)",
                        data=csv_age_checks,
                        file_name=f"age_checks_{selected_site.lower()}.csv",
                        mime="text/csv"
                    )
            
                else:
                    st.success("No individuals with age validation issues found!")
            
            except Exception as e:
                st.error(f"Error in age checks: {e}")
                st.exception(e)

            # ==================== Consolidated Data Quality Report ====================
            st.markdown("---")
            st.subheader("Consolidated Data Quality Report")

            try:
                # List of all dataframes with their issue types
                consolidated_data = []

                # 1. Detailed GPS Data
                if 'missing_gps_df' in locals() and not missing_gps_df.empty:
                    df = missing_gps_df.copy()
                    df['Issue_Type'] = 'Detailed GPS Data'
                    consolidated_data.append(df)

                # 2. Missing Consent
                if 'missing_consent_df' in locals() and not missing_consent_df.empty:
                    df = missing_consent_df.copy()
                    df['Issue_Type'] = 'Missing Consent'
                    consolidated_data.append(df)

                # 3. Missing Respondent or HH Member Information
                if 'missing_respondent_df' in locals() and not missing_respondent_df.empty:
                    df = missing_respondent_df.copy()
                    df['Issue_Type'] = 'Missing Respondent or HH Member Information'
                    consolidated_data.append(df)

                # 4. Households With No Members Recorded
                if 'no_members_df' in locals() and not no_members_df.empty:
                    df = no_members_df.copy()
                    df['Issue_Type'] = 'Households With No Members Recorded'
                    consolidated_data.append(df)

                # 5. Multiple Household Heads Table
                if 'multiple_heads_df' in locals() and not multiple_heads_df.empty:
                    df = multiple_heads_df.copy()
                    df['Issue_Type'] = 'Multiple Household Heads Table'
                    consolidated_data.append(df)

                # 6. Households With No Head Table
                if 'no_head_df' in locals() and not no_head_df.empty:
                    df = no_head_df.copy()
                    df['Issue_Type'] = 'Households With No Head Table'
                    consolidated_data.append(df)

                # 7. Duplicate Households (Same dwelling_number)
                if 'duplicate_households_df' in locals() and not duplicate_households_df.empty:
                    df = duplicate_households_df.copy()
                    df['Issue_Type'] = 'Duplicate Households (Same dwelling_number)'
                    consolidated_data.append(df)

                # 8. Duplicate Names Table
                if 'duplicate_names_df' in locals() and not duplicate_names_df.empty:
                    df = duplicate_names_df.copy()
                    df['Issue_Type'] = 'Duplicate Names Table'
                    consolidated_data.append(df)

                # 9. Missing Sex Table
                if 'missing_sex_df' in locals() and not missing_sex_df.empty:
                    df = missing_sex_df.copy()
                    df['Issue_Type'] = 'Missing Sex Table'
                    consolidated_data.append(df)

                # 10. Missing Age Table
                if 'missing_age_df' in locals() and not missing_age_df.empty:
                    df = missing_age_df.copy()
                    df['Issue_Type'] = 'Missing Age Table'
                    consolidated_data.append(df)

                # 11. Age Checks Table
                if 'age_checks_df' in locals() and not age_checks_df.empty:
                    df = age_checks_df.copy()
                    df['Issue_Type'] = 'Age Checks Table'
                    consolidated_data.append(df)

                # Create Excel file with multiple sheets
                if consolidated_data:
                    # Calculate total issues
                    total_issues = sum(len(df) for df in consolidated_data)

                    # Summary
                    st.markdown("#### Summary")
                    st.metric("Total Data Quality Issues", f"{total_issues:,}")

                    st.markdown("---")
                    st.subheader("Detailed Consolidated Report")

                    # Display summary table
                    summary_df = pd.DataFrame([
                        {'Issue_Type': df['Issue_Type'].iloc[0], 'Count': len(df)}
                        for df in consolidated_data
                    ])
                    st.dataframe(
                        summary_df,
                        column_config={
                            "Issue_Type": st.column_config.TextColumn("Issue Type"),
                            "Count": st.column_config.NumberColumn("Count")
                        },
                        hide_index=True,
                        use_container_width=True
                    )

                    # Create Excel file with multiple sheets
                    from io import BytesIO
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        for df in consolidated_data:
                            issue_type = df['Issue_Type'].iloc[0]
                            # Clean sheet name (remove special characters and limit length)
                            sheet_name = issue_type.replace('(', '').replace(')', '').replace(' ', '_')[:31]
                            df.drop('Issue_Type', axis=1).to_excel(writer, sheet_name=sheet_name, index=False)

                    output.seek(0)

                    # Download button for Excel file
                    st.download_button(
                        label="Download Consolidated Data Quality Report (Excel)",
                        data=output,
                        file_name=f"consolidated_data_quality_{selected_site.lower()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.success("No data quality issues found across all checks!")

            except Exception as e:
                st.error(f"Error creating consolidated report: {e}")
                st.exception(e)
                
        except Exception as e:
            st.error(f"Error running GPS quality query: {e}")

# Call the main function to actually run the app
if __name__ == "__main__":
    main()
