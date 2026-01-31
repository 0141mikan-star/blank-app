import streamlit as st
from supabase import create_client, Client
import pandas as pd
import random
import time
from datetime import datetime, date, timedelta, timezone
import urllib.parse
import hashlib
import altair as alt
from streamlit_calendar import calendar

# ページ設定
st.set_page_config(page_title="褒めてくれる勉強時間・タスク管理アプリ", layout="wide")

# --- 日本時間 (JST) の定義 ---
JST = timezone(timedelta(hours=9))

# --- Supabase接続設定 ---
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

# --- セキュリティ・基本関数 ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def login_user(username, password):
    try:
        username = username.strip()
        response = supabase.table("users").select("password").eq("username", username).execute()
        if response.data:
            if check_hashes(password, response.data[0]["password"]):
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
            "xp": 0, "coins": 0, "unlocked_themes": "標準",
            "current_title": "見習い", "unlocked_titles": "見習い",
            "current_wallpaper": "草原", "unlocked_wallpapers": "草原",
            "custom_title_unlocked": False
        }
        supabase.table("users").insert(data).execute()
        return True
    except:
        return False

# --- デザイン適用関数 ---
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
        body, p, h1, h2, h3, h4, h5, h6, input, textarea, label, button, .stTooltip, .stExpander {{
            font-family: '{name}', {fallback} !important;
        }}
        </style>
        """, unsafe_allow_html=True)

def apply_wallpaper(wallpaper_name, bg_opacity=0.3):
    wallpapers = {
        "草原": "1472214103451-9374bd1c798e", "夕焼け": "1472120435266-53107fd0c44a",
        "夜空": "1462331940025-496dfbfc7564", "ダンジョン": "1518709268805-4e9042af9f23",
        "王宮": "1544939514-aa98d908bc47", "図書館": "1521587760476-6c12a4b040da",
        "サイバー": "1535295972055-1c762f4483e5"
    }
    bg_css = f"background-color: #1E1E1E;"
    if wallpaper_name in wallpapers:
        id = wallpapers[wallpaper_name]
        url = f"https://images.unsplash.com/photo-{id}?auto=format&fit=crop&w=1920&q=80"
        bg_css += f'background-image: linear-gradient(rgba(0,0,0,{bg_opacity}), rgba(0,0,0,{bg_opacity})), url("{url}"); background-attachment: fixed; background-size: cover;'
    
    st.markdown(f"""
    <style>
    .stApp {{ {bg_css} }}
    .stMarkdown, .stText, h1, h2, h3, p, span, div {{ color: #ffffff !important; text-shadow: 1px 1px 3px rgba(0,0,0,0.8); }}
    div[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stExpander"], div[data-testid="stForm"], .task-container-box, .ranking-card {{
        background-color: rgba(20, 20, 20, 0.9) !important; border-radius: 12px; padding: 15px; border: 1px solid rgba(255,255,255,0.3);
    }}
    button[data-baseweb="tab"] {{ background-color: rgba(20, 20, 20, 0.9) !important; color: white !important; }}
    button[aria-selected="true"] {{ background-color: #FF4B4B !important; }}
    label {{ color: #FFD700 !important; font-weight: bold; }}
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
        df['status_rank'] = df['status'].apply(lambda x: 1 if x == '未完了' else 2)
        df = df.sort_values(by=['status_rank', 'created_at'])
    return df

def add_task(username, name, date, prio):
    supabase.table("tasks").insert({"username": username, "task_name": name, "status": "未完了", "due_date": str(date), "priority": prio}).execute()

def complete_tasks_bulk(ids, username, amount):
    supabase.table("tasks").update({"status": "完了"}).in_("id", ids).execute()
    u = get_user_data(username)
    supabase.table("users").update({"xp": u['xp'] + amount, "coins": u['coins'] + amount}).eq("username", username).execute()

def delete_task(tid):
    supabase.table("tasks").delete().eq("id", tid).execute()

def add_study_log(username, subj, mins):
    date_str = datetime.now(JST).strftime('%Y-%m-%d')
    supabase.table("study_logs").insert({"username": username, "subject": subj, "duration_minutes": mins, "study_date": date_str}).execute()
    u = get_user_data(username)
    supabase.table("users").update({"xp": u['xp'] + mins, "coins": u['coins'] + mins}).eq("username", username).execute()

def delete_study_log(lid, username, mins):
    supabase.table("study_logs").delete().eq("id", lid).execute()
    u = get_user_data(username)
    supabase.table("users").update({"xp": max(0, u['xp'] - mins), "coins": max(0, u['coins'] - mins)}).eq("username", username).execute()

def get_study_logs(username):
    res = supabase.table("study_logs").select("*").eq("username", username).execute()
    df = pd.DataFrame(res.data)
    return df.sort_values('created_at', ascending=False) if not df.empty else df

# --- メイン処理 ---
def main():
    # 1. ログイン状態の管理のみ最初に初期化
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = ""

    # 2. 未ログイン時の画面
    if not st.session_state["logged_in"]:
        st.sidebar.title("🔐 ログイン")
        choice = st.sidebar.selectbox("メニュー", ["ログイン", "新規登録"])
        if choice == "ログイン":
            st.subheader("ログイン")
            u = st.text_input("ユーザー名")
            p = st.text_input("パスワード", type='password')
            if st.button("ログイン"):
                ok, msg = login_user(u, p)
                if ok:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = u.strip()
                    st.rerun()
                else: st.error(msg)
        else:
            st.subheader("新規登録")
            nu = st.text_input("ユーザー名 (ID)")
            np = st.text_input("パスワード", type='password')
            nn = st.text_input("ニックネーム")
            if st.button("登録"):
                if nu and np and nn:
                    if add_user(nu, np, nn): st.success("登録完了！ログインしてください。")
                    else: st.error("そのIDは使われています。")
                else: st.warning("全項目入力してください。")
        return

    # 3. ログイン後のみ、RPG機能用変数を初期化
    post_login_defaults = {
        "is_studying": False, "start_time": None, "current_subject": "",
        "celebrate": False, "toast_msg": None, "last_cal_event": None
    }
    for k, v in post_login_defaults.items():
        if k not in st.session_state: st.session_state[k] = v

    # 4. ユーザーデータ取得
    user = get_user_data(st.session_state["username"])
    if not user:
        st.session_state["logged_in"] = False
        st.rerun()

    # 5. 集中モード表示 (エラー回避のため .get() を使用)
    if st.session_state.get("is_studying", False):
        st.markdown(f"### 🔥 {st.session_state.get('current_subject', '勉強')} を勉強中...")
        elapsed = int(time.time() - st.session_state.get("start_time", time.time()))
        st.markdown(f'<div style="text-align:center; font-size:80px; font-weight:bold; color:#FF4B4B;">{elapsed//3600:02}:{(elapsed%3600)//60:02}:{elapsed%60:02}</div>', unsafe_allow_html=True)
        if st.button("⏹️ 終了して記録", type="primary", use_container_width=True):
            mins = max(1, elapsed // 60)
            add_study_log(user['username'], st.session_state["current_subject"], mins)
            st.session_state["is_studying"] = False
            st.session_state["celebrate"] = True
            st.session_state["toast_msg"] = f"{mins}分 完了！お疲れ様！"
            st.rerun()
        time.sleep(1)
        st.rerun()
        return

    # 6. 通常画面
    apply_font(user.get('unlocked_themes', '標準').split(',')[0])
    apply_wallpaper(user.get('current_wallpaper', '草原'))
    
    # ★エラー修正済み: .get()を使ってキーが存在しなくても落ちないようにする
    if st.session_state.get("celebrate", False):
        st.balloons()
        st.session_state["celebrate"] = False
    if st.session_state.get("toast_msg"):
        st.toast(st.session_state["toast_msg"], icon="🆙")
        st.session_state["toast_msg"] = None

    # サイドバー
    with st.sidebar:
        st.subheader(f"👤 {user['nickname']}")
        st.caption(f"👑 {user['current_title']}")
        if st.button("ログアウト"):
            st.session_state["logged_in"] = False
            st.rerun()
        st.divider()
        st.write("🔧 デザイン調整")
        bg_op = st.slider("壁紙の暗さ", 0.0, 1.0, 0.4)
        wall_list = user['unlocked_wallpapers'].split(',')
        new_wall = st.selectbox("壁紙変更", wall_list, index=wall_list.index(user['current_wallpaper']) if user['current_wallpaper'] in wall_list else 0)
        if new_wall != user['current_wallpaper']:
            supabase.table("users").update({"current_wallpaper": new_wall}).eq("username", user['username']).execute()
            st.rerun()

    # メインステータス
    level = (user['xp'] // 50) + 1
    st.write(f"**Lv.{level}** | XP: {user['xp']} | {user['coins']} 💰")
    st.progress(min(1.0, (user['xp'] % 50) / 50))
    st.divider()

    # タブ
    t1, t2, t3, t4 = st.tabs(["📝 ToDo", "⏱️ タイマー", "🏆 ランク", "🛒 ショップ"])
    
    with t1:
        tasks = get_tasks(user['username'])
        col_a, col_b = st.columns([0.6, 0.4])
        with col_a:
            with st.expander("➕ タスク追加"):
                with st.form("at"):
                    n = st.text_input("タスク名")
                    d = st.date_input("期限")
                    if st.form_submit_button("追加"):
                        add_task(user['username'], n, d, "中")
                        st.rerun()
            if not tasks.empty:
                for _, r in tasks[tasks['status']=='未完了'].iterrows():
                    c1, c2 = st.columns([0.8, 0.2])
                    if c1.button(f"✅ {r['task_name']} (10xp)", key=f"t_{r['id']}"):
                        complete_tasks_bulk([r['id']], user['username'], 10)
                        st.session_state["celebrate"] = True
                        st.rerun()
                    if c2.button("🗑️", key=f"d_{r['id']}"):
                        delete_task(r['id'])
                        st.rerun()
        with col_b:
            logs = get_study_logs(user['username'])
            # カレンダー (簡易版)
            events = [{"title": f"📝 {r['task_name']}", "start": r['due_date']} for _, r in tasks.iterrows()]
            calendar(events=events, options={"initialView": "dayGridMonth"}, key="cal")

    with t2:
        st.subheader("勉強タイマー")
        subj = st.text_input("何を勉強する？", key="timer_subj")
        if st.button("▶️ スタート", type="primary"):
            if subj:
                st.session_state["is_studying"] = True
                st.session_state["start_time"] = time.time()
                st.session_state["current_subject"] = subj
                st.rerun()
            else: st.warning("教科を入力してください")
        
        st.divider()
        st.write("📖 最近の記録")
        logs = get_study_logs(user['username'])
        if not logs.empty:
            for _, r in logs.head(5).iterrows():
                cc1, cc2 = st.columns([0.8, 0.2])
                cc1.write(f"{r['study_date']} | {r['subject']} ({r['duration_minutes']}分)")
                if cc2.button("🗑️", key=f"dl_{r['id']}"):
                    delete_study_log(r['id'], user['username'], r['duration_minutes'])
                    st.rerun()

    with t3:
        st.subheader("🏆 週間ランキング")
        start = (datetime.now(JST) - timedelta(days=7)).strftime('%Y-%m-%d')
        rank_data = supabase.table("study_logs").select("username, duration_minutes").gte("study_date", start).execute()
        if rank_data.data:
            df_r = pd.DataFrame(rank_data.data).groupby('username').sum().sort_values('duration_minutes', ascending=False)
            st.table(df_r)
        else: st.info("データがありません")

    with t4:
        st.subheader("🛒 ショップ")
        items = [("草原", 500), ("夕焼け", 800), ("夜空", 1000), ("ダンジョン", 1500)]
        for name, price in items:
            with st.container(border=True):
                st.write(f"🖼️ 壁紙: {name} ({price}💰)")
                if name in user['unlocked_wallpapers'].split(','):
                    st.button("✅ 所有済み", disabled=True, key=f"bought_{name}")
                else:
                    if st.button(f"購入", key=f"buy_{name}"):
                        if user['coins'] >= price:
                            new_list = user['unlocked_wallpapers'] + f",{name}"
                            supabase.table("users").update({"coins": user['coins'] - price, "unlocked_wallpapers": new_list}).eq("username", user['username']).execute()
                            st.rerun()
                        else: st.error("コイン不足")

if __name__ == "__main__":
    main()
