from flask import Flask, jsonify, request, send_from_directory, redirect
import yaml, os, uuid, datetime, requests, random, time, threading
# Setting 
with open('data/config.yml', encoding='utf-8') as f:
    config = yaml.safe_load(f)
remote_oj = config['remote_oj']
website_info = config['website_info']
cf_jsession = config['cf_jsession']
# Get API from /data/api.yml
with open('data/api.yml', encoding='utf-8') as f:
    common_api = yaml.safe_load(f)
# Define
status_list = {
    0 : "Accepted",
    1 : "Time Limit Exceeded",
    2 : "Memory Limit Exceeded",
    3 : "Runtime Error",
    4 : "System Error",
    5 : "Pending",
    6 : "Compiling",
    7 : "Judging",
    8 : "Partial Accepted",
    9 : "Submitting",
    10 : "Submitted Failed",
    -10 : "Not Submitted",
    -5 : "Submitted Unknown Result",
    -4 : "Canceled",
    -3 : "Presentation Error",
    -2 : "Compile Error",
    -1 : "Wrong Answer"
}    
common_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "DNT": "1",
    "Pragma": "no-cache",
    "Referer": remote_oj,
    "URL-Type": "general"
}
# Code
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'data', 'config.yml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
            # 配置项合法性校验
            required_keys = ['remote_oj', 'website_info', 'cf_jsession']
            for key in required_keys:
                if key not in config:
                    raise ValueError(f'Missing required config key: {key}')
            return config
    except Exception as e:
        print(f'[ERROR] 配置加载失败: {str(e)}')
        return {
            'remote_oj': 'http://ssf.hdoi.cn',
            'website_info': {
                'name': 'HOJOJ',
                'description': '通过合理利用（滥用）HOJ 的评测资源搭建的 OJ 平台',
                'version': '1.2.0',
                'author': 'longStone'
            },
            'cf_jsession': ''
        }

def save_config(config):
    config_path = os.path.join(os.path.dirname(__file__), 'data', 'config.yml')
    with open(config_path, 'w', encoding='utf-8', newline='\n') as f:
        yaml.dump(
            {
                'last_runid': config.get('last_runid', 0),
                'remote_oj': config['remote_oj'],
                'website_info': config['website_info'],
                'cf_jsession': config['cf_jsession']
            },
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False
        )

def load_users():
    user_file = os.path.join('data', 'user.yml')
    if os.path.exists(user_file):
        try:
            with open(user_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f'读取用户文件失败: {e}')
    return {}


# 生成token
def generate_token(username):
    token = str(uuid.uuid4())
    # 设置token过期时间为7天
    expire_date = datetime.datetime.now() + datetime.timedelta(days=7)
    return token, expire_date

