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

st.sidebar.header("Navigation & Filters")
selected_filters = {}

# Generate multi-select widgets dynamically for each column
for col in filter_columns:
    if col in df.columns:
        # Safely fill missing values with blanks, then force the whole column to string type
        df[col] = df[col].fillna("").astype(str)
        
        # Now every value is guaranteed to be a string, so .strip() will never fail
        unique_values = sorted([val for val in df[col].unique() if val.strip() != '' and val.strip().lower() != 'nan'])
        
        selected_filters[col] = st.sidebar.multiselect(
            f"Filter by {col}", 
            options=unique_values
        )

# Apply selected filters to the dataframe
filtered_df = df.copy()
for col, selections in selected_filters.items():
    if selections:
        filtered_df = filtered_df[filtered_df[col].isin(selections)]

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

# Display the interactive dataframe
st.subheader("Tracker Data")
st.dataframe(filtered_df, use_container_width=True, hide_index=True)
