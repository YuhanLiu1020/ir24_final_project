from flask import Flask, request, render_template, Response, jsonify, redirect, url_for, session
from elasticsearch import Elasticsearch
from urllib.parse import unquote
import html
import json
import time
import os
import datetime

app = Flask(__name__, static_folder=os.path.abspath('../static'))
app.config['SECRET_KEY'] = 'your_secret_key'

es = Elasticsearch(["http://localhost:9200"], verify_certs=False)
INDEX_NAME = "my_index"
PAGE_SIZE = 15  # 设置每页显示的结果数

USERS_FILE = 'users.json'
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w') as f:
        json.dump([], f)

PAGERANK_SCORES_FILE = "E:\ir24\ir_lab4\ir4_code\pagerank\pagerank_scores.json"
pagerank_scores = {}

def load_pagerank_scores():
    global pagerank_scores
    if os.path.exists(PAGERANK_SCORES_FILE):
        with open(PAGERANK_SCORES_FILE, "r", encoding="utf-8") as f:
            pagerank_scores = json.load(f)
    else:
        print("pagerank_scores.json 文件未找到")
        pagerank_scores = {}


def load_users():
    with open(USERS_FILE, 'r') as f:
        try:
            users = json.load(f)
        except json.JSONDecodeError:
            users = []
    return users

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def user_exists(user_id):
    users = load_users()
    for u in users:
        if u['user_id'] == user_id:
            return True
    return False

def verify_user(user_id, password):
    users = load_users()
    for u in users:
        if u['user_id'] == user_id and u['password'] == password:
            return True
    return False

def add_user(user_id, password):
    if user_exists(user_id):
        return False
    users = load_users()
    users.append({'user_id': user_id, 'password': password})
    save_users(users)
    return True

def read_logs(file_path):
    """尝试读取日志文件，如果文件不存在或不是有效JSON则返回空列表。"""
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            content = file.read()
            if content:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return []
            else:
                return []
    return []

def write_logs(logs, file_path):
    """将日志数据写入文件，确保是有效的JSON格式。"""
    with open(file_path, 'w') as file:
        json.dump(logs, file, indent=4)

def save_search_history(entry):
    """保存查询历史记录。"""
    log_file_path = 'query_log.json'
    logs = read_logs(log_file_path)

    # 移除已存在的相同查询记录
    logs = [log for log in logs if log['query'] != entry['query']]

    entry['timestamp'] = datetime.datetime.now().isoformat()
    if 'user_id' in session:
        entry['user_id'] = session['user_id']
    logs.append(entry)

    # 保持日志文件中记录数量不超过100条
    if len(logs) > 100:
        logs = logs[-100:]

    write_logs(logs, log_file_path)

@app.route("/get_recent_searches")
def get_recent_searches():
    log_file_path = 'query_log.json'
    try:
        if not os.path.exists(log_file_path):
            with open(log_file_path, 'w') as file:
                json.dump([], file)
            logs = []
        else:
            with open(log_file_path, 'r') as file:
                logs = json.load(file)
    except json.JSONDecodeError:
        logs = []

    if 'user_id' in session:
        logs = [l for l in logs if l.get('user_id') == session['user_id']]

    recent_searches = logs[-10:] if len(logs) > 10 else logs
    recent_searches.reverse()
    return jsonify(recent_searches)

@app.route("/history")
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    log_file_path = 'query_log.json'
    if not os.path.exists(log_file_path):
        with open(log_file_path, 'w') as file:
            json.dump([], file)

    with open(log_file_path, 'r') as file:
        try:
            logs = json.load(file)
        except json.JSONDecodeError:
            logs = []

    user_logs = [log for log in logs if log.get('user_id') == session['user_id']]

    return render_template('history.html', history=user_logs)

