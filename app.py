from flask import Flask
from flask_cors import CORS
import pymysql
import joblib
from flask import request, jsonify
import re
from functools import wraps


app = Flask(__name__)
CORS(app)  # 允许跨域请求


# 数据库配置
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Jyx10.25!!!',  # 替换为你的数据库密码
    'database': 'house_db',
    'cursorclass': pymysql.cursors.DictCursor,
}

# 连接数据库
def get_db_connection():
    return pymysql.connect(**db_config)

# 用户注册
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 0)  # 默认是普通用户

    if not username or not email or not password:
        return jsonify({"success": False, "message": "请填写完整信息"}), 400

    connection = None  # 初始化 connection 变量
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # 检查邮箱是否已注册
            sql = "SELECT * FROM users WHERE email = %s"
            cursor.execute(sql, (email,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "邮箱已注册"}), 400

            # 插入新用户
            sql = """
                INSERT INTO users (username, email, password, is_admin)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (username, email, password, role))
            connection.commit()
            return jsonify({"success": True, "message": "注册成功"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection:  # 检查 connection 是否已赋值
            connection.close()

# 用户登录
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 0)

    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE email = %s AND password = %s AND is_admin = %s"
            cursor.execute(sql, (email, password, role))
            user = cursor.fetchone()
            if user:
                return jsonify({"success": True, "message": "登录成功", "user_id": user['user_id'], "is_admin": user['is_admin']})
            else:
                return jsonify({"success": False, "message": "邮箱或密码错误"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection:
            connection.close()

models = {
    'random_forest': joblib.load('model/random_forest_model.pkl'),
    'xgboost': joblib.load('model/xgb_model.pkl'),
    'GBDT': joblib.load('model/gbr_model.pkl'),
    'decision_tree': joblib.load('model/decision_tree_model.pkl'),
    'svm': joblib.load('model/svm_model.pkl')
}


# 获取特征重要性
def get_feature_importance(model, feature_names):
    if hasattr(model, 'feature_importances_'):
        return dict(zip(feature_names, model.feature_importances_))
    return None


# 保存房屋信息
@app.route('/api/save-house', methods=['POST'])
def save_house():
    data = request.json
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO houses 
                (area, rooms, halls, kitchens, restroom,street, decoration, floor, heating)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s ,%s)
            """
            cursor.execute(sql, (
                data['area'], data['rooms'], data['halls'], data['kitchens'],data['restroom'],
                data['street'], data['decoration'], data['floor'], data['heating']
            ))
            house_id = cursor.lastrowid
            connection.commit()
            return jsonify({"success": True, "house_id": house_id})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection: connection.close()


# 房价预测
@app.route('/api/predict', methods=['POST'])
def predict():
    data = request.json

    # 准备特征数据（与训练时完全一致的结构）
    features = {
        '建筑面积': data['area'],
        '室': data['rooms'],
        '厅': data['halls'],
        '厨': data['kitchens'],
        '卫': data['restroom'],
        # 以下字段需要设置为0或1
        '浦口 南京工业大学': 0,
        '浦口 南审': 0,
        '浦口 天润城': 0,
        '浦口 弘阳广场': 0,
        '浦口 柳州东路': 0,
        '浦口 江北中央商务区': 0,
        '浦口 江北研创园': 0,
        '浦口 江浦街道': 0,
        '浦口 泰山街道': 0,
        '浦口 浦口其它': 0,
        '浦口 海峡科技城': 0,
        '浦口 澳林广场': 0,
        '浦口 高新区': 0,
        '其他': 0,
        '毛坯': 0,
        '简装': 0,
        '精装': 0,
        '中楼层': 0,
        '低楼层': 0,
        '地下室': 0,
        '高楼层': 0,
        '无': 0,
        '暂无数据': 0,
        '有': 0
    }

    # 根据用户选择设置对应的特征为1
    features[f"{data['street']}"] = 1
    features[f"{data['decoration']}"] = 1
    features[f"{data['floor']}"] = 1
    features[f"{data['heating']}"] = 1

    # 转换为模型需要的格式
    feature_names = [
        '建筑面积', '室', '厅', '厨','卫', '浦口 南京工业大学', '浦口 南审', '浦口 天润城',
        '浦口 弘阳广场', '浦口 柳州东路', '浦口 江北中央商务区', '浦口 江北研创园',
        '浦口 江浦街道', '浦口 泰山街道', '浦口 浦口其它', '浦口 海峡科技城',
        '浦口 澳林广场', '浦口 高新区', '其他', '毛坯', '简装', '精装', '中楼层',
        '低楼层', '地下室', '高楼层', '无', '暂无数据', '有'
    ]

    feature_values = [features[name] for name in feature_names]
    # 取模型类型，如果没有给就默认 random_forest
    model= data.get('model', 'random_forest')

    # 找到对应模型
    selected_model = models.get(model)
    if not selected_model:
        return jsonify({"success": False, "message": "模型类型无效"}), 400

    # 进行预测
    prediction = selected_model.predict([feature_values])[0]

    return jsonify({
        "success": True,
        "prediction": float(prediction),
        "model": model  # 返回模型类型
    })


