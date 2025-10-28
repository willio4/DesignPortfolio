from flask import request, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from .database import db

class UserModel(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    profile = db.relationship("UserProfile", back_populates="user", uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


def register_auth_routes(app):
    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            
            # Check if user already exists
            existing_user = UserModel.query.filter_by(email=email).first()
            if existing_user:
                return "User already exists!"  # Replace with flash message later
            
            # Create user instance
            new_user = UserModel(username=username, email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            # ✅ Store user_id in session for later use
            session['user_id'] = new_user.id
            
            # Redirect to profile setup
            return redirect(url_for('setup_profile'))
        
        return render_template('signup.html')
    

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']

            user = UserModel.query.filter_by(email=email).first()
            if user and user.check_password(password):
                # ✅ Store user_id in session for later use
                session['user_id'] = user.id
                return redirect(url_for('show_feed'))
            else:
                return "Invalid credentials"  # Replace with flash later
        return render_template('login.html')
    

    @app.route('/setup_profile', methods=['GET', 'POST'])
    def setup_profile():
        from .user_profile import UserProfile

        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))  # force login if session expired

        if request.method == 'POST':
            profile = UserProfile(
                user_id=user_id,
                f_name=request.form['f_name'],
                l_name=request.form['l_name'],
                age=int(request.form['age']),
                sex=request.form['sex'],
                weight_lbs=float(request.form['weight_lbs']),
                height_ft=int(request.form['height_ft']),
                height_in=int(request.form['height_in']),
                goal=request.form['goal']
            )

            db.session.add(profile)
            db.session.commit()

            # ✅ Clear session after setup if you want to log them in again later
            session.pop('user_id', None)

            return redirect(url_for('login'))

        return render_template('setup_profile.html')
