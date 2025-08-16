# flask-api-server/app.py
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv

# ── 환경 변수 로드 ─────────────────────────────────────────────
load_dotenv()
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
FASTAPI_TIMEOUT = int(os.getenv("FASTAPI_TIMEOUT", "120"))
TRUSTED_API_KEY = os.getenv("TRUSTED_API_KEY", "my-secure-api-key")

# ── Flask 기본 설정 ───────────────────────────────────────────
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "mutualcloud-very-secret-key")

# ── DB 설정 ───────────────────────────────────────────────────
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mutualcloud.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ── 모델 ──────────────────────────────────────────────────────
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)  # 데모용(운영은 해시 필수)

class Provider(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    cpu_free = db.Column(db.Float, nullable=False)
    ram_free = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(16), nullable=False)
    ip_address = db.Column(db.String(64), nullable=True)

# ── 라우트 ────────────────────────────────────────────────────
@app.route('/')
def home():
    providers = Provider.query.order_by(Provider.name.asc()).all()
    return render_template('home.html', providers=providers)

# 회원가입
@app.route('/register', methods=['GET', 'POST'])
def html_register():
    if request.method == 'GET':
        return render_template('register.html')

    username = (request.form.get('username') or '').strip()
    password = (request.form.get('password') or '')
    if not username or not password:
        return "유효하지 않은 입력", 400
    if User.query.filter_by(username=username).first():
        return "이미 존재하는 사용자", 409

    db.session.add(User(username=username, password=password))  # 데모용
    db.session.commit()
    flash("회원가입 완료. 로그인해 주세요.")
    return redirect(url_for('login'))

# 로그인/로그아웃
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    if user and user.password == password:  # 데모용(운영은 check_password_hash)
        session['user_id'] = user.id
        session['username'] = user.username
        return redirect(url_for('home'))
    return "로그인 실패", 401

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('home'))

# 공급자 상세
@app.route('/provider/<int:provider_id>', methods=['GET'])
def provider_detail(provider_id):
    provider = Provider.query.get_or_404(provider_id)
    return render_template('prov-detail.html', provider=provider)

# 작업 요청 (Flask -> FastAPI 프록시)
@app.route('/submit_job/<int:provider_id>', methods=['POST'])
def submit_job(provider_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    provider = Provider.query.get_or_404(provider_id)
    image = (request.form.get('image') or 'alpine:3.19').strip()
    script = (request.form.get('script') or '').strip()
    env_text = (request.form.get('env') or '').strip()

    env_dict = {}
    if env_text:
        for line in env_text.splitlines():
            line = line.strip()
            if not line or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env_dict[k.strip()] = v.strip()

    payload = {
        "image": image,
        "script": script,
        "provider_label_value": provider.name,  # 필요시 라벨 매핑 테이블로 교체
        "namespace": "mutual-cloud",
        "env": env_dict,
        "backoff_limit": 0,
        "ttl_seconds_after_finished": 300
    }

    try:
        r = requests.post(f"{FASTAPI_BASE_URL}/submit-job", json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()  # { job_name, namespace }
    except Exception as e:
        return f"FastAPI 호출 오류: {e}", 500

    return redirect(url_for('result', namespace=data["namespace"], job_id=data["job_name"]))

# 결과 보기 (FastAPI 로그 조회)
@app.route('/result/<namespace>/<job_id>')
def result(namespace, job_id):
    try:
        r = requests.get(
            f"{FASTAPI_BASE_URL}/jobs/{namespace}/{job_id}/logs",
            params={"timeout": FASTAPI_TIMEOUT},
            timeout=FASTAPI_TIMEOUT + 10
        )
        r.raise_for_status()
        data = r.json()  # {"pod": "...", "phase": "...", "logs": "..."}
    except Exception as e:
        return f"FastAPI 로그 조회 오류: {e}", 500

    return render_template('result.html', ns=namespace, job_id=job_id, result=data)

# 공급자 등록 API (에이전트가 호출)
@app.route('/api/provider/register', methods=['POST'])
def register_provider():
    api_key = request.headers.get('X-API-KEY')
    if api_key != TRUSTED_API_KEY:
        return jsonify({'error': '인증 실패'}), 403

    data = request.get_json(silent=True) or {}
    if data.get('ip_address') != request.remote_addr:
        return jsonify({'error': 'IP 주소 불일치'}), 400

    try:
        cpu = float(data.get('cpu_free'))
        if not (0 <= cpu <= 100):
            raise ValueError
        ram = float(data.get('ram_free'))
        if ram < 0:
            raise ValueError
    except Exception:
        return jsonify({'error': '잘못된 자원 수치'}), 400

    new = Provider(
        name=data.get('name', 'unknown'),
        cpu_free=cpu,
        ram_free=ram,
        status=data.get('status', 'Unknown'),
        ip_address=data.get('ip_address')
    )
    db.session.add(new)
    db.session.commit()

    return jsonify({'message': '등록 완료', 'provider_id': new.id}), 201

# ── 실행 ──────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
