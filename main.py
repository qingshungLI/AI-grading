import streamlit as st
# Set page config must be the first Streamlit command
st.set_page_config(page_title="AI判卷系统", layout="wide")

from PIL import Image, ImageDraw, ImageFont
import os
import json
from io import BytesIO
import base64
import tempfile
import io
import pandas as pd
import numpy as np
import requests
import time
import re
import dashscope
import logging
import zhipuai 
import docx2pdf
import shutil
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
from jsoncat import *
from db_manager import DatabaseManager
import secrets
# Import OpenAI client for Moonshot API
from openai import OpenAI
import base64
from convert import *
from modelcall import *
from analyse import *
import mimetypes
# Import ZhipuAI SDK for ZhipuAI (GLM) API
try:

    from zhipuai import ZhipuAI
    ZHIPU_AVAILABLE = True
except ImportError:
    ZHIPU_AVAILABLE = False

# Import Volcengine SDK for zhipu API - 已弃用，改为使用智谱AI
import os
# Try different imports to ensure compatibility
try:
    from volcenginesdkarkruntime import Ark, ArkClient
except ImportError:
    try:
        from volcengine.ark import Ark, ArkRuntime
        ArkClient = ArkRuntime
    except ImportError:
        # Fall back to just Ark if nothing else works
        from volcenginesdkarkruntime import Ark

# Check if required packages are available
MOONSHOT_AVAILABLE = True
try:
    from openai import OpenAI
except ImportError:
    MOONSHOT_AVAILABLE = False

# Check if Doubao SDK is available
ZHIPU_AVAILABLE = True
try:
    import volcenginesdkarkruntime
except ImportError:
    ZHIPU_AVAILABLE = False



 


# 设置日志
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ai_grading_system')

# 添加调试函数
def debug_log(message):
    logger.debug(message)
    
def info_log(message):
    logger.info(message)
    
def error_log(message):
    logger.error(message)
    
# 给st添加调试方法
st.debug = debug_log
st.info_log = info_log
st.error_log = error_log

# Try to import optional packages with fallbacks
try:
    import fitz  # PyMuPDF for PDF to image conversion
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    st.warning("PyMuPDF not installed. PDF to image conversion will be limited. Install with: pip install PyMuPDF")

try:
    import docx2txt
    DOCX2TXT_AVAILABLE = True
except ImportError:
    DOCX2TXT_AVAILABLE = False
    st.warning("docx2txt not installed. DOCX to image conversion will be limited. Install with: pip install docx2txt")

try:
    from openai import OpenAI
    MOONSHOT_AVAILABLE = True
except ImportError:
    MOONSHOT_AVAILABLE = False
    st.warning("OpenAI package not installed. Moonshot API grading will be disabled. Install with: pip install openai")

try:
    from volcenginesdkarkruntime import Ark
    ZHIPU_AVAILABLE= True
except ImportError:
    ZHIPU_AVAILABLE = False
    st.warning("Volcengine SDK package not installed. zhipu API grading will be disabled. Install with: pip install volcenginesdkarkruntime")


def fix_uploaded_file(file):
    """补全文件 MIME 类型（仅在浏览器上传异常时调用）"""
    if not file.type or file.type == 'application/octet-stream':
        mime, _ = mimetypes.guess_type(file.name)
        if mime:
            file.type = mime
    return file

# 添加用户名验证函数
def validate_username(username):
    if not username:
        return False, "用户名不能为空"
    if len(username) < 3:
        return False, "用户名长度至少为3个字符"
    if len(username) > 20:
        return False, "用户名长度不能超过20个字符"
    if not username.isalnum():
        return False, "用户名只能包含字母和数字"
    return True, "用户名格式正确"

# 添加密码验证函数
def validate_password(password):
    if not password:
        return False, "密码不能为空"
    if len(password) < 8:
        return False, "密码长度至少为8个字符"
    if not any(c.isupper() for c in password):
        return False, "密码必须包含大写字母"
    if not any(c.islower() for c in password):
        return False, "密码必须包含小写字母"
    if not any(c.isdigit() for c in password):
        return False, "密码必须包含数字"
    return True, "密码格式正确"


