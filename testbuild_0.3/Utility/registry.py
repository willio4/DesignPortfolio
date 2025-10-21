# Global state container
""" Purpose of the Global State: It'll act as a central hub for all the constraints. Instead of adding them 
individually to the LLM prompt, everyone can pass what their working on to this file. This way we avoid extra work.
"""

""" How it works: """

from future import annotations
from typing import Any, Dict, List, Optional, Union
from copy import deepcopy
import threading

# Global State Container
class Registry:
    def __init__(self) -> None:

# Thread safe for app wide state management
    self._Lock = threading.Lock()