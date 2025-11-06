from .database import db
from sqlalchemy import column # adding to store constraints per user
from sqlalchemy.types import JSON # SQLAlchemy JSON type
from flask import render_template, request, redirect, url_for

class UserProfile(db.Model):
    __tablename__ = 'user_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship("UserModel", back_populates="profile")

    f_name = db.Column(db.String(80))
    l_name = db.Column(db.String(80))
    weight_lbs = db.Column(db.Float)
    height_ft = db.Column(db.Integer)
    height_in = db.Column(db.Integer)
    age = db.Column(db.Integer)
    sex = db.Column(db.String(1))
    goal = db.Column(db.String(20))
    # Additional column to store user-specific constraints
    constraints = db.Column(JSON, nullable=False, default={})
        
    def set_f_name(self, x):
        self.f_name = x
        
    def set_l_name(self, x):
        self.l_name = x
        
    def set_weight_lbs(self, x):
        self.weight_lbs = x

    def set_height_ft(self, x):
        self.height_ft = x
        
    def set_height_in(self, x):
        self.height_in = x
        
    def set_age(self, x):
        self.age = x

    def set_sex(self, x):
        self.sex = x
        
    def set_goal(self, x):
        self.goal = x