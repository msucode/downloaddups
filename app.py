import streamlit as st
import pandas as pd
from datetime import datetime
from utils import convert_to_csv_url, build_yearly_index, get_block_key
from matcher import find_best_match
import config
import base64

st.title("Patient Duplicate Finder")

yearly_url = st.text_input("Yearly Database Sheet URL")
daily_url = st.text_input("Today's Linelist URL")

def create_download_link(df1, filename1, df2, filename2):
    """Create a single button that downloads both files"""
    csv1 = df1.to_csv(index=False)
    csv2 = df2.to_csv(index=False)
    
    b64_1 = base64.b64encode(csv1.encode()).decode()
    b64_2 = base64.b64encode(csv2.encode()).decode()
    
    html = f"""
    <script>
    function downloadBothFiles() {{
        // Download first file
        var link1 = document.createElement('a');
        link1.href = 'data:text/csv;base64,{b64_1}';
        link1.download = '{filename1}';
        link1.click();
        
        // Download second file after small delay
        setTimeout(function() {{
            var link2 = document.createElement('a');
            link2.href = 'data:text/csv;base64,{b64_2}';
            link2.download = '{filename2}';
            link2.click();
        }}, 500);
    }}
    </script>
    <button onclick="downloadBothFiles()" style="
        background-color: #4CAF50;
        border: none;
        color: white;
        padding: 15px 32px;
        text-align: center;
        font-size: 16px;
        cursor: pointer;
        border-radius: 8px;
        font-weight: bold;
    ">📥 Download Both Files</button>
    """
    return html

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
    
    if st.button("🔍 Find Duplicates"):
        df_yearly = st.session_state['df_yearly']
        df_daily = st.session_state['df_daily']
        
        st.info("Building index...")
        yearly_blocks = build_yearly_index(df_yearly, mobile_col)
        
        st.info("Comparing...")
        
        perfect_duplicate_ids = set()
        all_results = []
        
        for i, daily_row in df_daily.iterrows():
            block_key = get_block_key(daily_row[mobile_col])
            candidates = yearly_blocks.get(block_key, [])
            
            best_match = find_best_match(daily_row, candidates, name_col, mobile_col, addr_col, extra_col)
            
            if best_match and best_match['match_type'] == '🟢 PERFECT':
                perfect_duplicate_ids.add(i)
                status = "PERFECT DUPLICATE"
            else:
                status = "NEW/PARTIAL"
            
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
        
        df_perfect_duplicates = df_daily[df_daily.index.isin(perfect_duplicate_ids)]
        df_new_records = df_daily[~df_daily.index.isin(perfect_duplicate_ids)]
        
        st.success(f"✅ {len(df_perfect_duplicates)} PERFECT DUPLICATES | {len(df_new_records)} TO UPLOAD")
        
        if all_results:
            df_results = pd.DataFrame(all_results)
            
            perfect = df_results[df_results['Status'] == 'PERFECT DUPLICATE']
            others = df_results[df_results['Status'] == 'NEW/PARTIAL']
            
            if len(perfect) > 0:
                with st.expander(f"🟢 Perfect Duplicates - Skip These ({len(perfect)})"):
                    st.dataframe(perfect, use_container_width=True)
            
            if len(others) > 0:
                st.subheader(f"📋 To Upload - New & Partial Matches ({len(others)})")
                st.dataframe(others, use_container_width=True)
        
        # Generate filenames
        today = datetime.now()
        date_str = today.strftime("%d_%m_%Y")
        
        duplicates_filename = f"{date_str}_possibleDuplicate.csv"
        new_records_filename = f"{date_str}_DailyLinelist.csv"
        
        # Single button to download both files
        st.subheader("📂 Download Files")
        
        col_metrics = st.columns(2)
        with col_metrics[0]:
            st.metric("Perfect Duplicates", len(df_perfect_duplicates))
        with col_metrics[1]:
            st.metric("New Records", len(df_new_records))
        
        if len(df_perfect_duplicates) > 0 or len(df_new_records) > 0:
            st.markdown("---")
            download_html = create_download_link(
                df_perfect_duplicates, 
                duplicates_filename,
                df_new_records,
                new_records_filename
            )
            st.markdown(download_html, unsafe_allow_html=True)
            st.caption("⬆️ Click button above to download both files at once")
        else:
            st.info("No files to download")