@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    query_term = request.args.get("q", "").strip()
    if not query_term:
        return jsonify([])

    # Elasticsearch 查询，匹配标题或内容前缀
    query_body = {
        "query": {
            "prefix": {
                "title": query_term  # 根据标题前缀匹配
            }
        },
        "size": 10,  # 返回前 10 条结果
        "_source": ["title"]
    }

    response = es.search(index=INDEX_NAME, body=query_body)
    hits = response.get("hits", {}).get("hits", [])

    # 提取标题字段，确保返回的是字符串列表
    suggestions = [hit["_source"].get("title", "") for hit in hits if "title" in hit["_source"]]
    return jsonify(suggestions)


@app.route("/snapshot")
def snapshot():
    url = request.args.get('url')
    if not url:
        return "URL parameter is missing", 404

    decoded_url = unquote(url)
    query_body = {
        "query": {
            "term": {
                "url": decoded_url
            }
        },
        "_source": ["raw_html"]
    }
    response = es.search(index=INDEX_NAME, body=query_body)
    hits_data = response.get("hits", {})
    hits = hits_data.get("hits", [])
    if hits:
        raw_html = hits[0]['_source'].get('raw_html', 'No content available')
        return Response(raw_html, mimetype='text/html; charset=utf-8')
    else:
        return "No snapshot available for this URL", 404

def standard_search(es, query_term, index_name, results_size=1000):
    query_body = {
        "query": {
            "function_score": {  # 使用 function_score 将 pagerank_score 加权
                "query": {
                    "multi_match": {
                        "query": query_term,
                        "fields": ["title", "content", "anchor_texts"]
                    }
                },
                "field_value_factor": {  # 使用字段的数值加权
                    "field": "pagerank_score",  # 使用 PageRank 分数字段
                    "factor": 1.0,  # 加权因子，调整影响程度
                    "modifier": "log1p",  # 对分数取对数 +1，使分数分布更均匀
                    "missing": 1  # 如果字段不存在，默认值为1
                },
                "boost_mode": "sum"  # 综合搜索得分和 PageRank 分数
            }
        },
        "size": results_size
    }
    return es.search(index=index_name, body=query_body)


def phrase_search(es, query_term, index_name, results_size=1000):
    query_body = {
        "query": {
            "match_phrase": {
                "content": {
                    "query": query_term,
                    "slop": 0
                }
            }
        },
        "size": results_size
    }
    return es.search(index=index_name, body=query_body)

def document_search(es, query_term, index_name, results_size=1000):
    response = standard_search(es, query_term, index_name)
    hits_data = response.get("hits", {})
    hits = hits_data.get("hits", [])
    filtered_hits = []
    for hit in hits:
        attachments = hit["_source"].get("attachments", [])
        if any(att.endswith('.pdf') or att.endswith('.docx') or att.endswith('.xlsx') or att.endswith('.doc') for att in attachments):
            filtered_hits.append(hit)
    return {"hits": {"hits": filtered_hits}}

DEFAULT_RESULTS_SIZE = 1000

def wildcard_search(es, query_term, index_name, results_size=1000):
    """
    使用 query_string 在 text 字段上进行通配符查询。
    支持 * 匹配多个字符，? 匹配单个字符。
    """
    query_body = {
        "query": {
            "query_string": {
                "query": f"*{query_term}*",
                "fields": ["title^3", "content^2", "anchor_texts"],  # 设置权重，title最高
                "default_operator": "AND"  # 默认操作符
            }
        },
        "size": results_size
    }
    response = es.search(index=index_name, body=query_body)
    return response


@app.route("/", methods=["GET"])
def home():
    return render_template("search.html",
                           message=None,
                           logged_in=('user_id' in session),
                           user_id=session.get('user_id'))

# 调用一次加载 PageRank 分数
load_pagerank_scores()

def get_pagerank_score(url):
    """根据 URL 从本地文件中获取 PageRank 分数"""
    return pagerank_scores.get(url, 0.0)

