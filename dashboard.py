import streamlit as st
import sqlite3
import pandas as pd
import json
from openai import OpenAI
from streamlit_mic_recorder import speech_to_text

# --- ⭐ 关键修复：确保云端自动创建新账本 ⭐ ---
def init_db():
    conn = sqlite3.connect('ledger.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            customer_name TEXT,
            product_name TEXT,
            quantity INTEGER,
            amount REAL,
            type TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db() # 每次运行都先铺好底层的表格

# --- 1. 初始化 AI 核心引擎 ---
client = OpenAI(
    api_key="sk-3235185726a646259da210dc0351b9b2", 
    base_url="https://api.deepseek.com"
)

# --- 2. 网页基础排版设置 ---
st.set_page_config(page_title="二批老板管账系统", layout="wide")
st.title("📊 二批市场 AI 管账看板 V3.1 (云端智享版)")
st.write("欢迎老板！点击麦克风直接说话，或者在下方打字，AI 会自动为您记账。")

# --- 3. 融合输入区：语音 + 文字 ---
col_voice, col_text = st.columns([1, 2]) 

with col_voice:
    st.info("🎤 语音记账 (点击下方开始/停止录音)")
    voice_text = speech_to_text(language='zh-CN', just_once=True, key='speech_input', use_container_width=True)

with col_text:
    st.info("⌨️ 文字记账")
    text_input = st.chat_input("或在这里打字：刚刚王大妈拿了10箱水...")

final_input = voice_text if voice_text else text_input

# --- 4. 开始算账逻辑 ---
if final_input:
    st.success(f"老板指令：【{final_input}】")
    
    with st.spinner('AI 助理正在拼命算账中...'):
        try:
            system_prompt = """
            你是一个极其专业的二批市场财务助理。
            请从老板的话中提取记账信息，并严格只输出 JSON 格式的数据。
            必须包含以下字段：
            - customer_name: 客户名字 (字符串)
            - product_name: 商品名字 (字符串)
            - quantity: 数量 (整数)
            - amount: 金额 (数字)
            - type: "收入" 或 "支出"
            """
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_input}
                ]
            )
            
            ai_reply = response.choices[0].message.content
            ai_reply = ai_reply.replace("```json", "").replace("```", "").strip()
            data = json.loads(ai_reply)
            
            conn = sqlite3.connect('ledger.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (date, customer_name, product_name, quantity, amount, type)
                VALUES (datetime('now', 'localtime'), ?, ?, ?, ?, ?)
            ''', (data['customer_name'], data['product_name'], data['quantity'], data['amount'], data['type']))
            conn.commit()
            conn.close()
            
            st.success(f"✅ 记账成功！已将【{data['customer_name']}】的账单存入数据库。刷新网页即可查看最新图表。")
            
        except Exception as e:
            st.error(f"❌ 记账失败，请检查网络或说得更清楚些。错误：{e}")

st.markdown("---") 

# --- 5. 数据大屏与可视化展示 ---
conn = sqlite3.connect('ledger.db')
df = pd.read_sql_query("SELECT * FROM transactions ORDER BY id DESC", conn) 
conn.close()

if not df.empty:
    st.subheader("📈 核心经营数据")
    total_income = df[df['type'] == '收入']['amount'].sum()
    total_orders = len(df)
    best_product = df.groupby('product_name')['quantity'].sum().idxmax()
    
    col1, col2, col3 = st.columns(3)
    col1.metric(label="💰 总营业额 (元)", value=f"¥ {total_income}")
    col2.metric(label="📦 总单数", value=f"{total_orders} 单")
    col3.metric(label="🔥 销量之王", value=best_product)

    col_chart, col_table = st.columns([1, 1]) 
    with col_chart:
        st.subheader("📊 各商品销售额对比")
        sales_by_product = df.groupby('product_name')['amount'].sum()
        st.bar_chart(sales_by_product)

    with col_table:
        st.subheader("📝 实时流水明细")
        st.dataframe(df, use_container_width=True)
        
    st.markdown("---")
    
    st.subheader("🤖 AI 财务总监深度诊断")
    if st.button("一键生成今日经营诊断报告"):
        with st.spinner('总监正在仔细审阅账本，请稍候...'):
            try:
                data_summary = df.to_json(orient="records", force_ascii=False)
                analysis_prompt = f"""
                你现在是一个拥有20年经验的二批市场财务总监。
                下面是你老板近期的经营流水账单数据（JSON格式）：
                {data_summary}
                
                请根据这些真实数据，给老板写一段简明扼要的经营诊断报告。
                要求：
                1. 语气要像一个专业的合伙人，称呼对方为“老板”。
                2. 明确指出哪个商品最赚钱，哪个客户贡献最大。
                3. 根据目前的数据，给老板提供一条务实建议。
                4. 语言必须是接地气的大白话。
                5. 字数控制在 200 字左右。
                """
                
                analysis_response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "user", "content": analysis_prompt}
                    ]
                )
                
                st.info(analysis_response.choices[0].message.content)
            except Exception as e:
                st.error(f"❌ 呼叫总监失败：{e}")
else:
    st.info("目前账本里还没有数据哦。")
