import io
import re
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
import plotly.express as px

# Optional: real drag & drop (Kanban-like)
try:
    from streamlit_sortables import sort_items  # pip: streamlit-sortables
    HAS_SORTABLES = True
except Exception:
    HAS_SORTABLES = False


# -----------------------------
# UI: Page setup + Arabic feel
# -----------------------------
st.set_page_config(page_title="🕋 نظام تسكين الحجاج (Game Mode)", page_icon="🕋", layout="wide")

st.markdown(
    """
<style>
/* RTL */
.main, .block-container { direction: rtl; }
h1,h2,h3,h4,p,li,div,label { text-align: right; }

/* Make it feel like a game */
.badge {
  display:inline-block;
  padding:0.2rem 0.6rem;
  border-radius:999px;
  font-size:0.85rem;
  border:1px solid rgba(0,0,0,0.08);
  margin-left: 0.35rem;
}
.badge-private { background: rgba(33, 150, 243, 0.12); }
.badge-sharedm { background: rgba(76, 175, 80, 0.12); }
.badge-sharedf { background: rgba(233, 30, 99, 0.12); }
.badge-family  { background: rgba(255, 152, 0, 0.12); }
.badge-warn    { background: rgba(255, 193, 7, 0.18); }
.badge-err     { background: rgba(244, 67, 54, 0.16); }

.small { font-size: 0.9rem; opacity: 0.9; }

hr { margin: 0.8rem 0; }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Data model
# -----------------------------
@dataclass
class Room:
    room_id: str
    room_no: int
    floor: int
    kind: str               # private | shared | family_shared
    capacity: int
    gender_rule: str        # Any | M | F
    family_rule: Optional[int] = None  # if dedicated to one family
    notes: str = ""

    def label_kind_ar(self) -> str:
        return {
            "private": "خاص",
            "shared": "جماعي",
            "family_shared": "عائلي-جماعي",
        }.get(self.kind, self.kind)

    def badge_class(self) -> str:
        if self.kind == "private":
            return "badge-private"
        if self.kind == "family_shared":
            return "badge-family"
        if self.kind == "shared" and self.gender_rule == "M":
            return "badge-sharedm"
        if self.kind == "shared" and self.gender_rule == "F":
            return "badge-sharedf"
        return "badge-warn"


# -----------------------------
# Helpers
# -----------------------------
def _norm_str(x) -> str:
    return str(x).strip() if x is not None else ""

def normalize_gender(val: str) -> str:
    v = _norm_str(val)
    if v in {"ذكر", "Male", "M", "m"}:
        return "M"
    if v in {"أنثى", "Female", "F", "f"}:
        return "F"
    # Try fuzzy
    if "ذكر" in v or "male" in v.lower():
        return "M"
    if "أنث" in v or "female" in v.lower():
        return "F"
    return "U"

def gender_ar(code: str) -> str:
    return {"M": "ذكر", "F": "أنثى", "U": "غير محدد"}.get(code, code)

def parse_room_request(val) -> Tuple[str, int]:
    """
    Returns (request_kind, capacity_hint)
    - request_kind: private/shared
    - capacity_hint: 2/3/4/5 (best guess)
    """
    v = _norm_str(val)
    # Arabic
    if "جماعي" in v or "مشترك" in v:
        return "shared", 0
    # English
    if v.lower() in {"shared", "group", "communal"}:
        return "shared", 0

    # numeric
    try:
        n = int(float(v))
        if n in (2, 3):
            return "private", n
        if n in (4, 5):
            return "shared", n
    except Exception:
        pass

    # default: shared(unknown)
    return "shared", 0

def guess_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Accept Arabic/English column names.
    Required final columns: PID, Name, Gender, FamilyID, ReqRaw
    """
    mapping = {}
    for col in df.columns:
        c = _norm_str(col)
        c_low = c.lower()
        if ("اسم" in c) or ("name" in c_low):
            mapping[col] = "Name"
        elif ("جنس" in c) or ("gender" in c_low):
            mapping[col] = "Gender"
        elif ("عائلة" in c) or ("family" in c_low) or ("مجموعة" in c) or ("group" in c_low):
            mapping[col] = "FamilyID"
        elif ("غرفة" in c) or ("room" in c_low) or ("سكن" in c) or ("type" in c_low):
            mapping[col] = "ReqRaw"

    df2 = df.rename(columns=mapping).copy()

    missing = [c for c in ["Name", "Gender", "FamilyID", "ReqRaw"] if c not in df2.columns]
    if missing:
        raise ValueError(f"الملف ناقص أعمدة أساسية: {missing}. الأعمدة المطلوبة: الاسم، الجنس، رقم العائلة، نوع الغرفة.")

    df2 = df2[["Name", "Gender", "FamilyID", "ReqRaw"]].copy()
    df2.insert(0, "PID", range(1, len(df2) + 1))

    df2["Name"] = df2["Name"].astype(str).str.strip()
    df2["Gender"] = df2["Gender"].apply(normalize_gender)
    df2["FamilyID"] = pd.to_numeric(df2["FamilyID"], errors="coerce").fillna(0).astype(int)
    df2["ReqKind"], df2["ReqCapHint"] = zip(*df2["ReqRaw"].apply(parse_room_request))

    return df2

def make_template_bytes() -> bytes:
    sample = pd.DataFrame(
        {
            "رقم العائلة": [101, 101, 102, 102, 103],
            "نوع الغرفة": ["2", "2", "جماعي", "جماعي", "3"],
            "الجنس": ["ذكر", "أنثى", "ذكر", "ذكر", "أنثى"],
            "الاسم الثلاثي": ["مثال: محمد أحمد", "مثال: فاطمة علي", "مثال: خالد يوسف", "مثال: عمر يوسف", "مثال: سناء مصطفى"],
        }
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        sample.to_excel(writer, index=False, sheet_name="Pilgrims")
    return buf.getvalue()

def new_room(room_no: int, floor: int, kind: str, capacity: int, gender_rule: str, family_rule: Optional[int]) -> Room:
    return Room(
        room_id=f"R{uuid.uuid4().hex[:8]}",
        room_no=room_no,
        floor=floor,
        kind=kind,
        capacity=capacity,
        gender_rule=gender_rule,
        family_rule=family_rule,
        notes="",
    )

def auto_allocate(
    pilgrims: pd.DataFrame,
    shared_capacity_for_remaining: int,
    start_room_no: int,
) -> Tuple[List[Room], Dict[int, Optional[str]]]:
    """
    Priority:
    1) Private rooms (2/3) - allow mixed genders ONLY inside same family (private).
    2) Family groups of size 4 or 5 (per gender subset) -> dedicated rooms 4/5.
    3) Remaining shared allocation by gender into chosen shared_capacity_for_remaining (4 or 5).
       Last room can be underfilled -> flagged "needs sharing".
    Returns rooms + assignment(PID -> room_id or None)
    """
    rooms: List[Room] = []
    assign: Dict[int, Optional[str]] = {int(pid): None for pid in pilgrims["PID"].tolist()}

    room_no = start_room_no
    floor = 1

    remaining = pilgrims.copy()

    # ---------- 1) PRIVATE ----------
    private_df = remaining[remaining["ReqKind"] == "private"].copy()
    # group by family + requested capacity
    for (fam_id, cap), g in private_df.groupby(["FamilyID", "ReqCapHint"], sort=True):
        pids = g["PID"].tolist()

        # chunk into rooms of size cap (even leftovers become a private room)
        idx = 0
        while idx < len(pids):
            chunk = pids[idx : idx + cap]
            idx += cap

            r = new_room(
                room_no=room_no,
                floor=floor,
                kind="private",
                capacity=int(cap),
                gender_rule="Any",
                family_rule=int(fam_id) if int(fam_id) != 0 else None,
            )
            rooms.append(r)
            for pid in chunk:
                assign[int(pid)] = r.room_id
            room_no += 1

    # remove allocated
    allocated_pids = {pid for pid, rid in assign.items() if rid is not None}
    remaining = remaining[~remaining["PID"].isin(list(allocated_pids))].copy()

    # ---------- 2) FAMILY SIZE 4/5 (shared) ----------
    # Work per family AND per gender subset, because shared must be single-gender.
    shared_df = remaining.copy()
    for (fam_id, gcode), g in shared_df.groupby(["FamilyID", "Gender"], sort=True):
        if int(fam_id) == 0:
            continue
        count = len(g)
        if count in (4, 5):
            cap = count
            r = new_room(
                room_no=room_no,
                floor=floor,
                kind="family_shared",
                capacity=cap,
                gender_rule=gcode,
                family_rule=int(fam_id),
            )
            rooms.append(r)
            for pid in g["PID"].tolist():
                assign[int(pid)] = r.room_id
            room_no += 1

    allocated_pids = {pid for pid, rid in assign.items() if rid is not None}
    remaining = pilgrims[~pilgrims["PID"].isin(list(allocated_pids))].copy()

    # ---------- 3) REMAINING SHARED ----------
    cap = int(shared_capacity_for_remaining)
    for gcode in ["M", "F", "U"]:
        pool = remaining[remaining["Gender"] == gcode].copy()
        if pool.empty:
            continue
        # keep families near each other
        pool = pool.sort_values(["FamilyID", "PID"])
        pids = pool["PID"].tolist()

        idx = 0
        while idx < len(pids):
            chunk = pids[idx : idx + cap]
            idx += cap

            r = new_room(
                room_no=room_no,
                floor=floor,
                kind="shared",
                capacity=cap,
                gender_rule=gcode if gcode in {"M", "F"} else "Any",
                family_rule=None,
            )
            if len(chunk) < cap:
                r.notes = "⚠️ غرفة غير مكتملة: سيتم استكمالها مع باقي الغروبات"
            rooms.append(r)
            for pid in chunk:
                assign[int(pid)] = r.room_id
            room_no += 1

    return rooms, assign

def room_occ(rooms: List[Room], assign: Dict[int, Optional[str]]) -> Dict[str, List[int]]:
    occ: Dict[str, List[int]] = {r.room_id: [] for r in rooms}
    for pid, rid in assign.items():
        if rid is None:
            continue
        if rid not in occ:
            occ[rid] = []
        occ[rid].append(pid)
    return occ

def validate_state(
    pilgrims: pd.DataFrame,
    rooms: List[Room],
    assign: Dict[int, Optional[str]],
    allow_mixed_private_same_family: bool = True,
) -> Tuple[List[str], List[str]]:
    """
    Returns (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    occ = room_occ(rooms, assign)
    rooms_by_id = {r.room_id: r for r in rooms}

    # unassigned
    unassigned = [pid for pid, rid in assign.items() if rid is None]
    if unassigned:
        errors.append(f"يوجد {len(unassigned)} حاج/ـة غير مسكنين بعد. يجب تسكين الجميع قبل التحميل.")

    # room checks
    for rid, pids in occ.items():
        r = rooms_by_id.get(rid)
        if not r:
            errors.append(f"يوجد تعيين إلى غرفة غير موجودة (RoomID={rid}).")
            continue

        if len(pids) > r.capacity:
            errors.append(f"الغرفة {r.room_no} (طابق {r.floor}) تجاوزت السعة: {len(pids)}/{r.capacity}.")
        if len(pids) < r.capacity:
            # for shared rooms, that's okay but warn
            if r.kind in {"shared", "family_shared"}:
                warnings.append(f"الغرفة {r.room_no} (طابق {r.floor}) غير مكتملة: {len(pids)}/{r.capacity}. {r.notes}".strip())

        gset = set(pilgrims.set_index("PID").loc[pids, "Gender"].tolist()) if pids else set()
        famset = set(pilgrims.set_index("PID").loc[pids, "FamilyID"].tolist()) if pids else set()

        # shared must be single gender (unless gender_rule Any for unknown)
        if r.kind in {"shared", "family_shared"}:
            if r.gender_rule in {"M", "F"} and (gset - {r.gender_rule}):
                errors.append(f"الغرفة {r.room_no} (جماعي) تحتوي جنساً مخالفاً لقاعدة الغرفة.")
            if r.kind == "family_shared":
                if r.family_rule is not None and (famset - {r.family_rule}):
                    errors.append(f"الغرفة {r.room_no} (عائلية) تحتوي أفراداً من عائلات مختلفة.")
        elif r.kind == "private":
            # private: allow mixed genders only if same family (as requested)
            if r.family_rule is not None and (famset - {r.family_rule}):
                errors.append(f"الغرفة {r.room_no} (خاص) مخصصة لعائلة {r.family_rule} لكن تحتوي عائلات أخرى.")
            if allow_mixed_private_same_family:
                if len(gset) > 1 and (len(famset) != 1 or (0 in famset)):
                    errors.append(f"الغرفة {r.room_no} (خاص) مختلطة الجنس لكنها ليست لعائلة واحدة واضحة.")
            else:
                if len(gset) > 1:
                    errors.append(f"الغرفة {r.room_no} (خاص) مختلطة الجنس (غير مسموح بالإعدادات الحالية).")

    # room numbers uniqueness
    nums = [(r.floor, r.room_no) for r in rooms]
    if len(nums) != len(set(nums)):
        errors.append("يوجد تكرار في (رقم الغرفة + الطابق). يجب أن تكون فريدة.")

    return errors, warnings

def pilgrim_card(pid: int, pilgrims: pd.DataFrame) -> str:
    row = pilgrims[pilgrims["PID"] == pid].iloc[0]
    fam = int(row["FamilyID"])
    g = gender_ar(row["Gender"])
    name = str(row["Name"])
    return f"{pid:04d} | {name} ({g}) | عائلة {fam}"

def parse_pid(card_text: str) -> int:
    # Format: "0001 | ..."
    m = re.match(r"^\s*(\d+)\s*\|", str(card_text))
    if not m:
        # fallback: take first digits
        m2 = re.match(r"^\s*(\d+)", str(card_text))
        if not m2:
            raise ValueError(f"لا أستطيع قراءة PID من البطاقة: {card_text}")
        return int(m2.group(1))
    return int(m.group(1))

def build_sortable_containers(
    pilgrims: pd.DataFrame,
    rooms: List[Room],
    assign: Dict[int, Optional[str]],
    page_rooms: List[Room],
) -> List[dict]:
    occ = room_occ(rooms, assign)

    # Unassigned
    unassigned_pids = [pid for pid, rid in assign.items() if rid is None]
    unassigned_items = [pilgrim_card(pid, pilgrims) for pid in unassigned_pids]

    containers = [{
        "header": f"🧩 غير مسكنون ({len(unassigned_items)})",
        "items": unassigned_items
    }]

    # Rooms (paged)
    for r in page_rooms:
        pids = occ.get(r.room_id, [])
        items = [pilgrim_card(pid, pilgrims) for pid in pids]
        header = f"🏠 {r.room_no} | ط{r.floor} | {r.label_kind_ar()} | {len(items)}/{r.capacity}"
        if r.gender_rule in {"M", "F"}:
            header += f" | {gender_ar(r.gender_rule)}"
        if r.kind == "private":
            header += " | خاص"
        if r.family_rule:
            header += f" | عائلة {r.family_rule}"
        if r.notes:
            header += " | ⚠️"
        # embed id for mapping stability
        header += f" | #{r.room_id}"
        containers.append({"header": header, "items": items})
    return containers

def apply_sortable_result(
    result: List[dict],
    rooms: List[Room],
    assign: Dict[int, Optional[str]],
):
    """
    Update assignment based on sortables output. We match room by room_id embedded in header.
    """
    # reset all to unassigned first
    for pid in list(assign.keys()):
        assign[pid] = None

    for container in result:
        header = container.get("header", "")
        items = container.get("items", []) or []
        # room_id at end: "| #Rxxxx"
        m = re.search(r"#(R[0-9a-fA-F]{8})", header)
        if not m:
            # unassigned container
            for it in items:
                pid = parse_pid(it)
                assign[pid] = None
            continue

        room_id = m.group(1)
        for it in items:
            pid = parse_pid(it)
            assign[pid] = room_id

def export_excel_bytes(
    pilgrims: pd.DataFrame,
    rooms: List[Room],
    assign: Dict[int, Optional[str]],
) -> bytes:
    rooms_by_id = {r.room_id: r for r in rooms}
    out = pilgrims.copy()
    out["RoomID"] = out["PID"].apply(lambda pid: assign.get(int(pid)))
    out["RoomNo"] = out["RoomID"].apply(lambda rid: rooms_by_id[rid].room_no if rid in rooms_by_id else None)
    out["Floor"] = out["RoomID"].apply(lambda rid: rooms_by_id[rid].floor if rid in rooms_by_id else None)
    out["FinalRoomKind"] = out["RoomID"].apply(lambda rid: rooms_by_id[rid].label_kind_ar() if rid in rooms_by_id else None)
    out["FinalCapacity"] = out["RoomID"].apply(lambda rid: rooms_by_id[rid].capacity if rid in rooms_by_id else None)
    out["FinalRoomNotes"] = out["RoomID"].apply(lambda rid: rooms_by_id[rid].notes if rid in rooms_by_id else None)

    # For humans: Arabic gender and request
    out["Gender_AR"] = out["Gender"].apply(gender_ar)
    out = out.rename(columns={"Name": "الاسم", "FamilyID": "رقم العائلة", "ReqRaw": "طلب الغرفة"})
    out = out[["PID", "الاسم", "Gender_AR", "رقم العائلة", "طلب الغرفة", "Floor", "RoomNo", "FinalRoomKind", "FinalCapacity", "FinalRoomNotes"]]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        out.to_excel(writer, index=False, sheet_name="Housing")
        # Also room summary
        occ = room_occ(rooms, assign)
        room_rows = []
        for r in rooms:
            pids = occ.get(r.room_id, [])
            room_rows.append({
                "Floor": r.floor,
                "RoomNo": r.room_no,
                "Kind": r.label_kind_ar(),
                "GenderRule": gender_ar(r.gender_rule) if r.gender_rule in {"M","F"} else "Any",
                "Capacity": r.capacity,
                "Occupancy": len(pids),
                "FamilyRule": r.family_rule if r.family_rule else "",
                "Notes": r.notes
            })
        pd.DataFrame(room_rows).sort_values(["Floor","RoomNo"]).to_excel(writer, index=False, sheet_name="Rooms")
    return buf.getvalue()

def renumber_rooms(rooms: List[Room], start_room_no: int, rooms_per_floor: int, start_floor: int):
    # Stable order: by current (floor, room_no, room_id)
    ordered = sorted(rooms, key=lambda r: (r.floor, r.room_no, r.room_id))
    for i, r in enumerate(ordered):
        r.floor = start_floor + (i // rooms_per_floor)
        r.room_no = start_room_no + i

def add_empty_room_ui(rooms: List[Room]):
    st.markdown("#### ➕ إضافة غرفة جديدة")
    c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2])
    with c1:
        kind = st.selectbox("النوع", ["خاص", "جماعي", "عائلي-جماعي"], index=1, key="new_kind")
    with c2:
        cap = st.selectbox("السعة", [2,3,4,5], index=2, key="new_cap")
    with c3:
        floor = st.number_input("الطابق", min_value=1, value=1, step=1, key="new_floor")
    with c4:
        gender = st.selectbox("قيد الجنس", ["ذكر", "أنثى", "Any"], index=2, key="new_gender")
    with c5:
        fam = st.number_input("قيد العائلة (اختياري)", min_value=0, value=0, step=1, key="new_fam")

    kind_map = {"خاص": "private", "جماعي": "shared", "عائلي-جماعي": "family_shared"}
    gender_map = {"ذكر": "M", "أنثى": "F", "Any": "Any"}

    if st.button("إضافة الغرفة", use_container_width=True):
        # find next room number
        max_no = max([r.room_no for r in rooms], default=100)
        r = new_room(
            room_no=max_no + 1,
            floor=int(floor),
            kind=kind_map[kind],
            capacity=int(cap),
            gender_rule=gender_map[gender],
            family_rule=int(fam) if int(fam) != 0 else None,
        )
        rooms.append(r)
        st.success("تمت إضافة غرفة جديدة ✅")
        st.session_state["_board_refresh"] = st.session_state.get("_board_refresh", 0) + 1


# -----------------------------
# Sidebar: Upload + settings
# -----------------------------
st.sidebar.title("⚙️ الإعدادات")
st.sidebar.markdown("**هدف التطبيق:** تسكين كامل + تعديل Drag & Drop + منع التصدير حتى خلو الأخطاء.")

with st.sidebar.expander("📥 نموذج Excel جاهز", expanded=True):
    st.download_button(
        "تحميل Template (Excel)",
        data=make_template_bytes(),
        file_name="hajj_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

uploaded = st.sidebar.file_uploader("ارفع ملف Excel/CSV", type=["xlsx", "csv"])

shared_capacity = st.sidebar.radio("سعة الغرف الجماعية لما تبقى", options=[5, 4], index=0, horizontal=True)
start_room_no = st.sidebar.number_input("رقم بداية الغرف", min_value=1, value=101, step=1)

allow_mixed_private_same_family = st.sidebar.toggle("السماح باختلاط الجنسين في الغرف الخاصة (لنفس العائلة فقط)", value=True)

st.sidebar.markdown("---")
st.sidebar.caption("✅ إذا لم يظهر لك Drag & Drop، تأكد أنك أضفت streamlit-sortables في requirements.txt.")


# -----------------------------
# Main: Guide
# -----------------------------
st.title("🕋 نظام تسكين الحجاج — وضع اللعبة (Game Mode)")
st.write("واجهة تفاعلية لتسكين الحجاج: **توزيع ذكي أولاً** ثم **تعديل Drag & Drop** مع **تحقق صارم** قبل التحميل.")

with st.expander("📘 دليل سريع (مهم جداً)", expanded=True):
    st.markdown(
        """
**الحقول المطلوبة في Excel (أي ترتيب):**
- **رقم العائلة** (FamilyID): رقم موحد لكل أفراد العائلة (اختياري لمن لا ينتمي لعائلة).
- **نوع الغرفة** (Room Type): 2 أو 3 (خاص) / أو "جماعي" / أو 4/5 (جماعي).
- **الجنس**: ذكر / أنثى.
- **الاسم**: الاسم الثلاثي.

**قواعد هذا النظام (حسب طلبك):**
1) **الأولوية للغرف الخاصة** (2 و 3).  
2) ثم **مجموعات نفس العائلة** التي عددها **4 أو 5** (ضمن نفس الجنس للجماعي).  
3) ثم توزيع الباقي في غرف جماعية **سعتها تختارها أنت بالبداية** (4 أو 5).  
4) لو بقيت غرفة جماعية **غير مكتملة** يظهر تنبيه: *"ستُستكمل مع باقي الغروبات"*.