st.markdown("""
<style>
.starry-bg {
  position: fixed;
  z-index: 0;
  top: 0; left: 0; width: 100vw; height: 100vh;
  pointer-events: none;
  overflow: hidden;
  background: #070a1a;
}
.star {
  position: absolute;
  border-radius: 50%;
  opacity: 0.85;
  animation: twinkle 2.5s infinite alternate;
}
.star.s1 { background: #fff; width:3px; height:3px; }
.star.s2 { background: #FFD700; width:4px; height:4px; }
.star.s3 { background: #4169E1; width:3px; height:3px; }
.star.s4 { background: #FF4500; width:2.5px; height:2.5px; }
.star.s5 { background: #32CD32; width:3px; height:3px; }
@keyframes twinkle {
  from { opacity: 0.5; }
  to { opacity: 1; }
}
.meteor {
  position: absolute;
  width: 2.5px;
  height: 140px;
  background: linear-gradient(90deg, #4169E1 0%, #FFD700 100%);
  opacity: 0.85;
  border-radius: 50%;
  transform: rotate(-25deg);
  animation: meteor-fall-accel 2.2s linear infinite;
}
.meteor.m1 { left: 10vw; top: 10vh; animation-delay: 0s; }
.meteor.m2 { left: 30vw; top: 20vh; animation-delay: 0.7s; }
.meteor.m3 { left: 60vw; top: 5vh; animation-delay: 1.3s; }
.meteor.m4 { left: 80vw; top: 15vh; animation-delay: 1.8s; }
.meteor.m5 { left: 50vw; top: 30vh; animation-delay: 0.9s; }
.meteor.m6 { left: 20vw; top: 40vh; animation-delay: 1.5s; }
.meteor.m7 { left: 70vw; top: 25vh; animation-delay: 0.4s; }
.meteor.m8 { left: 90vw; top: 8vh; animation-delay: 1.6s; }
@keyframes meteor-fall-accel {
  0% {
    opacity: 0;
    transform: rotate(-25deg) translateY(-200px) translateX(0) scaleX(1) scaleY(1);
  }
  10% {
    opacity: 1;
    transform: rotate(-25deg) translateY(0px) translateX(0) scaleX(1) scaleY(1);
  }
  60% {
    opacity: 1;
    transform: rotate(-25deg) translateY(400px) translateX(120px) scaleX(1.1) scaleY(0.9);
  }
  100% {
    opacity: 0;
    transform: rotate(-25deg) translateY(900px) translateX(300px) scaleX(1.2) scaleY(0.8);
  }
}
</style>
<div class="starry-bg">
  <!-- 更大更密集的多色星星，分布随机 -->
  <div class="star s1" style="top:10vh;left:20vw;animation-duration:2.2s"></div>
  <div class="star s2" style="top:30vh;left:40vw;animation-duration:1.7s"></div>
  <div class="star s3" style="top:60vh;left:70vw;animation-duration:2.5s"></div>
  <div class="star s4" style="top:80vh;left:10vw;animation-duration:1.9s"></div>
  <div class="star s5" style="top:50vh;left:90vw;animation-duration:2.1s"></div>
  <div class="star s1" style="top:20vh;left:60vw;animation-duration:2.3s"></div>
  <div class="star s2" style="top:40vh;left:80vw;animation-duration:1.8s"></div>
  <div class="star s3" style="top:70vh;left:30vw;animation-duration:2.4s"></div>
  <div class="star s4" style="top:15vh;left:55vw;animation-duration:2.0s"></div>
  <div class="star s5" style="top:75vh;left:15vw;animation-duration:2.6s"></div>
  <div class="star s1" style="top:12vh;left:25vw;animation-duration:2.1s"></div>
  <div class="star s2" style="top:35vh;left:45vw;animation-duration:1.6s"></div>
  <div class="star s3" style="top:65vh;left:75vw;animation-duration:2.2s"></div>
  <div class="star s4" style="top:85vh;left:12vw;animation-duration:1.8s"></div>
  <div class="star s5" style="top:55vh;left:92vw;animation-duration:2.0s"></div>
  <div class="star s1" style="top:22vh;left:62vw;animation-duration:2.4s"></div>
  <div class="star s2" style="top:42vh;left:82vw;animation-duration:1.7s"></div>
  <div class="star s3" style="top:72vh;left:32vw;animation-duration:2.3s"></div>
  <div class="star s4" style="top:18vh;left:58vw;animation-duration:2.2s"></div>
  <div class="star s5" style="top:78vh;left:18vw;animation-duration:2.5s"></div>
  <!-- 更多星星可继续添加 -->
  <div class="meteor m1"></div>
  <div class="meteor m2"></div>
  <div class="meteor m3"></div>
  <div class="meteor m4"></div>
  <div class="meteor m5"></div>
  <div class="meteor m6"></div>
  <div class="meteor m7"></div>
  <div class="meteor m8"></div>
</div>
""", unsafe_allow_html=True)
# 添加自定义CSS样式
st.markdown("""
<style>
@keyframes border-rainbow {
    0% { border-image: linear-gradient(90deg, #FFD700, #4169E1, #32CD32, #FF4500) 1; }
    25% { border-image: linear-gradient(90deg, #FF4500, #FFD700, #4169E1, #32CD32) 1; }
    50% { border-image: linear-gradient(90deg, #32CD32, #FF4500, #FFD700, #4169E1) 1; }
    75% { border-image: linear-gradient(90deg, #4169E1, #32CD32, #FF4500, #FFD700) 1; }
    100% { border-image: linear-gradient(90deg, #FFD700, #4169E1, #32CD32, #FF4500) 1; }
}
@keyframes bg-glow {
    0% { box-shadow: 0 0 60px 10px #FFD70044, 0 0 0px 0px #4169E144; }
    50% { box-shadow: 0 0 80px 30px #4169E144, 0 0 40px 10px #FFD70044; }
    100% { box-shadow: 0 0 60px 10px #FFD70044, 0 0 0px 0px #4169E144; }
}
.artistic-title {
    font-family: 'Arial Black', 'Impact', sans-serif;
    font-size: 7em;
    text-align: center;
    background: linear-gradient(90deg, #4169E1 0%, #FFD700 33%, #32CD32 66%, #FF4500 100%);
    background-clip: text;
    -webkit-background-clip: text;
    color: transparent;
    -webkit-text-fill-color: transparent;
    /* 更强烈的3D立体感text-shadow */
    text-shadow:
        0 2px 0 #fff,
        0 4px 0 #FFD700,
        0 8px 0 #FFD700,
        0 12px 0 #FFD700,
        0 16px 8px #333,
        3px 3px 0 #FFD700,
        -3px 3px 0 #4169E1,
        3px -3px 0 #32CD32,
        -3px -3px 0 #FF4500,
        0 4px 12px rgba(0,0,0,0.45),
        0 8px 24px rgba(0,0,0,0.35),
        0 1px 0 #fff;
    padding: 30px 0 20px 0;
    margin: 0;
    border: 8px solid;
    border-radius: 18px;
    border-image: linear-gradient(90deg, #FFD700, #4169E1, #32CD32, #FF4500) 1;
    letter-spacing: 4px;
    text-transform: uppercase;
    font-weight: 900;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    font-smooth: always;
    position: relative;
    filter: contrast(1.2) brightness(1.05);
    overflow: hidden;
    /* 让大方框变成左右平行四边形 */
    clip-path: polygon(6% 0, 94% 0, 100% 100%, 0% 100%);
    animation: border-rainbow 4s linear infinite, bg-glow 3s ease-in-out infinite;
    box-shadow: 0 0 60px 10px #FFD70044, 0 0 0px 0px #4169E144;
    margin-bottom: 48px !important;  /* 加大下方间距 */
}
.artistic-title::after {
    content: '';
    position: absolute;
    left: -10%;
    top: 0;
    width: 20%;
    height: 100%;
    background: linear-gradient(
        to bottom,
        rgba(0,0,0,0.8) 0%,
        rgba(255,255,255,0) 10%,
        rgba(255,215,0,0.7) 40%,
        rgba(255,215,0,1) 50%,
        rgba(255,215,0,0.7) 60%,
        rgba(255,255,255,0) 90%,
        rgba(0,0,0,0.8) 100%
    );
    pointer-events: none;
    mix-blend-mode: lighten;
    filter: blur(2px);
    animation: goldshine 1.2s linear infinite;
    transform: skewX(-20deg);
}
@keyframes goldshine {
    0% { left: -10%; }
    100% { left: 90%; }
}
.stApp h1 {
    margin-top: 0 !important;
    margin-bottom: 32px !important;  /* "AI判卷系统 - 登录"下方间距 */
}
.stTabs [data-baseweb="tab-list"] {
    margin-bottom: 24px !important;
    gap: 24px !important;  /* 选项卡间距 */
}
.stTabs [data-baseweb="tab"] {
    letter-spacing: 2.5px !important;  /* 选项卡字间距 */
    font-size: 1.15em !important;
    padding: 0.7em 2.2em !important;
}
.stTabs [data-baseweb="tab"]:hover {
    background: #f0f4ff;
    border-radius: 8px;
}
.stTabs [data-baseweb="tab"]:active {
    background: #e0e8ff;
}
.stTabs [data-baseweb="tab"] span {
    display: flex;
    align-items: center;
    gap: 0.5em;
}
</style>
""", unsafe_allow_html=True)

# 使用自定义样式的标题
st.markdown('<div class="artistic-title">📚 AI-grading</div>', unsafe_allow_html=True)
# 初始化数据库管理器
db_manager = DatabaseManager()

# 初始化 session_state 中的项目列表
# 初始化session state
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = None
if 'session_id' not in st.session_state:
    st.session_state['session_id'] = None
if 'login_attempts' not in st.session_state:
    st.session_state['login_attempts'] = {}
if 'last_login_attempt' not in st.session_state:
    st.session_state['last_login_attempt'] = {}
if 'current_project' not in st.session_state:
    st.session_state['current_project'] = None
if 'page' not in st.session_state:
    st.session_state['page'] = "main"
if 'projects' not in st.session_state:
    st.session_state['projects'] = {}
if 'manual_grading' not in st.session_state:
    st.session_state['manual_grading'] = {
        'question_count': 0,
        'scores': {},
        'current_student_index': 0,
        'current_image_index': 0
    }# 初始化session state

# 确保manual_grading中包含所有必要的键
elif 'manual_grading' in st.session_state:
    if 'current_student_index' not in st.session_state['manual_grading']:
        st.session_state['manual_grading']['current_student_index'] = 0
    if 'current_image_index' not in st.session_state['manual_grading']:
        st.session_state['manual_grading']['current_image_index'] = 0
    if 'scores' not in st.session_state['manual_grading']:
        st.session_state['manual_grading']['scores'] = {}
    if 'question_count' not in st.session_state['manual_grading']:
        st.session_state['manual_grading']['question_count'] = 0
# 检查会话状态
if st.session_state['session_id']:
    username = db_manager.verify_session(st.session_state['session_id'])
    if username:
        st.session_state['authenticated'] = True
        st.session_state['current_user'] = username


