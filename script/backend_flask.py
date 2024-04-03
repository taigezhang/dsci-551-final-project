from flask import Flask, request, jsonify
import pymysql
import hashlib

app = Flask(__name__)

# 数据库连接配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'artwork',
    'password': 'Tang2241',
    'charset': 'utf8mb4'
}

# 分片数量
SHARD_COUNT = 7

def get_shard_id(artwork_id):
    return artwork_id % SHARD_COUNT


def get_db_connection(shard_id):
    # 根据shard_id获取数据库连接
    db_name = f'shard{shard_id}'
    conn = pymysql.connect(database=db_name, **DB_CONFIG)
    print(f"Connected to database: {db_name}")  # 打印成功连接到哪个数据库
    return conn

@app.route('/artworks/<int:artwork_id>', methods=['GET'])
def get_artwork(artwork_id):
    shard_id = get_shard_id(artwork_id)
    print(f"Fetching artwork with ID {artwork_id} from shard {shard_id}")  # 显示从哪个分片获取数据
    conn = get_db_connection(shard_id)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute('SELECT * FROM artworks WHERE `Artwork ID` = %s', (artwork_id,))
    artwork = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(artwork) if artwork else ('Artwork not found', 404)


@app.route('/artworks', methods=['POST'])
def insert_artwork():
    data = request.json
    artwork_id = data['Artwork ID']
    shard_id = get_shard_id(artwork_id)
    print(f"Inserting artwork with ID {artwork_id} into shard {shard_id}")
    conn = get_db_connection(shard_id)
    cursor = conn.cursor()

    # Ensure column names are properly escaped
    columns = ', '.join([f"`{key}`" for key in data.keys()])
    placeholders = ', '.join(['%s'] * len(data))
    sql = f"INSERT INTO artworks ({columns}) VALUES ({placeholders})"

    cursor.execute(sql, list(data.values()))
    conn.commit()
    cursor.close()
    conn.close()
    return ('Artwork inserted', 201)


@app.route('/artworks/<int:artwork_id>', methods=['PUT'])
def update_artwork(artwork_id):
    data = request.json
    shard_id = get_shard_id(artwork_id)
    print(f"Updating artwork with ID {artwork_id} in shard {shard_id}")
    conn = get_db_connection(shard_id)
    cursor = conn.cursor()
    update_statement = ', '.join([f"{key} = %s" for key in data.keys()])
    sql = f"UPDATE artworks SET {update_statement} WHERE `Artwork ID` = {artwork_id}"
    cursor.execute(sql, list(data.values()))
    conn.commit()
    cursor.close()
    conn.close()
    return ('Artwork updated', 200)

@app.route('/artworks/<int:artwork_id>', methods=['DELETE'])
def delete_artwork(artwork_id):
    shard_id = get_shard_id(artwork_id)
    print(f"Deleting artwork with ID {artwork_id} from shard {shard_id}")
    conn = get_db_connection(shard_id)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM artworks WHERE `Artwork ID` = %s', (artwork_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return ('Artwork deleted', 200)


@app.route('/artworks/artist/<int:artist_id>', methods=['GET'])
def get_artworks_by_artist(artist_id):
    artworks = []
    for shard_id in range(SHARD_COUNT):
        conn = get_db_connection(shard_id)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('SELECT * FROM artworks WHERE `Artist ID` = %s', (artist_id,))
        artworks.extend(cursor.fetchall())
        cursor.close()
        conn.close()

    count = len(artworks)  # 计算总共查询到的艺术品数量
    if artworks:
        return jsonify({'count': count, 'artworks': artworks})
    else:
        return ('No artworks found for artist', 404)



if __name__ == '__main__':
    app.run(debug=True)
