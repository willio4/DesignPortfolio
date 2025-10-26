# imports
from flask import request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
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
            
            # check if user already exist
            existing_user = UserModel.query.filter_by(email=email).first()
            if existing_user:
                return "User already exists!" # throw error for now but should be changed to a template later on
            
            # Create user instance
            new_user = UserModel(username=username, email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()
            
            return redirect(url_for('setup_profile', user_id = new_user.id))
        
        return render_template('signup.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']

            user = UserModel.query.filter_by(email=email).first()
            if user and user.check_password(password):
                # TODO: set session or login user
                return redirect(url_for('show_feed'))
            else:
                return "Invalid credentials"  # or flash message
        return render_template('login.html')