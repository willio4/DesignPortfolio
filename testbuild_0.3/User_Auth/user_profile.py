from .database import db
from sqlalchemy import column # adding to store constraints per user
from sqlalchemy.types import JSON # SQLAlchemy JSON type

class UserProfile(db.Model):
    __tablename__ = 'user_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    user = db.relationship("UserModel", back_populates="profile")

    name = db.Column(db.String(80))
    weight_lbs = db.Column(db.Float)
    height_ft = db.Column(db.Integer)
    height_in = db.Column(db.Integer)
    age = db.Column(db.Integer)
    sex = db.Column(db.String(1))
    goal = db.Column(db.String(20))

    # Additional column to store user-specific constraints
    constraints = db.Column(JSON, nullable=False, default={})