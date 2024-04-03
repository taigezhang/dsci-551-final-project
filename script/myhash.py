import pandas as pd


# 定义哈希函数
def hash_function(artwork_id, total_shards=7):
    return artwork_id % total_shards


def split_dataset_into_shards(file_path, total_shards=7):
    # 读取CSV文件
    data = pd.read_csv(file_path)

    # 初始化7个分片的容器
    sharded_data = {i: [] for i in range(total_shards)}

    # 分配记录到7个小数据集中
    for _, row in data.iterrows():
        shard_id = hash_function(row['Artwork ID'], total_shards)
        sharded_data[shard_id].append(row)

    # 保存每个分片为CSV文件
    for shard_id, rows in sharded_data.items():
        df = pd.DataFrame(rows)
        file_name = f'./hash_datasets/artworks_shard_{shard_id}.csv'
        df.to_csv(file_name, index=False)
        print(f'Shard {shard_id} saved to {file_name}')


file_path = 'artworks.csv'

split_dataset_into_shards(file_path)
