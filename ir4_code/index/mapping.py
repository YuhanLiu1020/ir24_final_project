# mapping.py
from elasticsearch import Elasticsearch

# 连接 Elasticsearch（无用户名密码）
es = Elasticsearch(["http://localhost:9200"], verify_certs=False, request_timeout=60)

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

# 删除已有的同名索引（可选）
if es.indices.exists(index=index_name):
    es.indices.delete(index=index_name)

# 创建索引
es.indices.create(index=index_name, body=settings)
print(f"Index '{index_name}' created with given mapping.")
