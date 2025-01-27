import os
import ijson
import time
from elasticsearch import Elasticsearch, helpers

# 连接 Elasticsearch
es = Elasticsearch(["http://localhost:9200"], verify_certs=False, request_timeout=360)

index_name = "my_index"
json_dir = r"E:\ir24\ir_lab4\ir4_code\JSON"

failed_files = ["mse.json"]  # 之前出错的文件列表

def generate_actions_from_large_file(file_path):
    with open(file_path, 'rb') as f:  # 以二进制模式打开文件
        try:
            for doc in ijson.items(f, "item"):
                if isinstance(doc, dict):
                    yield {"_index": index_name, "_source": doc}
        except Exception as e:
            print(f"Error parsing file '{file_path}': {e}")

def reindex_large_files():
    print("Re-indexing failed files...")
    for file_name in failed_files:
        file_path = os.path.join(json_dir, file_name)
        if not os.path.exists(file_path):
            print(f"File '{file_name}' does not exist, skipping...")
            continue

        print(f"Processing large file: {file_name}")
        start_time = time.time()  # 开始时间
        success, failed = 0, 0
        try:
            # streaming_bulk 会逐条发送文档，这里监控进度
            for i, (ok, action) in enumerate(
                helpers.streaming_bulk(
                    client=es,
                    actions=generate_actions_from_large_file(file_path),
                    chunk_size=200,  # 每批次 200 条文档
                    request_timeout=120
                )
            ):
                if ok:
                    success += 1
                else:
                    failed += 1

                # 每 500 条文档输出一次进度
                if i % 500 == 0:
                    print(f"Progress: {i} documents processed, {success} successes, {failed} failures.")

            elapsed_time = time.time() - start_time  # 结束时间
            print(f"File '{file_name}' completed: {success} successes, {failed} failures in {elapsed_time:.2f} seconds.")

        except Exception as e:
            print(f"Error processing file '{file_name}': {e}")

if __name__ == "__main__":
    reindex_large_files()
