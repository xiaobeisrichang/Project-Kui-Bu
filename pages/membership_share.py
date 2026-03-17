import streamlit as st
import requests
import pandas as pd
import re
import json
import os

# 页面配置
st.set_page_config(page_title="会员分享&登录日志处理", layout="wide")

# --- 【新增】持久化文件缓存 logic ---
CACHE_FILE = ".token_cache.json"

def load_cache():
    """从本地文件读取 Token"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def save_cache(sessionid, csrftoken):
    """将 Token 保存到本地文件"""
    with open(CACHE_FILE, 'w') as f:
        json.dump({"sessionid": sessionid, "csrftoken": csrftoken}, f)

# 初始化凭证：优先级是 文件缓存 > SessionState > 默认值
cached_data = load_cache()
# 这里的逻辑保证了：只要文件在，刷新页面也会从文件恢复
init_sid = cached_data["sessionid"] if cached_data else "dosdd5y25izzisyp7z9e7p4nm5q9vijt"
init_csrf = cached_data["csrftoken"] if cached_data else "z7vBXCe7S4ApUreSzSkHnxJ1h9dKydi2sUpkn8GUvVRdP7PnFJBYtBzSmdWUSvea"

# --- 1. 弱登录功能 (侧边栏) ---
st.sidebar.title("🔐 登录授权")
login_user = st.sidebar.text_input("用户名", value="jerres.lee")
login_pwd = st.sidebar.text_input("密码", value="Kk123456", type="password")

# 初始化 SessionState
if 'sessionid' not in st.session_state:
    st.session_state.sessionid = init_sid
if 'csrftoken' not in st.session_state:
    st.session_state.csrftoken = init_csrf

def auto_login():
    """严格模拟四步走登录流程"""
    base_url = "http://10.233.202.73:18000"
    login_url = f"{base_url}/xadmin/"
    
    s = requests.Session()
    
    try:
        # 第一步：GET 请求，获取初始 csrftoken
        get_res = s.get(login_url, timeout=10)
        initial_csrf = s.cookies.get('csrftoken')
        if not initial_csrf:
            st.sidebar.error("❌ 无法获取初始 CSRF Token")
            return
            
        # 第二步：POST 登录
        payload = {
            "username": login_user,
            "password": login_pwd,
            "this_is_the_login_form": "1",
            "next": "/",
            "csrfmiddlewaretoken": initial_csrf,
            "token": "true"
        }
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/x-www-form-urlencoded",
            "Referer": base_url + "/"
        }
        
        post_res = s.post(login_url, data=payload, headers=headers, allow_redirects=False, timeout=10)
        new_cookies = s.cookies.get_dict()
        
        if 'sessionid' in new_cookies:
            # 【核心修改】更新内存的同时更新文件缓存
            st.session_state.sessionid = new_cookies['sessionid']
            st.session_state.csrftoken = new_cookies.get('csrftoken', initial_csrf)
            save_cache(st.session_state.sessionid, st.session_state.csrftoken)
            
            # 第三步 & 第四步：激活 session
            s.get(f"{base_url}/api/sites/connect/tools/", headers={"Referer": base_url + "/"})
            
            st.sidebar.success("✅ 登录成功！Token 已持久化到文件")
            if 'log_store' in st.session_state:
                st.session_state.log_store = {}
            st.rerun() 
        else:
            st.sidebar.error("❌ 登录失败：未获取到 sessionid。")
            
    except Exception as e:
        st.sidebar.error(f"🚀 登录链路异常: {e}")

if st.sidebar.button("🚀 一键获取 Token"):
    auto_login()

# 展示当前缓存的凭证
with st.sidebar.expander("📊 当前缓存凭证"):
    st.code(f"SID: {st.session_state.sessionid}\nCSRF: {st.session_state.csrftoken}")
    if st.button("🗑 清除本地缓存"):
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            st.rerun()

# --- 2. 封装 Headers ---
def get_headers():
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "content-type": "application/json;charset=UTF-8",
        "cookie": f"csrftoken={st.session_state.csrftoken}; sessionid={st.session_state.sessionid}",
        "Referer": "http://10.233.202.73:18000/"
    }

def call_query_api(database, sql, tab_name="1"):
    url = "http://10.233.202.73:18000/api/query/connect/"
    payload = {
        "database": database,
        "domain": "生产-mysql-标签&运营&安全-10.233.55.219:3306",
        "tabName": tab_name,
        "level": 1000,
        "sql": sql
    }
    try:
        res = requests.post(url, json=payload, headers=get_headers(), timeout=10)
        data = res.json()
        if data.get("msg") == "success" and len(data.get("list", [])) > 1:
            return data["list"][1]
        return []
    except Exception as e:
        st.error(f"查询失败: {e}")
        return []

def decrypt_ext_key(ext_key):
    try:
        url = f"http://10.230.144.227:9008/decryptMembership?text={ext_key}"
        res = requests.get(url, timeout=5)
        text = res.text
        match = re.search(r"时间：([\d\-\s:]+)", text)
        share_time = match.group(1) if match else None
        return text, share_time
    except:
        return "解析失败", None

# --- UI 界面 ---
st.title("💡 亲情卡查询工具")

col_in1, col_in2 = st.columns(2)
with col_in1:
    jjid_input = st.text_input("1. 输入 JJID (查分享):", placeholder="例如: 426569136")
with col_in2:
    hotel_id_input = st.text_input("2. 输入酒店会员 ID (查登录):", placeholder="例如: 459990072")

search_btn = st.button("🚀 查询")

if 'log_store' not in st.session_state:
    st.session_state.log_store = {}

if jjid_input and hotel_id_input:
    share_sql = f"select * from m_membership_share_mapping where mebid = {jjid_input} order by createTime desc limit 5"
    share_records = call_query_api("member_operate", share_sql, "1")
    
    if not share_records:
        if search_btn: st.info("未查到数据。若之前正常，请尝试点击左侧[一键获取 Token]")
    else:
        st.write("### 📋 分享明细及登录日志溯源")
        for i, row in enumerate(share_records):
            ext_key = row.get("extKey")
            dec_text, s_time = decrypt_ext_key(ext_key)
            
            info_col, btn_col = st.columns([0.8, 0.2])
            with info_col:
                st.markdown(f"**记录 {i+1}** | 分享JJID: `{row.get('mebId')}` | 分享时间: :red[{s_time or '未知'}] | 领取人: `{row.get('getLevelMebId')}` | 领取时间: `{row.get('createTime')}` | 领取等级: `{row.get('shareLevel')}`")
            
            with btn_col:
                if st.button(f"🔍 登录日志", key=f"btn_{i}"):
                    if s_time:
                        with st.spinner("查询中..."):
                            login_sql = f"select * from m_loginlog where mebid = {hotel_id_input} and logintime < '{s_time}' order by logintime desc limit 5"
                            logs = call_query_api("member_auth", login_sql, "2")
                            st.session_state.log_store[f"log_{i}"] = logs

            if f"log_{i}" in st.session_state.log_store:
                logs = st.session_state.log_store[f"log_{i}"]
                st.caption(f"解析详情: {dec_text}")
                if logs:
                    log_df = pd.DataFrame(logs)
                    display_map = {"loginTime": "登录时间", "loginType": "登录方式", "sourceType": "登录渠道", "businessType": "业务类型"}
                    df_final = log_df[list(display_map.keys())].rename(columns=display_map)
                    
                    def make_red(val):
                        return 'color: #ff6c6c; font-weight: bold;'
                    styled_df = df_final.style.applymap(make_red, subset=['登录时间'])
                    st.table(styled_df)
                else:
                    st.write("🚫 该分享时间前无登录记录")
            st.divider()

st.success("数据处理完成")