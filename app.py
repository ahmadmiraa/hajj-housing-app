import streamlit as st
import pandas as pd
import plotly.express as px
import io

# --- إعدادات الصفحة ---
st.set_page_config(page_title="نظام التسكين الذكي - إصدار المحترفين", layout="wide", page_icon="🕋")

# --- تنسيق CSS لجعل الواجهة تشبه اللعبة ---
st.markdown("""
<style>
    .room-card {
        border: 2px solid #ddd;
        border-radius: 10px;
        padding: 10px;
        margin: 5px;
        text-align: right;
        transition: 0.3s;
    }
    .room-private { background-color: #e3f2fd; border-color: #2196f3; }
    .room-shared-m { background-color: #e8f5e9; border-color: #4caf50; }
    .room-shared-f { background-color: #fce4ec; border-color: #e91e63; }
    .room-family-shared { background-color: #fff3e0; border-color: #ff9800; }
    
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

st.title("🕋 نظام التسكين الذكي (Logic Pro)")
st.markdown("**يدعم العائلات المختلطة في الخاص، وتجميع العائلات في الجماعي.**")

# --- 1. الدوال المساعدة ---
def clean_room_req(val):
    val = str(val).strip()
    if val in ['2', '2.0']: return 2
    if val in ['3', '3.0']: return 3
    if val in ['4', '4.0']: return 4
    if val in ['5', '5.0']: return 5
    return 4 # الافتراضي جماعي 4

# --- 2. التحميل ---
uploaded_file = st.file_uploader("ارفع ملف الإكسل (مع رقم العائلة)", type=['xlsx', 'csv'])

if uploaded_file:
    # قراءة الملف
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # توحيد الأعمدة
    col_mapping = {}
    for col in df.columns:
        if 'عائلة' in col or 'Family' in col: col_mapping[col] = 'FamilyID'
        elif 'نوع' in col or 'Type' in col: col_mapping[col] = 'RequestType'
        elif 'جنس' in col or 'Gender' in col: col_mapping[col] = 'Gender'
        elif 'اسم' in col or 'Name' in col: col_mapping[col] = 'Name'
    
    df.rename(columns=col_mapping, inplace=True)
    
    # تنظيف
    df['FamilyID'] = df['FamilyID'].fillna(0).astype(int)
    df['Capacity_Req'] = df['RequestType'].apply(clean_room_req)
    
    # إضافة أعمدة للمعالجة إذا لم تكن موجودة
    if 'Assigned_Room' not in df.columns:
        df['Assigned_Room'] = 0
    if 'Floor' not in df.columns:
        df['Floor'] = 1

    # --- 3. الخوارزمية الذكية (The Brain) ---
    if st.button("🚀 ابدأ التوزيع الذكي (Auto-Allocation)"):
        
        # قائمة الغرف النهائية
        rooms = []
        room_counter = 101
        
        # نسخة للعمل عليها
        work_df = df.copy()
        work_df['Is_Allocated'] = False
        
        # >> الاستراتيجية 1: الغرف الخاصة (أولوية قصوى - يسمح باختلاط العائلة) <<
        # نجمع حسب العائلة ونوع الطلب الخاص
        families = work_df[work_df['Capacity_Req'].isin([2, 3])].groupby(['FamilyID', 'Capacity_Req'])
        
        for (fam_id, cap), group in families:
            if fam_id == 0: continue # تخطي الأفراد بدون عائلة مؤقتاً
            
            # تحويل المجموعة لقائمة
            members = group.to_dict('records')
            
            # تقسيم العائلة إلى غرف (مثلاً عائلة 4 أشخاص طلبوا ثنائي -> غرفتين ثنائيتين)
            while members:
                chunk = members[:cap] # نأخذ عدد أشخاص يساوي سعة الغرفة
                members = members[cap:]
                
                # إنشاء الغرفة
                room_num = room_counter
                room_counter += 1
                
                # تحديث الجدول الرئيسي
                for p in chunk:
                    work_df.loc[work_df['Name'] == p['Name'], 'Is_Allocated'] = True
                    work_df.loc[work_df['Name'] == p['Name'], 'Assigned_Room'] = room_num
                    work_df.loc[work_df['Name'] == p['Name'], 'Room_Type_Final'] = f"خاصة {cap}"

        # >> الاستراتيجية 2: عائلات كاملة في الجماعي (تسكين معاً) <<
        # العائلات التي طلبت جماعي (4 أو 5)
        shared_families = work_df[(~work_df['Is_Allocated']) & (work_df['FamilyID'] != 0)].groupby('FamilyID')
        
        for fam_id, group in shared_families:
            members = group.to_dict('records')
            count = len(members)
            
            # إذا كان عدد العائلة 4 أو 5، نعطيهم غرفة خاصة بهم
            target_cap = 4 
            if count >= 5: target_cap = 5
            
            # هل يمكن وضعهم في غرفة وحدهم؟
            if count == 4 or count == 5:
                room_num = room_counter
                room_counter += 1
                for p in members:
                    work_df.loc[work_df['Name'] == p['Name'], 'Is_Allocated'] = True
                    work_df.loc[work_df['Name'] == p['Name'], 'Assigned_Room'] = room_num
                    work_df.loc[work_df['Name'] == p['Name'], 'Room_Type_Final'] = f"عائلية {count}"

        # >> الاستراتيجية 3: التسكين التقليدي (فصل الجنسين للبقية) <<
        remaining = work_df[~work_df['Is_Allocated']].sort_values(by=['Gender', 'FamilyID'])
        
        for gender in remaining['Gender'].unique():
            gender_pool = remaining[remaining['Gender'] == gender]
            
            # نبدأ بغرف رباعية افتراضياً للجماعي
            cap = 4 
            queue = gender_pool.to_dict('records')
            current_room = []
            
            while queue:
                person = queue.pop(0)
                current_room.append(person)
                
                if len(current_room) == cap:
                    room_num = room_counter
                    room_counter += 1
                    # حفظ البيانات
                    for p in current_room:
                        work_df.loc[work_df['Name'] == p['Name'], 'Is_Allocated'] = True
                        work_df.loc[work_df['Name'] == p['Name'], 'Assigned_Room'] = room_num
                        work_df.loc[work_df['Name'] == p['Name'], 'Room_Type_Final'] = f"جماعي {gender}"
                    current_room = []
            
            # البواقي
            if current_room:
                room_num = room_counter
                room_counter += 1
                for p in current_room:
                    work_df.loc[work_df['Name'] == p['Name'], 'Is_Allocated'] = True
                    work_df.loc[work_df['Name'] == p['Name'], 'Assigned_Room'] = room_num
                    work_df.loc[work_df['Name'] == p['Name'], 'Room_Type_Final'] = f"جماعي {gender}"

        st.session_state['df_allocated'] = work_df
        st.success("✅ تم توزيع الغرف بذكاء! يمكنك الآن التعديل يدوياً.")

    # --- 4. واجهة التعديل (Drag & Drop Simulation) ---
    if 'df_allocated' in st.session_state:
        editable_df = st.session_state['df_allocated']
        
        st.markdown("---")
        st.subheader("🕹️ لوحة التحكم والتعديل (Drag & Drop Mode)")
        st.info("قم بتغيير 'رقم الغرفة' أو 'الطابق' وسيقوم النظام فوراً بنقل الحاج وتحديث الشكل البصري.")

        # نستخدم Data Editor لأنه يدعم السحب والنسخ واللصق وهو الأسرع
        edited_df = st.data_editor(
            editable_df[['Name', 'Gender', 'FamilyID', 'Assigned_Room', 'Floor', 'Room_Type_Final']],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Assigned_Room": st.column_config.NumberColumn("رقم الغرفة", help="غير الرقم لنقل الشخص", step=1),
                "Floor": st.column_config.NumberColumn("الطابق", step=1),
                "Room_Type_Final": st.column_config.SelectboxColumn("نوع الغرفة", options=["خاصة 2", "خاصة 3", "جماعي ذكر", "جماعي أنثى", "عائلية"])
            }
        )
        
        # --- 5. العرض البصري (Game Map) ---
        st.markdown("### 🗺️ خريطة الفندق (Visual Map)")
        
        # تجميع البيانات للعرض
        rooms_view = edited_df.groupby(['Floor', 'Assigned_Room'])
        
        # فرز الطوابق
        floors = sorted(edited_df['Floor'].unique())
        
        for floor in floors:
            with st.expander(f"🏢 الطابق {floor}", expanded=True):
                # عرض الغرف كشبكة (Grid)
                floor_rooms = edited_df[edited_df['Floor'] == floor]['Assigned_Room'].unique()
                floor_rooms = sorted(floor_rooms)
                
                # تقسيم الغرف إلى صفوف (كل صف 4 غرف مثلاً)
                cols = st.columns(4)
                for i, room_num in enumerate(floor_rooms):
                    occupants = edited_df[(edited_df['Floor'] == floor) & (edited_df['Assigned_Room'] == room_num)]
                    count = len(occupants)
                    
                    # تحديد ستايل الغرفة بناءً على المحتوى
                    genders = occupants['Gender'].unique()
                    is_mixed = len(genders) > 1
                    is_family = occupants['FamilyID'].nunique() == 1 and occupants['FamilyID'].iloc[0] != 0
                    
                    css_class = "room-private"
                    if is_mixed: css_class = "room-family-shared"
                    elif 'ذكر' in genders: css_class = "room-shared-m"
                    elif 'أنثى' in genders: css_class = "room-shared-f"
                    
                    # محتوى البطاقة
                    with cols[i % 4]:
                        names_html = "".join([f"<li>{n} <small>({g})</small></li>" for n, g in zip(occupants['Name'], occupants['Gender'])])
                        st.markdown(f"""
                        <div class="room-card {css_class}">
                            <h4>🔑 غرفة {int(room_num)}</h4>
                            <p><b>العدد:</b> {count}</p>
                            <ul style="font-size:12px; padding-right:15px; margin-bottom:5px;">
                                {names_html}
                            </ul>
                        </div>
                        """, unsafe_allow_html=True)

        # زر التصدير النهائي
        st.markdown("---")
        final_csv = edited_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 تحميل التوزيع النهائي واعتماده", final_csv, "Final_Hajj_Plan.csv", "text/csv")