# 登录/注册界面
if not st.session_state['authenticated']:
    st.title("📚 AI判卷系统 - 登录")
    
    # 创建选项卡
    login_tab, register_tab, reset_tab, help_tab = st.tabs([
        "🔑 登录", "📝 注册", "🔄 重置密码", "❓ 帮助"
    ])
    
    with login_tab:
        st.markdown("### 登录")
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        remember_me = st.checkbox("记住登录状态（7天）")
        
        # 检查登录尝试次数
        if username in st.session_state['login_attempts']:
            attempts = st.session_state['login_attempts'][username]
            last_attempt = st.session_state['last_login_attempt'].get(username)
            
            if attempts >= 5 and last_attempt:
                lockout_time = last_attempt + timedelta(minutes=15)
                if datetime.now() < lockout_time:
                    remaining_time = (lockout_time - datetime.now()).seconds // 60
                    st.error(f"登录尝试次数过多，请{remaining_time}分钟后再试")
                    st.stop()
                else:
                    # 重置尝试次数
                    st.session_state['login_attempts'][username] = 0
        
        if st.button("登录"): 
            # 验证用户名格式
            valid_username, username_msg = validate_username(username)
            if not valid_username:
                st.error(username_msg)
                st.stop()
            
            success, message = db_manager.verify_user(username, password)
            if success:
                st.session_state['authenticated'] = True
                st.session_state['current_user'] = username
                
                # 如果选择记住登录状态，创建会话
                if remember_me:
                    session_id = secrets.token_urlsafe(32)
                    db_manager.create_session(username, session_id)
                    st.session_state['session_id'] = session_id
                
                # 重置登录尝试次数
                if username in st.session_state['login_attempts']:
                    st.session_state['login_attempts'][username] = 0
                
                st.success(message)
                st.rerun()
            else:
                # 增加登录尝试次数
                st.session_state['login_attempts'][username] = st.session_state['login_attempts'].get(username, 0) + 1
                st.session_state['last_login_attempt'][username] = datetime.now()
                st.error(message)
                if st.session_state['login_attempts'][username] >= 3:
                    st.warning(f"注意：您还有{5 - st.session_state['login_attempts'][username]}次尝试机会")
    
    with register_tab:
        st.markdown("### 注册新用户")
        new_username = st.text_input("用户名", key="reg_username")
        new_password = st.text_input("密码", type="password", key="reg_password")
        confirm_password = st.text_input("确认密码", type="password", key="reg_confirm")
        
        # 显示密码强度要求
        st.markdown("""
        **密码要求：**
        - 至少8位长度
        - 包含大写字母
        - 包含小写字母
        - 包含数字

        """)
        
        # 预设安全问题列表
        security_questions = [
            "你的出生城市是？",
            "你的小学名称是？",
            "你的第一个宠物的名字是？",
            "你最喜欢的运动是？",
            "你的母亲的名字是？",
            "你的出生年份是？",
            "你的第一个手机号码后四位是？",
            "你的高中班主任的姓氏是？",
            "你的第一个网名是？",
            "你的第一个QQ号码后四位是？"
        ]
        
        # 使用selectbox让用户选择安全问题
        selected_question = st.selectbox(
            "选择安全问题（请选择一个）",
            security_questions,
            key="security_question"
        )
        
        # 用户输入答案
        hint_answer = st.text_input("安全问题答案", key="hint_answer")
        
        if st.button("注册"):
            # 验证用户名格式
            valid_username, username_msg = validate_username(new_username)
            if not valid_username:
                st.error(username_msg)
                st.stop()
            
            # 验证密码强度
            valid_password, password_msg = validate_password(new_password)
            if not valid_password:
                st.error(password_msg)
                st.stop()
            
            if new_password != confirm_password:
                st.error("两次输入的密码不一致")
            elif not new_username or not new_password or not hint_answer:
                st.error("请填写所有必填项")
            else:
                success, message = db_manager.register_user(new_username, new_password, selected_question, hint_answer)
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    with reset_tab:
        st.markdown("### 重置密码")
        reset_username = st.text_input("用户名", key="reset_username")
        if reset_username:
            hint = db_manager.get_hint(reset_username)
            if hint:
                st.info(f"安全问题：{hint}")
                hint_answer = st.text_input("安全问题答案", key="reset_answer")
                new_password = st.text_input("新密码", type="password", key="reset_new_password")
                confirm_new_password = st.text_input("确认新密码", type="password", key="reset_confirm")
                
                # 显示密码强度要求
                st.markdown("""
                **新密码要求：**
                - 至少8位长度
                - 包含大写字母
                - 包含小写字母
                - 包含数字
                
                """)
                
                if st.button("重置密码"):
                    # 验证密码强度
                    valid_password, password_msg = validate_password(new_password)
                    if not valid_password:
                        st.error(password_msg)
                        st.stop()
                    
                    if new_password != confirm_new_password:
                        st.error("两次输入的密码不一致")
                    else:
                        if db_manager.verify_hint_answer(reset_username, hint_answer):
                            success, message = db_manager.reset_password(reset_username, new_password)
                            if success:
                                st.success(message)
                            else:
                                st.error(message)
                        else:
                            st.error("安全问题答案错误")
            else:
                st.error("用户不存在")

    with help_tab:
        st.markdown("### 💡 登录与注册帮助")
        st.markdown("""
        <div class="help-content">
        <h4>登录问题解答</h4>
        <ul>
            <li><strong>无法登录？</strong> 请检查用户名和密码是否正确，区分大小写</li>
            <li><strong>账号被锁定？</strong> 连续5次错误登录后账号会被锁定15分钟</li>
            <li><strong>需要长期登录？</strong> 请勾选"记住登录状态"，可保持7天</li>
        </ul>
        
        <h4>注册须知</h4>
        <ul>
            <li><strong>用户名要求：</strong></li>
            <li>- 长度3-20个字符</li>
            <li>- 只能包含字母和数字</li>
            <li>- 注册后不可更改</li>
        </ul>
        <ul>
            <li><strong>密码要求：</strong></li>
            <li>- 至少8位长度</li>
            <li>- 包含大写字母</li>
            <li>- 包含小写字母</li>
            <li>- 包含数字</li>
        </ul>
        <ul>
            <li><strong>密码要求：</strong></li>
            <li>- 至少8位长度</li>
            <li>- 包含大写字母</li>
            <li>- 包含小写字母</li>
            <li>- 包含数字</li>
        </ul>
        <ul>
            <li><strong>安全问题：</strong></li>
            <li>- 用于密码找回</li>
            <li>- 请选择容易记住但他人难以猜测的答案</li>
            <li>- 答案区分大小写</li>
        </ul>
        
        <h4>密码找回</h4>
        <ul>
            <li>通过"重置密码"标签页</li>
            <li>输入用户名</li>
            <li>回答预设的安全问题</li>
            <li>设置新密码</li>
        </ul>
        
        <h4>注意事项</h4>
        <ul>
            <li>定期更换密码可提高账号安全性</li>
            <li>请勿与他人分享您的登录信息</li>
            <li>尽量避免在公共设备上记住登录状态</li>
            <li>如遇严重问题请联系管理员</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

# 登录后立刻显示新手提示
        st.markdown(
    """
    <div style="font-size:1.3em; background:#fffbe6; border-radius:12px; padding:18px 20px; margin-bottom:18px; border:2px solid #ffe066; display:flex; align-items:center; gap:12px;">
        <span style="font-size:2em;">👉</span>
        <span>
            <b>欢迎使用AI判卷系统！</b><br>
            请点击左上角的 <b style="font-size:1.2em;">""> </b> 展开侧边栏，<br>
            然后点击 <b>➕ 创建新项目</b> 开始体验吧！
        </span>
        <span style="font-size:2em;">✨</span>
    </div>
    """,
    unsafe_allow_html=True
)

# 主界面
else:
    # 添加登出按钮
    if st.sidebar.button("登出"):
        if st.session_state['session_id']:
            db_manager.delete_session(st.session_state['session_id'])
        st.session_state['authenticated'] = False
        st.session_state['current_user'] = None
        st.session_state['session_id'] = None
        st.rerun()
    
    st.sidebar.markdown(f"当前用户：{st.session_state['current_user']}")
    
    # 添加教程展开器
    with st.sidebar.expander("📖 使用教程", expanded=False):
        st.markdown("""
        <div class="tutorial-content">
        <h3>快速入门指南</h3>
        
        <h4>1. 创建新项目</h4>
        <ul>
            <li>点击侧边栏的"➕ 创建新项目"</li>
            <li>输入项目名称（如：2024高一期中考试）</li>
            <li>点击"创建项目"按钮</li>
        </ul>

        <h4>2. 上传内容</h4>
        <ul>
            <li>在"📤 内容上传"标签页中：</li>
            <li>上传题目图片或文档</li>
            <li>上传标准答案</li>
            <li>添加学生并上传他们的作答内容</li>
            <li>上传评分标准（可选）</li>
        </ul>

        <h4>3. 评分方式</h4>
        <ul>
            <li><strong>人工评分：</strong></li>
            <li>点击"🖋️ 人工判卷"标签页</li>
            <li>设置题目数量</li>
            <li>点击"开始人工判卷"</li>
            <li>逐题评分并保存</li>
        </ul>
        <ul>   
            <li><strong>AI自动评分：</strong></li>
            <li>点击"AI自动评分"按钮</li>
            <li>等待AI完成评分</li>
            <li>在"成绩表单"中查看结果</li>
        </ul>

        <h4>4. 查看成绩</h4>
        <ul>
            <li>在"📊 成绩表单"标签页中：</li>
            <li>查看所有学生的成绩</li>
            <li>查看各模型的评分详情</li>
            <li>导出成绩表到Excel</li> 
            <li>查看统计信息</li>
        </ul>

        <h4>5. 系统设置</h4>
        <ul>
            <li><strong>考试满分设置：</strong></li>
            <li>在成绩表单页面点击"⚙️ 设置考试满分"</li>
            <li>输入新的满分值</li>
            <li>点击确认修改</li>
        </ul>
        <ul>
            <li><strong>AI模型选择：</strong></li>
            <li>系统支持多个AI模型：</li>
            <li>- 千问模型（默认）</li>
            <li>- Moonshot模型</li>
            <li>- 智谱AI模型</li>
            <li>可在评分时选择使用不同模型</li>
        </ul>
        <ul>
            <li><strong>文件格式支持：</strong></li>
            <li>图片：PNG, JPG, JPEG</li>
            <li>文档：PDF, DOCX, DOC</li>
            <li>文本：TXT</li>
        </ul>
        <ul>  
            <li><strong>账号管理：</strong></li>
            <li>可随时修改密码</li>
            <li>支持记住登录状态（7天）</li>
            <li>忘记密码可通过安全问题重置</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # 从数据库加载用户的项目数据
    if 'projects' not in st.session_state:
        st.session_state['projects'] = db_manager.get_user_projects(st.session_state['current_user'])
    if 'current_project' not in st.session_state:
        st.session_state['current_project'] = None

    # 新建项目
    with st.sidebar.expander("➕ 创建新项目"):
        new_project_name = st.text_input("项目名称（如：2025高一期中考试）", key="new_project_name_input")
        if st.button("创建项目", key="create_project_button"):
            if new_project_name in st.session_state['projects']:
                st.warning("⚠️ 该项目名已存在！")
            elif new_project_name.strip() == "":
                st.warning("⚠️ 项目名不能为空")
            else:
                st.session_state['projects'][new_project_name] = {}
                st.session_state['current_project'] = new_project_name
                # 保存到数据库
                db_manager.save_project(
                    st.session_state['current_user'],
                    new_project_name,
                    st.session_state['projects'][new_project_name]
                )
                st.success(f"✅ 已创建并进入项目：{new_project_name}")

    # 选择已有项目
    if st.session_state['projects']:
        for name in list(st.session_state['projects'].keys()):
            col1, col2 = st.sidebar.columns([4, 1])
            if col1.button(f"📁 {name}", key=f"switch_{name}"):
                st.session_state['current_project'] = name
            if col2.button("❌", key=f"delete_{name}"):
                del st.session_state['projects'][name]
                # 从数据库删除项目
                db_manager.delete_project(st.session_state['current_user'], name)
                st.sidebar.warning(f"🗑️ 已删除项目：{name}")
                if st.session_state['current_project'] == name:
                    st.session_state['current_project'] = next(
                        iter(st.session_state['projects']), None)
    else:
        st.sidebar.info("暂无项目，请先创建")

# 主页面
if st.session_state['page'] == "main" and st.session_state['current_project']:
    st.markdown(f"### 当前项目：`{st.session_state['current_project']}`")
    
    # 添加选项卡
    tab1, tab2, tab3, tab4 = st.tabs(["📤 内容上传", "🖋️ 人工判卷", "📊 成绩表单", "⚙️ 设置"])
    
    with tab1:
        st.markdown("请上传判卷所需的内容，每项支持多张图片和多个文档上传，可自定义名称：")

        # 移动所有上传功能到Tab1中
        upload_section("📝 题目", "q")
        upload_section("📄 标准答案", "ans")
        upload_student_section()
        upload_section("✅ 评分标准", "rub")

# --------------------
# 1. 项目管理区域
# --------------------
st.sidebar.header("🗂️ 项目管理")

# 新建项目
with st.sidebar.expander("➕ 创建新项目"):
    new_project_name = st.text_input("项目名称（如：2025高一期中考试）")
    if st.button("创建项目"):
        if new_project_name in st.session_state['projects']:
            st.warning("⚠️ 该项目名已存在！")
        elif new_project_name.strip() == "":
            st.warning("⚠️ 项目名不能为空")
        else:
            st.session_state['projects'][new_project_name] = {}
            st.session_state['current_project'] = new_project_name
            st.success(f"✅ 已创建并进入项目：{new_project_name}")

# 选择已有项目
if st.session_state['projects']:
    for name in list(st.session_state['projects'].keys()):
        col1, col2 = st.sidebar.columns([4, 1])
        if col1.button(f"📁 {name}", key=f"switch_{name}"):
            st.session_state['current_project'] = name
        if col2.button("❌", key=f"delete_{name}"):
            del st.session_state['projects'][name]
            st.sidebar.warning(f"🗑️ 已删除项目：{name}")
            if st.session_state['current_project'] == name:
                st.session_state['current_project'] = next(
                    iter(st.session_state['projects']), None)

else:
    st.sidebar.info("暂无项目，请先创建")

# 定义上传学生内容的函数
def upload_student_section():
    st.markdown("#### 👨‍🎓 学生作答（多学生管理）")
    project = st.session_state['projects'][st.session_state['current_project']]

    # 初始化学生数据结构
    if 'stu' not in project or not isinstance(project['stu'], dict):
        project['stu'] = {}

    # 添加学生
    with st.expander("➕ 添加学生"):
        new_students_input = st.text_area(
            "输入多个学生姓名（每行一个）", key="new_student_input")

        # 提前初始化，防止未点击按钮时报错
        added = []
        skipped = []

        if st.button("添加学生"):
            # 拆分输入，去除空行和首尾空格
            new_students = [
                name.strip() for name in new_students_input.split('\n') if name.strip()]

            for name in new_students:
                if name in project['stu']:
                    skipped.append(name)
                else:
                    project['stu'][name] = {'images': [], 'files': []}
                    added.append(name)

            if added:
                st.success(f"✅ 已添加学生：{', '.join(added)}")
                st.session_state['selected_student'] = added[-1]
            if skipped:
                st.warning(f"⚠️ 已跳过已存在学生：{', '.join(skipped)}")

    # 学生选择（下拉菜单）
    if project['stu']:
        student_names = list(project['stu'].keys())
        selected = st.selectbox(
            "选择学生", student_names, key="selected_student_dropdown")
        st.session_state['selected_student'] = selected

        # 添加删除学生按钮
        if st.button("🗑️ 删除当前学生", key="delete_current_student"):
            if selected in project['stu']:
                del project['stu'][selected]
                # 同时删除评分数据
                if selected in st.session_state['manual_grading']['scores']:
                    del st.session_state['manual_grading']['scores'][selected]
                st.success(f"✅ 已删除学生：{selected}")
                # 重新选择下一个学生（如果有）
                if project['stu']:
                    st.session_state['selected_student'] = next(iter(project['stu']))
                else:
                    st.session_state['selected_student'] = None
                st.rerun()

        student_data = project['stu'][selected]
        col_img, col_file = st.columns(2)

        # 上传图片
        with col_img:
            uploaded_imgs = st.file_uploader("上传作答图片", type=[
                                             "png", "jpg", "jpeg"], accept_multiple_files=True, key=f"{selected}_stu_img")
            
            # 清除上传控件状态，避免重复添加
            if f"{selected}_last_img_count" not in st.session_state:
                st.session_state[f"{selected}_last_img_count"] = 0
            
            # 检测新上传
            if uploaded_imgs and len(uploaded_imgs) > 0 and len(uploaded_imgs) != st.session_state[f"{selected}_last_img_count"]:
                st.session_state[f"{selected}_last_img_count"] = len(uploaded_imgs)
                
                # 添加新上传的图片（去重）
                for img in uploaded_imgs:
                    # 检查是否已经存在相同名称的图片
                    if not any(existing_img['name'] == img.name for existing_img in student_data['images']):
                        student_data['images'].append({'name': img.name, 'data': img})
            
            # 批量删除图片功能
            if student_data['images']:
                st.markdown(f"##### 批量管理图片 ({len(student_data['images'])} 张)")
                # 创建复选框让用户选择要删除的图片
                selected_images = []
                cols = st.columns(3)  # 使用3列布局来显示复选框
                for i, item in enumerate(student_data['images']):
                    col_index = i % 3
                    with cols[col_index]:
                        if st.checkbox(f"{item['name']}", key=f"{selected}_img_batch_{i}"):
                            selected_images.append(i)
                
                # 批量删除按钮
                if selected_images:
                    if st.button(f"🗑️ 删除选中的 {len(selected_images)} 张图片", key=f"{selected}_delete_selected_images"):
                        # 从高索引到低索引删除，避免索引变化问题
                        for index in sorted(selected_images, reverse=True):
                            student_data['images'].pop(index)
                        st.success(f"✅ 已删除 {len(selected_images)} 张图片")
                        st.rerun()
            
            # 单个图片管理（保留原有功能）
            for i, item in enumerate(student_data['images']):
                with st.expander(f"📷 {item['name']}"):
                    new_name = st.text_input(
                        "重命名", value=item['name'], key=f"{selected}_img_rename_{i}")
                    item['name'] = new_name
                    if st.button("🗑️ 删除图片", key=f"{selected}_img_del_{i}"):
                        student_data['images'].pop(i)
                        st.rerun()

        # 上传文档
        with col_file:
            uploaded_docs = st.file_uploader("上传作答文档", type=[
                                             "pdf", "docx", "txt"], accept_multiple_files=True, key=f"{selected}_stu_file")
            
            # 清除上传控件状态，避免重复添加
            if f"{selected}_last_doc_count" not in st.session_state:
                st.session_state[f"{selected}_last_doc_count"] = 0
            
            # 检测新上传
            if uploaded_docs and len(uploaded_docs) > 0 and len(uploaded_docs) != st.session_state[f"{selected}_last_doc_count"]:
                st.session_state[f"{selected}_last_doc_count"] = len(uploaded_docs)
                
                # 处理新上传的文档
                for doc in uploaded_docs:
                    # 转换文档为图片并存储（仅处理新文档）
                    doc_name_exists = any('original_file' in img and img['original_file'] == doc.name for img in student_data['images'])
                    if not doc_name_exists:
                        images = convert_document_to_images(doc)
                        if images:
                            for i, img_data in enumerate(images):
                                # 生成图片名称
                                base_name = os.path.splitext(doc.name)[0]
                                img_name = f"{base_name}_page_{i+1}.png"
                                # 将转换的图片添加到学生图片列表
                                student_data['images'].append({
                                    'name': img_name,
                                    'data': img_data,
                                    'original_file': doc.name
                                })
                            st.success(f"已将文档 '{doc.name}' 转换为 {len(images)} 张图片")
                        else:
                            st.error(f"无法转换文档 '{doc.name}' 为图片")

    else:
        st.info("请先添加一位学生后再上传内容。")

# 定义上传内容的通用函数
def upload_section(label, key_prefix):
    """处理文档上传和图片转换的通用函数"""
    # 初始化session state
    if f'{key_prefix}_images' not in st.session_state:
        st.session_state[f'{key_prefix}_images'] = []
    if f'{key_prefix}_converted_files' not in st.session_state:
        st.session_state[f'{key_prefix}_converted_files'] = set()
    
    uploaded_files = st.file_uploader(
        f"上传{label}",
        type=['png', 'jpg', 'jpeg', 'pdf', 'docx', 'doc'],
        key=f"{key_prefix}_uploader",
        accept_multiple_files=True
    )
    
    if uploaded_files:
        new_images = []
        for file in uploaded_files:
            file = fix_uploaded_file(file)
            try:
                # 检查文件是否已经转换过
                if file.name in st.session_state[f'{key_prefix}_converted_files']:
                    logger.info(f"文件 '{file.name}' 已经转换过，跳过转换")
                    continue
                    
                # 检查文件类型
                file_ext = os.path.splitext(file.name)[1].lower()
                
                if file_ext in ['.png', '.jpg', '.jpeg']:
                    # 直接处理图片文件
                    img = Image.open(file)
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)
                    new_images.append({
                        'name': file.name,
                        'data': img_byte_arr,
                        'original_file': file.name
                    })
                    # 添加到已转换文件集合
                    st.session_state[f'{key_prefix}_converted_files'].add(file.name)
                    
                elif file_ext in ['.pdf', '.docx', '.doc']:
                    # 使用文档转换函数处理PDF和Word文档
                    converted_images = convert_document_to_images(file)
                    if converted_images:
                        base_name = os.path.splitext(file.name)[0]
                        for i, img_data in enumerate(converted_images):
                            img_name = f"{base_name}_page_{i+1}.png"
                            new_images.append({
                                'name': img_name,
                                'data': img_data,
                                'original_file': file.name
                            })
                        # 添加到已转换文件集合
                        st.session_state[f'{key_prefix}_converted_files'].add(file.name)
                        st.success(f"已将文档 '{file.name}' 转换为 {len(converted_images)} 张图片")
                    else:
                        st.error(f"无法转换文档 '{file.name}' 为图片")
                else:
                    st.error(f"不支持的文件格式: {file_ext}")
                    
            except Exception as e:
                st.error(f"处理文件 '{file.name}' 时出错: {str(e)}")
                logger.error(f"处理文件 '{file.name}' 时出错: {str(e)}")
                continue
        
        # 更新session state，只添加新转换的图片
        if new_images:
            # 将新图片添加到现有图片列表中
            st.session_state[f'{key_prefix}_images'].extend(new_images)
            st.success(f"✅ 成功添加 {len(new_images)} 张{label}图片")
            
            # 显示预览（只显示新添加的图片）
            st.markdown(f"#### 新添加的{label}预览")
            cols = st.columns(min(3, len(new_images)))
            for idx, img_data in enumerate(new_images):
                with cols[idx % 3]:
                    st.image(img_data['data'], caption=img_data['name'])
        else:
            st.info(f"ℹ️ 没有新的{label}文件需要处理")
            
    # 显示所有已上传图片的数量
    total_images = len(st.session_state[f'{key_prefix}_images'])
    if total_images > 0:
        st.info(f"当前共有 {total_images} 张{label}图片")
        
    return st.session_state[f'{key_prefix}_images']

