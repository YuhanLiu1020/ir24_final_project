import json
import os
from elasticsearch import Elasticsearch, helpers
from elasticsearch.helpers import BulkIndexError

# 连接 Elasticsearch
es = Elasticsearch(["http://localhost:9200"], verify_certs=False, request_timeout=360)

index_name = "my_index"
json_dir = r"E:\ir24\ir_lab4\ir4_code\JSON\government_output"

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