**مهم:** لا يمكن تحميل النتيجة إذا بقي حاج غير مسكن أو يوجد خطأ سعة/جنس/تكرار غرف.
"""
    )


# -----------------------------
# State init
# -----------------------------
if "pilgrims" not in st.session_state:
    st.session_state.pilgrims = None
if "rooms" not in st.session_state:
    st.session_state.rooms = []
if "assign" not in st.session_state:
    st.session_state.assign = {}
if "_board_refresh" not in st.session_state:
    st.session_state._board_refresh = 0

# -----------------------------
# Load data
# -----------------------------
if uploaded:
    try:
        if uploaded.name.lower().endswith(".csv"):
            raw_df = pd.read_csv(uploaded)
        else:
            raw_df = pd.read_excel(uploaded)

        pilgrims = guess_columns(raw_df)
        st.session_state.pilgrims = pilgrims
        st.success(f"✅ تم تحميل البيانات: {len(pilgrims)} اسم/اسماء")
    except Exception as e:
        st.error(f"⚠️ خطأ في قراءة الملف: {e}")

if st.session_state.pilgrims is None:
    st.info("ارفع ملف Excel من الشريط الجانبي للبدء (أو استخدم Template).")
    st.stop()

pilgrims = st.session_state.pilgrims


# -----------------------------
# Auto allocation controls
# -----------------------------
cA, cB, cC = st.columns([1.2, 1.2, 1.2])
with cA:
    if st.button("🚀 توزيع ذكي (Auto-Allocate)", use_container_width=True):
        rooms, assign = auto_allocate(
            pilgrims=pilgrims,
            shared_capacity_for_remaining=int(shared_capacity),
            start_room_no=int(start_room_no),
        )
        st.session_state.rooms = rooms
        st.session_state.assign = assign
        st.session_state._board_refresh += 1
        st.success("تم التوزيع الذكي ✅ انتقل لوضع اللعبة للتعديل.")

with cB:
    if st.button("🧹 تصفير التسكين", use_container_width=True):
        st.session_state.rooms = []
        st.session_state.assign = {int(pid): None for pid in pilgrims["PID"].tolist()}
        st.session_state._board_refresh += 1
        st.warning("تم تصفير جميع الغرف والتعيينات.")

with cC:
    if st.button("🧠 إصلاح سريع (فتح غرف للزحمة)", use_container_width=True):
        rooms = st.session_state.rooms
        assign = st.session_state.assign
        occ = room_occ(rooms, assign)
        max_no = max([r.room_no for r in rooms], default=int(start_room_no))
        rooms_by_id = {r.room_id: r for r in rooms}
        for rid, pids in list(occ.items()):
            r = rooms_by_id.get(rid)
            if not r or len(pids) <= r.capacity:
                continue
            overflow = pids[r.capacity:]
            keep = pids[:r.capacity]
            for pid in keep:
                assign[pid] = rid
            max_no += 1
            nr = new_room(
                room_no=max_no,
                floor=r.floor,
                kind=r.kind,
                capacity=r.capacity,
                gender_rule=r.gender_rule,
                family_rule=r.family_rule,
            )
            nr.notes = "⚠️ غرفة أضيفت تلقائياً بسبب تجاوز السعة"
            rooms.append(nr)
            for pid in overflow:
                assign[pid] = nr.room_id
        st.session_state.rooms = rooms
        st.session_state.assign = assign
        st.session_state._board_refresh += 1
        st.success("تم الإصلاح السريع ✅")

if not st.session_state.assign:
    st.session_state.assign = {int(pid): None for pid in pilgrims["PID"].tolist()}

if not st.session_state.rooms:
    st.session_state.rooms = []


# -----------------------------
# Tabs
# -----------------------------
tab_game, tab_rooms, tab_dash, tab_export = st.tabs(["🎮 وضع اللعبة", "🏨 إدارة الغرف", "📊 لوحة الأرقام", "📥 التصدير"])

rooms: List[Room] = st.session_state.rooms
assign: Dict[int, Optional[str]] = st.session_state.assign

# -----------------------------
# Tab: Rooms management
# -----------------------------
with tab_rooms:
    st.subheader("🏨 إدارة الغرف (إضافة/حذف/ترقيم/طوابق)")
    add_empty_room_ui(rooms)

    st.markdown("---")
    st.markdown("#### 🔢 إعادة ترقيم الغرف وتوزيع الطوابق")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        rn_start = st.number_input("بداية الترقيم", min_value=1, value=int(start_room_no), step=1, key="rn_start")
    with cc2:
        per_floor = st.number_input("عدد الغرف لكل طابق", min_value=1, value=20, step=1, key="per_floor")
    with cc3:
        fl_start = st.number_input("رقم بداية الطابق", min_value=1, value=1, step=1, key="fl_start")

    if st.button("تطبيق الترقيم + الطوابق", use_container_width=True):
        renumber_rooms(rooms, start_room_no=int(rn_start), rooms_per_floor=int(per_floor), start_floor=int(fl_start))
        st.session_state.rooms = rooms
        st.session_state._board_refresh += 1
        st.success("تمت إعادة الترقيم ✅")

    st.markdown("---")
    st.markdown("#### 🗑️ حذف غرفة")
    if rooms:
        room_opts = {f"غرفة {r.room_no} | ط{r.floor} | {r.label_kind_ar()} | #{r.room_id}": r.room_id for r in rooms}
        sel = st.selectbox("اختر غرفة للحذف", list(room_opts.keys()))
        rid = room_opts[sel]
        occ = room_occ(rooms, assign).get(rid, [])
        if occ:
            st.warning(f"هذه الغرفة تحتوي {len(occ)} شخص. عند الحذف سيتم نقلهم إلى (غير مسكنون).")
        if st.button("حذف الغرفة الآن", type="primary"):
            for pid in occ:
                assign[pid] = None
            st.session_state.assign = assign
            st.session_state.rooms = [r for r in rooms if r.room_id != rid]
            st.session_state._board_refresh += 1
            st.success("تم حذف الغرفة ✅")

    st.markdown("---")
    st.markdown("#### ✏️ تعديل خصائص غرفة")
    if rooms:
        room_opts2 = {f"غرفة {r.room_no} | ط{r.floor} | #{r.room_id}": r.room_id for r in rooms}
        sel2 = st.selectbox("اختر غرفة للتعديل", list(room_opts2.keys()), key="edit_room_sel")
        rid2 = room_opts2[sel2]
        r = next(x for x in rooms if x.room_id == rid2)

        e1, e2, e3, e4, e5 = st.columns(5)
        with e1:
            r.room_no = st.number_input("رقم الغرفة", min_value=1, value=int(r.room_no), step=1, key="ed_no")
        with e2:
            r.floor = st.number_input("الطابق", min_value=1, value=int(r.floor), step=1, key="ed_floor")
        with e3:
            kind_ar = st.selectbox("النوع", ["خاص", "جماعي", "عائلي-جماعي"], index=["private","shared","family_shared"].index(r.kind), key="ed_kind")
        with e4:
            r.capacity = st.selectbox("السعة", [2,3,4,5], index=[2,3,4,5].index(int(r.capacity)), key="ed_cap")
        with e5:
            gr = st.selectbox("قيد الجنس", ["Any","ذكر","أنثى"], index={"Any":0,"M":1,"F":2}.get(r.gender_rule,0), key="ed_gr")

        r.kind = {"خاص":"private","جماعي":"shared","عائلي-جماعي":"family_shared"}[kind_ar]
        r.gender_rule = {"Any":"Any","ذكر":"M","أنثى":"F"}[gr]
        r.family_rule = st.number_input("قيد العائلة (0 = لا)", min_value=0, value=int(r.family_rule or 0), step=1, key="ed_fam") or None
        r.notes = st.text_input("ملاحظات", value=r.notes, key="ed_notes")

        st.session_state.rooms = rooms
        st.session_state._board_refresh += 1
        st.info("تم تحديث خصائص الغرفة (يتطبق فوراً).")


# -----------------------------
# Tab: Game mode
# -----------------------------
with tab_game:
    st.subheader("🎮 وضع اللعبة: اسحب وأفلت الأسماء داخل الغرف")
    if not HAS_SORTABLES:
        st.error("مكتبة Drag & Drop غير متاحة. أضف `streamlit-sortables` إلى requirements.txt.")
        st.stop()

    # Pagination to avoid too many columns
    st.markdown("<div class='small'>💡 لتجنب تزاحم الأعمدة، نعرض الغرف على صفحات.</div>", unsafe_allow_html=True)
    per_page = st.slider("عدد الغرف في الصفحة", min_value=4, max_value=12, value=8, step=1)
    total_pages = max(1, (len(rooms) + per_page - 1) // per_page)
    page = st.number_input("صفحة", min_value=1, max_value=total_pages, value=1, step=1)

    ordered_rooms = sorted(rooms, key=lambda r: (r.floor, r.room_no, r.room_id))
    start = (page - 1) * per_page
    end = start + per_page
    page_rooms = ordered_rooms[start:end]

    containers = build_sortable_containers(pilgrims, rooms, assign, page_rooms)

    custom_style = """
    .sortable-component { background: transparent; padding: 0; }
    .sortable-container { border: 1px solid rgba(0,0,0,0.08); border-radius: 12px; padding: 6px; min-width: 250px; }
    .sortable-container-header { font-weight: 700; border-radius: 10px; padding: 8px; background: rgba(0,0,0,0.03); }
    .sortable-item, .sortable-item:hover { border-radius: 10px; padding: 8px; font-weight: 600; }
    """

    result = sort_items(
        containers,
        multi_containers=True,
        direction="horizontal",
        custom_style=custom_style,
        key=f"board_{st.session_state._board_refresh}_{page}_{per_page}",
    )

    if result:
        apply_sortable_result(result, rooms, assign)
        st.session_state.assign = assign

    errors, warnings = validate_state(
        pilgrims=pilgrims,
        rooms=rooms,
        assign=assign,
        allow_mixed_private_same_family=allow_mixed_private_same_family,
    )

    st.markdown("---")
    if errors:
        st.markdown("<span class='badge badge-err'>🚫 أخطاء تمنع التحميل</span>", unsafe_allow_html=True)
        for e in errors:
            st.error(e)
    else:
        st.markdown("<span class='badge badge-private'>✅ جاهز للتصدير</span>", unsafe_allow_html=True)

    if warnings:
        st.markdown("<span class='badge badge-warn'>⚠️ تنبيهات</span>", unsafe_allow_html=True)
        for w in warnings[:10]:
            st.warning(w)
        if len(warnings) > 10:
            st.info(f"يوجد {len(warnings) - 10} تنبيهات إضافية...")

# -----------------------------
# Tab: Dashboard
# -----------------------------
with tab_dash:
    st.subheader("📊 لوحة الأرقام")
    occ = room_occ(rooms, assign)
    total = len(pilgrims)
    unassigned_n = sum(1 for pid, rid in assign.items() if rid is None)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("إجمالي الحجاج", total)
    c2.metric("غير مسكنون", unassigned_n)
    c3.metric("عدد الغرف", len(rooms))
    c4.metric("إجمالي المسكنين", total - unassigned_n)

    summary_rows = []
    for r in rooms:
        summary_rows.append({
            "النوع": r.label_kind_ar(),
            "السعة": r.capacity,
            "قيد الجنس": gender_ar(r.gender_rule) if r.gender_rule in {"M","F"} else "Any",
            "الإشغال": len(occ.get(r.room_id, [])),
            "الطابق": r.floor,
        })
    if summary_rows:
        s = pd.DataFrame(summary_rows)
        left, right = st.columns(2)
        with left:
            fig1 = px.pie(s, names="النوع", title="توزيع أنواع الغرف")
            st.plotly_chart(fig1, use_container_width=True)
        with right:
            fig2 = px.bar(
                s.groupby(["النوع","السعة"], as_index=False).size(),
                x="النوع",
                y="size",
                title="عدد الغرف حسب النوع والسعة",
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("#### 📋 ملخص الغرف")
        st.dataframe(s.sort_values(["الطابق","النوع","السعة"]), use_container_width=True, height=380)

# -----------------------------
# Tab: Export
# -----------------------------
with tab_export:
    st.subheader("📥 التصدير النهائي")

    errors, warnings = validate_state(
        pilgrims=pilgrims,
        rooms=rooms,
        assign=assign,
        allow_mixed_private_same_family=allow_mixed_private_same_family,
    )

    if errors:
        st.error("لا يمكن التصدير حتى يتم حل جميع الأخطاء في تبويب (وضع اللعبة).")
    else:
        st.success("✅ كل الحجاج مسكنون ولا توجد أخطاء تمنع التصدير.")

    xl = export_excel_bytes(pilgrims, rooms, assign) if not errors else None
    st.download_button(
        "⬇️ تحميل النتيجة النهائية (Excel)",
        data=xl if xl else b"",
        file_name="final_hajj_housing.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=bool(errors),
        use_container_width=True,
    )

    st.markdown("---")
    st.markdown("#### 📝 ملاحظات مهمة")
    st.write(
        "- إذا ظهرت غرف غير مكتملة في الجماعي: هذا طبيعي عند وجود باقي (مثل 6 رجال مع سعة 5). "
        "يمكنك ترك الغرفة غير مكتملة وسيظهر تنبيه أنها ستُستكمل مع باقي الغروبات، أو افتح غرفة جديدة وعدّل التوزيع."
    )
