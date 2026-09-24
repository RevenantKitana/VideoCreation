"""
Gói module sub_generate - Chuyên trách sinh và kiểm tra kịch bản video script.json.
"""

from .generator import generate_script
from .validator import validate_script
from .schema_rules import SYSTEM_PROMPT

__all__ = ["generate_script", "validate_script", "SYSTEM_PROMPT"]
