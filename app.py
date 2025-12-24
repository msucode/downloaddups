import streamlit as st
import pandas as pd
from utils import convert_to_csv_url, build_yearly_index, get_block_key
from matcher import find_best_match
import config

st.title("Patient Duplicate Finder")

yearly_url = st.text_input("Yearly Database Sheet URL")
daily_url = st.text_input("Today's Linelist URL")

if st.button("Load Sheets"):
    if yearly_url and daily_url:
        try:
            df_yearly = pd.read_csv(convert_to_csv_url(yearly_url))
            df_daily = pd.read_csv(convert_to_csv_url(daily_url))
            
            st.session_state['df_yearly'] = df_yearly
            st.session_state['df_daily'] = df_daily
            
            st.success(f"✅ {len(df_yearly)} yearly, {len(df_daily)} daily")
            st.write("**Columns:**", list(df_daily.columns[:15]))
        except Exception as e:
            st.error(f"❌ {e}")

if 'df_yearly' in st.session_state:
    cols = list(st.session_state['df_daily'].columns)
    
    st.subheader("Select Columns")
    col1, col2 = st.columns(2)
    
    with col1:
        name_col = st.selectbox("Column 1 (Name)", cols, key='col1')
        mobile_col = st.selectbox("Column 2 (Mobile)", cols, key='col2')
    
    with col2:
        addr_col = st.selectbox("Column 3 (Address)", cols, key='col3')
        extra_col = st.selectbox("Column 4 (Extra)", cols, key='col4')
    
    duplicate_threshold = st.slider("Duplicate Threshold", 60, 100, config.DEFAULT_DUPLICATE_THRESHOLD)
    
    if st.button("🔍 Find Duplicates"):
        df_yearly = st.session_state['df_yearly']
        df_daily = st.session_state['df_daily']
        
        st.info("Building index...")
        yearly_blocks = build_yearly_index(df_yearly, mobile_col)
        
        st.info("Comparing...")
        
        duplicate_ids = set()
        all_results = []
        
        for i, daily_row in df_daily.iterrows():
            block_key = get_block_key(daily_row[mobile_col])
            candidates = yearly_blocks.get(block_key, [])
            
            best_match = find_best_match(daily_row, candidates, name_col, mobile_col, addr_col, extra_col)
            
            if best_match and best_match['score'] >= duplicate_threshold:
                duplicate_ids.add(i)
                status = "DUPLICATE"
            else:
                status = "NEW"
            
            if best_match:
                result = {
                    'Daily_Rec': i+1,
                    'Status': status,
                    'Match_Type': best_match['match_type'],
                    'Score': best_match['score'],
                    'Daily_Col1': daily_row[name_col],
                    'Yearly_Col1': best_match['yearly_row'][name_col],
                    'Daily_Col2': daily_row[mobile_col],
                    'Yearly_Col2': best_match['yearly_row'][mobile_col],
                }
                
                if best_match['is_exact']:
                    result.update({
                        'Col1': '✅',
                        'Col2': '✅' if best_match['mobile_match'] else '❌',
                        'Col3': '✅' if best_match['addr_match'] else '❌',
                        'Col4': '✅' if best_match['extra_match'] else '❌'
                    })
                else:
                    result.update({
                        'Col1%': f"{int(best_match['col1_pct'])}%",
                        'Col2': '✅' if best_match['col2_match'] else '❌',
                        'Col3%': f"{int(best_match['col3_pct'])}%",
                        'Col4%': f"{int(best_match['col4_pct'])}%"
                    })
                
                all_results.append(result)
        
        # Split files
        df_duplicates = df_daily[df_daily.index.isin(duplicate_ids)]
        df_new = df_daily[~df_daily.index.isin(duplicate_ids)]
        
        st.success(f"✅ {len(df_duplicates)} DUPLICATES | {len(df_new)} NEW")
        
        if all_results:
            df_results = pd.DataFrame(all_results)
            st.dataframe(df_results, use_container_width=True)
            st.download_button("📥 Full Report", df_results.to_csv(index=False), "report.csv")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.metric("Duplicates", len(df_duplicates))
            if len(df_duplicates) > 0:
                st.download_button("📥 Duplicates", df_duplicates.to_csv(index=False), "duplicates.csv")
        
        with col_b:
            st.metric("New Records", len(df_new))
            if len(df_new) > 0:
                st.download_button("📥 New Records", df_new.to_csv(index=False), "new_records.csv")
