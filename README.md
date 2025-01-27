------

# **基于 Elasticsearch 的南开校内资源 Web 搜索引擎**

## **一、实验目的**

针对南开校内资源构建一个 **Web 搜索引擎**，提供包括 **网页抓取**、**文本索引**、**链接分析**、**查询服务** 和 **个性化查询和推荐** 在内的功能。

------

## **二、实验环境**

- **操作系统**：Windows 11

- **开发语言**：Python 3.10.14

- 框架与工具：

  - Flask：实现 Web 应用和后端逻辑
  - Elasticsearch：提供数据存储、检索与排序功能
  - BeautifulSoup4：用于网页抓取与解析
  - JSON 文件：保存用户数据与查询历史记录

- 依赖库：

  ```bash
  pip install flask elasticsearch beautifulsoup4 requests
  ```

- 实验目录结构

  ```
  IR4_CODE/
  │
  ├── index/                   # 数据索引模块
  │   ├── index_data.py        # 批量导入 JSON 数据到 Elasticsearch
  │   ├── mapping.py           # 定义索引的映射和分词器配置
  │   └── __pycache__/         # 缓存文件夹
  │
  ├── JSON/                    # 存储爬取的数据集
  │   ├── ai.json
  │   ├── bs.json
  │   ├── finance.json
  │   └── ...                  # 其他数据文件
  │
  ├── pagerank/                # PageRank 模块
  │   ├── pagerank.py          # PageRank 算法实现
  │   └── pagerank_scores.json # 存储 PageRank 结果
  │
  ├── query/                   # Flask Web 应用模块
  │   ├── templates/           # HTML 模板文件
  │   │   ├── search.html      # 搜索页面
  │   │   ├── results.html     # 搜索结果页面
  │   │   ├── history.html     # 查询历史页面
  │   │   ├── login.html       # 用户登录页面
  │   │   ├── register.html    # 用户注册页面
  │   │   └── user_home.html   # 用户主页
  │   │
  │   ├── static/              # 静态资源
  │   │   └── images/          # 图片资源
  │   │       └── title.png
  │   │
  │   ├── query.py             # Flask 主程序
  │   ├── query_log.json       # 存储查询历史
  │   ├── users.json           # 存储用户信息
  │   └── __pycache__/         # 缓存文件夹
  │
  └── spider.py                # 网页爬虫模块
  ```

  

------

## **三、系统设计与实现**

### **3.1 网页抓取模块**

#### **实现目标**：

针对南开校内资源（包括南开新闻网和多个专业学院）进行网页爬取，获取网页标题、内容、锚文本、附件链接等。

#### **代码文件**：

- **`spider.py`**：实现网页抓取和数据保存。

#### **关键功能**：

1. **遵守 robots.txt 协议**，礼貌抓取网页资源。
2. 支持 **同域名网页爬取** 和 **附件链接识别**（PDF、DOCX 等）。
3. 将抓取到的网页内容保存为 JSON 文件，存储在 `JSON` 目录下。

**数据结构示例**：

```json
{
  "url": "https://physics.nankai.edu.cn/",
  "title": "物理科学学院",
  "content": "南开大学物理科学学院成立于...",
  "anchor_texts": ["招生信息", "新闻动态"],
  "attachments": ["https://example.com/file.pdf"],
  "raw_html": "<html>...</html>"
}
```

------

### **3.2 文本索引模块**

#### **实现目标**：

将抓取到的网页数据导入 Elasticsearch，构建多字段索引。

#### **代码文件**：

- **`mapping.py`**：定义 Elasticsearch 的索引映射和分词器

```python
# 设置索引名称
index_name = "my_index"

# 定义索引的设置与映射
settings = {
    "settings": {
        "analysis": {
            "analyzer": {
                "ik_smart_analyzer": {
                    "type": "custom",
                    "tokenizer": "ik_smart",
                    "filter": ["lowercase"]
                },
                "ik_max_word_analyzer": {
                    "type": "custom",
                    "tokenizer": "ik_max_word",
                    "filter": ["lowercase"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "url": {"type": "keyword",
            "ignore_above": 256  # 避免过长字符串浪费空间
            },
            "title": {
                "type": "text",
                "analyzer": "ik_max_word_analyzer",
                "index_options": "offsets"
            },
            "anchor_texts": {
                "type": "text",
                "analyzer": "ik_smart_analyzer",
            },
            "content": {
                "type": "text",
                "analyzer": "ik_max_word_analyzer",
                "index_options": "offsets"
            },
            "outlinks": {"type": "keyword"},
            "raw_html": {"type": "text"}, 
            "attachments": {"type": "keyword"} 
        }
    }
}
```



