from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = "nexus_hub_v4_fucking_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nexus.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# DATABASE MODELS
# ==========================================
class User(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='active')
    rep = db.Column(db.Integer, default=0)
    tasks_done = db.Column(db.Integer, default=0)
    avatar = db.Column(db.String(5))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Task(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    desc = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default='medium')
    status = db.Column(db.String(20), default='pending') # pending, inprogress, completed
    author_id = db.Column(db.String(50), db.ForeignKey('user.id'))
    assignee_id = db.Column(db.String(50), db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    comments = db.relationship('Comment', backref='task', lazy=True, cascade="all, delete-orphan")
    votes = db.relationship('Vote', backref='task', lazy=True, cascade="all, delete-orphan")

    @property
    def score(self):
        return sum(vote.value for vote in self.votes)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    task_id = db.Column(db.String(50), db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.String(50), db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='comments')

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    task_id = db.Column(db.String(50), db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.String(50), db.ForeignKey('user.id'), nullable=False)

class Log(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    actor_id = db.Column(db.String(50))
    action = db.Column(db.String(200))
    target_id = db.Column(db.String(50), nullable=True)

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def log_event(actor_id, action, target_id=None):
    db.session.add(Log(
        id=f"l_{int(datetime.utcnow().timestamp())}_{random.randint(100,999)}", 
        actor_id=actor_id, 
        action=action, 
        target_id=target_id
    ))
    db.session.commit()

def get_current_user():
    if 'user_id' not in session: return None
    return User.query.get(session['user_id'])

# ==========================================
# ROUTES & API
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

# --- AUTH ---
@app.route('/api/me')
def get_me():
    u = get_current_user()
    if not u: return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'id': u.id, 'username': u.username, 'role': u.role, 'avatar': u.avatar, 'rep': u.rep, 'tasksDone': u.tasks_done})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').lower()
    role = data.get('role', 'user')
    
    u = User.query.filter_by(username=username).first()
    if not u:
        u = User(id=f"u_{int(datetime.utcnow().timestamp())}", username=username, role=role, avatar=username[:2].upper())
        db.session.add(u)
        db.session.commit()
        log_event(u.id, "Account created")
        
    if u.status != 'active': 
        return jsonify({'error': 'Account Suspended'}), 403
        
    session['user_id'] = u.id
    log_event(u.id, "Logged in")
    return jsonify({'success': True, 'user': {'id': u.id, 'username': u.username, 'role': u.role, 'avatar': u.avatar}})

@app.route('/api/logout', methods=['POST'])
def logout():
    log_event(session.get('user_id', 'system'), "Logged out")
    session.clear()
    return jsonify({'success': True})

# --- DATA (DASHBOARD & KANBAN) ---
@app.route('/api/stats')
def get_stats():
    return jsonify({
        'total_tasks': Task.query.count(),
        'active_tasks': Task.query.filter(Task.status != 'completed').count(),
        'users_count': User.query.count(),
        'comp_rate': int((Task.query.filter_by(status='completed').count() / max(1, Task.query.count())) * 100),
        'top_users': [{'id': u.id, 'username': u.username, 'rep': u.rep, 'avatar': u.avatar} for u in User.query.order_by(User.rep.desc()).limit(5)]
    })

