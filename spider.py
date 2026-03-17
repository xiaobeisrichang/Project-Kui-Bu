import requests
import json
import os
import re
import sys
from urllib.parse import urlparse, parse_qs
from markdownify import markdownify as md

# --- 1. 核心配置 ---
# ⚠️ 姐姐，Cookie 还是得在这里手动更新一下，因为它是动态的
COOKIES_STR = "_qddaz=QD.545372394039613; tapdsession=1760077640914e0679046b32b35c6bb0c5e9acc3598101199a1cb7bdbdda1d227675812a64; __root_domain_v=.tapd.cn; t_u=dcec7e507bd82f858f5054f3d0206a2b708606bf74cb0594ce3cd4f06332b6201dc644ce5a0c61a5ae6027852f40e0136e3bd8769087a5af1230921e256b30933d38d5e41d9fb2cd%7C1; new_worktable=my_dashboard; _t_uid=2002513451; _t_crop=20037371; tapd_div=101_0; dsc-token=IPBy7HrcBRV5k0tR; cloud_current_workspaceId=48533287; cherry-ai-guide-2002513451=1; editor_type=markdown; locale=zh_CN; _wt=eyJ1aWQiOiIyMDAyNTEzNDUxIiwiY29tcGFueV9pZCI6IjIwMDM3MzcxIiwiZXhwIjoxNzcxMTMxOTMwfQ%3D%3D.c4f941bc6ae5584a657958d4986ea3ff2c9bf34d9802789128d9fcec46ccf9d1; t_i_token=MjAwMjUxMzQ1MSwxNzcxMjYxMjMx.73b0e3ee6adac62d24b5fe2e24369dce738bd98fc3f65816b3f609136526f13b"
DSC_TOKEN = "IPBy7HrcBRV5k0tR" # 通常和 Cookie 里的 dsc_token 对应

def get_cookies_dict(cookie_str):
    return {item.split('=')[0]: item.split('=')[1] for item in cookie_str.split('; ')}

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}

# --- 2. 解析链接工具 ---
def parse_tapd_url(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    
    # 提取 workspace_id: 路径中的 48533287
    workspace_match = re.search(r'tapd_fe/(\d+)/', url)
    workspace_id = workspace_match.group(1) if workspace_match else None
    
    # 提取 category_id: 参数中的 categoryId
    category_id = params.get('categoryId', [None])[0]
    
    return workspace_id, category_id

# --- 3. 核心获取逻辑 ---
def fetch_and_save_story(workspace_id, story_id, story_name):
    detail_api = "https://www.tapd.cn/api/aggregation/story_aggregation/get_story_transition_info"
    params = {
        "menu_workitem_type_id": "1148533287001000001",
        "workspace_id": workspace_id,
        "story_id": story_id,
        "field_blocker": ""
    }
    
    try:
        res = requests.get(detail_api, params=params, headers=HEADERS, cookies=get_cookies_dict(COOKIES_STR))
        if res.status_code == 200:
            resp_data = res.json()
            # 路径：data -> get_workflow_by_story -> data -> current_story -> Story -> description
            try:
                html_content = resp_data['data']['get_workflow_by_story']['data']['current_story']['Story']['description']
            except KeyError:
                html_content = ""

            if html_content:
                # 转换并补全图片链接
                content_md = md(html_content)
                content_md = content_md.replace('src="/tfl/captures/', 'src="https://www.tapd.cn/tfl/captures/')
                content_md = content_md.replace('(/tfl/captures/', '(https://www.tapd.cn/tfl/captures/')
                
                safe_name = re.sub(r'[\\/:*?"<>|]', '_', story_name).strip()
                os.makedirs("01_Knowledge_Base", exist_ok=True)
                file_path = f"01_Knowledge_Base/{safe_name}.md"
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"# {story_name}\n\n{content_md}")
                return True
        return False
    except Exception as e:
        print(f"💥 处理 {story_name} 异常: {e}")
        return False

# --- 4. 主程序入口 ---
def main():
    if len(sys.argv) < 2:
        print("❌ 用法错误！请输入链接，例如: python3 spider.py \"https://www.tapd.cn/...\"")
        return

    input_url = sys.argv[1]
    ws_id, cat_id = parse_tapd_url(input_url)

    if not ws_id or not cat_id:
        print(f"❌ 无法从链接中解析出必要的 ID。ID探测结果: workspace_id={ws_id}, category_id={cat_id}")
        return

    print(f"📡 正在解析项目 {ws_id} 下分类 {cat_id} 的需求列表...")

    list_url = "https://www.tapd.cn/api/entity/stories/stories_list"
    payload = {
        "workspace_id": ws_id,
        "category_id": cat_id,
        "perpage": 50,
        "page": 1,
        "dsc_token": DSC_TOKEN
    }

    response = requests.post(list_url, headers=HEADERS, cookies=get_cookies_dict(COOKIES_STR), json=payload)
    
    if response.status_code == 200:
        stories = response.json().get('data', {}).get('stories_list', [])
        total = len(stories)
        print(f"🚀 找到 {total} 条需求，准备收割干货...\n")
        
        for index, item in enumerate(stories):
            story = item.get('Story', {})
            if story:
                if fetch_and_save_story(ws_id, story['id'], story['name']):
                    print(f"[{index+1}/{total}] ✅ 已下载: {story['name']}")
                else:
                    print(f"[{index+1}/{total}] ⚠️ {story['name']} 内容为空")
        print("\n✨ 全部搞定！请查看 01_Knowledge_Base 文件夹。")
    else:
        print(f"❌ 列表请求失败 (HTTP {response.status_code})，请检查 Cookie。")

if __name__ == "__main__":
    main()