- **`index_data.py`**：将 JSON 数据批量导入 Elasticsearch。

```python
index_name = "my_index"
json_dir = r".\ir4_code\JSON"

# 定义数据生成函数
def generate_actions():
    # 遍历 JSON 目录中的所有文件
    for filename in os.listdir(json_dir):
        if filename.endswith(".json"):  # 只处理 .json 文件
            file_path = os.path.join(json_dir, filename)
            print(f"Processing file: {filename}")
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)  # 加载整个 JSON 文件

                    # 如果是 JSON 数组，每个元素为一个文档
                    if isinstance(data, list):
                        for doc in data:
                            yield {"_index": index_name, "_source": doc}

                    # 如果是单个 JSON 对象
                    elif isinstance(data, dict):
                        yield {"_index": index_name, "_source": data}

                except json.JSONDecodeError as e:
                    print(f"Invalid JSON in file '{filename}': {e}")
                except Exception as e:
                    print(f"Error processing file '{filename}': {e}")

# 批量导入数据
try:
    print("Disabling index refresh interval...")
    es.indices.put_settings(index=index_name, body={"index": {"refresh_interval": "-1"}})

    print("Starting bulk indexing...")
    success, failed = 0, 0
    for ok, action in helpers.streaming_bulk(
        client=es,
        actions=generate_actions(),
        chunk_size=500,  # 每批次 500 条文档
        request_timeout=120
    ):
        if ok:
            success += 1
        else:
            failed += 1

    print(f"Bulk indexing completed: {success} successes, {failed} failures.")
except BulkIndexError as e:
    print(f"BulkIndexError encountered: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    print("Re-enabling index refresh interval...")
    es.indices.put_settings(index=index_name, body={"index": {"refresh_interval": "1s"}})
    print("Data indexing process completed successfully!")
```

#### **功能说明**：

- 使用 **IK 分词器** 进行中文分词，支持 `ik_max_word` 和 `ik_smart` 分词。
- 索引字段包括：`url`、`title`、`content`、`anchor_texts`、`attachments` 和 `raw_html`。

------

### **3.3 链接分析模块**

#### **实现目标**：

使用 **PageRank 算法** 对网页链接进行权重计算，优化搜索结果排序。

#### **代码文件**：

- **`pagerank.py`**：实现 PageRank 算法，计算网页权重。

```python
# 从JSON中读取数据并构建图
for filename in os.listdir(json_dir):
    if filename.endswith(".json"):
        file_path = os.path.join(json_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 同index_data.py一致的结构判断
            docs = data if isinstance(data, list) else [data]
            for doc in docs:
                url = doc.get("url")
                outlinks = doc.get("outlinks", [])
                if url:
                    if not G.has_node(url):
                        G.add_node(url)
                    for link in outlinks:
                        if link and link != url:  # 避免自环
                            if not G.has_node(link):
                                G.add_node(link)
                            G.add_edge(url, link)

# 计算 PageRank
pagerank_scores = nx.pagerank(G)

# 排序
sorted_scores = sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True)
sorted_url_scores = {url: score for url, score in sorted_scores}
```

- **`pagerank_scores.json`**：存储 PageRank 计算结果。

------

### **3.4 查询服务模块**

#### **实现目标**：

实现站内查询、文档查询、短语查询、通配查询、查询日志、网页快照六种高级搜索功能，满足用户不同的查询需求。

#### **代码文件**：

- **`query.py`**：实现搜索服务的主要逻辑。

#### **功能说明**：

