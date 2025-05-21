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
import pythoncom  # 添加COM支持
import win32com.client  # 添加Windows COM支持
from jsoncat import *
# Import OpenAI client for Moonshot API
from openai import OpenAI
import base64
from convert import *
# Remove circular import
# from modelcall import *  # This is also unnecessary since we're in modelcall.py
# from analyse import *    # Remove this circular import
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

dashscope.api_key = ""
def create_scoring_prompt(base_prompt, question_count, max_score):
    """
    创建标准化的评分提示词，确保模型输出符合要求的分数
    
    参数:
    base_prompt - 基础提示词
    question_count - 题目数量上限
    max_score - 每道题的满分值
    
    返回:
    优化后的提示词
    """
    scoring_instruction = f"""
请严格按照以下要求进行评分（评分标准非常严格）：

1. 题目数量限制：
   - 本试卷共有 {question_count} 道题目
   - 只对第1到第{question_count}题进行评分
   - 严禁输出第{question_count}题之后的分数
   - 如果看到第{question_count}题之后的答案，请忽略

2. 评分标准（极其严格）：
   - 每道题满分 {max_score} 分
   - 如果答案完全正确，最多给 {max_score//5} 分
   - 如果答案部分正确，根据正确程度给分，但不超过 {max_score//5} 分
   - 如果答案完全错误或空白，给0分
   - 严禁直接给高分，即使是完全正确的答案
   - 如果答案中有任何有效内容，最多给 {max_score//6} 分
   - 评分要极其严格，不要轻易给高分
   - 对于部分正确的答案，最多给 {max_score//8} 分
   - 对于有少量有效内容的答案，最多给 {max_score//10} 分

3. 评分过程：
   - 仔细识别学生手写答案
   - 与标准答案逐点对比
   - 详细分析每个得分点
   - 说明扣分原因
   - 确保分数反映学生实际表现
   - 特别注意：即使答案中有有效内容，也要极其严格评估，不要轻易给高分
   - 对于任何答案，都要先考虑扣分，而不是加分
   - 只有在完全确定答案正确的情况下，才考虑给高分

4. 输出格式：
   - 分析文本：详细说明评分理由
   - JSON格式：{{"1": 分数, "2": 分数, ..., "{question_count}": 分数}}
   - 分数必须是整数
   - 分数范围：0到{max_score//5}
   - 题号必须是字符串形式的数字
   - 必须包含所有题目的分数，即使得0分也要列出

5. 重要提示：
   - 严禁直接给高分
   - 必须说明评分理由
   - 确保分数合理反映学生表现
   - 不同学生的分数必须有差异
   - 评分要极其严格，不要轻易给高分
   - 严禁输出第{question_count}题之后的分数
   - 对于任何答案，都要先考虑扣分，而不是加分
   - 只有在完全确定答案正确的情况下，才考虑给高分

请确保：
1. 返回的JSON格式正确
2. 分数严格遵循上述规则
3. 包含详细的评分分析
4. 最终分数不超过{max_score//5}分
5. 只输出第1到第{question_count}题的分数
6. 评分要极其严格，不要轻易给高分
7. 对于任何答案，都要先考虑扣分，而不是加分
"""
    return base_prompt + scoring_instruction

