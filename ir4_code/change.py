from elasticsearch import Elasticsearch

# 连接 Elasticsearch 服务
es = Elasticsearch(["http://localhost:9200"], verify_certs=False)

# 删除索引
index_name = "my_index"
if es.indices.exists(index=index_name):
    es.indices.delete(index=index_name, ignore=[400, 404])
    print(f"索引 {index_name} 删除成功！")
else:
    print(f"索引 {index_name} 不存在，无需删除。")