1. **站内查询**：通过 Elasticsearch 的 `multi_match` 查询实现站内搜索。
2. **文档查询**：筛选包含附件链接（PDF、DOCX 等）的网页数据。
3. **短语查询**：使用 `match_phrase` 查询，支持精确短语匹配。
4. **通配查询**：使用 `wildcard` 查询，支持正则匹配。
5. **查询日志**：记录用户的查询历史，存储到 `query_log.json`。
6. **网页快照**：返回网页的原始 HTML 内容，通过 `/snapshot` 路由访问。

------

### **3.5 个性化查询模块**

#### **实现目标**：

实现用户注册、登录功能，并提供今日推荐与根据用户历史记录推荐的数条内容。

#### **代码文件**：

- **`query.py`**：实现用户管理、个性化推荐逻辑。
- **`users.json`**：存储用户账号信息。

#### **功能说明**：

1. **用户管理**：
   - 支持用户注册与登录功能。
   - 用户信息存储在 `users.json` 文件中。
2. **历史记录推荐**：
   - 根据用户历史查询记录，提供个性化推荐。
   - 每个用户的查询历史记录存储在 `query_log.json`，查询日志与用户绑定。
3. **Web 界面**：
   - 用户登录后可访问 **个人主页**，展示推荐内容。

------

### **3.6 Web 界面设计**

#### **实现目标**：

通过简单直观的 Web 页面，为用户提供搜索与个性化推荐服务。

#### **主要页面**：

1. **搜索页面 (`search.html`)**：
   - 包含搜索框与搜索类型选择功能。
   - 显示最近的查询历史。
2. **搜索结果页面 (`results.html`)**：
   - 显示查询结果，包括标题、URL、网页摘要、PageRank 分数等。
3. **用户注册与登录页面 (`register.html`, `login.html`)**：
   - 提供用户账号注册与登录功能。
4. **用户主页 (`user_home.html`)**：
   - 展示个性化推荐内容，包括“今日推荐”和“基于历史记录推荐”。
5. **历史记录页面 (`history.html`)**：
   - 显示用户的查询历史记录。

### **3.7 个性化推荐模块**

#### **实现目标**：

用户在输入框中输入关键字后，系统会根据关键字提供十条相关联的查询推荐

#### **代码文件**：

- **`query.py`**：实现关键字联想的推荐逻辑。<img src=".\pages\9d7174b8a96513a64b03a55db450401.png" alt="9d7174b8a96513a64b03a55db450401" style="zoom: 25%;" />

------

## **四、系统运行与测试**

### **4.1 数据导入**

运行以下命令将数据索引到 Elasticsearch：

```bash
python mapping.py      # 创建索引
python index_data.py   # 导入数据
```

运行以下命令使用PageRank进行链接分析，评估网页权重：

```bash
python pagerank.py     # 链接分析
```

### **4.2 系统启动**

运行 Flask 服务：

```bash
python query.py
```

在浏览器中访问：`http://127.0.0.1:5000`。

### **4.3 功能测试**

1. **查询功能**：默认为站内搜索（标准查询），在查询选择那栏可以选择短语查询、通配符查询或文档查询。<img src=".\pages\9383fc4c70219fd39b42406ef840c3f.png" alt="9383fc4c70219fd39b42406ef840c3f" style="zoom: 25%;" />

   ① 使用标准查询（**站内查询**）"加强网络生态评估"，按照加权分数从上到下一次显示了查询的相关结果，每一条包含URL链接，标题，网页快照和部分内容。

   <img src=".\pages\dc5ccf703cd92c07fe85aa925c82791.png" alt="dc5ccf703cd92c07fe85aa925c82791" style="zoom:33%;" />

   点击第一条的标题跳转到对应网页<img src=".\pages\a024555d417c2c7191a4c8e0fdb7241.png" alt="a024555d417c2c7191a4c8e0fdb7241" style="zoom: 25%;" />

   

   ② 使用**短语查询**“加强网络生态治理评估”，发现只有包含完整短语的网页才被索引出来。

   ![a80f42b6329c2376f1bb786a41dcc7b](.\pages\a80f42b6329c2376f1bb786a41dcc7b.png)

   ③ 点击第一个链接的**网页快照**，可以在本地看到爬虫时保存的源html（图片无法显示是因为使用的是相对链接）

   ![97750081401b1aad2fe4fb97cde0f2f](.\pages\97750081401b1aad2fe4fb97cde0f2f.png)

   

   ④ 使用**文档查询**“交换项目“，查询结果只会返回网页中包含文档链接的条目。

   ![02d0377587f29d10a0031fd4c40f6ef](.\pages\02d0377587f29d10a0031fd4c40f6ef.png)

   点击第二条搜索结果，该网页下的确有文档下载链接。

   ![55686111d6d0ef69b768cd6cc322193](.\pages\55686111d6d0ef69b768cd6cc322193.png)

   

   ⑤ 使用**通配符查询**“刘？”和“*刘**”。支持 * 匹配多个字符，? 匹配单个字符。![9b20693fdde710aa0882700882401c4](.\pages\9b20693fdde710aa0882700882401c4.png)

   ![2ade718626b66f979d5f76994aca653](.\pages\2ade718626b66f979d5f76994aca653.png)

   ⑥ **查询日志**：在查询主页，在没输入查询词时点击“输入查询词的窗口，也会显示当前用户的历史记录

   <img src=".\pages\c45bba306697596bdedb5a5b1cfff2b.png" alt="c45bba306697596bdedb5a5b1cfff2b" style="zoom: 25%;" />

