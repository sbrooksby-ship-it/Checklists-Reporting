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

# Clean the 'Div' column so the options are perfect
df['Div'] = df['Div'].fillna("").astype(str).str.strip()

# 1. INSTANT ONE-CLICK FILTER (Radio Buttons)
div_options = ["All"] + sorted([d for d in df['Div'].unique() if d and d.lower() != 'nan'])
selected_div = st.sidebar.radio("Quick Filter: Division", options=div_options)

# Apply the primary division filter
filtered_df = df.copy()
if selected_div != "All":
    filtered_df = filtered_df[filtered_df['Div'] == selected_div]

# 2. CASCADING SECONDARY FILTERS (Hidden in a clean expander)
with st.sidebar.expander("More Filters (Optional)"):
    # Notice how this only shows completers for the selected division!
    completer_options = sorted([c for c in filtered_df['Completer'].fillna("").astype(str).unique() if c and c.lower() != 'nan'])
    selected_completer = st.multiselect("Completer", options=completer_options)
    
    if selected_completer:
        filtered_df = filtered_df[filtered_df['Completer'].isin(selected_completer)]

# Top-level metrics based on the filtered data
st.subheader("Current View Metrics")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Total Sections/Tasks", value=len(filtered_df))
with col2:
    if '# of TM' in filtered_df.columns:
        tm_sum = pd.to_numeric(filtered_df['# of TM'], errors='coerce').sum()
        st.metric(label="Total TM", value=int(tm_sum))
with col3:
    if 'Total Points Possible' in filtered_df.columns:
        pts_sum = pd.to_numeric(filtered_df['Total Points Possible'], errors='coerce').sum()
        st.metric(label="Total Points Possible", value=int(pts_sum))

# 3. APPLYING CUSTOM COLORS
# This function applies background colors based on the Division number
def color_rows(row):
    div = str(row['Div']).strip()
    
    # Using soft pastel hex codes to match your original sheet
    # Adding 'color: black' ensures text is readable even if the user has Streamlit dark mode on
    if div == '7':
        return ['background-color: #e3f2fd; color: black'] * len(row) # Light Blue
    elif div == '1':
        return ['background-color: #fff8e1; color: black'] * len(row) # Light Yellow
    elif div == '2':
        return ['background-color: #f3e5f5; color: black'] * len(row) # Light Purple
    
    return [''] * len(row)

st.subheader("Tracker Data")

# Apply the style to the dataframe before displaying it
styled_df = filtered_df.style.apply(color_rows, axis=1)
st.dataframe(styled_df, use_container_width=True, hide_index=True)
