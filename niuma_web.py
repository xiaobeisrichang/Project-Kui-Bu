import streamlit as st
import requests
import os
import datetime
import re
import json

# niuma_web.py 头部
from config import STORY_PATH, GOLD_CASES_FILE, OLLAMA_URL, MODEL_NAME, TEAM_MEMBERS, BUSINESS_MODULES


# --- 2. 初始化 ---
if not os.path.exists(STORY_PATH): os.makedirs(STORY_PATH)
for folder in BUSINESS_MODULES.keys(): os.makedirs(os.path.join(STORY_PATH, folder), exist_ok=True)
if "current_user" not in st.session_state: st.session_state.current_user = TEAM_MEMBERS[0]


# --- 3. 工具函数 ---
def save_gold_case(query, answer):
    cases = []
    if os.path.exists(GOLD_CASES_FILE):
        with open(GOLD_CASES_FILE, 'r', encoding='utf-8') as f: cases = json.load(f)
    cases = [c for c in cases if c['query'] != query]
    cases.append({"query": query, "answer": answer, "update_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")})
    with open(GOLD_CASES_FILE, 'w', encoding='utf-8') as f: json.dump(cases, f, ensure_ascii=False, indent=2)
    st.toast("🎯 案例库已同步最新逻辑！")

def get_similar_gold_case(query):
    if not os.path.exists(GOLD_CASES_FILE): return None
    with open(GOLD_CASES_FILE, 'r', encoding='utf-8') as f: cases = json.load(f)
    for c in cases:
        if any(kw in c['query'] for kw in re.split(r'\s+', query) if len(kw) > 1): return c
    return None

def get_qwen_chat_response(messages):
    try:
        payload = {"model": MODEL_NAME, "messages": messages, "stream": True, "options": {"temperature": 0.0}}
        res = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=60)
        full_res = ""; container = st.empty()
        for line in res.iter_lines():
            if line:
                chunk = json.loads(line.decode('utf-8'))
                content = chunk.get('message', {}).get('content', '')
                full_res += content
                container.markdown(full_res + "▌")
        container.markdown(full_res); return full_res
    except Exception: return None

def smart_search(query):
    results = []
    keywords = [kw for kw in re.split(r'\s+', query) if kw]
    for root, dirs, files in os.walk(STORY_PATH):
        for file in files:
            if file.endswith(".md"):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if any(kw.lower() in content.lower() or kw.lower() in file.lower() for kw in keywords):
                        results.append({"path": path, "content": content})
    return results[:3]

# --- 4. 页面布局 ---
st.set_page_config(page_title="外挂牛马 V2.5 Pro", layout="wide", page_icon="🐴")

with st.sidebar:
    st.title("⚙️ 系统管理")
    st.session_state.current_user = st.selectbox("👤 用户：", TEAM_MEMBERS, index=TEAM_MEMBERS.index(st.session_state.current_user))
    st.divider()
    st.success(f"动力内核：{MODEL_NAME}")

st.title("🐴 外挂牛马 V2.5 Pro")
# ✅ 5个 Tab 安排上了！
tabs = st.tabs(["💬 业务咨询", "📥 规则录入", "🔍 知识库管理", "🏅 案例库管理", "📊 规则统计"])

# --- Tab 0: 业务咨询 ---
with tabs[0]:
    # 1. 核心持久化：保住答案不消失
    if "last_ans" not in st.session_state: st.session_state.last_ans = None
    if "last_query" not in st.session_state: st.session_state.last_query = None

    c_top1, c_top2 = st.columns([8, 2])
    u_input = c_top1.text_input("想问哪个业务逻辑？", 
                                value=st.session_state.last_query if st.session_state.last_query else "", 
                                key="q_input_box",
                                placeholder="输入关键词...")
    
    # 功能 3：刷新缓存
    if c_top2.button("♻️ 刷新缓存"):
        st.cache_data.clear()
        st.toast("✅ 缓存已清理")
        st.rerun()

    # 2. 查询逻辑块
    if st.button("开始查询", type="primary"):
        if u_input:
            with st.spinner("牛马翻找中..."):
                try:
                    # 获取所有搜索结果，不进行物理拦截
                    raw_res = smart_search(u_input)
                    if raw_res:
                        is_deep = any(k in u_input for k in ["底层", "深挖", "实现"])
                        processed_context = ""
                        for r in raw_res:
                            parts = r['content'].split("### 🔒 [底层细节")
                            content_block = parts[1] if is_deep and len(parts) > 1 else parts[0]
                            # 显式注入路径，AI 必须根据这个判断模块
                            processed_context += f"【当前文档物理路径：{r['path']}】\n{content_block}\n\n"
                        
                        gold_case = get_similar_gold_case(u_input)
                        gold_info = f"【过往标准参考】：\n{gold_case['answer']}\n\n" if gold_case else ""

                        # 样式死守 + 路由指令
                        sys_msg = f"""【绝对禁令：严禁输出任何开场白、结语、个人建议或无关背景。严禁输出除文档记录之外的对话。】

你是一个冷酷的逻辑提取器。

【0. 模块路由锁（最高优先级）】
- 默认检索：仅限“07_会员基础支持”模块。
- 显式切换：仅当问题含“全部”或明确其他模块名（如：离店、技术）时，才索引对应模块。

【1. 结论先行权重（极速路径）】
- 核心准则：优先锁定【过往标准参考】与【资料库】中最晚日期的一条记录。
- 默认输出：**仅输出那条最新、最优的规则结论。**
- 历史回溯触发：只有当用户明确要求“列出此前规则”、“查看明细”或“对比版本”时，才按照时间轴倒序罗列旧规则并归纳差异。

【2. 内容提取深度】
- 默认：仅提取“业务逻辑”中的【对外规则】。
- 深挖：仅当问题含“底层”、“深挖”、“实现”词汇时，才在输出【对外规则】后给底层细节。

【3. 冲突与隐藏】
- 冲突：仅在相同模块内不同文档对【当前最新规则】描述冲突时，才标注路径对比。
- 隐藏：严禁输出路径、文件名、录入人信息。

【4. 格式死令（严格按照文档记录）】
- 必须使用标准 Markdown 列表（-）。
- 核心逻辑词必须**加粗**。
- 脱敏星号必须包裹在反引号内，如 `441****2727`。"""

                        ans = get_qwen_chat_response([
                            {"role": "system", "content": sys_msg}, 
                            {"role": "user", "content": f"{gold_info}【资料库内容】：\n{processed_context}\n问题：{u_input}"}
                        ])
                        
                        if ans:
                            st.session_state.last_ans = ans
                            st.session_state.last_query = u_input
                            st.rerun()
                    else:
                        st.warning("没搜到东西，可能关键词太生僻了。")
                except Exception as e:
                    st.error(f"❌ 运行崩溃：{e}")
        else:
            st.error("请输入内容")

    # 3. 结果显示区域（稳定渲染，功能 1 & 2 就在这里）
    if st.session_state.last_ans:
        st.write("---")
        st.markdown(st.session_state.last_ans)
        
        c1, c2 = st.columns([1, 8])
        # ✅ 点完准确，案例录入，且因为有 session_state，答案不会消失
        if c1.button("👍 准确"):
            save_gold_case(st.session_state.last_query, st.session_state.last_ans)
            st.success("🎯 已同步！")
            st.rerun() 
            
        if c2.button("👎 有误"):
            st.session_state.last_ans = None
            st.rerun()    

