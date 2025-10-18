from flask import render_template, request, redirect, url_for

def register_auth_routes(app):
    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            print(f"User dreated: {username}")
            return redirect(url_for('login'))
        return render_template('signup.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            print(f"Login attempt: {username}")
            return redirect(url_for('show_feed'))  # redirect to feed after login
        return render_template('login.html')