@app.route('/api/tasks', methods=['GET', 'POST', 'PUT'])
def handle_tasks():
    current_user = get_current_user()
    if not current_user: return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'GET':
        tasks = Task.query.all()
        return jsonify([{'id': t.id, 'title': t.title, 'desc': t.desc, 'priority': t.priority, 'status': t.status, 'assigneeId': t.assignee_id} for t in tasks])
        
    if request.method == 'POST':
        data = request.json
        assignee_id = data.get('assigneeId')
        
        # Security Check: Only admins can assign tasks to other people
        if assignee_id and current_user.role != 'admin':
            return jsonify({'error': 'Only admins can assign tasks'}), 403

        t = Task(
            id=f"t_{int(datetime.utcnow().timestamp())}_{random.randint(100,999)}", 
            title=data['title'], 
            desc=data.get('desc', ''), 
            priority=data['priority'], 
            assignee_id=assignee_id, 
            author_id=current_user.id
        )
        db.session.add(t)
        log_event(current_user.id, f"Created task: {t.title}")
        db.session.commit()
        return jsonify({'success': True})
        
    if request.method == 'PUT': # Update Status via Drag and Drop
        data = request.json
        t = Task.query.get(data['id'])
        if not t: return jsonify({'error': 'Task not found'}), 404
        
        # Strict Kanban Security: Only Admin or Assigned Operator can move the task
        if current_user.role != 'admin' and t.assignee_id != current_user.id:
            return jsonify({'error': 'Permission Denied'}), 403

        t.status = data['status']
        if t.status == 'completed' and t.assignee_id:
            assignee = User.query.get(t.assignee_id)
            if assignee:
                assignee.rep += 15
                assignee.tasks_done += 1
                
        log_event(current_user.id, f"Moved task {t.id} to {t.status}")
        db.session.commit()
        return jsonify({'success': True})

# --- DIRECTORY & LOGS (Admin Only) ---
@app.route('/api/users')
def get_users():
    current_user = get_current_user()
    if not current_user or current_user.role != 'admin': return jsonify({'error': 'Unauthorized'}), 401
    return jsonify([{'id': u.id, 'username': u.username, 'role': u.role, 'status': u.status, 'rep': u.rep, 'avatar': u.avatar} for u in User.query.all()])

@app.route('/api/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    current_user = get_current_user()
    if not current_user or current_user.role != 'admin': return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    target_user = User.query.get(user_id)
    if not target_user: return jsonify({'error': 'User not found'}), 404
    
    # Update profile fields
    target_user.role = data.get('role', target_user.role)
    target_user.status = data.get('status', target_user.status)
    target_user.rep = data.get('rep', target_user.rep)
    
    log_event(current_user.id, f"Updated profile for {target_user.username}", target_user.id)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/logs')
def get_logs():
    current_user = get_current_user()
    if not current_user or current_user.role != 'admin': return jsonify({'error': 'Unauthorized'}), 401
    logs = Log.query.order_by(Log.timestamp.desc()).limit(50).all()
    return jsonify([{'timestamp': l.timestamp.isoformat(), 'actorId': l.actor_id, 'action': l.action, 'targetId': l.target_id} for l in logs])

# --- FEED (Reddit Style) ---
@app.route('/api/feed')
def get_feed():
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    feed_data = []
    for t in tasks:
        feed_data.append({
            'id': t.id, 'title': t.title, 'desc': t.desc, 'score': t.score,
            'author': User.query.get(t.author_id).username if t.author_id else 'System',
            'comments': [{'id': c.id, 'content': c.content, 'author': c.user.username} for c in t.comments]
        })
    return jsonify(feed_data)

@app.route('/api/feed/<task_id>/vote', methods=['POST'])
def vote_task(task_id):
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    val = int(request.json.get('value', 1))
    v = Vote.query.filter_by(task_id=task_id, user_id=session['user_id']).first()
    
    if v:
        if v.value == val: db.session.delete(v) # Toggle off if clicking same vote
        else: v.value = val # Switch vote
    else:
        db.session.add(Vote(task_id=task_id, user_id=session['user_id'], value=val))
        
    db.session.commit()
    return jsonify({'success': True, 'new_score': Task.query.get(task_id).score})

@app.route('/api/feed/<task_id>/comment', methods=['POST'])
def comment_task(task_id):
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    db.session.add(Comment(content=request.json.get('content'), task_id=task_id, user_id=session['user_id']))
    db.session.commit()
    return jsonify({'success': True})

# ==========================================
# APP INITIALIZATION
# ==========================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Seed Admin if no users exist
        if not User.query.first():
            db.session.add(User(id="u_admin", username="admin", role="admin", avatar="AD", rep=500))
            db.session.commit()
    app.run(debug=True, port=5000)