# --- Tab 1: 规则录入 ---
with tabs[1]:
    st.subheader("📥 录入业务规则")
    c1, c2 = st.columns(2)
    m1 = c1.selectbox("一级模块", list(BUSINESS_MODULES.keys()), key="reg_m1")
    m2 = c2.selectbox("二级业务", BUSINESS_MODULES[m1], key="reg_m2")
    title = st.text_input("规则名称", key="reg_title")
    body = st.text_area("内容描述", value="### 📢 [通用规则]\n-业务逻辑： \n-使用范围： \n\n---\n### 🔒 [底层细节/内部逻辑]\n-核心逻辑：\n-技术配置： \n--- ### 🏷️ 搜索关键词关键词：\n---", height=350, key="reg_body")
    if st.button("确认存入", type="primary"):
        if title:
            path = os.path.join(STORY_PATH, m1, f"{title}_{datetime.datetime.now().strftime('%m%d')}.md")
            with open(path, "w", encoding="utf-8") as f: f.write(f"# {title}\n- **录入**：{st.session_state.current_user}\n---\n{body}")
            st.success("✅ 存入成功！"); st.rerun()

# --- Tab 2: 知识库管理 ---
with tabs[2]:
    st.subheader("🔍 文档浏览与编辑")
    all_fs = []
    for r, d, fs in os.walk(STORY_PATH):
        for f in fs:
            if f.endswith(".md"): all_fs.append(os.path.join(r, f))
    if all_fs:
        sf = st.selectbox("选择要修改的文档：", all_fs)
        with open(sf, 'r', encoding='utf-8') as f: doc_c = f.read()
        new_c = st.text_area("内容编辑：", value=doc_c, height=450, key="edit_area")
        if st.button("💾 保存修改"):
            with open(sf, 'w', encoding='utf-8') as f: f.write(new_c)
            st.success("✅ 更新成功！")
    else: st.info("知识库暂无内容")

# --- Tab 3: 案例库管理 ---
with tabs[3]:
    st.subheader("🏅 调教案例库管理")
    if os.path.exists(GOLD_CASES_FILE):
        with open(GOLD_CASES_FILE, 'r', encoding='utf-8') as f: cases = json.load(f)
        for i, c in enumerate(cases):
            with st.expander(f"Q: {c['query']} ({c['update_at']})"):
                st.write(c['answer'])
                if st.button(f"删除记录 {i}"):
                    cases.pop(i)
                    with open(GOLD_CASES_FILE, 'w', encoding='utf-8') as f: json.dump(cases, f, ensure_ascii=False, indent=2)
                    st.rerun()
    else: st.info("暂无点赞案例")

# --- Tab 4: 规则统计 ---
with tabs[4]:
    st.subheader("📊 知识库实时看板")
    col1, col2 = st.columns(2)
    
    # 统计文档总数
    doc_count = 0
    module_stats = {}
    for m in BUSINESS_MODULES.keys():
        m_path = os.path.join(STORY_PATH, m)
        if os.path.exists(m_path):
            count = len([f for f in os.listdir(m_path) if f.endswith('.md')])
            doc_count += count
            module_stats[m] = count
            
    # 统计点赞总数
    gold_count = 0
    if os.path.exists(GOLD_CASES_FILE):
        with open(GOLD_CASES_FILE, 'r', encoding='utf-8') as f: gold_count = len(json.load(f))
            
    col1.metric("📚 业务规则总条数", f"{doc_count} 条")
    col2.metric("🧠 已调教案例数", f"{gold_count} 个")
    
    st.write("---")
    st.write("📂 **模块分布详情：**")
    for m, c in module_stats.items():
        if c > 0:
            st.write(f"- {m}: **{c}** 条文档")