# 保存预测记录
@app.route('/api/save-prediction', methods=['POST'])
def save_prediction():
    data = request.json
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO predictions 
                (user_id, house_id, predicted_price,model)
                VALUES (%s, %s, %s,%s)
            """
            cursor.execute(sql, (
                data['user_id'], data['house_id'], data['predicted_price'],data['model']
            ))
            connection.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection: connection.close()


# 获取用户预测记录
@app.route('/api/user-predictions', methods=['GET'])
def get_user_predictions():
    user_id = request.args.get('user_id')
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                SELECT p.*, h.*, p.model 
                FROM predictions p
                JOIN houses h ON p.house_id = h.house_id
                WHERE p.user_id = %s
                ORDER BY p.created_at DESC
            """
            cursor.execute(sql, (user_id,))
            results = cursor.fetchall()

            # 转换日期格式
            for result in results:
                if 'created_at' in result and result['created_at']:
                    result['created_at'] = result['created_at'].strftime('%Y-%m-%d %H:%M:%S')

            return jsonify({"success": True, "predictions": results})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection: connection.close()


# 更新用户资料
@app.route('/api/update-profile', methods=['POST'])
def update_profile():
    data = request.json
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # 更新用户名
            if data.get('username'):
                sql = "UPDATE users SET username = %s WHERE user_id = %s"
                cursor.execute(sql, (data['username'], data['user_id']))

            # 更新密码
            if data.get('password'):
                sql = "UPDATE users SET password = %s WHERE user_id = %s"
                cursor.execute(sql, (data['password'], data['user_id']))

            connection.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection: connection.close()