# 加载token
def load_tokens():
    token_file = os.path.join('tmp', 'token.yml')

    if os.path.exists(token_file):
        try:
            with open(token_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or []
        except Exception as e:
            print(f'读取token文件失败: {e}')
    return []

# 保存token
def save_tokens(tokens):
    token_file = os.path.join('tmp', 'token.yml')

    try:
        with open(token_file, 'w', encoding='utf-8') as f:
            yaml.dump(tokens, f, allow_unicode=True)
        return True
    except Exception as e:
        print(f'保存token文件失败: {e}')
        return False

# 验证token
def validate_token(token):
    tokens = load_tokens()
    current_time = datetime.datetime.now()
    valid_tokens = []
    is_valid = False
    username = None

    for t in tokens:
        # 检查token是否过期
        expire_date = datetime.datetime.strptime(t['expire_date'], '%Y-%m-%d %H:%M:%S')
        if expire_date > current_time:
            valid_tokens.append(t)
            # 检查token是否匹配
            if t['token'] == token:
                is_valid = True
                username = t['username']
        # 过期的token会被自动过滤掉

    # 保存更新后的token列表（移除过期token）
    save_tokens(valid_tokens)
    return is_valid, username
def craw_submit(runid, pid, token, author):
    # 获取远程评测结果
    config = load_config()
    # 初始化last_runid
    if 'last_runid' not in config:
        config['last_runid'] = 0

    current_runid = config['last_runid'] + 1
    # 在成功获取数据后更新
    config['last_runid'] = current_runid
    save_config(config)
    while True:
        api_url = f'{remote_oj}{common_api["GetSubmission"]}?submitId={runid}'
        headers = common_headers
        headers['Authorization'] = token
        try:
            response = requests.get(api_url, headers=headers, timeout=10)

            data = response.json()
            print(data)

            
            # 解析评测结果
            submission = data['data']['submission']
            # 构造YAML条目
            entry = {
                'runid': current_runid,
                'pid': pid,
                'status': submission['status'],
                'timems': submission['time'],
                'memorykb': submission['memory'],
                # 显示 HOJOJ 用户名
                'author': author,
                'language': submission['language'],
                'score': submission['score'],
                'code': submission['code'],
                'createtime': submission['submitTime'].replace('T', ' ')[:19]
            }

            # 加载现有提交记录
            submission_file = os.path.join('data', 'submission.yml')
            existing = []
            if os.path.exists(submission_file):
                with open(submission_file, 'r') as f:
                    existing = yaml.safe_load(f) or []

            # 更新或添加记录
            found = False
            for idx, item in enumerate(existing):
                if item['runid'] == current_runid:
                    if item['status'] in (5,6,7):
                        existing[idx].update(entry)
                        found = True
                    break

            if not found:
                # 添加到最前面
                existing.insert(0, entry)

            # 没有爬完也要写入
            with open(submission_file, 'w') as f:
                yaml.dump(existing, f, allow_unicode=True)
        except Exception as e:
            return {'error': f'获取评测结果失败: {str(e)}'}
        if submission['status'] in (5,6,7):
            # 保持轮询直到最终状态
            time.sleep(1)
        else:
            # 写入YAML文件
            with open(submission_file, 'w') as f:
                yaml.dump(existing, f, allow_unicode=True)
            # 保存记录
            user_file = os.path.join('data', 'user.yml')
            users = []
            if os.path.exists(user_file):
                with open(user_file, 'r') as f:
                    users = yaml.safe_load(f) or []
            # 查找并更新用户数据
            for user in users:
                if user['username'] == author:
                    user['try'] = user.get('try', 0) + 1
                    if submission['status'] == 0 and entry['pid'] not in user.get('solve_list', []):
                        user['solved'] = user.get('solved', 0) + 1
                        user.setdefault('solve_list', []).append(entry['pid'])
                    break
            with open(user_file, 'w') as f:
                yaml.dump(users, f, allow_unicode=True)
            return entry

app = Flask(__name__)
# Frontend
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('web', 'favicon.ico')
@app.route('/')
def index():
    return redirect('/home')
@app.route('/home')
def home():
    return send_from_directory('web', 'home.html')
@app.route('/problemset')
def problem():
    return send_from_directory('web', 'problemset.html')
@app.route('/problemset/<pid>')
def problem_detail(pid):
    problem_dir = os.path.join('problem', pid)
    info_file = os.path.join(problem_dir, 'info.html')
    
    # 检查文件是否存在
    if os.path.exists(info_file):
        return send_from_directory(problem_dir, 'info.html')
    else:
        return jsonify({'error': '题目不存在'}), 404
@app.route('/submit', methods=['GET'])
def submit():
    return send_from_directory('web', 'submit.html')
@app.route('/status', methods=['GET'])
def status():
    return send_from_directory('web', 'status.html')
@app.route('/status/<int:runid>')
def status_detail(runid):
    submission_file = os.path.join('data', 'submission.yml')
    try:
        with open(submission_file, 'r') as f:
            submissions = yaml.safe_load(f) or []
            submission = next((s for s in submissions if s['runid'] == runid), None)
            if submission:
                return send_from_directory('web', 'status_detail.html')
            return jsonify({'error': '提交记录不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/user/<username>')
def user_profile(username):
    return send_from_directory('web', 'user.html')
@app.route('/file/<filename>')
def get_file(filename):
    return send_from_directory('file', filename)
@app.route('/login')
def login_frame():
    return send_from_directory('web', 'login.html')

# API
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'msg': '用户名和密码不能为空'}), 400

    # 加载用户数据
    users = load_users()

    is_login = False
    # 验证用户
    for user in users:
        if user['username'] == username:
            if user['password'] == password:
                is_login = True
                break
            else:
                return jsonify({'msg': '密码错误'}), 401
    if not is_login:
        return jsonify({'msg': '不存在的用户名'}), 401

    # 生成token
    token, expire_date = generate_token(username)

    # 加载现有token
    tokens = load_tokens()

    # 移除该用户现有的token（如果有）
    tokens = [t for t in tokens if t['username'] != username]

    # 添加新token
    tokens.append({
        'token': token,
        'expire_date': expire_date.strftime('%Y-%m-%d %H:%M:%S'),
        'username': username
    })

    # 保存token
    if not save_tokens(tokens):
        return jsonify({'msg': '生成token失败'}), 500
    
    # token 应存储在返回的Authorization头中
    response = jsonify({
        'msg': '登录成功',
        'expire_date': expire_date.strftime('%Y-%m-%d %H:%M:%S')
    })
    response.headers['Authorization'] = f'{token}'
    return response, 200

