import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

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
    # We identify real data rows by ensuring 'Completer' or 'Section' isn't null
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

# Define columns we want to filter by
filter_columns = ['Examiner', 'Div', 'Dept', 'Section', 'Completer', 'Due Date']

st.sidebar.header("Navigation")

# Clean the 'Div' column to ensure colors map correctly (removes '.0' if pandas read it as a decimal)
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

# 3. GRAPHS
st.subheader("Performance Overview")
if 'Completer' in filtered_df.columns and 'Total Points Possible' in filtered_df.columns:
    # Group data for the chart, drop empty completers
    chart_data = filtered_df[filtered_df['Completer'] != ""].groupby('Completer')['Total Points Possible'].sum().reset_index()
    # Display a native Streamlit bar chart
    st.bar_chart(data=chart_data, x='Completer', y='Total Points Possible', use_container_width=True)

# 4. CUSTOM COLORS & DATA DISPLAY
def color_rows(row):
    # Ensure strict matching by converting to string and dropping any rogue decimals
    div = str(row.get('Div', '')).strip().replace('.0', '')
    
    if div == '7':
        return ['background-color: #e3f2fd; color: black'] * len(row) # Light Blue
    elif div == '1':
        return ['background-color: #fff8e1; color: black'] * len(row) # Light Yellow
    elif div == '2':
        return ['background-color: #f3e5f5; color: black'] * len(row) # Light Purple
    
    return [''] * len(row)

st.subheader("Tracker Data")

# Apply the style and strict 2-decimal formatting to the dataframe
styled_df = filtered_df.style.apply(color_rows, axis=1).format(precision=2, na_rep="")
st.dataframe(styled_df, use_container_width=True, hide_index=True)
