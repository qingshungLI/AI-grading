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




def convert_docx_to_pdf(docx_path, pdf_path):
    """使用Word应用程序转换DOCX为PDF"""
    try:
        # 初始化COM
        pythoncom.CoInitialize()
        
        # 创建Word应用程序实例
        word = win32com.client.Dispatch('Word.Application')
        word.Visible = False
        
        try:
            # 打开文档
            doc = word.Documents.Open(docx_path)
            # 另存为PDF
            doc.SaveAs(pdf_path, FileFormat=17)  # 17 表示PDF格式
            doc.Close()
            return True
        except Exception as e:
            logger.error(f"Word转换失败: {str(e)}")
            return False
        finally:
            # 关闭Word应用程序
            word.Quit()
    except Exception as e:
        logger.error(f"COM初始化或Word应用程序创建失败: {str(e)}")
        return False
    finally:
        # 清理COM
        pythoncom.CoUninitialize()

def convert_document_to_images(doc):
    """将文档转换为图片列表，支持PDF和Word文档"""
    try:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 获取文件扩展名
            file_ext = os.path.splitext(doc.name)[1].lower()
            
            if file_ext == '.pdf':
                # 直接处理PDF文件
                pdf_path = os.path.join(temp_dir, 'input.pdf')
                with open(pdf_path, 'wb') as f:
                    f.write(doc.getvalue())
                return convert_pdf_to_images(pdf_path)
                
            elif file_ext in ['.docx', '.doc']:
                try:
                    # 先将Word转换为PDF
                    docx_path = os.path.join(temp_dir, 'input.docx')
                    pdf_path = os.path.join(temp_dir, 'output.pdf')
                    
                    # 保存上传的Word文件
                    with open(docx_path, 'wb') as f:
                        f.write(doc.getvalue())
                    
                    # 尝试使用Word应用程序转换
                    if convert_docx_to_pdf(docx_path, pdf_path):
                        logger.info(f"Word文档 '{doc.name}' 成功转换为PDF")
                        # 将PDF转换为图片
                        images = convert_pdf_to_images(pdf_path)
                        if not images:
                            st.error(f"❌ 无法将转换后的PDF转换为图片: {doc.name}")
                            return []
                        return images
                    else:
                        # 如果Word应用程序转换失败，尝试使用docx2pdf
                        try:
                            docx2pdf.convert(docx_path, pdf_path)
                            logger.info(f"使用docx2pdf成功转换Word文档 '{doc.name}' 为PDF")
                            images = convert_pdf_to_images(pdf_path)
                            if images:
                                return images
                        except Exception as pdf_error:
                            logger.error(f"docx2pdf转换失败: {str(pdf_error)}")
                            
                        st.error(f"❌ 无法转换Word文档: {doc.name}")
                        return []
                        
                except Exception as e:
                    error_msg = f"Word文档转换失败: {str(e)}"
                    logger.error(error_msg)
                    st.error(f"❌ {error_msg}")
                    return []
            else:
                error_msg = f"不支持的文件格式: {file_ext}"
                logger.error(error_msg)
                st.error(f"❌ {error_msg}")
                return []
                
    except Exception as e:
        error_msg = f"文档转换失败: {str(e)}"
        logger.error(error_msg)
        st.error(f"❌ {error_msg}")
        return []
def convert_pdf_to_images(pdf_path):
    """将PDF文件转换为图片列表"""
    try:
        images = []
        # 打开PDF文件
        pdf_document = fitz.open(pdf_path)
        
        # 遍历每一页
        for page_num in range(len(pdf_document)):
            # 获取页面
            page = pdf_document[page_num]
            
            # 将页面转换为图片
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))  # 300 DPI
            
            # 转换为PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # 将图片转换为字节流
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            images.append(img_byte_arr)
            
        pdf_document.close()
        return images
        
    except Exception as e:
        logger.error(f"PDF转图片失败: {str(e)}")
        raise


def text_to_image(text, title=""):
    """将文本转换为图像"""
    # 设置图像参数
    width = 1000
    line_height = 20
    padding = 20
    
    # 计算需要的行数和高度
    lines = text.split('\n')
    height = len(lines) * line_height + padding * 2
    if height < 500:  # 设置最小高度
        height = 500
        
    # 创建空白图像
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    
    try:
        # 尝试加载字体，如果失败则使用默认字体
        font = ImageFont.truetype("arial.ttf", 14)
    except IOError:
        font = ImageFont.load_default()
    
    # 绘制标题
    if title:
        d.text((padding, padding), f"文件名: {title}", fill=(0, 0, 0), font=font)
        
    # 绘制文本内容
    y_position = padding + 25  # 标题下方开始
    for line in lines:
        d.text((padding, y_position), line, fill=(0, 0, 0), font=font)
        y_position += line_height
        
    return img