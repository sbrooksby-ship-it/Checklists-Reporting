import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import altair as alt

# Page configuration
st.set_page_config(page_title="Division Tracker Dashboard", layout="wide")
st.title("Division Tracker Dashboard")

# Establish connection to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def load_data():
    # header=2 sets row 3 as column headers
    df = conn.read(header=2)
    df = df.dropna(subset=['Completer'], how='all')
    
    if 'Div' in df.columns:
        df['Div'] = df['Div'].ffill()
        
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"Error loading data. Check your secrets.toml URL. Details: {e}")
    st.stop()

st.sidebar.header("Navigation")

# Clean 'Div' column to avoid float issues (.0)
df['Div'] = df['Div'].fillna("").astype(str).str.strip().str.replace('.0', '', regex=False)

# 1. QUICK DIVISION FILTER
div_options = ["All"] + sorted([d for d in df['Div'].unique() if d and d.lower() != 'nan'])
selected_div = st.sidebar.radio("Quick Filter: Division", options=div_options)

filtered_df = df.copy()
if selected_div != "All":
    filtered_df = filtered_df[filtered_df['Div'] == selected_div]

# Identify month columns dynamically (e.g., Aug, Sept, Oct, etc.)
possible_months = ['Aug', 'Sept', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul']
month_cols = [c for c in filtered_df.columns if c in possible_months or any(m in c for m in possible_months)]

# 2. CASCADING SECONDARY FILTERS
with st.sidebar.expander("More Filters (Optional)"):
    if 'Examiner' in filtered_df.columns:
        examiner_options = sorted([e for e in filtered_df['Examiner'].fillna("").astype(str).unique() if e and e.lower() != 'nan'])
        selected_examiner = st.multiselect("Examiner", options=examiner_options)
        if selected_examiner:
            filtered_df = filtered_df[filtered_df['Examiner'].isin(selected_examiner)]
            
    dept_col = 'Dept' if 'Dept' in filtered_df.columns else ('Department' if 'Department' in filtered_df.columns else None)
    if dept_col:
        dept_vals = filtered_df[dept_col].fillna("").astype(str).str.strip().str.replace('.0', '', regex=False)
        dept_options = sorted([d for d in dept_vals.unique() if d and d.lower() != 'nan'])
        selected_dept = st.multiselect("Department", options=dept_options)
        if selected_dept:
            filtered_df = filtered_df[filtered_df[dept_col].fillna("").astype(str).str.strip().str.replace('.0', '', regex=False).isin(selected_dept)]

    if 'Completer' in filtered_df.columns:
        completer_options = sorted([c for c in filtered_df['Completer'].fillna("").astype(str).unique() if c and c.lower() != 'nan'])
        selected_completer = st.multiselect("Completer", options=completer_options)
        if selected_completer:
            filtered_df = filtered_df[filtered_df['Completer'].isin(selected_completer)]

    if 'Due Date' in filtered_df.columns:
        due_options = sorted([d for d in filtered_df['Due Date'].fillna("").astype(str).unique() if d and d.lower() != 'nan'])
        selected_due = st.multiselect("Due Date", options=due_options)
        if selected_due:
            filtered_df = filtered_df[filtered_df['Due Date'].isin(selected_due)]

# Force numeric columns to floats
for col in ['# of TM', '# of Points', 'Total Points Possible']:
    if col in filtered_df.columns:
        filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce').fillna(0)

# ---------------------------------------------------------
# MEANINGFUL METRIC CALCULATIONS
# ---------------------------------------------------------
total_tasks = len(filtered_df)
total_tm = int(filtered_df['# of TM'].sum()) if '# of TM' in filtered_df.columns else 0
total_pts = filtered_df['Total Points Possible'].sum() if 'Total Points Possible' in filtered_df.columns else 0

avg_pts_per_tm = round(total_pts / total_tm, 2) if total_tm > 0 else 0.0
avg_pts_per_task = round(total_pts / total_tasks, 2) if total_tasks > 0 else 0.0

st.subheader("Current View Metrics")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Total Active Tasks", value=total_tasks)
with col2:
    st.metric(label="Total Team Members", value=total_tm)
with col3:
    st.metric(label="Avg Points / Person", value=avg_pts_per_tm, help="Total Points Possible ÷ Total Team Members")
with col4:
    st.metric(label="Avg Weight / Task", value=avg_pts_per_task, help="Average point density per task section")

# ---------------------------------------------------------
# COLOR MAP DEFINITIONS
# ---------------------------------------------------------

# Division Colors (Row Backgrounds)
TABLE_COLOR_MAP = {
    '1': '#fff8e1',  # Light Yellow
    '2': '#f3e5f5',  # Light Purple
    '3': '#e8f5e9',  # Light Green
    '4': '#fff3e0',  # Light Peach/Orange
    '5': '#fce4ec',  # Light Pink
    '6': '#e0f7fa',  # Light Cyan/Teal
    '7': '#e3f2fd',  # Light Blue
}

CHART_COLOR_MAP = [
    '#fbc02d', '#ab47bc', '#66bb6a', '#ffa726', '#ec407a', '#26c6da', '#42a5f5'
]

# ---------------------------------------------------------
# TABS INTERFACE
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 Workload & Capacity", "🗓️ Monthly Status Heatmap", "📁 Full Data & Export"])

with tab1:
    st.subheader("Performance & Points Distribution")
    if 'Completer' in filtered_df.columns and 'Total Points Possible' in filtered_df.columns:
        chart_data = (
            filtered_df[filtered_df['Completer'] != ""]
            .groupby(['Completer', 'Div'])['Total Points Possible']
            .sum()
            .reset_index()
        )
        
        if not chart_data.empty:
            domain_divisions = ['1', '2', '3', '4', '5', '6', '7']
            
            chart = (
                alt.Chart(chart_data)
                .mark_bar()
                .encode(
                    x=alt.X('Completer:N', sort='-y', title='Completer'),
                    y=alt.Y('Total Points Possible:Q', title='Total Points Possible'),
                    color=alt.Color('Div:N', scale=alt.Scale(domain=domain_divisions, range=CHART_COLOR_MAP), title='Division'),
                    tooltip=['Completer', 'Div', 'Total Points Possible']
                )
                .properties(height=380)
            )
            
            st.altair_chart(chart, use_container_width=True)

with tab2:
    st.subheader("Monthly Submission Status Heatmap")
    
    if month_cols:
        # Reshape data into long format for monthly status analysis
        melted_df = filtered_df.melt(
            id_vars=['Section', 'Completer', 'Div'],
            value_vars=month_cols,
            var_name='Month',
            value_name='Status'
        )
        
        # Standardize Status Strings
        melted_df['Status'] = melted_df['Status'].fillna('Not Submitted').astype(str).str.strip()
        melted_df['Status'] = melted_df['Status'].replace({'': 'Not Submitted', 'nan': 'Not Submitted'})
        
        # Monthly Status Stacked Bar Visual
        status_chart = (
            alt.Chart(melted_df)
            .mark_bar()
            .encode(
                x=alt.X('Month:N', sort=month_cols, title='Month'),
                y=alt.Y('count():Q', title='Number of Tasks'),
                color=alt.Color(
                    'Status:N',
                    scale=alt.Scale(
                        domain=['100%', 'Late', 'Not Submitted', 'N/A'],
                        range=['#00e5ff', '#ffeb3b', '#ff5252', '#9e9e9e']
                    ),
                    title='Submission Status'
                ),
                tooltip=['Month', 'Status', 'count()']
            )
            .properties(height=320)
        )
        st.altair_chart(status_chart, use_container_width=True)
    else:
        st.info("No monthly columns (Aug, Sept, Oct) found in the current sheet format.")

with tab3:
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.subheader("Complete Tracker Data")
    with col_b:
        csv_data = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Current View to CSV",
            data=csv_data,
            file_name="division_tracker_export.csv",
            mime="text/csv",
        )

    # Function to apply Division background colors
    def color_rows(row):
        div = str(row.get('Div', '')).strip().replace('.0', '')
        bg_color = TABLE_COLOR_MAP.get(div, '')
        if bg_color:
            return [f'background-color: {bg_color}; color: black'] * len(row)
        return [''] * len(row)

    # Function to apply cell-level status colors for Month Columns (Aug, Sept, Oct)
    def color_status_cells(val):
        val_str = str(val).strip().lower()
        if '100%' in val_str or val_str in ['1', '1.0', 'done']:
            return 'background-color: #00e5ff; color: black; font-weight: bold;'  # Cyan
        elif 'late' in val_str:
            return 'background-color: #ffeb3b; color: black; font-weight: bold;'  # Yellow
        elif 'not' in val_str or 'missing' in val_str or val_str in ['0', '0.0']:
            return 'background-color: #ff5252; color: white; font-weight: bold;'   # Red
        elif 'n/a' in val_str or 'na' in val_str:
            return 'background-color: #9e9e9e; color: white;'                    # Gray
        return ''

    # Apply styling: row division colors + specific month cell colors
    styled_df = filtered_df.style.apply(color_rows, axis=1)
    
    # Check for pandas version compatibility for element-wise mapping
    if month_cols:
        try:
            styled_df = styled_df.map(color_status_cells, subset=month_cols)
        except AttributeError:
            styled_df = styled_df.applymap(color_status_cells, subset=month_cols)

    styled_df = styled_df.format(precision=2, na_rep="")
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