# 获取用户信息
@app.route('/api/user-info', methods=['GET'])
def get_user_info():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"success": False, "message": "需要用户ID"}), 400

    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                SELECT user_id, username, email, is_admin 
                FROM users 
                WHERE user_id = %s
            """
            cursor.execute(sql, (user_id,))
            user = cursor.fetchone()

            if user:
                return jsonify({
                    "success": True,
                    "user": {
                        "user_id": user['user_id'],
                        "username": user['username'],
                        "email": user['email'],
                        "is_admin": user['is_admin']
                    }
                })
            return jsonify({"success": False, "message": "用户不存在"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection:
            connection.close()


# 修改管理员权限检查装饰器
def admin_required(f):
    @wraps(f)  # 保留原始函数信息
    def wrapper(*args, **kwargs):
        # 从请求参数中获取user_id（GET请求）或JSON body中获取（POST/PUT/DELETE）
        user_id = request.args.get('user_id') or (request.json and request.json.get('user_id'))

        if not user_id:
            return jsonify({"success": False, "message": "需要提供用户ID"}), 401

        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT is_admin FROM users WHERE user_id = %s", (user_id,))
                user = cursor.fetchone()
                if not user or user['is_admin'] != 1:
                    return jsonify({"success": False, "message": "需要管理员权限"}), 403
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            if conn: conn.close()

        return f(*args, **kwargs)

    return wrapper


# 管理员获取分析数据
@app.route('/api/admin/analytics', methods=['GET'])
@admin_required
def admin_analytics():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 户型分布
            cursor.execute("""
                SELECT CONCAT(rooms, '室', halls, '厅', kitchens, '厨',restroom, '卫') AS room_type, 
                       COUNT(*) AS count 
                FROM houses 
                GROUP BY room_type
            """)
            room_dist = {row['room_type']: row['count'] for row in cursor.fetchall()}

            # 区域分布
            cursor.execute("""
                SELECT street, COUNT(*) AS count 
                FROM houses 
                GROUP BY street
            """)
            area_dist = {row['street']: row['count'] for row in cursor.fetchall()}

            # 面积分布
            cursor.execute("""
                SELECT FLOOR(area/10)*10 AS size_group, 
                       COUNT(*) AS count 
                FROM houses 
                GROUP BY size_group 
                ORDER BY size_group
            """)
            size_dist = {f"{row['size_group']}-{row['size_group'] + 9}": row['count'] for row in cursor.fetchall()}

            # 装修情况
            cursor.execute("""
                SELECT decoration, COUNT(*) AS count 
                FROM houses 
                GROUP BY decoration
            """)
            decor_dist = {row['decoration']: row['count'] for row in cursor.fetchall()}

            return jsonify({
                "success": True,
                "data": {
                    "roomDistribution": room_dist,
                    "areaDistribution": area_dist,
                    "sizeDistribution": size_dist,
                    "decorationDistribution": decor_dist
                }
            })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


# 管理员获取用户列表
@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, username, email, is_admin FROM users")
            users = cursor.fetchall()
            return jsonify({"success": True, "users": users})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


# 管理员删除用户
@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    current_user_id = request.args.get('user_id')
    if str(user_id) == current_user_id:
        return jsonify({"success": False, "message": "不能删除当前登录用户"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 1. 先获取该用户的所有预测记录关联的house_id
            cursor.execute("SELECT house_id FROM predictions WHERE user_id = %s", (user_id,))
            house_ids = [row['house_id'] for row in cursor.fetchall()]

            # 2. 删除用户的所有预测记录（外键约束可能已自动处理）
            cursor.execute("DELETE FROM predictions WHERE user_id = %s", (user_id,))

            # 3. 删除关联的房屋信息
            if house_ids:
                cursor.execute("DELETE FROM houses WHERE house_id IN %s", (tuple(house_ids),))

            # 4. 最后删除用户
            cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))

            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


# 管理员修改用户权限
@app.route('/api/admin/users/<int:user_id>/admin', methods=['PUT'])
@admin_required
def admin_toggle_admin(user_id):
    current_user_id = request.json.get('user_id')
    if str(user_id) == current_user_id:
        return jsonify({"success": False, "message": "不能修改自己的权限"}), 400

    is_admin = request.json.get('is_admin', False)

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET is_admin = %s WHERE user_id = %s",
                (1 if is_admin else 0, user_id)
            )
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


# 街道管理接口
@app.route('/api/streets', methods=['GET'])
def get_streets():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            print("正在执行SQL查询")  # 调试日志
            cursor.execute("SELECT * FROM streets ORDER BY street_id")
            streets = cursor.fetchall()
            print("查询结果:", streets)  # 调试日志
            return jsonify({"success": True, "data": streets})
    except Exception as e:
        print("发生错误:", str(e))  # 错误日志
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/streets', methods=['POST'])
@admin_required
def add_street():
    """新增街道"""
    data = request.json
    if not data.get('street_name'):
        return jsonify({"success": False, "message": "街道名称不能为空"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO streets (street_name) VALUES (%s)",
                (data['street_name'],)
            )
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/streets/<int:street_id>', methods=['PUT'])
@admin_required
def update_street(street_id):
    """修改街道"""
    data = request.json
    if not data.get('street_name'):
        return jsonify({"success": False, "message": "街道名称不能为空"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE streets SET street_name = %s WHERE street_id = %s",
                (data['street_name'], street_id)
            )
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "街道不存在"}), 404
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/streets/<int:street_id>', methods=['DELETE'])
@admin_required
def delete_street(street_id):
    """删除街道"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 检查是否有房屋关联该街道
            cursor.execute("SELECT COUNT(*) FROM houses WHERE street = %s", (street_id,))
            if cursor.fetchone()['COUNT(*)'] > 0:
                return jsonify({"success": False, "message": "有房屋关联此街道，无法删除"}), 400

            cursor.execute("DELETE FROM streets WHERE street_id = %s", (street_id,))
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "街道不存在"}), 404
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


# 装修管理接口
@app.route('/api/decorations', methods=['GET'])
def get_decorations():
    """获取所有装修选项"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM decorations ORDER BY decoration_id")
            decorations = cursor.fetchall()
            return jsonify({"success": True, "data": decorations})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/decorations', methods=['POST'])
@admin_required
def add_decoration():
    """新增装修类型"""
    data = request.json
    if not data.get('decoration_name'):
        return jsonify({"success": False, "message": "装修类型名称不能为空"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO decorations (decoration_name) VALUES (%s)",
                (data['decoration_name'],)
            )
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/decorations/<int:decoration_id>', methods=['PUT'])
@admin_required
def update_decoration(decoration_id):
    """修改装修类型"""
    data = request.json
    if not data.get('decoration_name'):
        return jsonify({"success": False, "message": "装修类型名称不能为空"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE decorations SET decoration_name = %s WHERE decoration_id = %s",
                (data['decoration_name'], decoration_id)
            )
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "装修类型不存在"}), 404
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/decorations/<int:decoration_id>', methods=['DELETE'])
@admin_required
def delete_decoration(decoration_id):
    """删除装修类型"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 检查是否有房屋关联该装修类型
            cursor.execute("SELECT COUNT(*) FROM houses WHERE decoration = %s", (decoration_id,))
            if cursor.fetchone()['COUNT(*)'] > 0:
                return jsonify({"success": False, "message": "有房屋关联此装修类型，无法删除"}), 400

            cursor.execute("DELETE FROM decorations WHERE decoration_id = %s", (decoration_id,))
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "装修类型不存在"}), 404
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


