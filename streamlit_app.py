import streamlit as st
import sqlite3
import pandas as pd
import random
import time
from datetime import datetime, date

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

# --- データベース関連 ---
def init_db():
    """DB接続とテーブル作成、古いDBの自動更新"""
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    # テーブル作成
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
    
    # ※以前のバージョンのDBを使っている場合のために、列が存在するか確認して追加する
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
    # 未完了を上に、その中で優先度が高い順（高>中>低）、期限が近い順に並べる
    # SQLで並べ替えを工夫
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

    # --- サイドバー（入力フォーム） ---
    st.sidebar.header("📝 新しいタスク")
    
    with st.sidebar.form("task_form", clear_on_submit=True):
        new_task = st.text_input("タスク名 (例: レポート提出)")
        
        col1, col2 = st.columns(2)
        with col1:
            task_date = st.date_input("期限日", value=date.today())
        with col2:
            task_priority = st.selectbox("優先度", ["高", "中", "低"], index=1)
            
        submitted = st.form_submit_button("追加する")
        
        if submitted:
            if new_task:
                add_task(conn, new_task, task_date, task_priority)
                st.toast(f"タスクを追加しました！期限: {task_date}", icon="📅")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("タスク名を入力してください")

    # --- メインエリア ---
    
    # データの取得
    df = get_tasks(conn)
    
    # 進捗状況の表示
    if not df.empty:
        total_tasks = len(df)
        completed_tasks = len(df[df['status'] == '完了'])
        progress = completed_tasks / total_tasks
        
        st.write(f"**進捗状況: {completed_tasks}/{total_tasks} 完了**")
        st.progress(progress)
    
    st.divider()

    # タスク一覧表示
    if df.empty:
        st.info("タスクはありません。サイドバーから追加しましょう！")
    else:
        for index, row in df.iterrows():
            # デザイン用の枠（コンテナ）
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([0.1, 0.4, 0.2, 0.15, 0.15])
                
                is_done = row['status'] == '完了'
                
                # チェックボックス
                with col1:
                    checked = st.checkbox("", value=is_done, key=f"check_{row['id']}")
                    if checked != is_done:
                        update_status(conn, row['id'], checked)
                        if checked: st.session_state["celebrate"] = True
                        st.rerun()

                # タスク名
                with col2:
                    if is_done:
                        st.markdown(f"~~{row['task_name']}~~")
                    else:
                        st.markdown(f"**{row['task_name']}**")

                # 期限日
                with col3:
                    if not is_done:
                        # 期限切れなら赤文字にする
                        due = datetime.strptime(row['due_date'], '%Y-%m-%d').date()
                        if due < date.today():
                            st.markdown(f":red[⚠️ {row['due_date']}]")
                        elif due == date.today():
                            st.markdown(f":orange[今日！ {row['due_date']}]")
                        else:
                            st.markdown(f"📅 {row['due_date']}")
                    else:
                        st.markdown("-")

                # 優先度バッジ
                with col4:
                    p = row['priority']
                    if p == "高":
                        st.markdown(":red[🔥 高]")
                    elif p == "中":
                        st.markdown(":blue[🔹 中]")
                    else:
                        st.markdown(":grey[☁️ 低]")

                # 削除ボタン
                with col5:
                    if st.button("🗑️", key=f"del_{row['id']}"):
                        delete_task(conn, row['id'])
                        st.rerun()
                
                st.markdown("---") # 区切り線

    conn.close()

if __name__ == "__main__":
    main()