@app.route('/api/verifyuser', methods=['POST'])
def verify_user():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'msg': 'token不能为空'}), 400
    
    # 验证token
    is_valid, username = validate_token(token)
    if is_valid:
        return jsonify({'msg': 'success', 'username': username}), 200
    else:
        return jsonify({'msg': 'token错误或已过期'}), 401

@app.route('/api/problems', methods=['GET'])
def get_problems():
    problem_dir = os.path.join(os.path.dirname(__file__), 'problem')
    problems = []
    # 遍历problem目录下的所有文件夹
    for item in os.listdir(problem_dir):
        item_path = os.path.join(problem_dir, item)
        # 检查是否是文件夹，且文件夹中包含information.yml
        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'information.yml')):
            # 读取information.yml文件内容
            info_file_path = os.path.join(item_path, 'information.yml')
            with open(info_file_path, 'r', encoding='utf-8') as f:
                # 解析YAML文件
                info_data = yaml.safe_load(f)
                
                # 提取题目信息
                problem_info = {}
                for entry in info_data:
                    for key, value in entry.items():
                        problem_info[key] = value
                    
                # 添加到题目列表
                problems.append({
                        'id': str(problem_info['id']),
                        'title': problem_info.get('name', f'题目 {item}'),
                        'diff': problem_info.get('diff', '--')
                })
        # 按题号排序
    problems.sort(key=lambda x: int(x['id']))
    return jsonify(problems), 200
@app.route('/api/submissions', methods=['GET'])
def get_submissions():
    submission_file = os.path.join('data', 'submission.yml')
    # 默认展示数量为最新的 10 条，最多 100 条
    count = int(request.args.get('count', 10))
    if count > 100:
        count = 100
    # 页数，默认第 1 页
    page = int(request.args.get('page', 1))
    try:
        with open(submission_file, 'r', encoding='utf-8') as f:
            submissions = yaml.safe_load(f) or []
            # 分页，跳过 (page-1)*count 条记录
            submissions = submissions[(page-1)*count:page*count]
            for sub in submissions:
                if 'createtime' in sub:
                    sub['time'] = sub.pop('createtime')
                if 'status' in sub:
                    # 保留原始状态码
                    sub['status_show'] = status_list[sub['status']]

            return jsonify(submissions)
    except FileNotFoundError:
        return jsonify({'error': '暂时没有评测记录'}), 404
    except Exception as e:
        return jsonify({'error': f'读取失败: {str(e)}'}), 500

