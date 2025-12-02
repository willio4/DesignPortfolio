from flask import request, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from .database import db
from .user_profile import UserProfile


class UserModel(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # I bumped this to 255 to align with the startup migration and keep Supabase from clipping hashes.
    password_hash = db.Column(db.String(255), nullable=False)

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
            
            # ---- 1) Check for existing user by email (your original logic) ----
            existing_user = UserModel.query.filter_by(email=email).first()
            if existing_user:
                # Check if user completed signup by querying user_profiles table
                completed_signUp = UserProfile.query.filter_by(user_id=existing_user.id).first()

                if completed_signUp:
                    # Existing account fully set up
                    return "ERROR User already exists with this email"  # TODO: replace with flash later

                elif username != existing_user.username:
                    # Email matches an unfinished signup, but username is different
                    return (
                        f"ERROR Existing signup process found with your email but "
                        f"with a different username. To continue sign up, retry with "
                        f"your original username: {existing_user.username}"
                    )

                # Same email + same username, signup not completed yet → resume
                session['user_id'] = existing_user.id
                return redirect(url_for('setup_profile'))

            # ---- 2) NEW: Check for existing user by username ----
            existing_username = UserModel.query.filter_by(username=username).first()
            if existing_username:
                # Someone else already took this username (even if email is different)
                return "ERROR User already exists with this username"  # TODO: flash instead

            # ---- 3) Create user instance ----
            new_user = UserModel(username=username, email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            # Store user_id in session for profile setup
            session['user_id'] = new_user.id

            # Redirect to profile setup
            return redirect(url_for('setup_profile'))
        
        # GET → render signup page
        return render_template('signup.html')

#
# def register_auth_routes(app):
#     @app.route('/signup', methods=['GET', 'POST'])
#     def signup():
#         if request.method == 'POST':
#             username = request.form['username']
#             email = request.form['email']
#             password = request.form['password']
            
#             # Check if user already exists
#             existing_user = UserModel.query.filter_by(email=email).first()
#             if existing_user:
#                 # check if user completed signup by querying user_profiles table based on id (foregin key)

#                 completed_signUp=UserProfile.query.filter_by(user_id=existing_user.id).first()
#                 # if not compelted signup then take to signup page
#                 if completed_signUp:
#                     return "ERROR User already exists with this email"  # Replace with flash message later
#                 elif username!=existing_user.username:
#                     # check if the user entered an existing email with a different username but hasnt completed sign up,
#                     # can cause error where user finishes signup but username is not updated
#                         return "ERROR Existing Signup Process Found with your email but with a different username \n to continue sign up retry with your original username: {existing_user.username}"
#                 # else allow user to continue sign up
#                 else:   
#                     # redirect to prevent a database error uploading same user twice
#                     session['user_id']=existing_user.id
#                     return redirect(url_for('setup_profile'))

#             # Create user instance
#             new_user = UserModel(username=username, email=email)
#             new_user.set_password(password)

#             db.session.add(new_user)
#             db.session.commit()

#             # ✅ Store user_id in session for later use
#             session['user_id'] = new_user.id
            
#             # Redirect to profile setup
#             return redirect(url_for('setup_profile'))
        
#         return render_template('signup.html')
    
#
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']

            user = UserModel.query.filter_by(email=email).first()
            if user and user.check_password(password):
                # ✅ Store user_id in session for later use
                session['user_id'] = user.id
                # check if user has compelted sign up
                completed_signUp=UserProfile.query.filter_by(user_id=user.id).first()
                if completed_signUp:
                    return redirect(url_for('get_started'))
                    # if not completed sign up then allow them to finish sign up
                else:
                    return redirect(url_for('setup_profile'))
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

            # # ✅ Clear session after setup if you want to log them in again later
            # session.pop('user_id', None)

            return redirect(url_for('index'))

        return render_template('setup_profile.html')