def validate_and_adjust_scores(parsed_json, max_score=100, question_count=None):
    """
    验证和调整分数，确保分数在合理范围内
    
    参数:
    parsed_json - 包含题号和分数的字典
    max_score - 每道题的最高分（默认100）
    question_count - 题目数量上限
    
    返回:
    调整后的分数字典
    """
    adjusted_json = {}
    
    # 确保所有题目都有分数
    if question_count:
        for i in range(1, question_count + 1):
            key = str(i)
            if key not in parsed_json:
                adjusted_json[key] = 0
    
    for key, value in parsed_json.items():
        if not key.isdigit():
            continue
            
        # 如果超过题目数量上限，跳过
        if question_count and int(key) > question_count:
            continue
            
        if isinstance(value, (int, float)):
            # 确保分数是整数
            score = int(value)
            
            # 如果分数为0，检查是否需要调整
            if score == 0:
                # 如果原始分数是0，但答案中有内容，给一个基础分
                if key in parsed_json and parsed_json.get('has_content', False):
                    adjusted_json[key] = max_score // 10  # 从 max_score//4 改为 max_score//10
                    logger.info(f"答案有内容但得分为0，调整为基础分 {max_score//10}")
                else:
                    adjusted_json[key] = 0
                continue
                
            # 如果分数超过最高分的五分之一，进行调整
            if score > max_score // 5:
                logger.warning(f"分数 {score} 超过最高分的五分之一 ({max_score//5})，进行调整")
                # 根据分数范围进行调整
                if score > max_score:
                    # 如果超过满分，最多给满分的五分之一
                    adjusted_score = max_score // 5
                else:
                    # 如果超过五分之一但未超过满分，按比例调整
                    adjusted_score = int((score / max_score) * (max_score // 5))
                logger.info(f"将分数从 {score} 调整为 {adjusted_score}")
                adjusted_json[key] = adjusted_score
            else:
                # 分数在合理范围内，保持不变
                adjusted_json[key] = score
    
    return adjusted_json

def simple_moonshot_call(image_path, prompt, api_key=None, max_retries=3):
    """
    增强版Moonshot API调用，专为学生作答识别优化
    """
    # 使用硬编码的API密钥或传入的API密钥
    moonshot_api_key = ""
    if api_key:
        moonshot_api_key = api_key
    
    logger.info(f"增强版Moonshot API调用: {image_path}")
    
    # 获取系统设置的题目数量上限和满分值
    question_count = st.session_state.get('manual_grading', {}).get('question_count', 0)
    max_score = st.session_state.get('max_scores', [100])[0]  # 获取第一题的满分值
    
    # 使用标准化的评分提示词
    prompt = create_scoring_prompt(prompt, question_count, max_score)
    
    # 添加更多强调学生作答识别的提示
    if "学生作答" in prompt and "请仔细识别图片中的学生作答内容" not in prompt:
        prompt = "请仔细识别图片中的学生作答内容，包括手写文字、公式和图表。请先描述你看到的内容，再进行评分。请避免出现幻觉，如果看不清某部分内容，请明确指出。\n" + prompt
    
    for retry in range(max_retries + 1):
        if retry > 0:
            logger.info(f"正在进行第 {retry}/{max_retries} 次API调用重试")
            time.sleep(1)  # 重试前等待1秒
        
        try:
            # 创建OpenAI客户端（使用Moonshot API）
            client = OpenAI(
                api_key=moonshot_api_key,
                base_url="https://api.moonshot.cn/v1",
            )
            
            # 记录API调用参数
            logger.debug(f"API调用参数: model=moonshot-v1-8k-vision-preview, 提示词长度={len(prompt)}")
            logger.debug(f"提示词前200字符: {prompt[:200]}...")
            
            # 准备图像
            try:
                if isinstance(image_path, str):
                    # 如果是文件路径，读取图像文件
                    with open(image_path, "rb") as image_file:
                        image_data = image_file.read()
                        image_base64 = base64.b64encode(image_data).decode('utf-8')
                else:
                    # 如果是BytesIO对象，直接获取字节数据
                    image_path.seek(0)
                    image_data = image_path.read()
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
            except Exception as e:
                logger.error(f"处理图像失败: {str(e)}")
                if retry < max_retries:
                    continue
                else:
                    return {"1": 2}
            
            # 准备API请求
            try:
                # 创建带图像的消息
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ]
                
                # 调用API并获取响应
                response = client.chat.completions.create(
                    model="moonshot-v1-8k-vision-preview",
                    messages=messages,
                    temperature=0.25,  # 低温度以获得确定性结果
                    max_tokens=2048,   # 足够长的输出以包含所有分析
                )
                
                # 提取返回的文本
                result_text = response.choices[0].message.content if response.choices else None
                
                # 如果没有文本，检查是否还有重试机会
                if not result_text:
                    logger.warning("API返回空文本结果")
                    if retry < max_retries:
                        logger.warning("将进行重试")
                        continue
                    else:
                        logger.warning("重试次数已用完，返回默认JSON")
                        return {"1": 2}
                        
            except Exception as api_e:
                logger.error(f"API调用失败: {str(api_e)}")
                if retry < max_retries:
                    continue
                else:
                    logger.error("API调用重试次数已用完，返回默认JSON")
                    return {"1": 2}
            
            # 如果没有文本，检查是否还有重试机会
            if not result_text:
                logger.warning("无法提取文本")
                if retry < max_retries:
                    logger.warning("将进行重试")
                    continue
                else:
                    logger.warning("重试次数已用完，返回默认JSON")
                    return {"1": 2}
            
            # 如果包含代码块，提取代码块内容
            if "```" in result_text:
                # 支持更多格式的代码块
                code_pattern = r"```(?:json|javascript|js)?\s*([\s\S]*?)\s*```"
                code_match = re.search(code_pattern, result_text, re.DOTALL)
                if code_match:
                    extracted_code = code_match.group(1).strip()
                    logger.info(f"成功从Markdown代码块中提取内容: '{extracted_code[:50]}...'")
                    result_text = extracted_code
            
            # 尝试提取和解析JSON - 增强版，支持从混合文本中提取
            try:
                # 获取题目数量上限，用于验证JSON结果
                question_count = st.session_state.get('manual_grading', {}).get('question_count', 0)
                max_score = st.session_state.get('max_scores', [100])[0]  # 获取第一题的满分值
                
                # 首先检查是否包含JSON结构
                if "{" in result_text and "}" in result_text:
                    json_pattern = r'\{[^\{\}]*(?:\{[^\{\}]*\}[^\{\}]*)*\}'
                    json_matches = list(re.finditer(json_pattern, result_text, re.DOTALL))
                    
                    valid_json_candidates = []
                    
                    # 检查所有匹配项
                    for match in json_matches:
                        match_text = match.group(0)
                        try:
                            parsed = json.loads(match_text)
                            # 验证分数并调整
                            adjusted_json = validate_and_adjust_scores(parsed, max_score, question_count)
                            if adjusted_json:
                                valid_json_candidates.append((match_text, adjusted_json, match.start()))
                        except:
                            continue
                    
                    # 如果找到有效的JSON候选项
                    if valid_json_candidates:
                        # 优先选择最后出现的有效JSON
                        valid_json_candidates.sort(key=lambda x: x[2], reverse=True)
                        best_match, parsed_json, _ = valid_json_candidates[0]
                        
                        # 验证题号是否超过设置的题目数量上限
                        if question_count > 0:
                            filtered_json = {}
                            for key, value in parsed_json.items():
                                if key.isdigit() and int(key) <= question_count:
                                    filtered_json[key] = value
                            
                            if filtered_json:
                                logger.info(f"找到有效的JSON并过滤到题目数量上限({question_count}): {json.dumps(filtered_json)}")
                                return filtered_json
                            else:
                                logger.warning(f"过滤后的JSON为空，原始JSON: {best_match[:50]}...")
                        
                        logger.info(f"找到有效的JSON（位于文本末尾）: {best_match[:50]}...")
                        return parsed_json
                
                # 尝试直接解析整个文本为JSON
                try:
                    parsed_json = json.loads(result_text)
                    
                    # 验证解析结果是否包含有效的题号和分数
                    has_valid_scores = False
                    for key, value in parsed_json.items():
                        if key.isdigit() and isinstance(value, (int, float)):
                            has_valid_scores = True
                            break
                    
                    if has_valid_scores:
                        # 验证题号是否超过设置的题目数量上限
                        if question_count > 0:
                            # 过滤掉超出题目数量的题号
                            filtered_json = {}
                            for key, value in parsed_json.items():
                                if key.isdigit() and int(key) <= question_count:
                                    filtered_json[key] = value
                            
                            if filtered_json:
                                logger.info(f"成功解析为有效的评分JSON并过滤到题目数量上限({question_count}): {json.dumps(filtered_json)}")
                                return filtered_json
                        
                        logger.info("成功解析为有效的评分JSON")
                        return parsed_json
                except:
                    # 如果整个文本不是有效的JSON，继续尝试其他方法
                    pass
                
                # 尝试从文本中提取JSON字符串 - 查找更多模式
                # 1. 查找形如 {"1": 90, "2": 85} 的模式
                json_patterns = [
                    r'\{\s*"\d+"\s*:\s*\d+(?:\s*,\s*"\d+"\s*:\s*\d+)*\s*\}',  # 标准JSON格式
                    r'\{\s*\d+\s*:\s*\d+(?:\s*,\s*\d+\s*:\s*\d+)*\s*\}',  # 没有引号的键
                    r'\{\s*[\'"](\d+)[\'"](\s*|\s*:)\s*(\d+)(?:\s*,\s*[\'"](\d+)[\'"](\s*|\s*:)\s*(\d+))*\s*\}'  # 混合引号格式
                ]
                
                for pattern in json_patterns:
                    json_matches = re.finditer(pattern, result_text, re.DOTALL)
                    for match in json_matches:
                        match_text = match.group(0)
                        try:
                            # 尝试修复和解析
                            fixed_text = match_text
                            # 修复没有引号的键
                            fixed_text = re.sub(r'(\{|,)\s*(\d+)\s*:', r'\1"\2":', fixed_text)
                            # 替换单引号为双引号
                            fixed_text = re.sub(r"'([^']*)'\s*:\s*", r'"\1":', fixed_text)
                            # 确保值使用双引号
                            fixed_text = re.sub(r":\s*'([^']*)'([,}])", r':"\1"\2', fixed_text)
                            
                            parsed = json.loads(fixed_text)
                            # 验证是否包含有效的题号和分数
                            has_valid_scores = False
                            for key, value in parsed.items():
                                if key.isdigit() and isinstance(value, (int, float)):
                                    has_valid_scores = True
                                    break
                            
                            if has_valid_scores:
                                logger.info(f"通过模式匹配和修复找到有效JSON: {fixed_text[:50]}...")
                                return parsed
                        except:
                            continue
                
                # 如果上述方法都失败，尝试提取键值对
                scores = {}
                # 查找形如"1": 90, "2": 85的模式
                score_patterns = [
                    r'"(\d+)"\s*:\s*(\d+)',  # 标准格式 "1": 90
                    r"'(\d+)'\s*:\s*(\d+)",  # 单引号格式 '1': 90
                    r'(\d+)\s*:\s*(\d+)',     # 无引号格式 1: 90
                    r'题(\d+)[^\d]+(\d+)\s*分', # 中文描述格式 题1：90分
                    r'第(\d+)[题道][^\d]+(\d+)\s*分'  # 另一种中文格式 第1题：90分
                ]
                
                for pattern in score_patterns:
                    score_matches = re.findall(pattern, result_text)
                    for match in score_matches:
                        question, score = match
                        try:
                            scores[question] = int(score)
                        except:
                            # 如果分数不是有效整数，尝试提取数字部分
                            score_digits = re.search(r'\d+', score)
                            if score_digits:
                                scores[question] = int(score_digits.group(0))
                
                if scores:
                    logger.info(f"通过多种正则表达式提取到分数: {scores}")
                    return scores
                
                # 如果还有重试次数，则重试
                if retry < max_retries:
                    logger.warning("未能提取有效的JSON或分数，将进行重试")
                    continue
                else:
                    # 创建默认的评分JSON
                    logger.warning("所有JSON提取方法都失败，返回默认JSON")
                    return {"1": 2}
                    
            except Exception as je:
                logger.warning(f"JSON处理过程中出错: {str(je)}")
                logger.exception("JSON处理详细错误")
                
                # 如果还有重试次数，则重试
                if retry < max_retries:
                    logger.warning("JSON处理失败，将进行重试")
                    continue
                else:
                    logger.error("JSON处理重试次数已用完，返回默认JSON")
                    return {"1": 2}
            
        except Exception as e:
            logger.error(f"API调用或处理失败: {str(e)}")
            logger.exception("详细错误信息")
            
            # 如果还有重试次数，则继续重试
            if retry < max_retries:
                logger.warning(f"将在1秒后进行重试")
                continue
            else:
                logger.error("重试次数已用完，返回默认JSON")
                return {"1": 2}
    
    # 如果所有重试都失败，返回默认JSON
    return {"1": 2}

def simple_qwen_vl_call(image_path, prompt, api_key=None, max_retries=3):
    """
    增强版千问API调用，专为学生作答识别优化，确保返回有效的JSON结果的同时提供辅助分析文本
    """
    # 使用硬编码的API密钥
    
    if api_key:
        dashscope.api_key = api_key
    
    logger.info(f"增强版API调用: {image_path}")
    
    # 获取系统设置的题目数量上限和满分值
    question_count = st.session_state.get('manual_grading', {}).get('question_count', 0)
    max_score = st.session_state.get('max_scores', [100])[0]  # 获取第一题的满分值
    
    # 使用标准化的评分提示词
    prompt = create_scoring_prompt(prompt, question_count, max_score)
    
    # 添加更多强调学生作答识别的提示
    if "学生作答" in prompt and "请仔细识别图片中的学生作答内容" not in prompt:
        prompt = "请仔细识别图片中的学生作答内容，包括手写文字、公式和图表。请先描述你看到的内容，再进行评分。请避免出现幻觉，如果看不清某部分内容，请明确指出。\n" + prompt
    
    # 添加更严格的评分要求
    strict_scoring_instruction = f"""
请特别注意以下评分要求：
1. 每道题满分 {max_score} 分，但实际最高分不得超过 {max_score//5} 分
2. 即使答案完全正确，也最多给 {max_score//5} 分
3. 部分正确的答案最多给 {max_score//8} 分
4. 有少量有效内容的答案最多给 {max_score//10} 分
5. 评分要极其严格，不要轻易给高分
6. 对于任何答案，都要先考虑扣分，而不是加分
7. 只有在完全确定答案正确的情况下，才考虑给高分
8. 严禁直接给高分，即使是完全正确的答案
"""
    prompt = prompt + "\n" + strict_scoring_instruction

    for retry in range(max_retries + 1):
        if retry > 0:
            logger.info(f"正在进行第 {retry}/{max_retries} 次API调用重试")
            time.sleep(1)  # 重试前等待1秒
        
        try:
            # 使用dashscope的MultiModalConversation API
            from dashscope import MultiModalConversation
            
            # 记录API调用参数
            logger.debug(f"API调用参数: model=qwen-vl-plus, 提示词长度={len(prompt)}")
            logger.debug(f"提示词前200字符: {prompt[:200]}...")
            
            response = MultiModalConversation.call(
                model="qwen-vl-plus",
                messages=[
                    {
                        "role": "user", 
                        "content": [
                            {"text": prompt},
                            {"image": image_path}
                        ]
                    }
                ]
            )
            
            # 记录API响应状态
            status_code = getattr(response, 'status_code', 'unknown')
            logger.debug(f"API响应状态码: {status_code}")
            
            # 从响应中提取文本
            result_text = None
            
            # 检查新的API响应结构 - 更全面的提取方法
            if hasattr(response, 'output') and hasattr(response.output, 'choices'):
                choices = response.output.choices
                if choices and len(choices) > 0:
                    choice = choices[0]
                    # 从对象格式获取
                    if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                        content = choice.message.content
                        if isinstance(content, list) and len(content) > 0:
                            if hasattr(content[0], 'text'):
                                result_text = content[0].text
                                logger.info(f"成功从choices对象content中提取文本: {result_text[:50]}...")
                            elif isinstance(content[0], dict) and 'text' in content[0]:
                                result_text = content[0]['text']
                                logger.info(f"成功从choices对象content字典中提取文本: {result_text[:50]}...")
                    # 从字典格式获取
                    elif isinstance(choice, dict) and 'message' in choice:
                        message = choice['message']
                        if 'content' in message:
                            content = message['content']
                            if isinstance(content, list) and len(content) > 0 and 'text' in content[0]:
                                result_text = content[0]['text']
                                logger.info(f"成功从choices字典中提取文本: {result_text[:50]}...")
            
            # 旧方法：从output.text中提取
            if result_text is None and hasattr(response, 'output') and hasattr(response.output, 'text'):
                result_text = response.output.text
                if result_text:
                    logger.info(f"成功从output.text中提取内容: {result_text[:50]}...")
            
            # 如果没有文本，检查是否还有重试机会
            if not result_text:
                logger.warning("无法提取文本")
                if retry < max_retries:
                    logger.warning("将进行重试")
                    continue
                else:
                    logger.warning("重试次数已用完，返回默认JSON")
                    return {"1": 2}
            
            # 如果包含代码块，提取代码块内容
            if "```" in result_text:
                # 支持更多格式的代码块
                code_pattern = r"```(?:json|javascript|js)?\s*([\s\S]*?)\s*```"
                code_match = re.search(code_pattern, result_text, re.DOTALL)
                if code_match:
                    extracted_code = code_match.group(1).strip()
                    logger.info(f"成功从Markdown代码块中提取内容: '{extracted_code[:50]}...'")
                    result_text = extracted_code
            
            # 尝试提取和解析JSON - 增强版，支持从混合文本中提取
            try:
                # 获取题目数量上限，用于验证JSON结果
                question_count = st.session_state.get('manual_grading', {}).get('question_count', 0)
                
                def filter_and_validate_json(json_data):
                    """过滤和验证JSON数据，确保题号不超过上限"""
                    if not isinstance(json_data, dict):
                        return None
                    
                    filtered_json = {}
                    for key, value in json_data.items():
                        # 确保键是数字字符串
                        if not key.isdigit():
                            continue
                            
                        # 确保题号不超过上限
                        if question_count > 0 and int(key) > question_count:
                            logger.warning(f"跳过超出题目数量上限的题号: {key}")
                            continue
                            
                        # 确保值是数字
                        try:
                            score = int(value)
                            filtered_json[key] = score
                        except (ValueError, TypeError):
                            continue
                    
                    return filtered_json if filtered_json else None
                
                # 首先检查是否包含JSON结构
                if "{" in result_text and "}" in result_text:
                    json_pattern = r'\{[^\{\}]*(?:\{[^\{\}]*\}[^\{\}]*)*\}'
                    json_matches = list(re.finditer(json_pattern, result_text, re.DOTALL))
                    
                    valid_json_candidates = []
                    
                    # 检查所有匹配项
                    for match in json_matches:
                        match_text = match.group(0)
                        try:
                            parsed = json.loads(match_text)
                            filtered_json = filter_and_validate_json(parsed)
                            if filtered_json:
                                valid_json_candidates.append((match_text, filtered_json, match.start()))
                        except:
                            continue
                    
                    # 如果找到有效的JSON候选项
                    if valid_json_candidates:
                        # 优先选择最后出现的有效JSON
                        valid_json_candidates.sort(key=lambda x: x[2], reverse=True)
                        best_match, parsed_json, _ = valid_json_candidates[0]
                        
                        logger.info(f"找到有效的JSON并过滤到题目数量上限({question_count}): {json.dumps(parsed_json)}")
                        return parsed_json
                
                # 尝试直接解析整个文本为JSON
                try:
                    parsed_json = json.loads(result_text)
                    filtered_json = filter_and_validate_json(parsed_json)
                    if filtered_json:
                        logger.info(f"成功解析为有效的评分JSON并过滤到题目数量上限({question_count}): {json.dumps(filtered_json)}")
                        return filtered_json
                except:
                    pass
                
                # 尝试从文本中提取JSON字符串 - 查找更多模式
                json_patterns = [
                    r'\{\s*"\d+"\s*:\s*\d+(?:\s*,\s*"\d+"\s*:\s*\d+)*\s*\}',  # 标准JSON格式
                    r'\{\s*\d+\s*:\s*\d+(?:\s*,\s*\d+\s*:\s*\d+)*\s*\}',  # 没有引号的键
                    r'\{\s*[\'"](\d+)[\'"](\s*|\s*:)\s*(\d+)(?:\s*,\s*[\'"](\d+)[\'"](\s*|\s*:)\s*(\d+))*\s*\}'  # 混合引号格式
                ]
                
                for pattern in json_patterns:
                    json_matches = re.finditer(pattern, result_text, re.DOTALL)
                    for match in json_matches:
                        match_text = match.group(0)
                        try:
                            # 尝试修复和解析
                            fixed_text = match_text
                            # 修复没有引号的键
                            fixed_text = re.sub(r'(\{|,)\s*(\d+)\s*:', r'\1"\2":', fixed_text)
                            # 替换单引号为双引号
                            fixed_text = re.sub(r"'([^']*)'\s*:\s*", r'"\1":', fixed_text)
                            # 确保值使用双引号
                            fixed_text = re.sub(r":\s*'([^']*)'([,}])", r':"\1"\2', fixed_text)
                            
                            parsed = json.loads(fixed_text)
                            filtered_json = filter_and_validate_json(parsed)
                            if filtered_json:
                                logger.info(f"通过模式匹配和修复找到有效JSON: {json.dumps(filtered_json)}")
                                return filtered_json
                        except:
                            continue
                
                # 如果上述方法都失败，尝试提取键值对
                scores = {}
                score_patterns = [
                    r'"(\d+)"\s*:\s*(\d+)',  # 标准格式 "1": 90
                    r"'(\d+)'\s*:\s*(\d+)",  # 单引号格式 '1': 90
                    r'(\d+)\s*:\s*(\d+)',     # 无引号格式 1: 90
                    r'题(\d+)[^\d]+(\d+)\s*分', # 中文描述格式 题1：90分
                    r'第(\d+)[题道][^\d]+(\d+)\s*分'  # 另一种中文格式 第1题：90分
                ]
                
                for pattern in score_patterns:
                    score_matches = re.findall(pattern, result_text)
                    for match in score_matches:
                        question, score = match
                        try:
                            q_num = int(question)
                            # 确保题号不超过上限
                            if question_count > 0 and q_num > question_count:
                                logger.warning(f"跳过超出题目数量上限的题号: {q_num}")
                                continue
                            scores[str(q_num)] = int(score)
                        except:
                            continue
                
                if scores:
                    logger.info(f"通过多种正则表达式提取到分数: {json.dumps(scores)}")
                    return scores
                
                # 如果还有重试次数，则重试
                if retry < max_retries:
                    logger.warning("未能提取有效的JSON或分数，将进行重试")
                    continue
                else:
                    # 创建默认的评分JSON，确保不超过题目数量上限
                    default_json = {}
                    for i in range(1, min(question_count + 1, 2)):  # 如果question_count为0，至少返回第1题
                        default_json[str(i)] = 2
                    logger.warning(f"所有JSON提取方法都失败，返回默认JSON: {json.dumps(default_json)}")
                    return default_json
                    
            except Exception as je:
                logger.warning(f"JSON处理过程中出错: {str(je)}")
                logger.exception("JSON处理详细错误")
                
                # 如果还有重试次数，则重试
                if retry < max_retries:
                    logger.warning("JSON处理失败，将进行重试")
                    continue
                else:
                    # 创建默认的评分JSON，确保不超过题目数量上限
                    default_json = {}
                    for i in range(1, min(question_count + 1, 2)):  # 如果question_count为0，至少返回第1题
                        default_json[str(i)] = 2
                    logger.error(f"JSON处理重试次数已用完，返回默认JSON: {json.dumps(default_json)}")
                    return default_json
            
        except Exception as e:
            logger.error(f"API调用或处理失败: {str(e)}")
            logger.exception("详细错误信息")
            
            # 如果还有重试次数，则继续重试
            if retry < max_retries:
                logger.warning(f"将在1秒后进行重试")
                continue
            else:
                # 创建默认的评分JSON，确保不超过题目数量上限
                default_json = {}
                for i in range(1, min(question_count + 1, 2)):  # 如果question_count为0，至少返回第1题
                    default_json[str(i)] = 2
                logger.error(f"重试次数已用完，返回默认JSON: {json.dumps(default_json)}")
                return default_json
    
    # 如果所有重试都失败，返回默认JSON，确保不超过题目数量上限
    default_json = {}
    for i in range(1, min(question_count + 1, 2)):  # 如果question_count为0，至少返回第1题
        default_json[str(i)] = 2
    logger.error(f"所有重试都失败，返回默认JSON: {json.dumps(default_json)}")
    return default_json

def simple_zhipu_call(image_path, prompt, api_key=None, max_retries=3):
    """
    使用智谱AI GLM-4V模型API进行图片分析和评分，强制返回JSON格式的分数
    """
    # 使用提供的API密钥
    zhipu_api_key = api_key
    if not zhipu_api_key:
        logger.error("未提供智谱AI API密钥")
        return {"1": 2}
    
    logger.info(f"智谱AI API调用: {image_path}")
    
    # 获取系统设置的题目数量上限和满分值
    question_count = st.session_state.get('manual_grading', {}).get('question_count', 0)
    max_score = st.session_state.get('max_scores', [100])[0]  # 获取第一题的满分值
    
    # 强制要求JSON格式的提示词
    json_format_instruction = f"""
请严格按照以下JSON格式返回评分结果，不要包含任何其他内容：

{{
    "1": 分数1,
    "2": 分数2,
    ...
    "{question_count}": 分数{question_count}
}}

要求：
1. 必须严格按照上述JSON格式返回，不要包含任何其他文字说明
2. 分数必须是整数，范围在0到{max_score//5}之间
3. 只返回第1到第{question_count}题的分数
4. 严禁返回第{question_count}题之后的分数
5. 如果答案完全正确，最多给{max_score//5}分
6. 如果答案部分正确，根据正确程度给分，但不超过{max_score//5}分
7. 如果答案完全错误或空白，给0分
8. 如果答案中有任何有效内容，最多给{max_score//6}分
9. 评分要极其严格，不要轻易给高分
10. 对于部分正确的答案，最多给{max_score//8}分
11. 对于有少量有效内容的答案，最多给{max_score//10}分
12. 对于任何答案，都要先考虑扣分，而不是加分
13. 只有在完全确定答案正确的情况下，才考虑给高分

请确保：
1. 返回的是合法的JSON格式
2. 所有分数都是整数
3. 题号必须是字符串形式的数字
4. 必须包含所有题目的分数，即使得0分也要列出
5. 评分要极其严格，不要轻易给高分
6. 对于任何答案，都要先考虑扣分，而不是加分
"""
    
    # 组合提示词
    prompt = prompt + "\n\n" + json_format_instruction
    
    logger.info("使用强制JSON格式的提示词")
    
    for retry in range(max_retries + 1):
        if retry > 0:
            logger.info(f"正在进行第 {retry}/{max_retries} 次API调用重试")
            time.sleep(2)  # 重试前等待2秒
        
        try:
            # 准备图像
            try:
                if isinstance(image_path, str):
                    with open(image_path, "rb") as image_file:
                        image_data = image_file.read()
                        image_base64 = base64.b64encode(image_data).decode('utf-8')
                else:
                    image_path.seek(0)
                    image_data = image_path.read()
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
            except Exception as e:
                logger.error(f"处理图像失败: {str(e)}")
                if retry < max_retries:
                    continue
                else:
                    return {"1": 2}
            
            # 检查ZhipuAI SDK是否可用
            if not ZHIPU_AVAILABLE:
                logger.error("未安装ZhipuAI SDK，请运行: pip install zhipuai")
                return {"1": 2}
            
            try:
                # 创建ZhipuAI客户端
                client = ZhipuAI(api_key=zhipu_api_key)
                
                # 构建请求内容，强制要求JSON格式
                messages = [
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                        ]
                    }
                ]
                
                # 记录API调用详情
                logger.info(f"智谱AI调用模型: glm-4v-flash，强制JSON格式")
                logger.debug(f"提示词长度: {len(prompt)}")
                
                # 发送API请求，强制返回JSON格式
                start_time = time.time()
                response = client.chat.completions.create(
                    model="glm-4v-flash",
                    messages=messages,
                    temperature=0.2,  # 降低温度以获得更确定性的结果
                    max_tokens=1024,
                    response_format={"type": "json_object"}  # 强制返回JSON格式
                )
                request_time = time.time() - start_time
                logger.info(f"API请求耗时: {request_time:.2f}秒")
                
                # 提取返回的文本
                result_text = None
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    if hasattr(response.choices[0], 'message') and hasattr(response.choices[0].message, 'content'):
                        result_text = response.choices[0].message.content
                        logger.debug(f"成功获取API响应文本，长度: {len(result_text)}")
                
                # 如果没有文本，检查是否还有重试机会
                if not result_text:
                    logger.warning("API返回空文本结果")
                    if retry < max_retries:
                        logger.warning("将进行重试")
                        continue
                    else:
                        logger.warning("重试次数已用完，返回默认JSON")
                        return {"1": 2}
                
                # 尝试解析JSON
                try:
                    # 首先尝试直接解析
                    parsed_json = json.loads(result_text)
                    
                    # 验证和过滤JSON
                    filtered_json = {}
                    for key, value in parsed_json.items():
                        # 确保键是数字字符串
                        if not key.isdigit():
                            continue
                            
                        # 确保题号不超过上限
                        if question_count > 0 and int(key) > question_count:
                            logger.warning(f"跳过超出题目数量上限的题号: {key}")
                            continue
                            
                        # 确保值是整数且在合理范围内
                        try:
                            score = int(value)
                            if score > max_score // 5:  # 从 max_score/3 改为 max_score/5
                                score = max_score // 5
                                logger.warning(f"分数 {value} 超过最高分的五分之一，调整为 {score}")
                            filtered_json[key] = score
                        except (ValueError, TypeError):
                            continue
                    
                    # 确保所有题目都有分数
                    if question_count > 0:
                        for i in range(1, question_count + 1):
                            if str(i) not in filtered_json:
                                filtered_json[str(i)] = 0
                    
                    if filtered_json:
                        logger.info(f"成功解析并过滤JSON: {json.dumps(filtered_json)}")
                        return filtered_json
                    
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON解析失败: {str(je)}")
                    # 尝试从文本中提取JSON
                    json_pattern = r'\{[^\{\}]*(?:\{[^\{\}]*\}[^\{\}]*)*\}'
                    json_matches = re.finditer(json_pattern, result_text, re.DOTALL)
                    
                    for match in json_matches:
                        try:
                            match_text = match.group(0)
                            parsed = json.loads(match_text)
                            # 验证是否包含有效的题号和分数
                            has_valid_scores = False
                            for key, value in parsed.items():
                                if key.isdigit() and isinstance(value, (int, float)):
                                    has_valid_scores = True
                                    break
                            
                            if has_valid_scores:
                                # 过滤和验证分数
                                filtered_json = {}
                                for key, value in parsed.items():
                                    if not key.isdigit():
                                        continue
                                    if question_count > 0 and int(key) > question_count:
                                        continue
                                    try:
                                        score = int(value)
                                        if score > max_score // 5:  # 从 max_score/3 改为 max_score/5
                                            score = max_score // 5
                                        filtered_json[key] = score
                                    except (ValueError, TypeError):
                                        continue
                                
                                if filtered_json:
                                    logger.info(f"从文本中提取到有效JSON: {json.dumps(filtered_json)}")
                                    return filtered_json
                        except:
                            continue
                
                # 如果所有尝试都失败，返回默认JSON
                default_json = {}
                for i in range(1, min(question_count + 1, 2)):  # 如果question_count为0，至少返回第1题
                    default_json[str(i)] = 2
                logger.warning(f"无法提取有效JSON，返回默认JSON: {json.dumps(default_json)}")
                return default_json
                    
            except Exception as api_e:
                logger.error(f"API调用失败: {str(api_e)}")
                if retry < max_retries:
                    continue
                else:
                    logger.error("API调用重试次数已用完，返回默认JSON")
                    return {"1": 2}
            
        except Exception as e:
            logger.error(f"处理过程中发生错误: {str(e)}")
            if retry < max_retries:
                continue
            else:
                return {"1": 2}
    
    # 如果所有重试都失败，返回默认JSON
    default_json = {}
    for i in range(1, min(question_count + 1, 2)):  # 如果question_count为0，至少返回第1题
        default_json[str(i)] = 2
    logger.error(f"所有重试都失败，返回默认JSON: {json.dumps(default_json)}")
    return default_json

