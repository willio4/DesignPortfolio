from flask import render_template, request, redirect, url_for
from datetime import datetime

# stores all post for display as feed
feed = []

# Post class
class Post:
    def __init__(self, user, content):
        self.user = user      # placeholder string for now
        self.content = content
        self.timestamp = datetime.now()

def register_feed_routes(app):
    @app.route('/feed_home')
    def home():
        return render_template('add_post.html')

    @app.route('/add_post', methods=['POST'])
    def add_post():
        user = request.form.get('user', 'Anonymous')
        content = request.form['content']
        new_post = Post(user, content)
        feed.append(new_post)
        return redirect(url_for('show_feed'))

    @app.route('/feed')
    def show_feed():
        sorted_feed = sorted(feed, key=lambda x: x.timestamp, reverse=True)
        return render_template('feed.html', posts=sorted_feed)
