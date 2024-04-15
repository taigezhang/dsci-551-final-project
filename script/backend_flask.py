from flask import Flask, render_template, request, redirect, url_for, jsonify, session

import pymysql
import datetime
import hashlib

app = Flask(__name__)
app.secret_key = "123456"

admin_user = "admin"
admin_password = "admin"

# 数据库连接配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'password',
    'charset': 'utf8mb4'
}

# 分片数量
SHARD_COUNT = 7


def get_shard_id(artwork_id):
    return artwork_id % SHARD_COUNT


def get_shard_db_connection(shard_id):
    # 根据shard_id获取数据库连接
    db_name = f'shard{shard_id}'
    conn = pymysql.connect(database=db_name, **DB_CONFIG)
    print(f"Connected to database: {db_name}")  # 打印成功连接到哪个数据库
    return conn


def get_artist_db_connection():
    db_name = 'artist'
    conn = pymysql.connect(database=db_name, **DB_CONFIG)
    print(f"Connected to database: {db_name}")  # 打印成功连接到哪个数据库
    return conn


def get_user_type():
    if "user" in session:
        return "admin"
    return "normal"


@app.route("/login", methods=['GET'])
def get_login():
    return render_template("login.html")


@app.route("/logout", methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route("/login", methods=['POST'])
def post_login():
    username = request.form.get("username").strip()
    password = request.form.get("password").strip()
    if username == admin_user and password == admin_password:
        session["user"] = "admin"
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/")
def index():
    return render_template("index.html", user_type=get_user_type())


@app.route("/artists/new")
def get_new_artist():
    return render_template("artist_new.html", user_type=get_user_type())


@app.route("/artworks/new")
def get_new_artwork():
    return render_template("artwork_new.html", user_type=get_user_type())


@app.route("/search/artist", methods=["POST", "GET"])
def search_by_artist():
    name = request.form.get("name").strip()
    conn = get_artist_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute('SELECT * FROM artist WHERE `name` = %s', (name,))
    artist = cursor.fetchone()
    cursor.close()
    conn.close()
    if artist:
        calculate_age(artist)

        artworks = get_artworks_by_artist(artist["artist_id"])
        return render_template("artist.html", info=artist, user_type=get_user_type(), artworks=artworks)
    else:
        return render_template("error.html", error_msg="There is no such artist")


@app.route("/search/artwork", methods=["POST"])
def search_by_artwork():
    name = request.form.get("name").strip()
    artworks = []
    id_set = {}
    for shard_id in range(SHARD_COUNT):
        conn = get_shard_db_connection(shard_id)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('SELECT * FROM artworks WHERE `Name` = %s', (name,))
        shard_res = cursor.fetchall()
        if shard_res:
            for work in shard_res:
                if work['Artwork ID'] not in id_set:
                    id_set[work['Artwork ID']] = 1
                    artworks.append(work)
        cursor.close()
        conn.close()

    print(artworks)
    if len(artworks) > 0:
        return render_template("artwork.html", user_type=get_user_type(), artworks=artworks)
    else:
        return render_template("error.html", error_msg="There is no such artwork")


def calculate_age(artist):
    if artist["birth_year"] > 0:
        if artist["death_year"] > 0:
            age = artist["death_year"] - artist["birth_year"]
        else:
            artist["death_year"] = "Unknown"
            age = datetime.datetime.now().year - artist["birth_year"]
    else:
        age = 0

    artist["age"] = age


@app.route('/artist/')
def get_artist():
    artist_id = int(request.args.get("artist_id"))
    print(f"Fetching artist with ID {artist_id}")
    conn = get_artist_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute('SELECT * FROM artist WHERE `artist_id` = %s', (artist_id,))
    artist = cursor.fetchone()
    cursor.close()
    conn.close()
    if artist:
        calculate_age(artist)
        artworks = get_artworks_by_artist(artist["artist_id"])

        return render_template("artist.html", info=artist, user_type=get_user_type(), artworks=artworks)
    else:
        return render_template("error.html", error_msg="There is no such artwork")


@app.route('/artworks/')
def get_artwork():
    artwork_id = int(request.args.get("artwork_id"))
    shard_id = get_shard_id(artwork_id)
    print(f"Fetching artwork with ID {artwork_id} from shard {shard_id}")  # 显示从哪个分片获取数据
    conn = get_shard_db_connection(shard_id)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute('SELECT * FROM artworks WHERE `Artwork ID` = %s', (artwork_id,))
    artwork = cursor.fetchone()
    cursor.close()
    conn.close()
    if artwork:
        return render_template("artwork.html", user_type=get_user_type(), artworks=[artwork])
    else:
        return render_template("error.html", error_msg="There is no such artwork")


@app.route('/artworks/update', methods=['POST'])
def update_artwork():
    data = {
        "Name": request.form.get("name"),
        "Title": request.form.get("title"),
        "Dimensions": request.form.get("dimensions"),
        "Date": request.form.get("date"),
        "Classification": request.form.get("classification"),
        "Medium": request.form.get("medium"),
        "Acquisition Date": request.form.get("acquisitionDate"),
    }
    artwork_id = int(request.form.get("artwork_id"))
    shard_id = get_shard_id(artwork_id)

    print(f"Updating artwork with ID {artwork_id} in shard {shard_id}")
    conn = get_shard_db_connection(shard_id)
    cursor = conn.cursor()
    # update_statement = ', '.join([f"`{key}`='{value}'" for key, value in data.items()])
    update_statement = ', '.join([f"`{key}`=%s" for key, value in data.items()])

    sql = f"UPDATE artworks SET {update_statement} WHERE `Artwork ID` = {artwork_id}"
    cursor.execute(sql, list(data.values()))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('get_artwork', artwork_id=artwork_id))


