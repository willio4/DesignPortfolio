# imports
from flask import render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# create a database using the SQLAlchemy import
db = SQLAlchemy()

class UserModel(db.Model):
    __tablename__ = 'users' # sets name of table to users
    
    id = db.Column(db.Integer, primary_key=True) # sets unique id to each user as primary identifier
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False) 
    password_hash = db.Column(db.String(128), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<UserModel {self.username}>"

def register_auth_routes(app):
    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            
            # check if user already exist
            existing_user = UserModel.query.filter_by(username=username).first()
            if existing_user:
                return "User already exists!" # throw error for now but should be changed to a template later on
            
            # Create user instance
            new_user = UserModel(username=username, email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()
            
            print(f"User created: {username}")
            return redirect(url_for('login'))
        
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