@app.route("/search", methods=["GET", "POST"])
def search():
    query_term = request.form.get("q", "").strip()
    query_type = request.form.get("type", "standard")
    page = int(request.args.get("page", 1))

    log_entry = {
        "query": query_term,
        "type": query_type,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_search_history(log_entry)

    if not query_term:
        return render_template("search.html",
                               message="请输入查询词",
                               logged_in=('user_id' in session),
                               user_id=session.get('user_id'))

    start = (page - 1) * PAGE_SIZE
    if query_type == "document":
        response = document_search(es, query_term, INDEX_NAME)
    elif query_type == "wildcard":
        response = wildcard_search(es, query_term, INDEX_NAME)
    elif query_type == "phrase":
        response = phrase_search(es, query_term, INDEX_NAME, DEFAULT_RESULTS_SIZE)
    else:
        response = standard_search(es, query_term, INDEX_NAME)

    hits_data = response.get("hits", {})
    total_data = hits_data.get("total", {})
    total_results = total_data.get("value", 0)
    hits = hits_data.get("hits", [])

    # 定义权重参数
    alpha = 0.7  # Elasticsearch 相关性分数权重
    beta = 0.3   # PageRank 分数权重

    results = [{"title": hit["_source"].get("title", ""),
                "url": hit["_source"].get("url", ""),
                "score": hit["_score"],
                "pagerank": get_pagerank_score(hit["_source"].get("url", "")),
                "final_score": alpha * hit["_score"] + beta * get_pagerank_score(hit["_source"].get("url", "")),
                "snippet": hit["_source"].get("content", "")[:200] + "..."} for hit in hits]
    # 根据最终分数排序
    results.sort(key=lambda x: x["final_score"], reverse=True)

    return render_template("results.html",
                           query=query_term,
                           results=results,
                           total_results=total_results,
                           page=page,
                           page_size=PAGE_SIZE,
                           logged_in=('user_id' in session),
                           user_id=session.get('user_id'))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        password = request.form.get("password", "").strip()
        if not user_id or not password:
            return render_template("register.html", message="用户ID和密码不能为空")
        if user_exists(user_id):
            return render_template("register.html", message="用户ID已存在，请更换")
        if add_user(user_id, password):
            return redirect(url_for('login'))
        else:
            return render_template("register.html", message="用户创建失败，请重试")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        password = request.form.get("password", "").strip()
        if verify_user(user_id, password):
            session['user_id'] = user_id
            return redirect(url_for('home'))
        else:
            return render_template("login.html", message="用户名或密码错误")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

# 新增个性化推荐页面（用户主页）
@app.route("/user_home")
def user_home():
    # 未登录则跳转登录
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # 1. 今日推荐：
    today_recommendations = [
        {"title": "南开大学主页", "url": "https://www.nankai.edu.cn"},
        {"title": "南开新闻网", "url": "https://news.nankai.edu.cn"},
        {"title": "南开大学招生信息", "url": "https://zk.nankai.edu.cn"},
        {"title": "南开大学图书馆", "url": "https://lib.nankai.edu.cn"},
        {"title": "南开大学研究生院", "url": "https://graduate.nankai.edu.cn"}
    ]

    # 2. 基于历史记录的五条推荐
    # 从用户历史查询中取最后一次查询，或最后几个查询，然后重新搜索获取结果。
    log_file_path = 'query_log.json'
    logs = read_logs(log_file_path)
    user_logs = [log for log in logs if log.get('user_id') == user_id]
    user_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)  # 按时间降序
    history_recommendations = []
    if user_logs:
        # 取用户最近的一条查询记录
        last_query = user_logs[0]["query"]
        # 用last_query再搜索，取前五条作为推荐
        resp = standard_search(es, last_query, INDEX_NAME, results_size=5)
        rec_hits = resp.get("hits", {}).get("hits", [])
        for rhit in rec_hits:
            rsource = rhit["_source"]
            history_recommendations.append({
                "title": rsource.get("title", ""),
                "url": rsource.get("url", "")
            })

    return render_template("user_home.html",
                           user_id=user_id,
                           today_recommendations=today_recommendations,
                           history_recommendations=history_recommendations)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