@app.route('/artists/new', methods=['POST'])
def new_artist():
    name = request.form.get("name"),
    nationality = request.form.get("nationality"),
    gender = request.form.get("gender"),
    birth_year = request.form.get("birthYear"),
    death_year = request.form.get("deathYear")
    print(f"create new artist")
    conn = get_artist_db_connection()
    cursor = conn.cursor()
    sql = "insert into artist(name, nationality, gender, birth_year, death_year) values (%s, %s, %s, %s, %s)"
    try:
        cursor.execute(sql, [name, nationality, gender, birth_year, death_year])
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        return render_template("error.html", error_msg="Failed to create new artist, " + str(e))

    return redirect(url_for('index'))



@app.route('/artworks/new', methods=['POST'])
def new_artwork():
    artwork_id = int(request.form.get("artwork_id"))
    artist_id = request.form.get("artist_id")
    name = request.form.get("name")
    title = request.form.get("title")
    dimensions = request.form.get("dimensions")
    date_val = request.form.get("date")
    classification = request.form.get("classification")
    medium = request.form.get("medium")
    acquisition_date = request.form.get("acquisitionDate")

    shard_id = get_shard_id(artwork_id)

    print(f"create artwork with ID {artwork_id} in shard {shard_id}")
    conn = get_shard_db_connection(shard_id)
    cursor = conn.cursor()
    sql = ("insert into artworks(`Artwork ID`, `Name`, `Title`, `Artist ID`, `Dimensions`, `Date`, `Classification`, `Medium`, `Acquisition Date`)"
           " values (%s, %s, %s, %s, %s, %s, %s, %s, %s)")
    try:
        cursor.execute(sql, [artwork_id, name, title, artist_id, dimensions, date_val, classification, medium, acquisition_date])
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        return render_template("error.html", error_msg="Failed to create new artwork, " + str(e))

    return redirect(url_for('index'))



@app.route('/artists/update', methods=['POST'])
def update_artist():
    data = {
        "name": request.form.get("name"),
        "nationality": request.form.get("nationality"),
        "gender": request.form.get("gender"),
        "birth_year": request.form.get("birthYear"),
        "death_year": request.form.get("deathYear")
    }
    artist_id = int(request.form.get("artist_id"))
    print(f"Updating aritst with ID {artist_id}")
    conn = get_artist_db_connection()
    cursor = conn.cursor()
    update_statement = ', '.join([f"{key} = %s" for key in data.keys()])
    sql = f"UPDATE artist SET {update_statement} WHERE `artist_id` = {artist_id}"
    cursor.execute(sql, list(data.values()))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('get_artist', artist_id=artist_id))


@app.route('/artworks', methods=['POST'])
def insert_artwork():
    data = request.json
    artwork_id = data['Artwork ID']
    shard_id = get_shard_id(artwork_id)
    print(f"Inserting artwork with ID {artwork_id} into shard {shard_id}")
    conn = get_shard_db_connection(shard_id)
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


@app.route('/artworks/delete/<int:artwork_id>', methods=['GET'])
def delete_artwork(artwork_id):
    shard_id = get_shard_id(artwork_id)
    print(f"Deleting artwork with ID {artwork_id} from shard {shard_id}")
    conn = get_shard_db_connection(shard_id)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM artworks WHERE `Artwork ID` = %s', (artwork_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("index"))


@app.route('/artists/delete/<int:artist_id>', methods=['GET'])
def delete_artist(artist_id):
    print(f"Deleting artist with ID {artist_id}")
    conn = get_artist_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM artist WHERE `artist_id` = %s', (artist_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("index"))


def get_artworks_by_artist(artist_id):
    artworks = []
    for shard_id in range(SHARD_COUNT):
        conn = get_shard_db_connection(shard_id)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('SELECT * FROM artworks WHERE `Artist ID` = %s', (artist_id,))
        artworks.extend(cursor.fetchall())
        cursor.close()
        conn.close()
    return artworks


if __name__ == '__main__':
    app.run(debug=True)
