"""
Gói module sub_render - Chuyên trách kiểm tra và render video từ script.json có sẵn.
"""

from .renderer import render_from_script, generate_preview, generate_voice, check_script

__all__ = ["render_from_script", "generate_preview", "generate_voice", "check_script"]
