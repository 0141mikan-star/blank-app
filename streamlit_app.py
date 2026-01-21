import streamlit as st
import sqlite3
import pandas as pd
import random
import time

# ページ設定
st.set_page_config(page_title="褒めてくれるタスク管理", layout="centered")
st.title("✅ 褒めてくれるタスク管理アプリ")

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

# --- データベース関連の関数 ---
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def add_task(conn, task_name):
    c = conn.cursor()
    c.execute('INSERT INTO tasks (task_name, status) VALUES (?, ?)', (task_name, '未完了'))
    conn.commit()

def get_tasks(conn):
    return pd.read_sql('SELECT * FROM tasks ORDER BY created_at DESC', conn)

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
    # DB接続
    conn = init_db()

    # セッション状態の初期化（褒めるフラグ）
    if "celebrate" not in st.session_state:
        st.session_state["celebrate"] = False

    # 画面リロード直後に褒める処理
    if st.session_state["celebrate"]:
        st.balloons()  # 風船を飛ばす
        msg = random.choice(PRAISE_MESSAGES)
        st.toast(msg, icon="🎉") # 右下にメッセージを表示
        st.session_state["celebrate"] = False # フラグを戻す

    # サイドバー：新規タスク追加
    st.sidebar.header("タスクを追加")
    new_task = st.sidebar.text_input("やることを入力", key="new_task_input")
    if st.sidebar.button("追加"):
        if new_task:
            add_task(conn, new_task)
            st.toast(f"「{new_task}」を追加しました！頑張りましょう！", icon="🔥")
            time.sleep(1) # メッセージを少し見せる
            st.rerun()
        else:
            st.sidebar.warning("タスク名を入力してください")

    # メインエリア：タスク一覧表示
    st.subheader("現在のタスク一覧")
    
    df = get_tasks(conn)

    if df.empty:
        st.info("タスクはまだありません。サイドバーから追加してください。")
    else:
        for index, row in df.iterrows():
            col1, col2, col3 = st.columns([0.1, 0.7, 0.2])
            
            is_done = row['status'] == '完了'
            
            with col1:
                # チェックボックスの状態が変わったらDBを更新
                # keyにIDを含めて一意にする
                checked = st.checkbox("", value=is_done, key=f"check_{row['id']}")
                
                if checked != is_done:
                    update_status(conn, row['id'], checked)
                    # 未完了 → 完了 になった時だけ褒めるフラグを立てる
                    if checked:
                        st.session_state["celebrate"] = True
                    st.rerun()

            with col2:
                if is_done:
                    st.markdown(f"~~{row['task_name']}~~")
                else:
                    st.markdown(f"{row['task_name']}")

            with col3:
                if st.button("削除", key=f"del_{row['id']}"):
                    delete_task(conn, row['id'])
                    st.rerun()

    conn.close()

if __name__ == "__main__":
    main()