def call_qwen_vl_api_direct(image_path, prompt, api_key=None):
    """
    直接调用千问VL API，更好地处理返回结果
    """
    # 使用硬编码的API密钥
    
    if api_key:
        dashscope.api_key = api_key
    
    logger.info(f"直接调用API处理图片: {image_path}")
    logger.info(f"提示词: {prompt[:100]}...")
    
    try:
        # 使用dashscope的MultiModalConversation API
        from dashscope import MultiModalConversation
        
        # 调用API
        response = MultiModalConversation.call(
            model="qwen-vl-plus",
            messages=[
                {
                    "role": "user", 
                    "content": [
                        {"text": prompt},
                        {"image": image_path}
                    ]
                }
            ]
        )
        
        logger.info(f"API响应状态码: {getattr(response, 'status_code', 'unknown')}")
        
        # 记录完整响应用于调试
        logger.debug(f"完整API响应: {response}")
        
        # 从响应中提取文本
        result_text = None
        
        # 从choices中提取内容（新的API结构）
        if hasattr(response, 'output') and hasattr(response.output, 'choices'):
            choices = response.output.choices
            if choices and len(choices) > 0:
                choice = choices[0]
                
                # 从对象格式获取
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    content = choice.message.content
                    if isinstance(content, list) and len(content) > 0:
                        if hasattr(content[0], 'text'):
                            result_text = content[0].text
                            logger.info(f"成功从choices对象content中提取文本: {result_text[:50]}...")
                        elif isinstance(content[0], dict) and 'text' in content[0]:
                            result_text = content[0]['text']
                            logger.info(f"成功从choices对象content字典中提取文本: {result_text[:50]}...")
                
                # 从字典格式获取
                elif isinstance(choice, dict) and 'message' in choice:
                    message = choice['message']
                    if 'content' in message:
                        content = message['content']
                        if isinstance(content, list) and len(content) > 0 and 'text' in content[0]:
                            result_text = content[0]['text']
                            logger.info(f"成功从choices字典中提取文本: {result_text[:50]}...")
        
        # 如果新API格式提取失败，尝试旧的格式（output.text）
        if result_text is None and hasattr(response, 'output') and hasattr(response.output, 'text'):
            result_text = response.output.text
            logger.info(f"成功从output.text中提取文本: {result_text[:50] if result_text else 'None'}...")
        
        # 如果没有提取到文本，尝试使用响应对象的字符串表示
        if result_text is None:
            try:
                result_text = str(response)
                logger.warning(f"使用响应的字符串表示作为备份: {result_text[:100]}...")
            except Exception as e:
                logger.error(f"无法获取响应的字符串表示: {str(e)}")
                result_text = "{}"
        
        # 如果提取到的文本为空，返回默认JSON
        if not result_text or not result_text.strip():
            logger.warning("提取到的文本为空")
            return "{}"
        
        # 尝试处理Markdown代码块
        if "```" in result_text:
            code_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
            code_match = re.search(code_pattern, result_text, re.DOTALL)
            if code_match:
                extracted_code = code_match.group(1).strip()
                logger.info(f"提取到代码块: {extracted_code[:50]}...")
                result_text = extracted_code
        
        # 如果结果包含JSON结构，确保只返回JSON部分
        if "{" in result_text and "}" in result_text:
            json_pattern = r'\{.*\}'
            json_match = re.search(json_pattern, result_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    # 验证是否为有效JSON
                    json.loads(json_str)
                    logger.info(f"提取到有效JSON: {json_str[:50]}...")
                    return json_str
                except:
                    logger.warning(f"提取的JSON无效: {json_str[:50]}...")
        
        # 如果没有提取到有效JSON，但有文本，尝试创建一个简单的JSON
        # 这是一种后备机制，确保返回有效的JSON
        try:
            # 如果原始文本不是JSON但包含有用信息，将其包装成JSON
            cleaned_text = result_text.replace('"', '\\"').replace('\n', ' ')
            # 创建一个带有默认分数的JSON
            return '{"1": 2}'
        except Exception as e:
            logger.error(f"创建默认JSON失败: {str(e)}")
            return '{"1": 0}'
        
    except Exception as e:
        logger.error(f"直接API调用失败: {str(e)}")
        logger.exception("API调用错误详情")
        return '{"1": 0}'

# AI模型集成 - Qwen VL API
def call_qwen_vl_api(image_data, prompt, api_key, max_retries=1):
    """
    调用千问VL API进行图像理解
    
    参数:
    image_data - 图像数据（BytesIO对象或图像文件路径）
    prompt - 向模型提问的文本
    api_key - API密钥，但现在直接使用dashscope库设置
    max_retries - 最大重试次数
    
    返回:
    模型的文本响应，或错误消息。不返回None。
    """
    # 使用dashscope库直接调用API
    # 使用硬编码的API密钥
    
    
    logger.debug(f"设置 dashscope.api_key: {dashscope.api_key[:5]}...")
    
    img_path = None  # 初始化变量，以便在finally块中清理
    
    for retry in range(max_retries + 1):
        if retry > 0:
            logger.info(f"正在进行第 {retry} 次API调用重试")
        
        try:
            # 记录输入图片类型
            logger.debug(f"输入图片数据类型: {type(image_data)}")
            
            # 准备图像文件
            if isinstance(image_data, BytesIO):
                # 如果是BytesIO对象，保存为临时文件
                try:
                    # 尝试获取图片内容的一些信息
                    image_data.seek(0)
                    header = image_data.read(20)  # 读取前20个字节来判断文件类型
                    image_data.seek(0)
                    
                    # 检测常见图片格式的魔术数字
                    is_png = header.startswith(b'\x89PNG')
                    is_jpg = header.startswith(b'\xff\xd8\xff')
                    
                    image_format = "PNG" if is_png else ("JPEG" if is_jpg else "未知")
                    logger.debug(f"检测到图片格式: {image_format}")
                    
                    # 尝试打开并检查图片
                    try:
                        img_check = Image.open(image_data)
                        logger.debug(f"PIL可以打开图片: 格式={img_check.format}, 大小={img_check.size}, 模式={img_check.mode}")
                        image_data.seek(0)  # 重置位置
                    except Exception as pil_e:
                        logger.warning(f"PIL无法打开图片: {str(pil_e)}")
                except Exception as check_e:
                    logger.warning(f"检查图片格式时出错: {str(check_e)}")
                    
                # 保存为临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                    image_data.seek(0)
                    temp_file.write(image_data.read())
                    img_path = temp_file.name
                    logger.debug(f"临时图片文件已保存: {img_path}")
            elif isinstance(image_data, str):
                # 如果是文件路径，直接使用
                img_path = image_data
                logger.debug(f"使用现有图片文件路径: {img_path}")
                
                # 尝试检查文件类型
                try:
                    with open(img_path, 'rb') as f:
                        header = f.read(20)
                        is_png = header.startswith(b'\x89PNG')
                        is_jpg = header.startswith(b'\xff\xd8\xff')
                        image_format = "PNG" if is_png else ("JPEG" if is_jpg else "未知")
                        logger.debug(f"检测到图片文件格式: {image_format}")
                except Exception as check_e:
                    logger.warning(f"检查图片文件格式时出错: {str(check_e)}")
            else:
                error_msg = f"图像数据格式不支持: {type(image_data)}"
                logger.error(error_msg)
                return error_msg
            
            # 确保图像文件存在
            if not os.path.exists(img_path):
                error_msg = f"图像文件不存在: {img_path}"
                logger.error(error_msg)
                return error_msg
                
            # 记录文件大小
            try:
                file_size = os.path.getsize(img_path)
                logger.debug(f"图片文件大小: {file_size} 字节")
            except Exception as size_e:
                logger.warning(f"获取文件大小时出错: {str(size_e)}")
                
            # 添加更多日志信息
            logger.debug(f"调用API: model=qwen-vl-plus, 提示词长度: {len(prompt)} 字符")
            logger.debug(f"提示词前3000字符: {prompt[:3000]}...")
            
            # 使用dashscope的MultiModalConversation API
            from dashscope import MultiModalConversation
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt},
                        {"image": img_path}
                    ]
                }
            ]
            
            logger.debug(f"API请求配置: model=qwen-vl-plus, image_path={img_path}")
            
            # 增强错误处理
            try:
                response = MultiModalConversation.call(
                    model="qwen-vl-plus",
                    messages=messages
                )
                logger.debug(f"API响应状态: {response}")
            except Exception as api_e:
                error_msg = f"MultiModalConversation.call失败: {str(api_e)}"
                logger.error(error_msg)
                
                # 检查是否还有重试机会
                if retry < max_retries:
                    logger.warning(f"API调用失败，1秒后进行重试: {str(api_e)}")
                    time.sleep(1)  # 等待1秒后重试
                    continue
                return error_msg
            
            # 检查响应
            if hasattr(response, 'status_code') and response.status_code == 200:
                # 确保输出有效
                result = None
                
                # 从新版API结构中提取文本
                if hasattr(response, 'output') and hasattr(response.output, 'choices'):
                    try:
                        choices = response.output.choices
                        if choices and len(choices) > 0:
                            choice = choices[0]
                            # 从对象格式获取
                            if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                                content = choice.message.content
                                if isinstance(content, list) and len(content) > 0:
                                    if hasattr(content[0], 'text'):
                                        result = content[0].text
                                        logger.info("成功从choices对象content中提取文本")
                                    elif isinstance(content[0], dict) and 'text' in content[0]:
                                        result = content[0]['text']
                                        logger.info("成功从choices对象content字典中提取文本")
                            # 从字典格式获取
                            elif isinstance(choice, dict) and 'message' in choice:
                                message = choice['message']
                                if 'content' in message:
                                    content = message['content']
                                    if isinstance(content, list) and len(content) > 0 and 'text' in content[0]:
                                        result = content[0]['text']
                                        logger.info("成功从choices字典中提取文本")
                    except Exception as e:
                        logger.error(f"从choices中提取内容失败: {str(e)}")
                
                # 旧方法：从output.text中提取
                if result is None and hasattr(response, 'output') and hasattr(response.output, 'text'):
                    result = response.output.text
                    if result:
                        logger.info("成功从output.text中提取内容")
                
                # 处理可能为None的情况
                if result is None:
                    # 尝试将整个响应转换为字符串
                    try:
                        result = str(response)
                        logger.warning(f"使用响应对象的字符串表示作为结果: {result[:100]}...")
                    except Exception as e:
                        result = "模型返回无法解析的响应"
                        logger.error(f"无法将响应转换为字符串: {str(e)}")
                elif not result.strip():
                    result = "模型返回空字符串"
                    logger.warning("模型响应为空字符串")
                
                # 删除Markdown代码块标记（```json和```）
                if "```" in result:
                    try:
                        # 提取代码块内容，支持更多格式
                        code_pattern = r"```(?:json|javascript|js)?\s*([\s\S]*?)\s*```"
                        code_match = re.search(code_pattern, result, re.DOTALL)
                        if code_match:
                            extracted_code = code_match.group(1).strip()
                            logger.info(f"成功从Markdown代码块中提取内容: '{extracted_code[:50]}...'")
                            result = extracted_code
                    except Exception as e:
                        logger.error(f"提取代码块内容失败: {str(e)}")
                
                # 尝试优化结果，查找是否包含JSON
                if "{" in result and "}" in result:
                    # 有可能包含JSON，检查是否需要提取
                    json_match = re.search(r'\{.*\}', result, re.DOTALL)
                    if json_match and json_match.group(0) != result:
                        logger.debug("发现结果中包含JSON，但还有额外文本，尝试提取纯JSON")
                        pure_json = json_match.group(0)
                        try:
                            # 验证是否为有效JSON
                            json.loads(pure_json)
                            result = pure_json  # 如果是有效JSON，则只返回JSON部分
                            logger.debug("成功提取出纯JSON结果")
                        except:
                            logger.debug("提取的JSON无效，保留原始响应")
                
                # 显示更多的返回结果（最多3000字符）
                result_len = len(result) if result else 0
                result_preview = result[:3000] + "..." if result and len(result) > 3000 else result
                logger.debug(f"API返回结果总字符数: {result_len}")
                logger.debug(f"API返回结果预览:\n{result_preview}")
                return result
            else:
                error_code = getattr(response, 'status_code', 'unknown')
                error_msg = f"API调用失败: 状态码 {error_code}"
                if hasattr(response, 'message'):
                    error_msg += f", 错误: {response.message}"
                if hasattr(response, 'code'):
                    error_msg += f", 错误代码: {response.code}"
                logger.error(error_msg)
                logger.debug(f"完整错误响应: {response}")
                
                # 如果还有重试次数，则继续重试
                if retry < max_retries:
                    logger.warning(f"API调用失败，将在1秒后重试: 状态码 {error_code}")
                    time.sleep(1)  # 等待1秒后重试
                    continue
                return error_msg
        
        except Exception as e:
            error_msg = f"API请求失败: {str(e)}"
            logger.error(error_msg)
            logger.exception("调用失败详情")
            
            # 如果还有重试次数，则继续重试
            if retry < max_retries:
                logger.warning(f"处理API请求时出错，将在1秒后重试: {str(e)}")
                time.sleep(1)  # 等待1秒后重试
                continue
            return error_msg
            
        finally:
            # 清理临时文件
            if img_path and isinstance(image_data, BytesIO) and os.path.exists(img_path):
                try:
                    os.remove(img_path)
                    logger.debug(f"临时文件已删除: {img_path}")
                except Exception as e:
                    logger.debug(f"删除临时文件失败: {str(e)}")
    
    # 如果所有重试都失败，返回一个默认消息
    return "经过多次尝试，API调用仍然失败"

