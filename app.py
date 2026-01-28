import streamlit as st
import pandas as pd
import plotly.express as px
import io

# --- إعدادات الصفحة ---
st.set_page_config(
    page_title="نظام تسكين الحجاج الذكي",
    page_icon="🕋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- تنسيق CSS للعربية ---
st.markdown("""
<style>
    .main { direction: rtl; }
    h1, h2, h3, p, div { text-align: right; font-family: 'Tajawal', sans-serif; }
    .stAlert { direction: rtl; text-align: right; }
    .stDataFrame { direction: rtl; }
    /* تحسين شكل القوائم المنسدلة */
    .streamlit-expanderHeader { font-weight: bold; font-size: 1.1em; color: #2c3e50; }
</style>
""", unsafe_allow_html=True)

# --- العنوان ---
st.title("🕋 نظام تسكين الحجاج وتوزيع الغرف الآلي")
st.markdown("**أداة ذكية لمساعدة المشرفين في توزيع الحجاج على الغرف مع مراعاة المحارم ونوع الغرف.**")

# --- الدليل التفاعلي (Interactive Guide) ---
with st.expander("📘 دليل الاستخدام والتعليمات (اضغط هنا قبل البدء)", expanded=True):
    st.markdown("""
    ### 🛠️ كيف تستخدم هذا النظام؟
    
    **الخطوة 1: تجهيز ملف الإكسل**
    لضمان عمل النظام بدقة 100%، يجب أن يحتوي ملفك على الأعمدة التالية:
    1.  **رقم العائلة (Family ID):** (هام جداً) ضع نفس الرقم لكل أفراد العائلة الواحدة (مثلاً الزوج وزوجته يأخذان رقم 10).
    2.  **نوع الغرفة (Room Type):** (2، 3، 4، 5) أو كلمة "جماعي".
    3.  **الجنس (Gender):** ذكر أو أنثى.
    4.  **الاسم الثلاثي (Full Name):** اسم الحاج.

    **الخطوة 2: رفع الملف**
    قم برفع الملف في الخانة المخصصة بالأسفل.
    
    **الخطوة 3: الحصول على النتائج**
    سيقوم النظام تلقائياً بتوزيع الغرف، وفصل النساء عن الرجال، مع محاولة وضع العائلات (التي تحمل نفس الرقم) في غرف متتابعة في القائمة.
    """)
    
    # --- ميزة: تحميل نموذج فارغ ---
    st.markdown("---")
    st.write("💡 **تسهيلاً عليك، يمكنك تحميل نموذج إكسل جاهز وتعبئته:**")
    
    # إنشاء ملف إكسل فارغ في الذاكرة
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        sample_data = pd.DataFrame({
            'رقم العائلة': [101, 101, 102, 102, 103],
            'نوع الغرفة': [2, 2, 'جماعي', 'جماعي', 3],
            'الجنس': ['ذكر', 'أنثى', 'ذكر', 'ذكر', 'أنثى'],
            'الاسم الثلاثي': ['مثال: محمد أحمد', 'مثال: فاطمة علي', 'مثال: خالد يوسف', 'مثال: عمر يوسف', 'مثال: سناء مصطفى']
        })
        sample_data.to_excel(writer, index=False, sheet_name='Sheet1')
        
    st.download_button(
        label="📥 اضغط لتحميل نموذج إكسل فارغ (Template)",
        data=buffer,
        file_name="نموذج_بيانات_الحجاج.xlsx",
        mime="application/vnd.ms-excel"
    )

st.markdown("---")

# --- واجهة التطبيق الرئيسية ---

uploaded_file = st.file_uploader("📂 قم برفع ملف بيانات الحجاج (Excel) هنا", type=['xlsx'])

# دالة مساعدة لتنظيف المدخلات
def clean_room_type(val):
    val = str(val).strip()
    if val in ['2', '2.0']: return 2
    if val in ['3', '3.0']: return 3
    if val in ['4', '4.0']: return 4
    if val in ['5', '5.0']: return 5
    return 4 # الافتراضي جماعي

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # تخمين أسماء الأعمدة (Mapping)
        col_mapping = {}
        for col in df.columns:
            if 'اسم' in col: col_mapping[col] = 'Name'
            elif 'جنس' in col: col_mapping[col] = 'Gender'
            elif 'غرفة' in col or 'سكن' in col or 'نوع' in col: col_mapping[col] = 'RoomType'
            elif 'عائلة' in col or 'رقم' in col or 'مجموعة' in col: col_mapping[col] = 'FamilyID'
        
        df.rename(columns=col_mapping, inplace=True)
        
        # التحقق من الأعمدة
        required_cols = ['Name', 'Gender', 'RoomType', 'FamilyID']
        if not all(col in df.columns for col in required_cols):
            st.error(f"⚠️ الملف غير مطابق! تأكد من وجود الأعمدة: {required_cols}")
            st.stop()

        # معالجة البيانات
        df['Capacity_Req'] = df['RoomType'].apply(clean_room_type)
        df['FamilyID'] = df['FamilyID'].fillna(9999) 
        
        # --- الخوارزمية ---
        # الفرز حسب الجنس -> نوع الغرفة -> رقم العائلة
        df_sorted = df.sort_values(by=['Gender', 'Capacity_Req', 'FamilyID'])
        
        rooms = []
        room_counter = 101 
        
        for gender in df_sorted['Gender'].unique():
            gender_df = df_sorted[df_sorted['Gender'] == gender]
            for cap in [2, 3, 4, 5]:
                subset = gender_df[gender_df['Capacity_Req'] == cap]
                queue = subset.to_dict('records')
                current_room = []
                
                while queue:
                    person = queue.pop(0)
                    current_room.append(person)
                    if len(current_room) == cap:
                        rooms.append({'Room': room_counter, 'Type': f'غرفة {cap}', 'Gender': gender, 'Occupants': current_room})
                        room_counter += 1
                        current_room = []
                
                if current_room: # البواقي
                     rooms.append({'Room': room_counter, 'Type': f'غرفة {cap} (تكملة)', 'Gender': gender, 'Occupants': current_room})
                     room_counter += 1

        # عرض النتائج
        final_data = []
        for r in rooms:
            names = " - ".join([p['Name'] for p in r['Occupants']])
            fam_ids = ", ".join([str(int(p['FamilyID'])) if p['FamilyID'] != 9999 else '-' for p in r['Occupants']])
            final_data.append({
                'رقم الغرفة': r['Room'], 'نوع الغرفة': r['Type'], 'جنس الغرفة': r['Gender'],
                'عدد الحجاج': len(r['Occupants']), 'أرقام العائلات': fam_ids, 'الأسماء': names
            })
        
        res_df = pd.DataFrame(final_data)
        
        st.success(f"✅ تمت عملية التسكين بنجاح! تم توزيع {len(df)} حاج وحاجة.")
        
        # لوحة القيادة
        c1, c2, c3 = st.columns(3)
        c1.metric("عدد الغرف الكلي", len(res_df))
        c2.metric("غرف الرجال", len(res_df[res_df['جنس الغرفة'].str.contains('ذكر')]))
        c3.metric("غرف النساء", len(res_df[res_df['جنس الغرفة'].str.contains('أنثى')]))
        
        # رسوم بيانية
        col_g1, col_g2 = st.columns(2)
        with col_g1:
             fig = px.pie(res_df, names='نوع الغرفة', title='توزيع أنواع الغرف')
             st.plotly_chart(fig, use_container_width=True)
        with col_g2:
             fig2 = px.bar(res_df, x='نوع الغرفة', color='جنس الغرفة', title='توزيع الجنس حسب نوع الغرفة')
             st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📋 جدول التسكين النهائي")
        st.dataframe(res_df, use_container_width=True)
        
        # تحميل النتيجة
        csv_buffer = io.BytesIO()
        res_df.to_excel(csv_buffer, index=False)
        st.download_button(
            label="📥 تحميل الكشف النهائي (Excel)",
            data=csv_buffer,
            file_name='Final_Housing_List.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة الملف: {e}")