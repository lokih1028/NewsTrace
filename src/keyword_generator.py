"""
智能关键词生成器
根据股票代码自动生成相关新闻关键词
"""
import logging
from typing import List, Dict
import os

logger = logging.getLogger(__name__)


class KeywordGenerator:
    """智能关键词生成器"""
    
    def __init__(self, llm_config: Dict = None):
        """
        初始化关键词生成器
        
        Args:
            llm_config: LLM配置(可选,用于AI增强)
        """
        self.llm_config = llm_config or {}
        self.client = None
        
        # 初始化LLM客户端(如果配置了)
        if llm_config and llm_config.get('api_key'):
            self._init_llm_client()
        
        logger.info("智能关键词生成器初始化完成")
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.llm_config.get('api_key') or os.getenv('OPENAI_API_KEY')
            )
            logger.info("LLM客户端初始化成功")
        except Exception as e:
            logger.warning(f"LLM客户端初始化失败: {e}")
    
    def generate_keywords(self, stock_code: str, use_ai: bool = True) -> List[str]:
        """
        根据股票代码生成关键词
        
        Args:
            stock_code: 股票代码(如 600519.SH)
            use_ai: 是否使用AI增强生成
            
        Returns:
            关键词列表
        """
        # 1. 获取股票基本信息
        stock_info = self._get_stock_info(stock_code)
        
        if not stock_info:
            logger.warning(f"无法获取 {stock_code} 的信息")
            return []
        
        # 2. 基础关键词(基于股票名称和行业)
        base_keywords = self._generate_base_keywords(stock_info)
        
        # 3. AI增强关键词(可选)
        if use_ai and self.client:
            ai_keywords = self._generate_ai_keywords(stock_info)
            keywords = list(set(base_keywords + ai_keywords))
        else:
            keywords = base_keywords
        
        logger.info(f"为 {stock_code} 生成了 {len(keywords)} 个关键词")
        return keywords[:15]  # 限制最多15个关键词
    
    def _get_stock_info(self, stock_code: str) -> Dict:
        """获取股票基本信息"""
        try:
            import tushare as ts
            
            token = os.getenv("TUSHARE_TOKEN")
            if not token:
                logger.warning("TUSHARE_TOKEN 未配置")
                return {}
            
            ts.set_token(token)
            pro = ts.pro_api()
            
            # 转换股票代码格式
            if '.' not in stock_code:
                if stock_code.startswith('6'):
                    ts_code = f"{stock_code}.SH"
                else:
                    ts_code = f"{stock_code}.SZ"
            else:
                ts_code = stock_code
            
            # 获取股票基本信息
            df = pro.stock_basic(ts_code=ts_code, fields='ts_code,name,industry,market,list_date')
            
            if df.empty:
                return {}
            
            info = df.iloc[0].to_dict()
            logger.info(f"获取到股票信息: {info['name']} ({info['industry']})")
            return info
            
        except Exception as e:
            logger.error(f"获取股票信息失败: {e}")
            return {}
    
    def _generate_base_keywords(self, stock_info: Dict) -> List[str]:
        """生成基础关键词"""
        keywords = []
        
        # 1. 股票名称
        name = stock_info.get('name', '')
        if name:
            keywords.append(name)
            
            # 提取公司简称(去掉"股份"、"有限公司"等后缀)
            short_name = name.replace('股份', '').replace('有限公司', '').replace('集团', '').strip()
            if short_name and short_name != name:
                keywords.append(short_name)
        
        # 2. 行业关键词
        industry = stock_info.get('industry', '')
        if industry:
            keywords.append(industry)
            
            # 行业相关词
            industry_map = {
                '白酒': ['茅台', '五粮液', '泸州老窖', '消费税', '白酒板块'],
                '银行': ['央行', '存款准备金率', '利率', '金融'],
                '房地产': ['地产', '房价', '调控', '土地'],
                '新能源': ['锂电池', '光伏', '风电', '储能'],
                '半导体': ['芯片', '集成电路', '晶圆', '光刻机'],
                '医药': ['创新药', 'CXO', '医保', '集采'],
                '汽车': ['新能源车', '智能驾驶', '车企'],
            }
            
            for key, related_words in industry_map.items():
                if key in industry:
                    keywords.extend(related_words)
                    break
        
        # 3. 市场板块
        market = stock_info.get('market', '')
        if market == '主板':
            keywords.append('A股')
        elif market == '科创板':
            keywords.extend(['科创板', '科技'])
        
        return list(set(keywords))
    
    def _generate_ai_keywords(self, stock_info: Dict) -> List[str]:
        """使用AI生成增强关键词"""
        if not self.client:
            return []
        
        try:
            name = stock_info.get('name', '')
            industry = stock_info.get('industry', '')
            
            prompt = f"""你是一个金融新闻关键词专家。请为以下股票生成5-10个相关新闻关键词:

股票名称: {name}
所属行业: {industry}

要求:
1. 关键词应该是可能出现在相关新闻标题中的词汇
2. 包括公司名、行业术语、政策相关词、上下游产业链词汇
3. 每个关键词2-6个字
4. 直接返回关键词列表,用逗号分隔,不要其他解释

示例格式: 茅台,白酒,消费税,高端白酒,贵州茅台"""

            response = self.client.chat.completions.create(
                model=self.llm_config.get('model', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": "你是一个金融新闻关键词生成专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            keywords = [kw.strip() for kw in content.split(',') if kw.strip()]
            
            logger.info(f"AI生成了 {len(keywords)} 个关键词")
            return keywords
            
        except Exception as e:
            logger.error(f"AI生成关键词失败: {e}")
            return []
    
    def generate_config(self, stock_codes: List[str]) -> Dict:
        """
        为多个股票代码生成配置
        
        Args:
            stock_codes: 股票代码列表
            
        Returns:
            配置字典
        """
        config = {
            "watch_keywords": [],
            "stock_mapping": {}
        }
        
        for code in stock_codes:
            keywords = self.generate_keywords(code)
            if keywords:
                config["watch_keywords"].extend(keywords)
                config["stock_mapping"][code] = keywords
        
        # 去重
        config["watch_keywords"] = list(set(config["watch_keywords"]))
        
        return config