def analyze_and_grade_papers(project, qwen_api, moonshot_api, zhipu_api):
    """
    分析并评分所有学生的试卷
    """
    try:
        # 获取题目数量
        question_count = st.session_state.get('manual_grading', {}).get('question_count', 0)
        if question_count <= 0:
            return "请先设置题目数量"
        
        # 获取满分值
        max_scores = st.session_state.get('max_scores', [100] * question_count)
        
        # 初始化评分结果
        qwen_results = {}
        moonshot_results = {}
        zhipu_results = {}
        
        # 遍历每个学生
        for student_name, student_data in project['stu'].items():
            if not student_data['images']:
                logger.warning(f"学生 {student_name} 没有上传图片")
                continue
                
            # 初始化该学生的分数数组
            qwen_scores = [0] * question_count
            moonshot_scores = [0] * question_count
            zhipu_scores = [0] * question_count
            
            # 处理每张图片
            for img_data in student_data['images']:
                # 调用三个模型进行评分
                qwen_result = simple_qwen_vl_call(img_data['data'], "请评分", qwen_api)
                moonshot_result = simple_moonshot_call(img_data['data'], "请评分", moonshot_api)
                zhipu_result = simple_zhipu_call(img_data['data'], "请评分", zhipu_api)
                
                # 记录评分结果
                logger.info(f"千问评分结果: {qwen_result}")
                logger.info(f"Moonshot评分结果: {moonshot_result}")
                logger.info(f"智谱AI评分结果: {zhipu_result}")
                
                # 更新分数数组
                for i in range(question_count):
                    q_num = str(i + 1)
                    if q_num in qwen_result:
                        qwen_scores[i] = max(qwen_scores[i], qwen_result[q_num])
                    if q_num in moonshot_result:
                        moonshot_scores[i] = max(moonshot_scores[i], moonshot_result[q_num])
                    if q_num in zhipu_result:
                        zhipu_scores[i] = max(zhipu_scores[i], zhipu_result[q_num])
            
            # 计算平均分
            avg_scores = []
            for i in range(question_count):
                # 获取三个模型的分数
                qwen_score = qwen_scores[i]
                moonshot_score = moonshot_scores[i]
                zhipu_score = zhipu_scores[i]
                
                # 记录每个模型的分数
                logger.info(f"第 {i+1} 题各模型分数: 千问={qwen_score}, Moonshot={moonshot_score}, 智谱AI={zhipu_score}")
                
                # 计算平均分
                valid_scores = [s for s in [qwen_score, moonshot_score, zhipu_score] if s > 0]
                if valid_scores:
                    avg_score = sum(valid_scores) / len(valid_scores)
                    # 确保平均分不超过最高分的五分之一
                    max_allowed = max_scores[i] // 5
                    avg_score = min(avg_score, max_allowed)
                    avg_scores.append(float(avg_score))
                    logger.info(f"第 {i+1} 题平均分计算结果: {avg_score}")
                else:
                    avg_scores.append(0.0)
                    logger.info(f"第 {i+1} 题无有效分数，设为0")
            
            # 记录平均分计算结果
            logger.info(f"学生 {student_name} 的最终平均分: {avg_scores}")
            
            # 保存评分结果
            qwen_results[student_name] = qwen_scores
            moonshot_results[student_name] = moonshot_scores
            zhipu_results[student_name] = zhipu_scores
            
            # 更新session_state中的评分结果
            if 'manual_grading' not in st.session_state:
                st.session_state['manual_grading'] = {'scores': {}}
            
            # 确保保存的是浮点数列表
            st.session_state['manual_grading']['scores'][student_name] = [float(score) for score in avg_scores]
            
            # 验证保存的分数
            saved_scores = st.session_state['manual_grading']['scores'][student_name]
            logger.info(f"已保存学生 {student_name} 的分数: {saved_scores}")
            
            # 验证保存的分数是否正确
            if len(saved_scores) != len(avg_scores):
                logger.error(f"保存的分数长度不匹配: 预期 {len(avg_scores)}, 实际 {len(saved_scores)}")
            else:
                for i, (expected, actual) in enumerate(zip(avg_scores, saved_scores)):
                    if abs(expected - actual) > 0.001:  # 允许小的浮点数误差
                        logger.error(f"第 {i+1} 题分数不匹配: 预期 {expected}, 实际 {actual}")
        
        # 保存各模型的评分结果
        st.session_state['qwen_grading_results'] = qwen_results
        st.session_state['moonshot_grading_results'] = moonshot_results
        st.session_state['zhipu_grading_results'] = zhipu_results
        
        return "AI评分完成"
        
    except Exception as e:
        logger.error(f"评分过程出错: {str(e)}")
        logger.exception("评分错误详情")
        return f"评分失败: {str(e)}"