# 楼层管理接口
@app.route('/api/floors', methods=['GET'])
def get_floors():
    """获取所有楼层选项"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM floors ORDER BY floor_id")
            floors = cursor.fetchall()
            return jsonify({"success": True, "data": floors})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/floors', methods=['POST'])
@admin_required
def add_floor():
    """新增楼层类型"""
    data = request.json
    if not data.get('floor_name'):
        return jsonify({"success": False, "message": "楼层类型名称不能为空"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO floors (floor_name) VALUES (%s)",
                (data['floor_name'],)
            )
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/floors/<int:floor_id>', methods=['PUT'])
@admin_required
def update_floor(floor_id):
    """修改楼层类型"""
    data = request.json
    if not data.get('floor_name'):
        return jsonify({"success": False, "message": "楼层类型名称不能为空"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE floors SET floor_name = %s WHERE floor_id = %s",
                (data['floor_name'], floor_id)
            )
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "楼层类型不存在"}), 404
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/floors/<int:floor_id>', methods=['DELETE'])
@admin_required
def delete_floor(floor_id):
    """删除楼层类型"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 检查是否有房屋关联该楼层类型
            cursor.execute("SELECT COUNT(*) FROM houses WHERE floor = %s", (floor_id,))
            if cursor.fetchone()['COUNT(*)'] > 0:
                return jsonify({"success": False, "message": "有房屋关联此楼层类型，无法删除"}), 400

            cursor.execute("DELETE FROM floors WHERE floor_id = %s", (floor_id,))
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "楼层类型不存在"}), 404
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


# 供暖管理接口
@app.route('/api/heatings', methods=['GET'])
def get_heatings():
    """获取所有供暖选项"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM heatings ORDER BY heating_id")
            heatings = cursor.fetchall()
            return jsonify({"success": True, "data": heatings})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/heatings', methods=['POST'])
@admin_required
def add_heating():
    """新增供暖类型"""
    data = request.json
    if not data.get('heating_name'):
        return jsonify({"success": False, "message": "供暖类型名称不能为空"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO heatings (heating_name) VALUES (%s)",
                (data['heating_name'],)
            )
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/heatings/<int:heating_id>', methods=['PUT'])
@admin_required
def update_heating(heating_id):
    """修改供暖类型"""
    data = request.json
    if not data.get('heating_name'):
        return jsonify({"success": False, "message": "供暖类型名称不能为空"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE heatings SET heating_name = %s WHERE heating_id = %s",
                (data['heating_name'], heating_id)
            )
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "供暖类型不存在"}), 404
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/heatings/<int:heating_id>', methods=['DELETE'])
@admin_required
def delete_heating(heating_id):
    """删除供暖类型"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 检查是否有房屋关联该供暖类型
            cursor.execute("SELECT COUNT(*) FROM houses WHERE heating = %s", (heating_id,))
            if cursor.fetchone()['COUNT(*)'] > 0:
                return jsonify({"success": False, "message": "有房屋关联此供暖类型，无法删除"}), 400

            cursor.execute("DELETE FROM heatings WHERE heating_id = %s", (heating_id,))
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "供暖类型不存在"}), 404
            conn.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


# 房价数据展示接口
def extract_number(text):
    """增强的数字提取，支持中文和阿拉伯数字"""
    cn_num = {
        '一': 1, '两': 2, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
    }

    # 检查中文数字
    for cn, val in cn_num.items():
        if cn in text:
            return val

    # 提取阿拉伯数字
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 0


def convert_time_text_to_months(time_text):
    """精确转换中文时间文本为月份数"""
    if not time_text:
        return float('inf')

    # 统一清理文本
    clean_text = time_text.replace("发布", "").replace("以前", "").replace("前", "").strip()

    # 获取数值
    num = extract_number(clean_text)

    # 根据单位转换
    if '天' in clean_text:
        return 0 if num <= 30 else 1
    elif '个月' in clean_text or '月' in clean_text:
        return num
    elif '年' in clean_text:
        return num * 12
    else:
        return float('inf')


