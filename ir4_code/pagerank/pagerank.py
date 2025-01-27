# pagerank.py
import json
import os
import networkx as nx

json_dir = r"E:\ir24\ir_lab4\ir4_code\JSON"

G = nx.DiGraph()

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

# 将结果写入JSON
output_file = 'pagerank_scores.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(sorted_url_scores, f, ensure_ascii=False, indent=4)

print(f"PageRank scores saved to {output_file}")
