import streamlit as st
from supabase import create_client
import pandas as pd
import random
import time
from datetime import datetime, date, timedelta, timezone
import hashlib
import altair as alt
from streamlit_calendar import calendar

# ページ設定
st.set_page_config(page_title="褒めてくれる勉強時間・タスク管理アプリ", layout="wide")

# --- 日本時間 (JST) ---
JST = timezone(timedelta(hours=9))

# --- Supabase接続 ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        return None

supabase = init_supabase()

if not supabase:
    st.error("Supabaseへの接続設定が見つかりません。")
    st.stop()

# --- セキュリティ ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def login_user(username, password):
    try:
        username = username.strip()
        res = supabase.table("users").select("password").eq("username", username).execute()
        if res.data and check_hashes(password, res.data[0]["password"]):
            return True, "成功"
        return False, "ユーザー名またはパスワードが違います"
    except Exception as e:
        return False, f"エラー: {e}"

def add_user(username, password, nickname):
    try:
        data = {
            "username": username.strip(),
            "password": make_hashes(password.strip()),
            "nickname": nickname.strip(),
            "xp": 0,
            "coins": 0,
            "unlocked_themes": "ピクセル風",
            "current_title": "見習い",
            "unlocked_titles": "見習い",
            "current_wallpaper": "草原",
            "unlocked_wallpapers": "草原",
            "custom_title_unlocked": False
        }
        supabase.table("users").insert(data).execute()
        return True
    except:
        return False

