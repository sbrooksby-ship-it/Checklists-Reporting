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

# ---------------------------------------------------------
# AUTHENTICATION & ROLE-BASED FILTERING
# ---------------------------------------------------------
# 1. Enforce Login
if not st.user.is_logged_in:
    st.warning("Please log in to view the Division Tracker.")
    if st.button("Log in with Google"):
        st.login()
    st.stop()

# 2. Get User Email & Show Logout
user_email = st.user.email
st.sidebar.markdown(f"**👤 Logged in as:**\n{user_email}")
if st.sidebar.button("Log out"):
    st.logout()
st.sidebar.divider()

# 3. Apply Permissions Filter
# ADD YOUR UNLIMITED ACCESS EMAILS HERE:
admin_emails = [
    "sbrooksby@bonadmin.com", 
    "bwilson@bonadmin.com", 
    "adickson@bonadmin.com"
] 

if user_email.lower() not in [email.lower() for email in admin_emails]:
    if 'Completer_Email' in df.columns:
        # Filter the master dataframe down to just this user's rows
        df = df[df['Completer_Email'].astype(str).str.strip().str.lower() == user_email.lower()]
    else:
        st.error("Setup Error: 'Completer_Email' column missing in Google Sheets.")
        st.stop()


# ---------------------------------------------------------
# NAVIGATION & FILTERS
# ---------------------------------------------------------
st.sidebar.header("Navigation")

# Clean 'Div' column to avoid float issues (.0)
df['Div'] = df['Div'].fillna("").astype(str).str.strip().str.replace('.0', '', regex=False)

# 1. QUICK DIVISION & SEARCH FILTERS
div_options = ["All"] + sorted([d for d in df['Div'].unique() if d and d.lower() != 'nan'])
selected_div = st.sidebar.radio("Quick Filter: Division", options=div_options)

search_query = st.sidebar.text_input("🔍 Keyword Search (Section, Completer, etc.)", "")

filtered_df = df.copy()
if selected_div != "All":
    filtered_df = filtered_df[filtered_df['Div'] == selected_div]

# Apply Keyword Search across all string columns
if search_query:
    mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
    filtered_df = filtered_df[mask]

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

for col in ['# of TM', '# of Points', 'Total Points Possible']:
    if col in filtered_df.columns:
        filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce').fillna(0)

# ---------------------------------------------------------
# METRIC CALCULATIONS & HEALTH SCORE
# ---------------------------------------------------------
total_tasks = len(filtered_df)
total_tm = int(filtered_df['# of TM'].sum()) if '# of TM' in filtered_df.columns else 0
total_pts = filtered_df['Total Points Possible'].sum() if 'Total Points Possible' in filtered_df.columns else 0

avg_pts_per_tm = round(total_pts / total_tm, 2) if total_tm > 0 else 0.0
avg_pts_per_task = round(total_pts / total_tasks, 2) if total_tasks > 0 else 0.0

# Calculate Overall Health (% of tasks marked 100%)
completion_rate = 0.0
if month_cols and total_tasks > 0:
    all_statuses = filtered_df[month_cols].values.flatten()
    # Adding str(s) guarantees it is text before trying to strip or lowercase it
    valid_statuses = [str(s) for s in all_statuses if str(s).strip().lower() not in ['nan', '', 'n/a', 'na', 'none']]
    if valid_statuses:
        on_time = sum(1 for s in valid_statuses if '100%' in str(s) or str(s).strip().lower() in ['1', '1.0', 'done'])
        completion_rate = round((on_time / len(valid_statuses)) * 100, 1)

st.subheader("Current View Metrics")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(label="Total Active Tasks", value=total_tasks)
with col2:
    st.metric(label="Total Team Members", value=total_tm)
with col3:
    st.metric(label="Avg Points / Person", value=avg_pts_per_tm)
with col4:
    st.metric(label="Avg Weight / Task", value=avg_pts_per_task)
with col5:
    st.metric(label="Overall On-Time %", value=f"{completion_rate}%", help="Percentage of valid monthly submissions marked 100%")

st.divider()

# ---------------------------------------------------------
# COLOR MAP DEFINITIONS
# ---------------------------------------------------------
TABLE_COLOR_MAP = {
    '1': '#fff8e1', '2': '#f3e5f5', '3': '#e8f5e9', 
    '4': '#fff3e0', '5': '#fce4ec', '6': '#e0f7fa', '7': '#e3f2fd'
}
CHART_COLOR_MAP = ['#fbc02d', '#ab47bc', '#66bb6a', '#ffa726', '#ec407a', '#26c6da', '#42a5f5']