# --------------------
# 2. 当前项目的上传界面（原始功能）
# --------------------
# 初始化页面状态
if 'page' not in st.session_state:
    st.session_state['page'] = "main"

# 主页面
if st.session_state['page'] == "main" and st.session_state['current_project']:
    st.markdown(f"### 当前项目：`{st.session_state['current_project']}`")
    
    # 添加选项卡
    tab1, tab2, tab3, tab4 = st.tabs(["📤 内容上传", "🖋️ 人工判卷", "📊 成绩表单", "⚙️ 设置"])
    
    with tab1:
        st.markdown("请上传判卷所需的内容，每项支持多张图片和多个文档上传，可自定义名称：")

        # 移动所有上传功能到Tab1中
        upload_section("📝 题目", "q")
        upload_section("📄 标准答案", "ans")
        upload_student_section()
        upload_section("✅ 评分标准", "rub")

    with tab2:
        st.markdown("### 🖋️ 人工判卷")
        
        # 设置题目数量
        with st.expander("⚙️ 设置题目数量"):
            question_count = st.number_input("本次考试题目数量", min_value=1, max_value=50, value=st.session_state['manual_grading']['question_count'] if st.session_state['manual_grading']['question_count'] > 0 else 5)
            if st.button("确认题目数量"):
                old_question_count = st.session_state['manual_grading']['question_count']
                st.session_state['manual_grading']['question_count'] = question_count
                
                # 初始化或调整每个学生的成绩结构
                project = st.session_state['projects'][st.session_state['current_project']]
                if 'stu' in project and isinstance(project['stu'], dict):
                    for student_name in project['stu']: 
                        if student_name not in st.session_state['manual_grading']['scores']:
                            # 新建学生成绩结构
                            st.session_state['manual_grading']['scores'][student_name] = [None] * question_count
                        else:
                            # 调整已有学生的成绩数组长度
                            current_scores = st.session_state['manual_grading']['scores'][student_name]
                            if len(current_scores) < question_count:
                                # 如果新题目数量更多，则扩展数组并补充None
                                st.session_state['manual_grading']['scores'][student_name] = current_scores + [None] * (question_count - len(current_scores))
                            elif len(current_scores) > question_count:
                                # 如果新题目数量更少，则截断数组
                                st.session_state['manual_grading']['scores'][student_name] = current_scores[:question_count]
                
                st.success(f"✅ 已设置题目数量为 {question_count}" + 
                          (f"（之前为 {old_question_count}）" if old_question_count > 0 else ""))
        
        
        # 开始人工判卷
        col1, col2 = st.columns(2)
        
        with col1:
            if st.session_state['manual_grading']['question_count'] > 0:
                if st.button("🖊️ 开始人工判卷"):
                    project = st.session_state['projects'][st.session_state['current_project']]
                    if 'stu' in project and isinstance(project['stu'], dict) and project['stu']:
                        st.session_state['page'] = "manual_grading"
                        st.rerun()
                    else:
                        st.warning("⚠️ 请先添加学生并上传作答内容")
        
        with col2:
            # AI自动评分按钮
            if st.button("🤖 AI自动评分（请耐心等待）"):
                project = st.session_state['projects'][st.session_state['current_project']]
                
                # 检查必要条件
                if st.session_state['manual_grading']['question_count'] <= 0:
                    st.error("⚠️ 请先设置题目数量")
                elif 'stu' not in project or not project['stu']:
                    st.error("⚠️ 请先添加学生并上传作答内容")
                else:
                    # 执行自动评分
                    with st.spinner("🔄 AI正在进行评分，请稍候..."):
                        # 硬编码API密钥
                        with st.expander("⚙️ 详细日志", expanded=False):
                            log_output = st.empty()
                            log_messages = []
                            
                            # 自定义日志处理器
                            class StreamlitLogHandler(logging.Handler):
                                def emit(self, record):
                                    log_messages.append(self.format(record))
                                    log_output.code("\n".join(log_messages))
                            
                            # 添加处理器到logger
                            streamlit_handler = StreamlitLogHandler()
                            streamlit_handler.setLevel(logging.INFO)
                            logger.addHandler(streamlit_handler)
                            
                            try:
                                result = analyze_and_grade_papers(project, QWEN_API_KEY, MOONSHOT_API_KEY, ZHIPU_API_KEY)
                                if result == "AI评分完成":
                                    st.success("✅ AI评分完成！请在「成绩表单」中查看结果")
                                else:
                                    st.error(f"❌ {result}")
                                    st.markdown("如果遇到图片识别问题，请尝试使用上方的「图像识别测试」工具先测试单张图片。")
                            finally:
                                # 移除handler
                                logger.removeHandler(streamlit_handler)
    
    with tab3:
        st.markdown("### 📊 成绩表单")
        
        # 获取学生成绩数据
        scores_data = st.session_state['manual_grading']['scores']
        question_count = st.session_state['manual_grading']['question_count']
        
        if not scores_data:
            st.warning("⚠️ 暂无成绩数据，请先进行评分")
        else:
            # 创建数据表格
            data = []
            for student_name, scores in scores_data.items():
                # 确保scores长度匹配question_count
                if len(scores) < question_count:
                    scores = scores + [None] * (question_count - len(scores))
                elif len(scores) > question_count:
                    scores = scores[:question_count]
                
                # 计算总分（忽略未评分的题目）
                valid_scores = [s for s in scores if s is not None]
                total_score = sum(valid_scores) if valid_scores else 0
                
                # 生成学生数据行
                student_data = [student_name]
                student_data.extend(scores)
                student_data.append(total_score)
                data.append(student_data)
            
            # 按总分排序
            data.sort(key=lambda x: x[-1], reverse=True)
            
            # 添加排名列
            for i, row in enumerate(data):
                row.append(i + 1)  # 添加排名
            
            # 创建表头
            headers = ["学生姓名"]
            headers.extend([f"Q{i+1}" for i in range(question_count)])
            headers.extend(["总分", "排名"])
            
            # 创建DataFrame
            df = pd.DataFrame(data, columns=headers)
            
            # 显示成绩表
            st.dataframe(df, use_container_width=True)
            
            # 添加查看单个模型评分的选项
            st.markdown("### 🔍 模型评分详情")
            model_tabs = st.tabs(["📊 综合评分", "🤖 千问模型评分", "🧠 Moonshot模型评分", "🤖 智谱AI模型评分"])
            
            with model_tabs[0]:
                st.info("当前显示的是三个模型评分（千问、Moonshot和智谱AI）的平均值")
            
            with model_tabs[1]:
                # 显示千问模型的评分结果
                if 'qwen_grading_results' in st.session_state and st.session_state['qwen_grading_results']:
                    qwen_data = []
                    for student_name, scores in st.session_state['qwen_grading_results'].items():
                        # 确保scores长度匹配question_count
                        if len(scores) < question_count:
                            scores = scores + [0] * (question_count - len(scores))
                        elif len(scores) > question_count:
                            scores = scores[:question_count]
                        
                        # 计算总分
                        total_score = sum(scores)
                        
                        # 生成学生数据行
                        student_data = [student_name]
                        student_data.extend(scores)
                        student_data.append(total_score)
                        qwen_data.append(student_data)
                    
                    # 按总分排序
                    qwen_data.sort(key=lambda x: x[-1], reverse=True)
                    
                    # 添加排名列
                    for i, row in enumerate(qwen_data):
                        row.append(i + 1)  # 添加排名
                    
                    # 创建DataFrame
                    qwen_df = pd.DataFrame(qwen_data, columns=headers)
                    st.dataframe(qwen_df, use_container_width=True)
                else:
                    st.warning("暂无千问模型的评分数据")
            
            with model_tabs[2]:
                # 显示Moonshot模型的评分结果
                if 'moonshot_grading_results' in st.session_state and st.session_state['moonshot_grading_results']:
                    moonshot_data = []
                    for student_name, scores in st.session_state['moonshot_grading_results'].items():
                        # 确保scores长度匹配question_count
                        if len(scores) < question_count:
                            scores = scores + [0] * (question_count - len(scores))
                        elif len(scores) > question_count:
                            scores = scores[:question_count]
                        
                        # 计算总分
                        total_score = sum(scores)
                        
                        # 生成学生数据行
                        student_data = [student_name]
                        student_data.extend(scores)
                        student_data.append(total_score)
                        moonshot_data.append(student_data)
                    
                    # 按总分排序
                    moonshot_data.sort(key=lambda x: x[-1], reverse=True)
                    
                    # 添加排名列
                    for i, row in enumerate(moonshot_data):
                        row.append(i + 1)  # 添加排名
                    
                    # 创建DataFrame
                    moonshot_df = pd.DataFrame(moonshot_data, columns=headers)
                    st.dataframe(moonshot_df, use_container_width=True)
                else:
                    st.warning("暂无Moonshot模型的评分数据或未启用Moonshot评分")
            
            with model_tabs[3]:
                # 显示智谱AI模型的评分结果
                if 'zhipu_grading_results' in st.session_state and st.session_state['zhipu_grading_results']:
                    zhipu_data = []
                    for student_name, scores in st.session_state['zhipu_grading_results'].items():
                        # 确保scores长度匹配question_count
                        if len(scores) < question_count:
                            scores = scores + [0] * (question_count - len(scores))
                        elif len(scores) > question_count:
                            scores = scores[:question_count]
                        
                        # 计算总分
                        total_score = sum(scores)
                        
                        # 生成学生数据行
                        student_data = [student_name]
                        student_data.extend(scores)
                        student_data.append(total_score)
                        zhipu_data.append(student_data)
                    
                    # 按总分排序
                    zhipu_data.sort(key=lambda x: x[-1], reverse=True)
                    
                    # 添加排名列
                    for i, row in enumerate(zhipu_data):
                        row.append(i + 1)  # 添加排名
                    
                    # 创建DataFrame
                    zhipu_df = pd.DataFrame(zhipu_data, columns=headers)
                    st.dataframe(zhipu_df, use_container_width=True)
            
            # 显示统计信息
            st.markdown("### 📈 统计信息")
            
            col_stats1, col_stats2 = st.columns(2)
            
            with col_stats1:
                # 计算各类统计量
                total_scores = [row[-2] for row in data]  # 获取所有总分
                avg_score = np.mean(total_scores) if total_scores else 0
                max_score = np.max(total_scores) if total_scores else 0
                min_score = np.min(total_scores) if total_scores else 0
                median_score = np.median(total_scores) if total_scores else 0
                std_dev = np.std(total_scores) if total_scores else 0
                
                st.markdown(f"**平均分**: {avg_score:.2f}")
                st.markdown(f"**最高分**: {max_score:.2f}")
                st.markdown(f"**最低分**: {min_score:.2f}")
                st.markdown(f"**中位数**: {median_score:.2f}")
                st.markdown(f"**标准差**: {std_dev:.2f}")
            
            with col_stats2:
                # 初始化 session_state
                if "exam_full_marks" not in st.session_state:
                    st.session_state.exam_full_marks = 100
                if "editing_full_marks" not in st.session_state:
                    st.session_state.editing_full_marks = False

                # 显示当前满分
                st.markdown(f"**当前满分**: {st.session_state.exam_full_marks}分")

                # 设置按钮：切换"编辑模式"
                if st.button("⚙️ 设置考试满分"):
                    st.session_state.editing_full_marks = True

                # 如果正在编辑，显示输入框和确认按钮
                if st.session_state.editing_full_marks:
                    new_full_marks = st.number_input(
                        "请输入考试满分：",
                        min_value=1,
                        max_value=1000,
                        value=st.session_state.exam_full_marks,
                        step=1,
                        key="full_marks_input"
                    )
                    if st.button("✅ 确认修改"):
                        st.session_state.exam_full_marks = new_full_marks
                        st.session_state.editing_full_marks = False
                        st.success(f"✅ 已更新考试满分为 {new_full_marks} 分")
                        st.rerun()  # 重新运行让 UI 立即刷新为非编辑状态

                # 以下使用更新后的满分计算
                full_marks = st.session_state.exam_full_marks

                # 成绩统计
                passing_threshold = full_marks * 0.6
                excellent_threshold = full_marks * 0.85
                passing_count = sum(1 for score in total_scores if score >= passing_threshold)
                excellent_count = sum(1 for score in total_scores if score >= excellent_threshold)
                total = len(total_scores)

                st.markdown(f"**及格标准(60%)**: {passing_threshold:.1f}分")
                st.markdown(f"**及格人数**: {passing_count}/{total}")
                st.markdown(f"**及格率**: {passing_count / total * 100:.2f}%" if total else "无数据")

                st.markdown(f"**优秀标准(85%)**: {excellent_threshold:.1f}分")
                st.markdown(f"**优秀人数**: {excellent_count}/{total}")
                st.markdown(f"**优秀率**: {excellent_count / total * 100:.2f}%" if total else "无数据")

            # 导出Excel按钮
            if st.button("📥 导出成绩表 (Excel)"):
                # 创建一个新的DataFrame，用于Excel导出
                export_df = df.copy()
                
                # 创建一个BytesIO对象用于保存Excel数据
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    export_df.to_excel(writer, sheet_name='成绩表', index=False)
                
                # 提供下载链接
                b64 = base64.b64encode(output.getvalue()).decode()
                href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="成绩表.xlsx">点击下载Excel文件</a>'
                st.markdown(href, unsafe_allow_html=True)

    with tab4:
        st.markdown("## ⚙️ 系统设置")
        
        # 评分设置
        st.markdown("### ⚖️ 评分设置")
        
        with st.expander("高级评分设置（每题分数）"):
            # 为每个题目设置最大分数
            if st.session_state['manual_grading']['question_count'] > 0:
                st.markdown("设置每道题的最高分值")
                
                # 初始化最大分数设置
                if 'max_scores' not in st.session_state:
                    st.session_state['max_scores'] = [100] * st.session_state['manual_grading']['question_count']
                elif len(st.session_state['max_scores']) != st.session_state['manual_grading']['question_count']:
                    # 确保长度匹配
                    if len(st.session_state['max_scores']) < st.session_state['manual_grading']['question_count']:
                        st.session_state['max_scores'] = st.session_state['max_scores'] + [100] * (st.session_state['manual_grading']['question_count'] - len(st.session_state['max_scores']))
                    else:
                        st.session_state['max_scores'] = st.session_state['max_scores'][:st.session_state['manual_grading']['question_count']]
                
                cols = st.columns(3)  # 使用3列布局
                max_scores_changed = False
                
                for i in range(st.session_state['manual_grading']['question_count']):
                    col_idx = i % 3
                    with cols[col_idx]:
                        new_max = st.number_input(
                            f"题目 {i+1} 最高分", 
                            min_value=1.0, 
                            max_value=1000.0, 
                            value=float(st.session_state['max_scores'][i]),
                            step=1.0,
                            key=f"max_score_{i}"
                        )
                        
                        if new_max != st.session_state['max_scores'][i]:
                            st.session_state['max_scores'][i] = new_max
                            max_scores_changed = True
                
                if max_scores_changed:
                    st.success("✅ 已更新题目最高分设置")
            else:
                st.info("请先在「人工判卷」标签页设置题目数量")
        
        # 界面设置
        st.markdown("#### 🎨 界面设置")
        with st.expander("界面偏好"):
            st.markdown("自定义界面显示选项")
            show_preview = st.checkbox("启用图片预览", value=True)
            if show_preview:
                preview_size = st.slider("预览图片大小", min_value=100, max_value=800, value=400)
                st.session_state['preview_size'] = preview_size
            
            theme = st.radio("界面主题", ["明亮", "暗黑"], horizontal=True)
            if theme == "暗黑":
                st.warning("⚠️ 主题将在下次启动应用时生效")