# --- デザイン ---
def apply_font(font_type):
    fonts = {
        "ピクセル風": ("DotGothic16", "sans-serif"),
        "手書き風": ("Yomogi", "cursive"),
        "ポップ": ("Hachi+Maru+Pop", "cursive"),
        "明朝体": ("Shippori+Mincho", "serif"),
        "筆文字": ("Yuji+Syuku", "serif")
    }
    if font_type in fonts:
        name, fallback = fonts[font_type]
        st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family={name}&display=swap');
        body, * {{
            font-family: '{name}', {fallback} !important;
        }}
        </style>
        """, unsafe_allow_html=True)

def apply_wallpaper(wallpaper_name, bg_opacity=0.3):
    wallpapers = {
        "草原": "1472214103451-9374bd1c798e",
        "夕焼け": "1472120435266-53107fd0c44a",
        "夜空": "1462331940025-496dfbfc7564",
        "ダンジョン": "1518709268805-4e9042af9f23",
        "王宮": "1544939514-aa98d908bc47",
        "図書館": "1521587760476-6c12a4b040da",
        "サイバー": "1535295972055-1c762f4483e5"
    }

    bg_css = "background-color:#1E1E1E;"
    if wallpaper_name in wallpapers:
        pid = wallpapers[wallpaper_name]
        url = f"https://images.unsplash.com/photo-{pid}?auto=format&fit=crop&w=1920&q=80"
        bg_css += f"""
        background-image:
        linear-gradient(rgba(0,0,0,{bg_opacity}), rgba(0,0,0,{bg_opacity})),
        url("{url}");
        background-size: cover;
        background-attachment: fixed;
        """

    st.markdown(f"""
    <style>
    .stApp {{{bg_css}}}
    * {{ color: white; }}
    </style>
    """, unsafe_allow_html=True)

# --- DB操作 ---
def get_user_data(username):
    res = supabase.table("users").select("*").eq("username", username).execute()
    return res.data[0] if res.data else None

def get_tasks(username):
    res = supabase.table("tasks").select("*").eq("username", username).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df["rank"] = df["status"].apply(lambda x: 0 if x == "未完了" else 1)
        df = df.sort_values(["rank", "created_at"])
    return df

def add_task(username, name, due, prio):
    supabase.table("tasks").insert({
        "username": username,
        "task_name": name,
        "status": "未完了",
        "due_date": str(due),
        "priority": prio
    }).execute()

def complete_tasks_bulk(ids, username, amount):
    supabase.table("tasks").update({"status": "完了"}).in_("id", ids).execute()
    u = get_user_data(username)
    supabase.table("users").update({
        "xp": u["xp"] + amount,
        "coins": u["coins"] + amount
    }).eq("username", username).execute()

def add_study_log(username, subj, mins):
    today = datetime.now(JST).strftime("%Y-%m-%d")
    supabase.table("study_logs").insert({
        "username": username,
        "subject": subj,
        "duration_minutes": mins,
        "study_date": today
    }).execute()
    u = get_user_data(username)
    supabase.table("users").update({
        "xp": u["xp"] + mins,
        "coins": u["coins"] + mins
    }).eq("username", username).execute()

# --- メイン ---
def main():

    # 🔒 session_state 完全初期化（最優先）
    for k, v in {
        "logged_in": False,
        "username": "",
        "is_studying": False,
        "celebrate": False,
        "toast_msg": None,
        "start_time": None,
        "current_subject": "",
        "last_cal_event": None
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # --- ログイン ---
    if not st.session_state.get("logged_in"):
        st.sidebar.title("🔐 ログイン")
        mode = st.sidebar.selectbox("メニュー", ["ログイン", "新規登録"])

        if mode == "ログイン":
            u = st.text_input("ユーザー名")
            p = st.text_input("パスワード", type="password")
            if st.button("ログイン"):
                ok, msg = login_user(u, p)
                if ok:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = u.strip()
                    st.rerun()
                else:
                    st.error(msg)
        else:
            nu = st.text_input("ユーザー名")
            np = st.text_input("パスワード", type="password")
            nn = st.text_input("ニックネーム")
            if st.button("登録"):
                if add_user(nu, np, nn):
                    st.success("登録完了！")
        return

    user = get_user_data(st.session_state["username"])
    if not user:
        st.session_state["logged_in"] = False
        st.rerun()

    # --- 集中モード ---
    if st.session_state.get("is_studying"):
        st.markdown(f"## 🔥 {st.session_state.get('current_subject')} 勉強中")
        elapsed = int(time.time() - st.session_state.get("start_time", time.time()))
        st.markdown(
            f"<h1 style='text-align:center'>{elapsed//60:02}:{elapsed%60:02}</h1>",
            unsafe_allow_html=True
        )
        if st.button("⏹ 終了"):
            mins = max(1, elapsed // 60)
            add_study_log(user["username"], st.session_state.get("current_subject"), mins)
            st.session_state["is_studying"] = False
            st.session_state["celebrate"] = True
            st.session_state["toast_msg"] = f"{mins}分お疲れ様！"
            st.rerun()
        time.sleep(1)
        st.rerun()
        return

    apply_font(user["unlocked_themes"].split(",")[0])
    apply_wallpaper(user["current_wallpaper"])

    if st.session_state.get("celebrate", False):
        st.balloons()
        st.session_state["celebrate"] = False

    if st.session_state.get("toast_msg"):
        st.toast(st.session_state["toast_msg"])
        st.session_state["toast_msg"] = None

    st.write(f"**Lv.{user['xp']//50 + 1}** | XP {user['xp']} | 💰{user['coins']}")
    st.progress((user["xp"] % 50) / 50)

    t1, t2 = st.tabs(["📝 ToDo", "⏱ タイマー"])

    with t1:
        tasks = get_tasks(user["username"])
        with st.form("add_task"):
            n = st.text_input("タスク名")
            d = st.date_input("期限")
            if st.form_submit_button("追加"):
                add_task(user["username"], n, d, "中")
                st.rerun()

        if not tasks.empty:
            for _, r in tasks[tasks["status"] == "未完了"].iterrows():
                if st.button(f"✅ {r['task_name']}"):
                    complete_tasks_bulk([r["id"]], user["username"], 10)
                    st.session_state["celebrate"] = True
                    st.rerun()

    with t2:
        subj = st.text_input("勉強内容")
        if st.button("▶ スタート"):
            if subj:
                st.session_state["is_studying"] = True
                st.session_state["start_time"] = time.time()
                st.session_state["current_subject"] = subj
                st.rerun()

if __name__ == "__main__":
    main()
