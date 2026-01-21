import streamlit as st
import sqlite3
import pandas as pd
import random
import time
from datetime import datetime, date, timedelta
import urllib.parse
from streamlit_calendar import calendar  # カレンダー用ライブラリ

# ページ設定
st.set_page_config(page_title="実用版タスク管理", layout="wide") # カレンダーが見やすいようにwideモードに変更
st.title("✅ 実用版・褒めてくれるタスク管理")

# 褒め言葉リスト
PRAISE_MESSAGES = [
    "素晴らしい！その調子です！🎉",
    "お疲れ様でした！偉い！✨",
    "タスク完了！すごいですね！🚀",
    "完璧です！また一つ片付きました！💪",
    "天才ですか？仕事が早い！😲",
    "着実に進んでいますね！偉業です！🏔️",
    "ナイスファイト！ゆっくり休んでください🍵"
]

# --- Googleカレンダー連携用 ---
def generate_google_calendar_link(task_name, due_date_str):
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    text = urllib.parse.quote(task_name)
    start_date = datetime.strptime(due_date_str, '%Y-%m-%d')
    end_date = start_date + timedelta(days=1)
    dates = f"{start_date.strftime('%Y%m%d')}/{end_date.strftime('%Y%m%d')}"
    details = urllib.parse.quote("Streamlitタスク管理アプリから追加")
    return f"{base_url}&text={text}&dates={dates}&details={details}"

# --- データベース関連 ---
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            status TEXT NOT NULL,
            due_date TEXT,
            priority TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        c.execute("SELECT due_date FROM tasks LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
        c.execute("ALTER TABLE tasks ADD COLUMN priority TEXT")
        conn.commit()
    conn.commit()
    return conn

def add_task(conn, task_name, due_date, priority):
    c = conn.cursor()
    c.execute('INSERT INTO tasks (task_name, status, due_date, priority) VALUES (?, ?, ?, ?)', 
              (task_name, '未完了', due_date, priority))
    conn.commit()

def get_tasks(conn):
    return pd.read_sql('''
        SELECT * FROM tasks 
        ORDER BY 
            CASE status WHEN '未完了' THEN 1 ELSE 2 END,
            CASE priority WHEN '高' THEN 1 WHEN '中' THEN 2 ELSE 3 END,
            due_date ASC
    ''', conn)

def update_status(conn, task_id, is_done):
    status = '完了' if is_done else '未完了'
    c = conn.cursor()
    c.execute('UPDATE tasks SET status = ? WHERE id = ?', (status, task_id))
    conn.commit()

def delete_task(conn, task_id):
    c = conn.cursor()
    c.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()

# --- メイン処理 ---
def main():
    conn = init_db()

    # 褒める処理
    if "celebrate" not in st.session_state:
        st.session_state["celebrate"] = False
    if st.session_state["celebrate"]:
        st.balloons()
        st.toast(random.choice(PRAISE_MESSAGES), icon="🎉")
        st.session_state["celebrate"] = False

    # サイドバー
    st.sidebar.header("📝 新しいタスク")
    with st.sidebar.form("task_form", clear_on_submit=True):
        new_task = st.text_input("タスク名")
        col1, col2 = st.columns(2)
        with col1:
            task_date = st.date_input("期限日", value=date.today())
        with col2:
            task_priority = st.selectbox("優先度", ["高", "中", "低"], index=1)
        
        if st.form_submit_button("追加する"):
            if new_task:
                add_task(conn, new_task, task_date, task_priority)
                st.toast(f"追加しました！", icon="📅")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("タスク名を入力してください")

    # データ取得
    df = get_tasks(conn)

    # --- タブで表示切り替え ---
    tab_list, tab_calendar = st.tabs(["📋 リスト一覧", "📅 カレンダー表示"])

    # === タブ1: リスト表示 ===
    with tab_list:
        if not df.empty:
            done = len(df[df['status'] == '完了'])
            total = len(df)
            st.write(f"**進捗状況: {done}/{total} 完了**")
            st.progress(done / total)
        
        st.divider()

        if df.empty:
            st.info("タスクはありません。")
        else:
            for index, row in df.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6 = st.columns([0.05, 0.35, 0.15, 0.1, 0.15, 0.1])
                    is_done = row['status'] == '完了'
                    
                    with col1:
                        checked = st.checkbox("", value=is_done, key=f"chk_{row['id']}")
                        if checked != is_done:
                            update_status(conn, row['id'], checked)
                            if checked: st.session_state["celebrate"] = True
                            st.rerun()
                    with col2:
                        st.markdown(f"~~{row['task_name']}~~" if is_done else f"**{row['task_name']}**")
                    with col3:
                        if not is_done:
                            due = datetime.strptime(row['due_date'], '%Y-%m-%d').date()
                            if due < date.today(): st.markdown(f":red[⚠️ {row['due_date']}]")
                            elif due == date.today(): st.markdown(f":orange[今日]")
                            else: st.markdown(f"{row['due_date']}")
                        else: st.markdown("-")
                    with col4:
                        p = row['priority']
                        color = "red" if p == "高" else "blue" if p == "中" else "grey"
                        st.markdown(f":{color}[{p}]")
                    with col5:
                        if not is_done:
                            cal_url = generate_google_calendar_link(row['task_name'], row['due_date'])
                            st.markdown(f'<a href="{cal_url}" target="_blank" style="text-decoration:none;"><button style="background-color:white; border:1px solid #ddd; border-radius:4px; font-size:12px; cursor:pointer;">📅 登録</button></a>', unsafe_allow_html=True)
                    with col6:
                        if st.button("🗑️", key=f"del_{row['id']}"):
                            delete_task(conn, row['id'])
                            st.rerun()
                    st.markdown("---")

    # === タブ2: カレンダー表示 ===
    with tab_calendar:
        if df.empty:
            st.info("タスクを追加するとここに表示されます。")
        else:
            # カレンダー用のデータ形式に変換
            events = []
            for index, row in df.iterrows():
                # 色の決定
                if row['status'] == '完了':
                    color = "#808080" # グレー
                elif row['priority'] == "高":
                    color = "#FF4B4B" # 赤
                elif row['priority'] == "中":
                    color = "#1C83E1" # 青
                else:
                    color = "#27C46D" # 緑

                events.append({
                    "title": row['task_name'],
                    "start": row['due_date'],
                    "backgroundColor": color,
                    "borderColor": color,
                })

            # カレンダーの設定
            calendar_options = {
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "dayGridMonth,timeGridWeek,timeGridDay"
                },
                "initialView": "dayGridMonth",
            }
            
            # カレンダー表示
            calendar(events=events, options=calendar_options)

    conn.close()

if __name__ == "__main__":
    main()
