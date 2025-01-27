from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"], verify_certs=False)

# 设置副本分片数为 0
es.indices.put_settings(
    index="my_index",
    body={
        "index": {
            "number_of_replicas": 0
        }
    }
)

print("副本分片已设置为 0，索引状态应变为 green。")
