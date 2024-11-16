import streamlit as st
import pandas as pd
import numpy as np
import sklearn.cluster
from datetime import datetime
from sklearn.cluster import KMeans

# Streamlit UI
st.title("Employee Attendance and Average Working Hours Dashboard")
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    # Load and prepare the data
    data = pd.read_csv(uploaded_file)
    data.columns = data.columns.str.lower().str.strip()
    data['tanggal'] = pd.to_datetime(data['tanggal'], errors='coerce')
    data['checkin_time_get'] = data['checkin_time_get'].fillna("placeholder")
    data['checkout_time_get'] = data['checkout_time_get'].fillna("placeholder")

    # Mark "lupa/perbaikan absensi" based on conditions
    def mark_absence_correction(row):
        if (pd.isnull(row['checkin_date_get']) or pd.isnull(row['checkout_date_get']) or
            (row['checkout_time_get'] == "12:12:12" and row['checkout_date_get'] == "2000-01-01") or
            pd.isnull(row['checkin_time_get']) or pd.isnull(row['checkout_time_get']) or
            row['checkin_time_get'] == "12:12:12" or row['checkout_time_get'] == "12:12:12"):
            return "lupa/perbaikan absensi"
        return np.nan

    data['jumlah_jam_kerja'] = data.apply(mark_absence_correction, axis=1)

    # Calculate working hours only if entry is not marked as "lupa/perbaikan absensi"
    def calculate_working_hours(row):
        if row['jumlah_jam_kerja'] != "lupa/perbaikan absensi":
            try:
                checkin = pd.to_datetime(f"{row['checkin_date_get']} {row['checkin_time_get']}", errors='coerce')
                checkout = pd.to_datetime(f"{row['checkout_date_get']} {row['checkout_time_get']}", errors='coerce')
                if pd.notnull(checkin) and pd.notnull(checkout):
                    hours_worked = (checkout - checkin).total_seconds() / 3600
                    return hours_worked if hours_worked >= 0 else None
            except:
                return None
        return None

    data['jumlah_jam_kerja'] = data.apply(
        lambda row: calculate_working_hours(row) if row['jumlah_jam_kerja'] != "lupa/perbaikan absensi" else None,
        axis=1
    )

    # Create checkin_datetime and checkout_datetime columns for additional analysis
    data['checkin_datetime'] = pd.to_datetime(data['checkin_date_get'] + ' ' + data['checkin_time_get'], errors='coerce')
    data['checkout_datetime'] = pd.to_datetime(data['checkout_date_get'] + ' ' + data['checkout_time_get'], errors='coerce')

    # Sidebar filters
    st.sidebar.title("Filters")
    if not data['tanggal'].isnull().all():
        min_date = data['tanggal'].min().date()
        max_date = data['tanggal'].max().date()
    else:
        min_date = None
        max_date = None

    start_date, end_date = st.sidebar.date_input("Select Date Range", [min_date, max_date] if min_date and max_date else [datetime.today().date(), datetime.today().date()])
    directorate = st.sidebar.selectbox("Directorate", ["All"] + sorted(data['dir_title'].dropna().unique()))
    work_type = st.sidebar.selectbox("Type of Work", ["All"] + sorted(data['type_work_name'].dropna().unique()))
    position_grade = st.sidebar.selectbox("Position Grade", ["All"] + sorted(data['pos_grade'].dropna().unique()))

    # Apply filters
    filtered_data = data.copy()
    if directorate != "All":
        filtered_data = filtered_data[filtered_data['dir_title'] == directorate]
    if work_type != "All":
        filtered_data = filtered_data[filtered_data['type_work_name'] == work_type]
    if position_grade != "All":
        filtered_data = filtered_data[filtered_data['pos_grade'] == position_grade]
    filtered_data = filtered_data[(filtered_data['tanggal'] >= pd.to_datetime(start_date)) & (filtered_data['tanggal'] <= pd.to_datetime(end_date))]

    # Tambahkan kolom lembur berdasarkan logika >= 10 jam kerja
    filtered_data['lembur'] = filtered_data['jumlah_jam_kerja'].apply(lambda x: 1 if x >= 10 else 0)

    # Ambil hari unik lembur
    overtime_days = filtered_data[filtered_data['lembur'] == 1].drop_duplicates(subset=['employee_id', 'tanggal'])

    # Metrics Display: Total Correction Requests, Early Departures, Late Check-ins
    corrections = filtered_data['jumlah_jam_kerja'].isna().sum() + filtered_data['jumlah_jam_kerja'].eq("lupa/perbaikan absensi").sum()
    early_departures = filtered_data[filtered_data['jumlah_jam_kerja'] < 9].shape[0]
    late_checkins = filtered_data[filtered_data['checkin_datetime'].dt.time > datetime.strptime("08:30:00", "%H:%M:%S").time()].shape[0]

    # Display metrics in the sidebar
    st.sidebar.metric("Total Correction Requests (Filtered)", corrections)
    st.sidebar.metric("Total Early Departures (<9 hours)", early_departures)
    st.sidebar.metric("Total Late Check-ins (>8:30 AM)", late_checkins)

    # Total lembur metrics
    total_overtime_frequency = overtime_days.shape[0]
    st.sidebar.metric("Total Overtime Frequency (Days)", total_overtime_frequency)

    # Visualization: Monthly Overtime Frequency Trend
    overtime_days['month'] = overtime_days['tanggal'].dt.to_period('M')
    overtime_frequency_monthly_trend = (
        overtime_days.groupby('month')
        .size()
        .sort_index()
    )
    st.subheader("Monthly Overtime Frequency Trend")
    st.line_chart(overtime_frequency_monthly_trend.rename("Frekuensi Lembur per Bulan"))

    # Step 1: Calculate per-employee daily averages
    daily_avg_per_employee = filtered_data.groupby(['employee_id', 'tanggal'])['jumlah_jam_kerja'].mean().reset_index()

    # Visualization 1: Average Working Hours by Compartment
    st.subheader("Average Working Hours by Compartment")
    avg_hours_by_compartment = daily_avg_per_employee.merge(filtered_data[['employee_id', 'komp_title']].drop_duplicates(), on='employee_id')
    avg_hours_by_compartment = avg_hours_by_compartment.groupby('komp_title')['jumlah_jam_kerja'].mean().fillna(0).round().astype(int)
    st.bar_chart(avg_hours_by_compartment.rename("Rata-rata Jam Kerja (jam)"))

    # Visualization 2: Average Working Hours by Job Category
    st.subheader("Average Working Hours by Job Category")
    avg_hours_by_job_category = daily_avg_per_employee.merge(filtered_data[['employee_id', 'kategori_jabatan']].drop_duplicates(), on='employee_id')
    avg_hours_by_job_category = avg_hours_by_job_category.groupby('kategori_jabatan')['jumlah_jam_kerja'].mean().fillna(0).round().astype(int)
    st.bar_chart(avg_hours_by_job_category.rename("Rata-rata Jam Kerja (jam)"))

    # Visualization 3: Average Working Hours by Position Grade (Ordered)
    st.subheader("Average Working Hours by Position Grade")
    avg_hours_by_pos_grade = daily_avg_per_employee.merge(filtered_data[['employee_id', 'pos_grade']].drop_duplicates(), on='employee_id')
    avg_hours_by_pos_grade = avg_hours_by_pos_grade.groupby('pos_grade')['jumlah_jam_kerja'].mean().fillna(0).sort_index().round().astype(int)
    st.bar_chart(avg_hours_by_pos_grade.rename("Rata-rata Jam Kerja (jam)"))

    # Visualization 4: Average Working Hours by Generation
    st.subheader("Average Working Hours by Generation")
    avg_hours_by_generation = daily_avg_per_employee.merge(filtered_data[['employee_id', 'generasi']].drop_duplicates(), on='employee_id')
    avg_hours_by_generation = avg_hours_by_generation.groupby('generasi')['jumlah_jam_kerja'].mean().fillna(0).round().astype(int)
    st.bar_chart(avg_hours_by_generation.rename("Rata-rata Jam Kerja (jam)"))

    # Visualization 5: Monthly Average Working Hours per Day (by jk_keterangan_name)
    filtered_data['month'] = filtered_data['tanggal'].dt.to_period('M')
    avg_hours_by_jk_and_month = (
        filtered_data.groupby(['month', 'jk_keterangan_name'])['jumlah_jam_kerja']
        .mean()
        .unstack()
        .fillna(0)
        .round()
        .astype(int)
    )
    st.subheader("Monthly Average Working Hours per Day by Work Description")
    st.line_chart(avg_hours_by_jk_and_month.rename_axis("Bulan").rename(columns=lambda x: f"{x} (jam)"))

    # Visualization 6: Dynamic Monthly Trend Line for Average Working Hours
    daily_avg_per_employee['month'] = daily_avg_per_employee['tanggal'].dt.to_period('M')
    monthly_hours_trend = (
        daily_avg_per_employee.groupby('month')['jumlah_jam_kerja']
        .mean()
        .fillna(0)
        .round()
    )
    st.subheader("Monthly Average Working Hours Trend")
    st.line_chart(monthly_hours_trend.rename("Rata-rata Jam Kerja (jam)"))

    # Additional Visualization: Count of Employees Working Less Than 9 Hours per Compartment
    st.subheader("Count of Employees Working Less Than 9 Hours by Compartment")
    under_9_hours = filtered_data[filtered_data['jumlah_jam_kerja'] < 9].groupby('komp_title').size()
    st.bar_chart(under_9_hours.rename("Jumlah Karyawan (<9 jam)"))

     # Clustering by jumlah_jam_kerja for each employee
    st.subheader("Clustering Employees by Average Working Hours")
    
    # Calculate total working hours per employee
    total_hours_per_employee = daily_avg_per_employee.groupby('employee_id')['jumlah_jam_kerja'].sum().reset_index()
    
    # Remove NaN values for clustering
    total_hours_per_employee = total_hours_per_employee.dropna()

    # Apply KMeans clustering on total working hours
    kmeans = KMeans(n_clusters=3, random_state=42)
    total_hours_per_employee['cluster'] = kmeans.fit_predict(total_hours_per_employee[['jumlah_jam_kerja']])

    # Merge cluster info back into original data
    clustered_data = total_hours_per_employee.merge(filtered_data[['employee_id']].drop_duplicates(), on='employee_id', how='left')

    # Display clustering results
    st.write(clustered_data)

    # Display clustering distribution
    cluster_counts = clustered_data['cluster'].value_counts().sort_index()
    st.bar_chart(cluster_counts.rename("Employee Clusters"))

    # Additional visualizations...

    # Visualization 1: Average Working Hours by Compartment
    st.subheader("Average Working Hours by Compartment")
    avg_hours_by_compartment = daily_avg_per_employee.merge(filtered_data[['employee_id', 'komp_title']].drop_duplicates(), on='employee_id')
    avg_hours_by_compartment = avg_hours_by_compartment.groupby('komp_title')['jumlah_jam_kerja'].mean().fillna(0).round().astype(int)
    st.bar_chart(avg_hours_by_compartment.rename("Rata-rata Jam Kerja (jam)"))