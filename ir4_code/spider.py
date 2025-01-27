import requests
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import urljoin, urlparse
from collections import deque
import re

# 设置保存路径
SAVE_PATH = r'E:\ir24\ir_lab4\ir4_code\JSON'
if not os.path.exists(SAVE_PATH):
    os.makedirs(SAVE_PATH)

# 初始URL
START_URL = 'https://cc.nankai.edu.cn/'

# 设置请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                  ' Chrome/112.0.0.0 Safari/537.36'
}

# 设置爬取限制
MAX_PAGES = 100000  # 最大爬取页面数
BATCH_SIZE = 3000   # 每个JSON文件保存的页面数
DELAY = 1            # 每次请求的延时（秒）

# 解析robots.txt
def parse_robots(url):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = requests.get(robots_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            disallow = []
            for line in response.text.split('\n'):
                if line.strip().lower().startswith('disallow'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        disallow.append(parts[1].strip())
            return disallow
    except Exception as e:
        print(f"无法获取robots.txt: {e}")
    return []

# 检查URL是否允许爬取
def is_allowed(url, disallow_list):
    parsed = urlparse(url)
    path = parsed.path
    for rule in disallow_list:
        if rule == '':
            continue
        if path.startswith(rule):
            return False
    return True

# 提取页面中的所有链接，并区分附件链接
def extract_links(soup, base_url, domain):
    links = set()
    attachments = set()
    attachment_pattern = re.compile(r'.*\.(pdf|docx?|xlsx?|pptx?)$', re.IGNORECASE)

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()
        full_url = urljoin(base_url, href)
        # 仅抓取同域的URL
        if urlparse(full_url).netloc.endswith(domain):
            full_url = full_url.split('#')[0]
            if re.match(r'^https?://', full_url):
                # 判断是否是附件
                if attachment_pattern.match(full_url):
                    attachments.add(full_url)
                else:
                    links.add(full_url)
    return links, attachments

# 提取页面信息
def extract_page_info(url, soup, anchor_texts, outlinks, attachments, raw_html):
    title_tag = soup.find('title')
    title = title_tag.get_text(strip=True) if title_tag else ''

    # 尝试提取正文内容（根据页面结构调整）
    content = ''
    article_div = soup.find('div', {'class': 'article-content'})
    if article_div:
        content = article_div.get_text(strip=True)
    else:
        # 没有明确区域，就简单获取全页文本前2000字符（根据需求调整）
        content = soup.get_text(strip=True)[:2000]

    return {
        'url': url,
        'title': title,
        'anchor_texts': list(anchor_texts),
        'content': content,
        'outlinks': list(outlinks),       # 新增字段：出链列表
        'attachments': list(attachments), # 新增字段：附件链接列表
        'raw_html': raw_html              # 新增字段：网页原始HTML
    }

def main():
    parsed_start = urlparse(START_URL)
    domain = parsed_start.netloc

    disallow_list = parse_robots(START_URL)
    if not is_allowed(START_URL, disallow_list):
        print(f"起始URL {START_URL} 被robots.txt禁止爬取。")
        return

    queue = deque([START_URL])
    visited = set()
    data_buffer = []
    file_index = 1
    page_count = 0

    while queue and page_count < MAX_PAGES:
        current_url = queue.popleft()
        if current_url in visited:
            continue
        if not is_allowed(current_url, disallow_list):
            print(f"跳过被robots.txt禁止的URL: {current_url}")
            continue

        try:
            response = requests.get(current_url, headers=HEADERS, timeout=10)
            if response.status_code != 200:
                print(f"无法访问URL: {current_url} 状态码: {response.status_code}")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            # 收集当前页面的锚文本
            anchor_texts = set(a.get_text(strip=True) for a in soup.find_all('a', href=True) if a.get_text(strip=True))

            # 提取新的链接
            outlinks, attachments = extract_links(soup, current_url, domain)

            # 构建页面信息
            page_info = extract_page_info(current_url, soup, anchor_texts, outlinks, attachments, response.text)
            data_buffer.append(page_info)
            page_count += 1
            print(f"爬取页面 {page_count}: {current_url}")

            # 保存数据
            if page_count % BATCH_SIZE == 0:
                file_path = os.path.join(SAVE_PATH, f'data_{file_index}.json')
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data_buffer, f, ensure_ascii=False, indent=4)
                print(f"保存 {BATCH_SIZE} 个页面到 {file_path}")
                data_buffer = []
                file_index += 1

            # 将 outlinks 加入队列
            for link in outlinks:
                if link not in visited:
                    queue.append(link)

            visited.add(current_url)
            time.sleep(DELAY)  # 延时防止对服务器造成压力

        except Exception as e:
            print(f"处理URL {current_url} 时出错: {e}")
            continue

    # 保存剩余的数据
    if data_buffer:
        file_path = os.path.join(SAVE_PATH, f'data_{file_index}.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_buffer, f, ensure_ascii=False, indent=4)
        print(f"保存剩余的 {len(data_buffer)} 个页面到 {file_path}")

    print("爬取完成。")

if __name__ == '__main__':
    main()