2. **个性化查询**：查询首页有登录/注册选项，可以注册新用户，登录后查询历史记录是否与用户绑定。
   这里点击用户登录，输入用户ID和密码，然后可以点击登录。下方的注册选项课跳转到注册界面。

   <img src=".\pages\df3adcbca00f756096435ceac468ae9.png" alt="df3adcbca00f756096435ceac468ae9" style="zoom:33%;" /><img src=".\pages\011bf9221bd6aa55bef4f1a87ee31d0.png" alt="011bf9221bd6aa55bef4f1a87ee31d0" style="zoom: 33%;" />

   登录后的查询界面如下图所示，显示了当前用户id，也可以选择登出、查看历史记录和用户主页。

   <img src=".\pages\ddb6479cb65ba89669fea0eef502dfd.png" alt="ddb6479cb65ba89669fea0eef502dfd" style="zoom: 25%;" />

   点击历史记录，可以看到之前查询的历史记录（包含时间戳和查询词）。

   <img src=".\pages\5f886547d415ab9b3b8e1be93413838.png" alt="5f886547d415ab9b3b8e1be93413838" style="zoom:33%;" />

   登录用户主页，查看今日推荐和根据历史记录进行推荐的个性化推荐内容。![7d2251e38e779cedd8b053bf62d324c](.\pages\7d2251e38e779cedd8b053bf62d324c.png)

3. **个性化推荐：**

   输入“计算”后，系统会进行搜索上的联想关联，然后进行提示。

   ![9d7174b8a96513a64b03a55db450401](.\pages\9d7174b8a96513a64b03a55db450401.png)

------

## **五、操作提示**

1. 爬虫文件我按照JSON形式进行保存，对于一个域名下的网页爬取，最初我设置了20000条保存到一个JSON文件里，但这样导致文件占用空间过大（3000条以上就可能大于1G），在将数据索引到 Elasticsearch时提示电脑内存不足，无法读取，只能重新爬取，浪费时间精力。建议将每个JSON文件保存的页面数设置到3000条以下。

2. 可以通过http://localhost:9200/_cat/indices查看Elasticsearch读取文档数量，有助于管理Elasticsearch集群中的索引。如下图所示，

   <img src=".\pages\f880a933c626d0ca81e64c54f81d2a2.png" alt="f880a933c626d0ca81e64c54f81d2a2" style="zoom: 33%;" />

   - **green**：索引健康，主分片和副本分片正常，数据分布均衡无问题，可正常读写。

   - **yellow**：主分片已分配，至少一个副本分片未分配，数据可读写但有一定风险。

   - **red**：主分片有丢失，数据可能部分不可用，需紧急修复。 

   - `open my_index`：`open`表示索引可读写，`my_index`是索引名。

   - `RfCBLYrURPelWXmH2lU7aA`：索引的唯一标识符（UUID） 

   - `1 0 101915 0 3.7gb 3.7gb 3.7gb`：101915为文档数量、4.1gb为索引占用磁盘空间（含义可能因版本等因素有别，仅供参考）。