@app.route('/api/houses', methods=['GET'])
def get_houses():
    try:
        # 获取参数
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        months = request.args.get('months', '')
        address = request.args.get('address', '')
        user_id = request.args.get('user_id')

        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 获取所有数据
            query = "SELECT * FROM house_data"
            params = []

            # 添加地址筛选条件
            if address:
                query += " WHERE address LIKE %s"
                params.append(f"%{address}%")

            cursor.execute(query, params)
            all_houses = cursor.fetchall()

            # 应用时间筛选
            filtered_houses = []
            for house in all_houses:
                time_text = house.get('publish_time', '')
                house_months = convert_time_text_to_months(time_text)

                if not months:
                    filtered_houses.append(house)
                else:
                    months_int = int(months)
                    if house_months <= months_int:
                        filtered_houses.append(house)

            # 按时间排序（从新到旧）
            filtered_houses.sort(
                key=lambda x: convert_time_text_to_months(x.get('publish_time', '')))

            # 分页处理
            total = len(filtered_houses)
            total_pages = max(1, (total + per_page - 1) // per_page)
            start = (page - 1) * per_page
            end = start + per_page
            paged_houses = filtered_houses[start:end]

            # 检查收藏状态
            if user_id:
                cursor.execute(
                    "SELECT house_id FROM favorites WHERE user_id = %s",
                    (user_id,)
                )
                favorites = {row['house_id'] for row in cursor.fetchall()}
                for house in paged_houses:
                    house['is_favorited'] = house['id'] in favorites

            return jsonify({
                "success": True,
                "houses": paged_houses,
                "total_pages": total_pages,
                "total_count": total
            })

    except Exception as e:
        app.logger.error(f"API错误: {str(e)}")
        return jsonify({
            "success": False,
            "message": "服务器内部错误"
        }), 500
    finally:
        if 'conn' in locals():
            conn.close()


# 收藏功能
@app.route('/api/toggle-favorite', methods=['POST'])
def toggle_favorite():
    """添加或移除收藏"""
    data = request.json
    user_id = data.get('user_id')
    house_id = data.get('house_id')
    action = data.get('action')  # 'add' or 'remove'

    if not user_id or not house_id or not action:
        return jsonify({"success": False, "message": "参数不完整"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 检查房屋是否存在
            cursor.execute("SELECT 1 FROM house_data WHERE id = %s", (house_id,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": "房源不存在"}), 404

            if action == 'add':
                # 添加收藏
                cursor.execute("""
                    INSERT INTO favorites (user_id, house_id)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE id=id
                """, (user_id, house_id))
                conn.commit()
                return jsonify({"success": True})

            elif action == 'remove':
                # 移除收藏
                cursor.execute("""
                    DELETE FROM favorites 
                    WHERE user_id = %s AND house_id = %s
                """, (user_id, house_id))
                conn.commit()
                return jsonify({
                    "success": True,
                    "deleted": cursor.rowcount > 0
                })

            else:
                return jsonify({"success": False, "message": "无效操作"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/user-favorites', methods=['GET'])
def get_user_favorites():
    """获取用户收藏列表"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"success": False, "message": "需要用户ID"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT f.id, h.id AS house_id, h.title AS house_title, 
                       h.community AS house_community, h.address AS house_address, 
                       h.total_price AS house_price, h.unit_price AS house_unit_price,
                       h.layout AS house_layout, h.floor AS house_floor,
                       h.area AS house_area, h.decoration AS house_decoration,
                       h.heating AS house_heating
                FROM favorites f
                JOIN house_data h ON f.house_id = h.id
                WHERE f.user_id = %s
                ORDER BY f.created_at DESC
            """, (user_id,))
            favorites = cursor.fetchall()
            return jsonify({"success": True, "favorites": favorites})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/remove-favorite', methods=['POST'])
def remove_favorite():
    """删除收藏"""
    data = request.json
    user_id = data.get('user_id')
    favorite_id = data.get('favorite_id')

    if not user_id or not favorite_id:
        return jsonify({"success": False, "message": "参数不完整"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM favorites 
                WHERE id = %s AND user_id = %s
            """, (favorite_id, user_id))
            conn.commit()
            return jsonify({
                "success": True,
                "deleted": cursor.rowcount > 0
            })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    app.run(debug=True)