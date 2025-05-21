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




def extract_text_from_response(response):
    """
    从API响应中提取文本内容
    支持多种响应格式，确保总是返回有效内容
    """
    result = None
    
    # 方法1：从choices中提取
    if hasattr(response, 'output') and hasattr(response.output, 'choices'):
        try:
            choices = response.output.choices
            if choices and len(choices) > 0:
                choice = choices[0]
                # 尝试对象格式
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    content = choice.message.content
                    if isinstance(content, list) and len(content) > 0:
                        if hasattr(content[0], 'text'):
                            result = content[0].text
                            logger.info("成功从choices对象content中提取文本内容")
                        elif isinstance(content[0], dict) and 'text' in content[0]:
                            result = content[0]['text']
                            logger.info("成功从choices对象content字典中提取文本内容")
                # 尝试字典格式
                elif isinstance(choice, dict) and 'message' in choice:
                    message = choice['message']
                    if 'content' in message:
                        content = message['content']
                        if isinstance(content, list) and len(content) > 0:
                            if 'text' in content[0]:
                                result = content[0]['text']
                                logger.info("成功从choices字典中提取文本内容")
        except Exception as e:
            logger.error(f"从choices中提取内容失败: {str(e)}")
    
    # 方法2：从output.text提取（旧版API格式）
    if result is None and hasattr(response, 'output') and hasattr(response.output, 'text'):
        result = response.output.text
        if result:
            logger.info("成功从output.text中提取内容")
    
    # 处理可能为None的情况
    if result is None:
        # 尝试直接获取响应的字符串表示
        try:
            result = str(response)
            logger.warning(f"使用响应的字符串表示作为备份: {result[:100]}...")
        except:
            result = "API响应无法解析"
            logger.error("无法获取API响应的字符串表示")
    elif not result.strip():
        result = "API返回空字符串"
        logger.warning("API响应为空字符串")
    
    # 处理Markdown代码块
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
    
    # 提取JSON内容（如果存在）
    if "{" in result and "}" in result:
        try:
            json_pattern = r'\{.*\}'
            json_match = re.search(json_pattern, result, re.DOTALL)
            if json_match and json_match.group(0) != result:
                pure_json = json_match.group(0)
                try:
                    # 验证是否为有效JSON
                    json.loads(pure_json)
                    result = pure_json  # 如果是有效JSON，则只返回JSON部分
                    logger.debug("成功提取出纯JSON结果")
                except:
                    logger.debug("提取的JSON无效，保留原始响应")
        except Exception as e:
            logger.error(f"尝试提取JSON时出错: {str(e)}")
    
    return result

def fix_json_format(text):
    """修复和提取JSON格式，确保返回有效的JSON对象"""
    if not text or not isinstance(text, str):
        return "{}"
        
    # 如果是Markdown代码块，提取内容
    if "```" in text:
        code_pattern = r"```(?:json|javascript|js)?\s*([\s\S]*?)\s*```"
        code_match = re.search(code_pattern, text, re.DOTALL)
        if code_match:
            text = code_match.group(1).strip()
            
    # 如果文本中包含JSON对象，提取它
    if "{" in text and "}" in text:
        json_pattern = r"\{[^{]*\}"
        json_matches = re.findall(json_pattern, text, re.DOTALL)
        if json_matches:
            # 尝试找到最长的有效JSON
            valid_jsons = []
            for match in json_matches:
                try:
                    parsed = json.loads(match)
                    valid_jsons.append((match, len(match), parsed))
                except:
                    pass
                    
            if valid_jsons:
                # 按长度排序，取最长的
                valid_jsons.sort(key=lambda x: x[1], reverse=True)
                return valid_jsons[0][0]
    
    # 如果没有找到有效JSON，尝试整体解析
    try:
        json.loads(text)
        return text
    except:
        pass
    
    # 最后的后备方案：返回空对象
    return "{}"

def extract_json(text):
    """从文本中提取JSON对象，如果失败则返回空对象"""
    try:
        # 第一步：修复格式
        fixed_json = fix_json_format(text)
        
        # 第二步：解析JSON
        return json.loads(fixed_json)
    except Exception as e:
        logger.error(f"JSON解析失败: {str(e)}")
        return {}

def extract_text_from_response(response):
    """
    从API响应中提取文本内容
    支持多种响应格式，确保总是返回有效内容
    """
    result = None
    
    # 方法1：从choices中提取
    if hasattr(response, 'output') and hasattr(response.output, 'choices'):
        try:
            choices = response.output.choices
            if choices and len(choices) > 0:
                choice = choices[0]
                # 尝试对象格式
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    content = choice.message.content
                    if isinstance(content, list) and len(content) > 0:
                        if hasattr(content[0], 'text'):
                            result = content[0].text
                            logger.info("成功从choices对象content中提取文本内容")
                        elif isinstance(content[0], dict) and 'text' in content[0]:
                            result = content[0]['text']
                            logger.info("成功从choices对象content字典中提取文本内容")
                # 尝试字典格式
                elif isinstance(choice, dict) and 'message' in choice:
                    message = choice['message']
                    if 'content' in message:
                        content = message['content']
                        if isinstance(content, list) and len(content) > 0:
                            if 'text' in content[0]:
                                result = content[0]['text']
                                logger.info("成功从choices字典中提取文本内容")
        except Exception as e:
            logger.error(f"从choices中提取内容失败: {str(e)}")
    
    # 方法2：从output.text提取（旧版API格式）
    if result is None and hasattr(response, 'output') and hasattr(response.output, 'text'):
        result = response.output.text
        if result:
            logger.info("成功从output.text中提取内容")
    
    # 处理可能为None的情况
    if result is None:
        # 尝试直接获取响应的字符串表示
        try:
            result = str(response)
            logger.warning(f"使用响应的字符串表示作为备份: {result[:100]}...")
        except:
            result = "API响应无法解析"
            logger.error("无法获取API响应的字符串表示")
    elif not result.strip():
        result = "API返回空字符串"
        logger.warning("API响应为空字符串")
    
    # 处理Markdown代码块
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
    
    # 提取JSON内容（如果存在）
    if "{" in result and "}" in result:
        try:
            json_pattern = r'\{.*\}'
            json_match = re.search(json_pattern, result, re.DOTALL)
            if json_match and json_match.group(0) != result:
                pure_json = json_match.group(0)
                try:
                    # 验证是否为有效JSON
                    json.loads(pure_json)
                    result = pure_json  # 如果是有效JSON，则只返回JSON部分
                    logger.debug("成功提取出纯JSON结果")
                except:
                    logger.debug("提取的JSON无效，保留原始响应")
        except Exception as e:
            logger.error(f"尝试提取JSON时出错: {str(e)}")
    
    return result