STATUS_LEGEND_HTML = """
<div style="display: flex; gap: 12px; align-items: center; margin-bottom: 18px; flex-wrap: wrap;">
    <span style="font-weight: bold; font-size: 14px;">Status Legend:</span>
    <span style="background-color: #00e5ff; color: #000; padding: 4px 12px; border-radius: 6px; font-weight: bold; font-size: 13px;">100% (On Time)</span>
    <span style="background-color: #ffeb3b; color: #000; padding: 4px 12px; border-radius: 6px; font-weight: bold; font-size: 13px;">Late</span>
    <span style="background-color: #ff5252; color: #fff; padding: 4px 12px; border-radius: 6px; font-weight: bold; font-size: 13px;">Not Submitted</span>
    <span style="background-color: #9e9e9e; color: #fff; padding: 4px 12px; border-radius: 6px; font-weight: bold; font-size: 13px;">N/A</span>
</div>
"""

# ---------------------------------------------------------
# TABS & CONTENT
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📊 Main Dashboard", "🗓️ Monthly Status Heatmap"])

with tab1:
    st.subheader("Performance Overview")
    if 'Completer' in filtered_df.columns and 'Total Points Possible' in filtered_df.columns:
        chart_data = filtered_df[filtered_df['Completer'] != ""].groupby(['Completer', 'Div'])['Total Points Possible'].sum().reset_index()
        if not chart_data.empty:
            domain_divisions = ['1', '2', '3', '4', '5', '6', '7']
            chart = alt.Chart(chart_data).mark_bar().encode(
                x=alt.X('Completer:N', sort='-y', title='Completer'),
                y=alt.Y('Total Points Possible:Q', title='Total Points Possible'),
                color=alt.Color('Div:N', scale=alt.Scale(domain=domain_divisions, range=CHART_COLOR_MAP), title='Division'),
                tooltip=['Completer', 'Div', 'Total Points Possible']
            ).properties(height=380)
            st.altair_chart(chart, use_container_width=True)

    st.divider()

    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.subheader("Tracker Data")
    with col_b:
        csv_data = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Current View to CSV", data=csv_data, file_name="division_tracker_export.csv", mime="text/csv")

    def color_rows(row):
        div = str(row.get('Div', '')).strip().replace('.0', '')
        bg_color = TABLE_COLOR_MAP.get(div, '')
        return [f'background-color: {bg_color}; color: black'] * len(row) if bg_color else [''] * len(row)

    def color_status_cells(val):
        val_str = str(val).strip().lower()
        if '100%' in val_str or val_str in ['1', '1.0', 'done']:
            return 'background-color: #00e5ff; color: black; font-weight: bold;'
        elif 'late' in val_str:
            return 'background-color: #ffeb3b; color: black; font-weight: bold;'
        elif 'not' in val_str or 'missing' in val_str or val_str in ['0', '0.0']:
            return 'background-color: #ff5252; color: white; font-weight: bold;'
        elif 'n/a' in val_str or 'na' in val_str:
            return 'background-color: #9e9e9e; color: white;'
        return ''

    styled_df = filtered_df.style.apply(color_rows, axis=1)
    if month_cols:
        try:
            styled_df = styled_df.map(color_status_cells, subset=month_cols)
        except AttributeError:
            styled_df = styled_df.applymap(color_status_cells, subset=month_cols)

    styled_df = styled_df.format(precision=2, na_rep="")
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


with tab2:
    st.subheader("Completer Status Heatmap")
    st.markdown(STATUS_LEGEND_HTML, unsafe_allow_html=True)

    if month_cols:
        melted_df = filtered_df.melt(
            id_vars=['Section', 'Completer', 'Div'],
            value_vars=month_cols,
            var_name='Month',
            value_name='Status'
        )
        
        melted_df['Status'] = melted_df['Status'].fillna('Not Submitted').astype(str).str.strip()
        melted_df['Status'] = melted_df['Status'].replace({'': 'Not Submitted', 'nan': 'Not Submitted'})
        
        # TRUE MATRIX HEATMAP
        heatmap = alt.Chart(melted_df).mark_rect(stroke='white', strokeWidth=1).encode(
            x=alt.X('Month:N', sort=month_cols, title='Month', axis=alt.Axis(labelAngle=0)),
            y=alt.Y('Completer:N', title='Completer'),
            color=alt.Color(
                'Status:N',
                scale=alt.Scale(
                    domain=['100%', 'Late', 'Not Submitted', 'N/A'],
                    range=['#00e5ff', '#ffeb3b', '#ff5252', '#9e9e9e']
                ),
                title='Submission Status',
                legend=None 
            ),
            tooltip=['Completer', 'Section', 'Month', 'Status']
        ).properties(height=max(300, len(filtered_df['Completer'].unique()) * 25))
        
        st.altair_chart(heatmap, use_container_width=True)
    else:
        st.info("No monthly columns found in the current sheet format.")
