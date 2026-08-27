import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import altair as alt

# Page configuration
st.set_page_config(page_title="Division Tracker Dashboard", layout="wide")
st.title("Division Tracker Dashboard")

# Establish connection to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Fetch data with caching to optimize performance and respect API limits
@st.cache_data(ttl=600)
def load_data():
    # header=2 sets the 3rd row of the sheet as the dataframe columns (0-indexed)
    df = conn.read(header=2)
    
    # Drop completely blank rows or organizational banner rows (e.g., "Div 7")
    df = df.dropna(subset=['Completer'], how='all')
    
    # Forward-fill the 'Div' column in case of merged cells in the original sheet
    if 'Div' in df.columns:
        df['Div'] = df['Div'].ffill()
        
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"Error loading data. Check your secrets.toml URL. Details: {e}")
    st.stop()

st.sidebar.header("Navigation")

# Clean the 'Div' column to ensure colors map correctly (removes '.0' if read as a decimal)
df['Div'] = df['Div'].fillna("").astype(str).str.strip().str.replace('.0', '', regex=False)

# 1. QUICK DIVISION FILTER
div_options = ["All"] + sorted([d for d in df['Div'].unique() if d and d.lower() != 'nan'])
selected_div = st.sidebar.radio("Quick Filter: Division", options=div_options)

filtered_df = df.copy()
if selected_div != "All":
    filtered_df = filtered_df[filtered_df['Div'] == selected_div]

# 2. CASCADING SECONDARY FILTERS
with st.sidebar.expander("More Filters (Optional)"):
    # Examiner Filter
    if 'Examiner' in filtered_df.columns:
        examiner_options = sorted([e for e in filtered_df['Examiner'].fillna("").astype(str).unique() if e and e.lower() != 'nan'])
        selected_examiner = st.multiselect("Examiner", options=examiner_options)
        if selected_examiner:
            filtered_df = filtered_df[filtered_df['Examiner'].isin(selected_examiner)]
            
    # Department Filter (Checks for 'Dept' or 'Department')
    dept_col = 'Dept' if 'Dept' in filtered_df.columns else ('Department' if 'Department' in filtered_df.columns else None)
    if dept_col:
        dept_vals = filtered_df[dept_col].fillna("").astype(str).str.strip().str.replace('.0', '', regex=False)
        dept_options = sorted([d for d in dept_vals.unique() if d and d.lower() != 'nan'])
        selected_dept = st.multiselect("Department", options=dept_options)
        if selected_dept:
            filtered_df = filtered_df[filtered_df[dept_col].fillna("").astype(str).str.strip().str.replace('.0', '', regex=False).isin(selected_dept)]

    # Completer Filter
    if 'Completer' in filtered_df.columns:
        completer_options = sorted([c for c in filtered_df['Completer'].fillna("").astype(str).unique() if c and c.lower() != 'nan'])
        selected_completer = st.multiselect("Completer", options=completer_options)
        if selected_completer:
            filtered_df = filtered_df[filtered_df['Completer'].isin(selected_completer)]

    # Due Date Filter
    if 'Due Date' in filtered_df.columns:
        due_options = sorted([d for d in filtered_df['Due Date'].fillna("").astype(str).unique() if d and d.lower() != 'nan'])
        selected_due = st.multiselect("Due Date", options=due_options)
        if selected_due:
            filtered_df = filtered_df[filtered_df['Due Date'].isin(selected_due)]

# Force numeric columns to floats and round to the nearest 100th
for col in ['# of TM', '# of Points', 'Total Points Possible']:
    if col in filtered_df.columns:
        filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce').round(2)

# Top-level metrics
st.subheader("Current View Metrics")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Total Sections/Tasks", value=len(filtered_df))
with col2:
    if '# of TM' in filtered_df.columns:
        st.metric(label="Total TM", value=round(filtered_df['# of TM'].sum(), 2))
with col3:
    if 'Total Points Possible' in filtered_df.columns:
        st.metric(label="Total Points Possible", value=round(filtered_df['Total Points Possible'].sum(), 2))

# ---------------------------------------------------------
# COLOR MAP DEFINITIONS FOR DIVISIONS 1 THROUGH 7
# ---------------------------------------------------------

# Pastel colors for Table Backgrounds
TABLE_COLOR_MAP = {
    '1': '#fff8e1',  # Light Yellow
    '2': '#f3e5f5',  # Light Purple
    '3': '#e8f5e9',  # Light Green
    '4': '#fff3e0',  # Light Peach/Orange
    '5': '#fce4ec',  # Light Pink
    '6': '#e0f7fa',  # Light Cyan/Teal
    '7': '#e3f2fd',  # Light Blue
}

# Richer tones matching the same colors for the bar chart
CHART_COLOR_MAP = [
    '#fbc02d',  # Div 1 - Yellow
    '#ab47bc',  # Div 2 - Purple
    '#66bb6a',  # Div 3 - Green
    '#ffa726',  # Div 4 - Peach/Orange
    '#ec407a',  # Div 5 - Pink
    '#26c6da',  # Div 6 - Teal
    '#42a5f5',  # Div 7 - Blue
]

# 3. COLOR-CODED BAR CHART
st.subheader("Performance Overview")
if 'Completer' in filtered_df.columns and 'Total Points Possible' in filtered_df.columns:
    # Group data by Completer AND Division so bars are color-coded by Division
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
                color=alt.Color(
                    'Div:N',
                    scale=alt.Scale(domain=domain_divisions, range=CHART_COLOR_MAP),
                    title='Division'
                ),
                tooltip=['Completer', 'Div', 'Total Points Possible']
            )
            .properties(height=380)
        )
        
        st.altair_chart(chart, use_container_width=True)

# 4. DATA TABLE DISPLAY WITH MATCHING BACKGROUND COLORS
def color_rows(row):
    div = str(row.get('Div', '')).strip().replace('.0', '')
    bg_color = TABLE_COLOR_MAP.get(div, '')
    if bg_color:
        return [f'background-color: {bg_color}; color: black'] * len(row)
    return [''] * len(row)

st.subheader("Tracker Data")

styled_df = filtered_df.style.apply(color_rows, axis=1).format(precision=2, na_rep="")
st.dataframe(styled_df, use_container_width=True, hide_index=True)
