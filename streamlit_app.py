import streamlit as st
import sqlite3
import pandas as pd
import random
import time
from datetime import datetime, date, timedelta
import urllib.parse

# ページ設定
st.set_page_config(page_title="実用版タスク管理", layout="centered")
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

# --- Googleカレンダー連携用関数 ---
def generate_google_calendar_link(task_name, due_date_str):
    """Googleカレンダー登録用のURLを生成する"""
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    
    # タイトルをURLエンコード
    text = urllib.parse.quote(task_name)
    
    # 日付を変換 (YYYY-MM-DD -> YYYYMMDD)
    # 終日イベントにするため、開始日はそのまま、終了日は+1日する
    start_date = datetime.strptime(due_date_str, '%Y-%m-%d')
    end_date = start_date + timedelta(days=1)
    
    dates = f"{start_date.strftime('%Y%m%d')}/{end_date.strftime('%Y%m%d')}"
    
    # 詳細（メモ）
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
    # 列追加のマイグレーション処理（念のため）
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

    # セッション状態（褒める用）
    if "celebrate" not in st.session_state:
        st.session_state["celebrate"] = False

    if st.session_state["celebrate"]:
        st.balloons()
        st.toast(random.choice(PRAISE_MESSAGES), icon="🎉")
        st.session_state["celebrate"] = False

    # --- サイドバー ---
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

    # --- メイン表示 ---
    df = get_tasks(conn)
    
    # 進捗バー
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
                # カラム構成を変更：リンク用のスペースを追加
                # col1:チェック, col2:タスク名, col3:期限, col4:優先度, col5:カレンダー, col6:削除
                col1, col2, col3, col4, col5, col6 = st.columns([0.1, 0.35, 0.15, 0.1, 0.15, 0.15])
                
                is_done = row['status'] == '完了'
                
                # 1. チェックボックス
                with col1:
                    checked = st.checkbox("", value=is_done, key=f"chk_{row['id']}")
                    if checked != is_done:
                        update_status(conn, row['id'], checked)
                        if checked: st.session_state["celebrate"] = True
                        st.rerun()

                # 2. タスク名
                with col2:
                    if is_done:
                        st.markdown(f"~~{row['task_name']}~~")
                    else:
                        st.markdown(f"**{row['task_name']}**")

                # 3. 期限日
                with col3:
                    if not is_done:
                        due = datetime.strptime(row['due_date'], '%Y-%m-%d').date()
                        if due < date.today():
                            st.markdown(f":red[⚠️ {row['due_date']}]")
                        elif due == date.today():
                            st.markdown(f":orange[今日]")
                        else:
                            st.markdown(f"{row['due_date']}")
                    else:
                        st.markdown("-")

                # 4. 優先度
                with col4:
                    p = row['priority']
                    color = "red" if p == "高" else "blue" if p == "中" else "grey"
                    st.markdown(f":{color}[{p}]")

                # 5. Googleカレンダー登録リンク (NEW!)
                with col5:
                    if not is_done:
                        cal_url = generate_google_calendar_link(row['task_name'], row['due_date'])
                        # リンクをボタンのように見せるHTML
                        st.markdown(f'''
                            <a href="{cal_url}" target="_blank" style="text-decoration:none;">
                                <button style="background-color:white; border:1px solid #ddd; border-radius:4px; padding:2px 8px; font-size:12px; cursor:pointer;">
                                📅 登録
                                </button>
                            </a>
                            ''', unsafe_allow_html=True)

                # 6. 削除ボタン
                with col6:
                    if st.button("🗑️", key=f"del_{row['id']}"):
                        delete_task(conn, row['id'])
                        st.rerun()
                
                st.markdown("---")

    conn.close()

if __name__ == "__main__":
    main()
