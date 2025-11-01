# contains helper functions to read/write contstraints per user
# TO DO:
#update_user_constraints function
# Add per-user write capability
# imlement update_user_constraints function
# add a small route for users to view/edit constraints

import json
from typing import Any, Dict
from User_Auth.user_profile import UserProfile
from User_Auth.database import db
from datetime import datetime

# get constraints for a specific user
def get_user_constraints(user_id: int) -> Dict[str, Any]:
    # fetch user profile
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        return {}
    c = getattr(profile, "constraints", None)
    #If constraints are stored as JSON type SQLA should return as dict
    if isinstance(c, dict):
        return c
    # if stored as text, parse it
    try:
        return json.loads(c)
    except Exception:
        return {}
    
# update constraints for a specific user  (finish tomorrow)
# def update_user_constraints(user_id: int, mapping: Dict[str, Any], updated_by: str | None = None) -> Dict[str, Any]: