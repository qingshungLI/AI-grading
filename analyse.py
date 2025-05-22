import streamlit as st

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
from modelcall import (
    simple_qwen_vl_call,
    simple_zhipu_call,
    simple_moonshot_call,
    call_qwen_vl_api_direct,
    call_qwen_vl_api,
    ZHIPU_API_KEY,
    MOONSHOT_API_KEY,
    QWEN_API_KEY
)
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




def analyze_and_grade_papers(project, api_key, moonshot_api_key=MOONSHOT_API_KEY, zhipu_api_key=ZHIPU_API_KEY):
    """
    分析并评分所有学生的答卷，使用三个AI模型并取平均值
    
    参数:
    project - 项目数据
    api_key - Qwen API密钥
    moonshot_api_key - Moonshot API密钥(可选)
    zhipu_api_key - zhipu API密钥(可选)
    
    返回:
    成功或失败的状态信息
    """
    logger.info("开始AI自动评分流程")
    
    if not api_key:
        logger.error("未提供千问API密钥")
        return "请提供千问API密钥"
    
    # 获取问题数量
    question_count = st.session_state['manual_grading']['question_count']
    if question_count <= 0:
        logger.error("题目数量未设置")
        return "请先设置题目数量"
    
    # 初始化评分结果存储
    if 'qwen_grading_results' not in st.session_state:
        st.session_state['qwen_grading_results'] = {}
    if 'moonshot_grading_results' not in st.session_state:
        st.session_state['moonshot_grading_results'] = {}
    if 'zhipu_grading_results' not in st.session_state:
        st.session_state['zhipu_grading_results'] = {}
    if 'ai_grading_results' not in st.session_state:
        st.session_state['ai_grading_results'] = {}
    
    # 初始化每个学生的分数数组
    qwen_scores = [None] * question_count
    moonshot_scores = [None] * question_count
    doubao_scores = [None] * question_count
    zhipu_scores = [None] * question_count
    
    # 获取参考内容（题目、标准答案和评分标准）
    question_images = st.session_state.get('q_images', [])
    answer_images = st.session_state.get('ans_images', [])
    rubric_images = st.session_state.get('rub_images', [])
    
    logger.info(f"找到 {len(question_images)} 张题目图片, {len(answer_images)} 张标准答案图片, {len(rubric_images)} 张评分标准图片")
    
    # 检查是否有足够的参考材料
    if not question_images:
        logger.error("未上传题目图片")
        return "请上传题目图片"
    
    # 提取评分标准
    scoring_rubrics = []
    if rubric_images:
        st.info("正在分析评分标准...")
        logger.info("开始分析评分标准")
        
        for i, rub_img in enumerate(rubric_images):
            try:
                logger.info(f"正在处理第 {i+1}/{len(rubric_images)} 张评分标准图片")
                prompt = """
                请仔细分析这张图片中的评分标准内容。
                
                要求:
                1. 识别所有题目的评分标准
                2. 提取每个题目的得分点
                3. 记录每个得分点的分值
                4. 注意评分细则和特殊要求
                5. 如果标准中包含扣分项，请特别标注
                
                请以结构化的方式提取评分标准，确保包含所有评分细节。
                """
                
                result = call_qwen_vl_api(rub_img['data'], prompt, api_key)
                if result:
                    scoring_rubrics.append(result)
                    logger.info(f"成功提取评分标准，内容长度: {len(result)}")
                else:
                    logger.warning(f"从评分标准图片 {i+1} 提取内容失败")
            except Exception as e:
                logger.error(f"分析评分标准图片时出错: {str(e)}", exc_info=True)
                st.warning(f"分析评分标准图片时出错: {str(e)}")
    
    # 如果没有评分标准，创建一个默认的评分标准
    if not scoring_rubrics:
        logger.warning("未找到评分标准，将使用默认评分标准")
        default_rubric = "评分标准：\n1. 答案正确性：60%\n2. 解题过程：30%\n3. 书写规范：10%"
        scoring_rubrics = [default_rubric]
        st.warning("⚠️ 未找到评分标准，将使用默认评分标准")
    
    # 从图片中提取题目信息
    questions_info = []
    st.info("正在分析题目图片...")
    logger.info("开始分析题目图片")
    
    for i, q_img in enumerate(question_images):
        try:
            logger.info(f"正在处理第 {i+1}/{len(question_images)} 张题目图片")
            # 使用更加明确和结构化的提示语
            prompt = """
            请仔细分析这张图片中的所有题目内容。
            
            要求:
            1. 识别所有可见的题目编号和题目内容
            2. 即使只能部分识别，也请提取出来
            3. 按照题号顺序列出所有题目
            4. 如果看不清某些部分，请尽量猜测或描述你能看到的内容
            5. 如果没有明确题号，请按顺序标注为"题目1"、"题目2"等
            
            请确保提取尽可能多的信息，即使图片质量不佳。
            """
            
            # 尝试处理图片，即使API失败也能继续
            result = call_qwen_vl_api(q_img['data'], prompt, api_key)
            if result:  # 确保结果不是None
                questions_info.append(result)
                logger.info(f"成功提取题目信息，内容长度: {len(result)}")
            else:
                # 如果API失败，尝试使用备用提示词
                logger.warning(f"从题目图片 {i+1} 提取内容失败，尝试备用提示")
                backup_prompt = "描述这张图片中你能看到的所有文字内容，不需要分析，只需要尽可能准确地提取文字。"
                backup_result = call_qwen_vl_api(q_img['data'], backup_prompt, api_key)
                if backup_result:
                    questions_info.append(backup_result)
                    logger.info(f"使用备用提示词成功提取内容，长度: {len(backup_result)}")
                else:
                    logger.error(f"备用提示词也失败了")
        except Exception as e:
            logger.error(f"分析题目图片时出错: {str(e)}", exc_info=True)
            st.warning(f"分析题目图片时出错: {str(e)}")
    
    # 确保questions_info中没有None值
    questions_info = [q for q in questions_info if q is not None]
    logger.info(f"成功提取 {len(questions_info)} 条题目信息")
    
    # 如果没有成功提取任何题目信息，但仍有题目图片，则创建一个默认题目列表
    if not questions_info and question_images:
        logger.warning("无法提取题目信息，将创建默认题目列表")
        default_questions = []
        for i in range(st.session_state['manual_grading']['question_count']):
            default_questions.append(f"题目 {i+1}: [无法从图片中提取，但系统将继续评分]")
        questions_info = ["\n".join(default_questions)]
        st.warning("⚠️ 无法从题目图片中提取信息，将使用默认题目列表继续评分")
    elif not questions_info:
        logger.error("无法从题目图片中提取有效信息")
        return "无法从题目图片中提取有效信息，请检查图片内容或调整图片质量"
    
    # 提取标准答案
    standard_answers = []
    st.info("正在分析标准答案图片...")
    logger.info("开始分析标准答案图片")
    
    for i, ans_img in enumerate(answer_images):
        try:
            logger.info(f"正在处理第 {i+1}/{len(answer_images)} 张标准答案图片")
            # 使用更加明确和结构化的提示语
            prompt = """
            请仔细分析这张图片中的所有标准答案内容。
            
            要求:
            6. 识别所有可见的题目答案
            7. 即使只能部分识别，也请提取出来
            8. 按照题号顺序列出所有标准答案
            9. 如果看不清某些部分，请尽量猜测或描述你能看到的内容
            10. 如果没有明确题号，请按顺序标注为"答案1"、"答案2"等
            
            请确保提取尽可能多的信息，即使图片质量不佳。
            """
            
            result = call_qwen_vl_api(ans_img['data'], prompt, api_key)
            if result:  # 确保结果不是None
                standard_answers.append(result)
                logger.info(f"成功提取标准答案，内容长度: {len(result)}")
            else:
                # 如果API失败，尝试使用备用提示词
                logger.warning(f"从标准答案图片 {i+1} 提取内容失败，尝试备用提示")
                backup_prompt = "描述这张图片中你能看到的所有文字内容，不需要分析，只需要尽可能准确地提取文字。"
                backup_result = call_qwen_vl_api(ans_img['data'], backup_prompt, api_key)
                if backup_result:
                    standard_answers.append(backup_result)
                    logger.info(f"使用备用提示词成功提取内容，长度: {len(backup_result)}")
                else:
                    logger.error(f"备用提示词也失败了")
        except Exception as e:
            logger.error(f"分析标准答案图片时出错: {str(e)}", exc_info=True)
            st.warning(f"分析标准答案图片时出错: {str(e)}")
    
    # 确保standard_answers中没有None值
    standard_answers = [a for a in standard_answers if a is not None]
    logger.info(f"成功提取 {len(standard_answers)} 条标准答案信息")
    
    # 如果没有成功提取任何标准答案信息，但有图片，创建默认答案
    if not standard_answers and answer_images:
        logger.warning("无法提取标准答案信息，将创建默认答案")
        default_answers = []
        for i in range(st.session_state['manual_grading']['question_count']):
            default_answers.append(f"答案 {i+1}: [无法从图片中提取，但系统将继续评分]")
        standard_answers = ["\n".join(default_answers)]
        st.warning("⚠️ 无法从标准答案图片中提取信息，将使用默认答案继续评分")
    
    # 为每个学生评分
    total_students = len(project['stu'])
    processed_students = 0
    logger.info(f"开始为 {total_students} 名学生评分")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 修改评分prompt，加入评分标准
    def create_grading_prompt(student_answer, question_info, standard_answer, rubric):
        """创建包含评分标准的评分提示词"""
        prompt = f"""
        请根据以下信息对学生答案进行评分：

        题目信息：
        {question_info}

        标准答案：
        {standard_answer}

        评分标准：
        {rubric}

        学生答案：
        {student_answer}

        评分要求：
        1. 严格按照评分标准进行评分
        2. 对每个得分点进行详细分析
        3. 说明扣分原因（如果有）
        4. 给出具体的得分理由
        5. 最后以JSON格式返回分数，格式为: {{"题号": 分数}}

        请确保：
        - 评分过程客观公正
        - 严格按照评分标准执行
        - 详细说明评分理由
        - 最终分数必须符合评分标准中的分值范围
        """
        return prompt

    for student_name, student_data in project['stu'].items():
        processed_students += 1
        progress = processed_students / total_students
        progress_bar.progress(progress)
        status_text.text(f"正在评分: {student_name} ({processed_students}/{total_students})")
        logger.info(f"开始评分学生 {student_name} ({processed_students}/{total_students})")
        
        # 检查学生是否有答卷图片
        if not student_data['images']:
            logger.warning(f"学生 {student_name} 没有上传答卷图片")
            st.warning(f"学生 {student_name} 没有上传答卷图片")
            continue
        
        logger.info(f"学生 {student_name} 有 {len(student_data['images'])} 张答卷图片")
        
        # 初始化该学生的评分结果
        student_scores = [None] * question_count
        
        for img_idx, img_data in enumerate(student_data['images']):
            try:
                logger.info(f"正在处理学生 {student_name} 的第 {img_idx+1}/{len(student_data['images'])} 张答卷图片")
                
                # 获取当前题目的相关信息
                question_info = questions_info[img_idx] if img_idx < len(questions_info) else f"题目 {img_idx + 1}"
                standard_answer = standard_answers[img_idx] if img_idx < len(standard_answers) else "标准答案未提供"
                rubric = scoring_rubrics[0] if scoring_rubrics else "使用默认评分标准"
                
                # 处理学生答案
                student_answer = ""  # 这里需要从学生图片中提取答案
                # TODO: 实现从学生图片中提取答案的逻辑
                
                # 使用新的评分prompt
                grading_prompt = create_grading_prompt(
                    student_answer,
                    question_info,
                    standard_answer,
                    rubric
                )
                
                # 构建上下文信息字符串，确保每个部分都有有效内容
                context_parts = []
                
                if questions_info:
                    context_parts.append("题目信息：" + "\n".join(questions_info))
                
                if standard_answers:
                    context_parts.append("标准答案：" + "\n".join(standard_answers))
                
                if scoring_rubrics:
                    context_parts.append("评分标准：" + "\n".join(scoring_rubrics))
                
                # 合并所有上下文信息
                context = "\n".join(context_parts)
                logger.debug(f"构建的上下文信息长度: {len(context)}")
                
                prompt = f"""
                请仔细识别图片中的学生作答内容，不要进行分析报告。
                请根据以下信息评分这张学生答卷:
                
                {context}
                
                针对这张答卷图片:
                1. 首先仔细识别图片中学生的所有作答内容，确保不遗漏任何答案
                2. 识别学生回答了哪些题目，即使答案不完整也要识别
                3. 对每道题目与标准答案进行对比
                4. 根据评分标准给每道题打分
                5. 如果学生没有回答这道题，请打0分

                请以JSON格式返回结果，格式为: {{"1": 分数, "2": 分数, ...}}，可以包含一些解释和分析
                
                例如，如果学生做了第1题和第3题，你的评分是第1题得80分，第3题得90分，那么返回:
                {{"1": 80, "3": 90}},最后返回的json一定要保证只有题目上限之内的非0分数，题目上限以上的数字对应0
                
                如果学生做了全部{question_count}题，那么返回:
                {{"1": 分数1, "2": 分数2, ..., "{question_count}": 分数{question_count}}}
                
                请确保:
                - 题号必须是字符串形式的数字，如"1"、"2"，不要用"题目1"或"Q1"，总题号数量依照设置为准
                - 分数必须是数字，严格按照评分标准给分
                - 严格按照上述JSON格式返回，可以添加一些辅助的文本分析和解释
                - 分数必须是数字，不要用文字描述分数
                - 分数必须是数字，不要用文字描述分数
                - 最后的分数一定小于评分标准的最高分
                - 返回的是这个学生的得分而不是这个题目的评分标准
                - 保证根据学生的答题情况和评分标准给分，所有的学生应该有差异（最重要，一定要注意）
                - 如果学生交的是白卷，请返回{{"1": 0, "2": 0, ..., "{question_count}": 0}}

                
                重要提示：请确保返回的文本中包含JSON格式
                """
                
                # 添加获取JSON结果的专门提示词 - 优化版
                json_prompt = f"""
                请仔细识别图片中的学生作答内容，不要进行分析报告。
                请根据以下信息评分这张学生答卷并返回JSON格式结果。

                {context}
                
                针对这张答卷图片:
                1. 首先仔细识别图片中学生的所有作答内容，确保不遗漏任何答案
                2. 识别学生回答了哪些题目，即使答案不完整也要识别
                3. 对每道题目与标准答案进行对比
                4. 根据评分标准给每道题打分
                5. 如果学生没有回答这道题，请打0分

                请以JSON格式返回结果，格式为: {{"1": 分数, "2": 分数, ...}}，可以包含一些解释和分析
                
                例如，如果学生做了第1题和第3题，你的评分是第1题得80分，第3题得90分，那么返回:
                {{"1": 80, "3": 90}}
                
                如果学生做了全部{question_count}题，那么返回:
                {{"1": 分数1, "2": 分数2, ..., "{question_count}": 分数{question_count}}}
                
                请确保:
                - 题号必须是字符串形式的数字，如"1"、"2"，不要用"题目1"或"Q1"，总题号数量依照设置为准
                - 分数必须是数字，严格按照评分标准给分
                - 严格按照上述JSON格式返回，可以添加一些辅助的文本分析和解释
                - 如果最终的结果不对，最多给这一问满分的一半分，例如第一问满分20，那么最多给10分，第二问满分15，那么最多给7分（直接舍去小数位）
                - 分数必须是数字，不要用文字描述分数
                - 分数必须是数字，不要用文字描述分数
                - 最后的分数一定小于评分标准的最高分
                - 返回的是这个学生的得分而不是这个题目的评分标准
                - 保证根据学生的答题情况和评分标准给分，所有的学生应该有差异（最重要，一定要注意）
                - 如果学生交的是白卷，请返回{{"1": 0, "2": 0, ..., "{question_count}": 0}}

                
                重要提示：请确保返回的文本中包含JSON格式
                """
                
                try:
                    # 检查并预处理图片
                    img_file = img_data['data']
                    
                    # 打开图片并检查格式
                    try:
                        with Image.open(img_file) as img:
                            # 记录原始图片信息，有助于排查问题
                            logger.debug(f"原始图片信息 - 格式: {img.format}, 大小: {img.size}, 模式: {img.mode}")
                            
                            # 如果不是RGB模式，转换为RGB模式
                            if img.mode != 'RGB':
                                logger.info(f"将图片从 {img.mode} 模式转换为 RGB 模式")
                                img = img.convert('RGB')
                            
                            # 保存为临时文件
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                                img.save(temp_file, format='JPEG', quality=95)
                                processed_img_path = temp_file.name
                            
                            logger.info(f"图片已预处理并保存为临时文件: {processed_img_path}")
                            
                            # 1. 使用Qwen VL模型评分
                            st.info(f"🔍 正在使用千问模型评分: {student_name} 图片 {img_idx+1}...")
                            logger.info("使用千问模型处理学生答卷")
                            qwen_score_dict = simple_qwen_vl_call(processed_img_path, json_prompt, api_key)
                            
                            # 2. 使用Moonshot模型评分
                            if MOONSHOT_AVAILABLE:
                                st.info(f"🔍 正在使用Moonshot模型评分: {student_name} 图片 {img_idx+1}...")
                                logger.info("使用Moonshot模型处理学生答卷")
                                moonshot_score_dict = simple_moonshot_call(processed_img_path, json_prompt, MOONSHOT_API_KEY)
                            else:
                                
                                logger.warning("未提供Moonshot API密钥，跳过Moonshot评分")
                            # 没有Moonshot API时，使用千问分数作为Moonshot分数
                                moonshot_score_dict = qwen_score_dict.copy()
                        
                            # 3. 使用智谱AI模型评分
                            if ZHIPU_AVAILABLE:
                                st.info(f"🔍 正在使用智谱AI GLM-4V模型评分: {student_name} 图片 {img_idx+1}...")
                                logger.info("使用智谱AI GLM-4V模型处理学生答卷")
                                zhipu_score_dict = simple_zhipu_call(processed_img_path, json_prompt,ZHIPU_API_KEY)
                                # 使用zhipu_score_dict替代原来的doubao_score_dict
                                doubao_score_dict = zhipu_score_dict
                            else:
                                if not ZHIPU_AVAILABLE:
                                    logger.warning("未安装智谱AI SDK，跳过智谱评分")
                                    st.warning("未安装智谱AI SDK，跳过智谱评分。请运行 pip install zhipuai")
                                elif not ZHIPU_API_KEY:
                                    logger.warning("未提供智谱AI API密钥，跳过智谱评分")
                                
                                # 没有智谱AI API时，使用千问分数
                                doubao_score_dict = qwen_score_dict.copy()
                                logger.info("使用千问分数作为智谱AI分数")
                                
                            logger.info(f"千问评分结果: {qwen_score_dict}")
                            logger.info(f"Moonshot评分结果: {moonshot_score_dict}")
                            logger.info(f"智谱AI评分结果: {doubao_score_dict}")
                            
                            # 4. 合并三个模型的结果，取平均值
                            # 获取所有题号
                            all_questions = set()
                            for q in qwen_score_dict.keys():
                                if q.isdigit() and 0 < int(q) <= question_count:
                                    all_questions.add(q)
                            for q in moonshot_score_dict.keys():
                                if q.isdigit() and 0 < int(q) <= question_count:
                                    all_questions.add(q)
                            for q in doubao_score_dict.keys():
                                if q.isdigit() and 0 < int(q) <= question_count:
                                    all_questions.add(q)
                            
                            # 计算平均分
                            avg_scores = {}
                            for q in all_questions:
                                qwen_score = float(qwen_score_dict.get(q, 0))
                                moonshot_score = float(moonshot_score_dict.get(q, 0))
                                doubao_score = float(doubao_score_dict.get(q, 0))
                                zhipu_score = float(zhipu_score_dict.get(q, 0))
                                avg_score = (qwen_score + moonshot_score + doubao_score + zhipu_score) / 4
                                avg_scores[q] = avg_score
                            
                            logger.info(f"平均评分结果: {avg_scores}")
                            
                            # 过滤超出范围的题号
                            filtered_questions = set()
                            for q_num_str in all_questions:
                                try:
                                    q_num = int(q_num_str)
                                    if 1 <= q_num <= question_count:  # 确保题号在有效范围内
                                        filtered_questions.add(q_num_str)
                                    else:
                                        logger.warning(f"题号 {q_num_str} 超出题目数量上限 {question_count}，将被忽略")
                                except ValueError:
                                    logger.warning(f"无效题号格式: {q_num_str}")
                            
                            logger.info(f"过滤后的有效题号: {filtered_questions}")
                            
                            # 更新每个模型的得分和最终得分
                            for q_num_str in filtered_questions:
                                try:
                                    q_num = int(q_num_str) - 1  # 转为0索引
                                    # 更新千问得分
                                    qwen_score = float(qwen_score_dict.get(q_num_str, 0))
                                    if qwen_scores[q_num] is None or qwen_score > qwen_scores[q_num]:
                                        qwen_scores[q_num] = qwen_score
                                        
                                    # 更新Moonshot得分
                                    moonshot_score = float(moonshot_score_dict.get(q_num_str, 0))
                                    if moonshot_scores[q_num] is None or moonshot_score > moonshot_scores[q_num]:
                                        moonshot_scores[q_num] = moonshot_score
                                
                                    # 更新Doubao得分
                                    doubao_score = float(doubao_score_dict.get(q_num_str, 0))
                                    if doubao_scores[q_num] is None or doubao_score > doubao_scores[q_num]:
                                        doubao_scores[q_num] = doubao_score
                                    
                                    # 更新智谱AI得分
                                    zhipu_score = float(zhipu_score_dict.get(q_num_str, 0))
                                    if zhipu_scores[q_num] is None or zhipu_score > zhipu_scores[q_num]:
                                        zhipu_scores[q_num] = zhipu_score
                                            
                                        # 更新平均得分
                                        avg_score = avg_scores.get(q_num_str, 0)
                                        if student_scores[q_num] is None or avg_score > student_scores[q_num]:
                                            student_scores[q_num] = avg_score
                                except (ValueError, IndexError) as e:
                                    logger.warning(f"处理题号 {q_num_str} 时出错: {str(e)}")
                                    continue
                            
                            # 处理完成后删除临时文件
                            try:
                                os.remove(processed_img_path)
                                logger.debug("临时图片文件已删除")
                            except Exception as e:
                                logger.warning(f"无法删除临时图片文件: {processed_img_path}")
                    except Exception as img_e:
                        logger.error(f"图片处理错误: {str(img_e)}")
                        st.error(f"图片处理错误: {str(img_e)}")
                except Exception as e:
                    logger.error(f"评分过程出错: {str(e)}")
                    st.error(f"评分过程出错: {str(e)}")
            except Exception as e:
                logger.error(f"处理学生 {student_name} 的答卷时出错: {str(e)}", exc_info=True)
                st.error(f"处理学生 {student_name} 的答卷时出错: {str(e)}")
        
        # 确保所有分数都有值（将None替换为0）
        qwen_scores = [s if s is not None else 0.0 for s in qwen_scores]
        moonshot_scores = [s if s is not None else 0.0 for s in moonshot_scores]  
        final_scores = [s if s is not None else 0.0 for s in student_scores]
        zhipu_scores = [s if s is not None else 0.0 for s in zhipu_scores]     
        # 保存该学生的最终分数
        st.session_state['qwen_grading_results'][student_name] = qwen_scores
        st.session_state['moonshot_grading_results'][student_name] = moonshot_scores
        st.session_state['ai_grading_results'][student_name] = final_scores
        st.session_state['zhipu_grading_results'][student_name] = zhipu_scores
        logger.info(f"已保存学生 {student_name} 的分数: {final_scores}")
        
        # 更新手动评分中的分数
        st.session_state['manual_grading']['scores'][student_name] = final_scores.copy()
    
    progress_bar.progress(1.0)
    status_text.text("评分完成!")
    logger.info("AI评分流程完成")
    return "AI评分完成" 