@app.route('/api/submission/<int:runid>')
def get_submission(runid):
    submission_file = os.path.join('data', 'submission.yml')
    try:
        with open(submission_file, 'r') as f:
            submissions = yaml.safe_load(f) or []
            submission = next((s for s in submissions if s['runid'] == runid), None)
            submission['status'] = status_list[submission['status']]
            if submission:
                return jsonify(submission)
            return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/submit', methods=['POST'])
def submit_problem():
    # 链接 POST 到/submit-remote
    return redirect('/api/submit-remote', code=307)

@app.route('/api/submit-remote', methods=['POST'])
def submit_problem_judge():
    data = request.json
    pid = data.get('pid')
    code = data.get('code')
    lang = data.get('lang')
    token = request.headers.get('Authorization')
    # 验证token
    is_valid, author = validate_token(token)
    if not is_valid:
        return jsonify({'msg': '请您先登录！'}), 401
    # 从对应题目的 information.yml 中获取 isremote 信息
    problem_dir = os.path.join(os.path.dirname(__file__), 'problem')
    info_file_path = os.path.join(problem_dir, pid, 'information.yml')
    with open(info_file_path, 'r', encoding='utf-8') as f:
        # 解析YAML文件
        info_data = yaml.safe_load(f)
        # 提取题目信息
        problem_info = {}
        for entry in info_data:
            for key, value in entry.items():
                problem_info[key] = value
        isremote = problem_info['isremote']

    if not pid or not code or not lang:
        return jsonify({'msg': 'pid, code, lang不能为空'}), 400
    if isremote == 'hdu' or isremote == 'poj':
        if not lang == 'C++' and not lang == 'C++ With O2' and not lang == 'C With O2' and not lang == 'C':
            return jsonify({'msg': '此题目仅支持C++和C语言'}), 400
        if lang == 'C++' or lang == 'C++ With O2':
            lang = 'G++'
        if lang == 'C With O2' or lang == 'C':
            lang = 'GCC'
    if isremote == 'cf':
        if not lang == 'C++' and not lang == 'C++ 17' and not lang == 'C++ 20' and not lang == 'Python 3' and not lang == 'Java':
            return jsonify({'msg': '此题目仅支持 C++, C++ 17, C++ 20, Java, Python 语言'}), 400
        if lang == 'C++' or lang == 'C++ 17':
            lang = 'GNU G++17'
        if lang == 'C++ 20':
            lang = 'GNU G++20'
        if lang == 'Python 3':
            lang = 'Python 3.9.1'
        if lang == 'Java':
            lang = 'Java 1.8.0_241 '
    # 转化 pid
    problem_dir = os.path.join(os.path.dirname(__file__), 'problem')
    info_file_path = os.path.join(problem_dir, pid, 'information.yml')
    with open(info_file_path, 'r', encoding='utf-8') as f:
        # 解析YAML文件
        info_data = yaml.safe_load(f)
        # 提取题目信息
        problem_info = {}
        for entry in info_data:
            for key, value in entry.items():
                problem_info[key] = value
        nxt_pid = problem_info['remoteid']
    # 从用botuser里选择最新的用户
    botuser_file = os.path.join('data', 'botuser.yml')
    try:
        with open(botuser_file, 'r', encoding='utf-8') as f:
            botuser = yaml.safe_load(f) or []
    except FileNotFoundError:
        return jsonify({'msg': '未配置远程账户，请联系管理员'}), 403
    # 判断是否为空
    if not botuser:
        return jsonify({'msg': '未配置远程账户，请联系管理员'}), 403
    # 选择最新的用户
    remote_username_judge = botuser[0]['username']
    remote_password_judge = botuser[0]['password']
    # 将第一项移动到最后防止重复调用
    botuser.append(botuser.pop(0))
    # 保存
    with open(botuser_file, 'w', encoding='utf-8') as f:
        yaml.dump(botuser, f, allow_unicode=True, default_flow_style=False)
    # 模拟登录请求
    login_url = remote_oj + common_api['Login']
    login_data = {
        "username": remote_username_judge,
        "password": remote_password_judge
    }    
    headers = common_headers
    # 从返回中得到令牌
    try:
        response = requests.post(login_url, json=login_data, headers=headers)
        response.raise_for_status()
        result = response.json()
        # 请注意无论登录成功与否都会返回 200，需检查 status 字段
        if result['status'] != 200:
            return jsonify({'msg': f'登录失败: {result["msg"]}，请联系管理员'}), 400
        # 从返回的 Header 中得到 token
        token = response.headers.get("Authorization")
        if not token:
            return jsonify({'msg': '登录失败，未返回token，可能是服务器问题'}), 400
    except Exception as e:
        return jsonify({'msg': f'登录失败: {str(e)}，请联系管理员'}), 400
    headers['Authorization'] = token
    print(f"Token 选择：{token}")
    target_url = remote_oj + common_api['submitProblem']
    if isremote == 'cf':
        update_url = remote_oj + common_api['updcfSession']
        data = {"cfSession": cf_jsession}

        try:
            response = requests.post(update_url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            print(result)
            if response.status_code == 200 and result.get("status") == 200:
                print(f"CFSession更新:{cf_jsession}")
            else:
                return jsonify({'msg': 'CFSession更新失败'}), 400
        except Exception as e:
            print(f"未知错误: ")
            print(response.json())
            return jsonify({'msg': f'未知错误{str(e)}'}), 400

    payload = {
        'pid': nxt_pid,
        'gid': None,
        'isRemote': (isremote != 'mine'),
        'code': code,
        'language': lang,
        'tid': None
    }
    response = requests.post(target_url, json=payload, headers=headers)
    result = response.json()
    print(result)

    if response.status_code == 200:
        threading.Thread(target=craw_submit, 
            args=(result['data']['submitId'], pid, token, author)).start()
        return jsonify({'msg': 'success'}), 200
    else:
        return jsonify({'msg': '提交失败'}), 400

@app.route('/api/user/<username>')
def get_user_data(username):
    user_file = os.path.join('data', 'user.yml')
    try:
        with open(user_file, 'r') as f:
            users = yaml.safe_load(f) or []
            user = next((u for u in users if u['username'] == username), None)
            score_count = 0
            # 从每个问题的 yml 中依次读取难度分并相加
            for problem in user['solve_list']:
                problem_dir = os.path.join(os.path.dirname(__file__), 'problem', problem)
                info_file_path = os.path.join(problem_dir, 'information.yml')
                with open(info_file_path, 'r', encoding='utf-8') as f:
                    info_data = yaml.safe_load(f)
                    for entry in info_data:
                        for key, value in entry.items():
                            if key == 'diff':
                                score_count += int(value)
            if user:
                return jsonify({
                    'username': user['username'],
                    'try': user['try'],
                    'solved': user['solved'],
                    'solve_list': user['solve_list'],
                    'score': score_count
                })
            return jsonify({'error': '用户不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/notice', methods=['GET'])
def get_notice():
    # 从 /data/notice.yml 中获取通知
    notice_path = os.path.join(os.path.dirname(__file__), 'data', 'notice.yml')
    try:
        with open(notice_path, 'r', encoding='utf-8') as file:
            notice_data = yaml.safe_load(file)
            return jsonify(notice_data)
    except FileNotFoundError:
        return jsonify({'error': '通知文件不存在'}), 404
    except yaml.YAMLError as e:
        return jsonify({'error': f'YAML解析错误: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'读取通知失败: {str(e)}'}), 500

@app.route('/api/about', methods=['GET'])
def get_about():
    return jsonify(website_info)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
