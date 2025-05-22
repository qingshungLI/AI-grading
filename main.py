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
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
from jsoncat import *
# Import OpenAI client for Moonshot API
from openai import OpenAI
import base64
from convert import *
from modelcall import *
from analyse import *
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









st.title("📚 AI-grading-V2（左上角‘>’创建项目）")

# 初始化 session_state 中的项目列表
if 'projects' not in st.session_state:
    st.session_state['projects'] = {}  # {项目名: 数据结构}
if 'current_project' not in st.session_state:
    st.session_state['current_project'] = None
if 'manual_grading' not in st.session_state:
    st.session_state['manual_grading'] = {
        'question_count': 0,
        'current_student_index': 0,
        'current_image_index': 0,
        'scores': {}
    }

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
                    st.image(img_data['data'], caption=img_data['name'], use_column_width=True)
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

                # 设置按钮：切换“编辑模式”
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
                    st.image(image, caption=student_data['images'][current_image_index]['name'], use_column_width=True)
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

 