# 人工判卷页面
elif st.session_state['page'] == "manual_grading" and st.session_state['current_project']:
    project = st.session_state['projects'][st.session_state['current_project']]
    student_names = list(project['stu'].keys())
    question_count = st.session_state['manual_grading']['question_count']
    current_student_index = st.session_state['manual_grading']['current_student_index']
    current_image_index = st.session_state['manual_grading']['current_image_index']
    
    # 返回主页按钮
    if st.button("⬅️ 返回主页"):
        st.session_state['page'] = "main"
        st.rerun()
    
    # 显示当前学生信息
    current_student = student_names[current_student_index]
    st.markdown(f"### 正在评阅：{current_student} 的答卷")
    
    # 创建两列布局：左侧显示学生作答内容，右侧是评分区域
    col_content, col_score = st.columns([3, 2])
    
    with col_content:
        st.markdown("#### 📝 学生作答内容")
        student_data = project['stu'][current_student]
        
        # 显示学生作答图片
        if student_data['images']:
            # 添加图片导航按钮
            img_nav_col1, img_nav_col2, img_nav_col3 = st.columns([1, 3, 1])
            with img_nav_col1:
                if st.button("⬅️ 上一张") and current_image_index > 0:
                    st.session_state['manual_grading']['current_image_index'] -= 1
                    st.rerun()
            
            with img_nav_col2:
                current_img = student_data['images'][current_image_index]
                img_info = current_img['name']
                if 'original_file' in current_img:
                    img_info += f" (来自 {current_img['original_file']})"
                st.markdown(f"**图片 {current_image_index + 1}/{len(student_data['images'])}**: {img_info}")
            
            with img_nav_col3:
                if st.button("➡️ 下一张") and current_image_index < len(student_data['images']) - 1:
                    st.session_state['manual_grading']['current_image_index'] += 1
                    st.rerun()
            
            # 显示当前图片
            if 0 <= current_image_index < len(student_data['images']):
                img_data = student_data['images'][current_image_index]['data']
                try:
                    image = Image.open(img_data)
                    
                    # 创建按钮布局
                    rotate_cw_col, rotate_ccw_col = st.columns([1, 1])
                    
                    # 旋转按钮
                    with rotate_cw_col:
                        rotate_cw = st.button("🔄 逆时针旋转")
                    
                    with rotate_ccw_col:
                        rotate_ccw = st.button("🔄 顺时针旋转")
                    
                    # 处理旋转
                    if 'rotated_angle' not in st.session_state:
                        st.session_state['rotated_angle'] = 0
                        
                    if rotate_cw:
                        st.session_state['rotated_angle'] = (st.session_state['rotated_angle'] + 90) % 360
                        st.rerun()
                        
                    if rotate_ccw:
                        st.session_state['rotated_angle'] = (st.session_state['rotated_angle'] - 90) % 360
                        st.rerun()
                    
                    # 应用旋转
                    if st.session_state['rotated_angle'] != 0:
                        image = image.rotate(st.session_state['rotated_angle'], expand=True)
                    
                    # 普通图片预览
                    st.image(image, caption=student_data['images'][current_image_index]['name'], use_container_width=True)
                except Exception as e:
                    st.error(f"无法显示图片：{e}")
        else:
            st.info("该学生未上传作答内容")

        # 移除文档显示部分
    
    with col_score:
        st.markdown("#### ✅ 评分区域")
        
        # 创建评分表单
        with st.form(key=f"grading_form_{current_student}"):
            scores = st.session_state['manual_grading']['scores'].get(current_student, [None] * question_count)
            
            # 确保分数列表长度与问题数量匹配
            if len(scores) < question_count:
                scores = scores + [None] * (question_count - len(scores))
            elif len(scores) > question_count:
                scores = scores[:question_count]
            
            # 为每道题目创建评分输入
            for q_idx in range(question_count):
                st.markdown(f"**第 {q_idx + 1} 题评分：**")
                # 创建评分按钮组和输入框并排显示
                col_btns, col_input = st.columns([3, 2])
                
                with col_btns:
                    # 使用radio代替按钮，这是表单兼容的
                    score_options = [1, 2, 3, 4, 5]
                    selected_score = st.radio(
                        "快速选择分数", 
                        score_options, 
                        horizontal=True,
                        key=f"score_radio_{current_student}_{q_idx}",
                        index=None
                    )
                    
                    # 如果选择了新的分数，更新session_state中的自定义分数
                    if selected_score is not None:
                        scores[q_idx] = selected_score
                        st.session_state[f"custom_score_{current_student}_{q_idx}"] = float(selected_score)
                
                with col_input:
                    # 添加自定义分数输入
                    custom_score = st.number_input(
                        "分数", 
                        min_value=0.0, 
                        max_value=100.0, 
                        value=float(scores[q_idx]) if scores[q_idx] is not None else 0.0,
                        step=0.5,
                        key=f"custom_score_{current_student}_{q_idx}"
                    )
                    # 更新分数到session_state
                    scores[q_idx] = custom_score
                
                # 显示当前分数和评分状态
                st.markdown(f"当前分数：**{scores[q_idx] if scores[q_idx] is not None else '未评分'}**")
                st.markdown("---")
            
            # 提交按钮 - 使用form_submit_button确保表单数据被提交
            submitted = st.form_submit_button("💾 保存评分")
            if submitted:
                st.session_state['manual_grading']['scores'][current_student] = scores.copy()
                st.success(f"✅ 已保存 {current_student} 的评分")
        
        # 学生导航按钮
        st.markdown("#### 切换学生")
        nav_col1, nav_col2 = st.columns(2)
        with nav_col1:
            if st.button("⬅️ 上一位学生") and current_student_index > 0:
                st.session_state['manual_grading']['current_student_index'] -= 1
                st.session_state['manual_grading']['current_image_index'] = 0
                st.rerun()
        
        with nav_col2:
            if st.button("➡️ 下一位学生") and current_student_index < len(student_names) - 1:
                st.session_state['manual_grading']['current_student_index'] += 1
                st.session_state['manual_grading']['current_image_index'] = 0
                st.rerun()
        
        # 显示评分进度
        st.progress(sum(1 for s in scores if s is not None) / question_count)
        st.markdown(f"已完成：{sum(1 for s in scores if s is not None)}/{question_count} 题")

 
