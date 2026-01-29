"""
增强型新闻分析器
提供情感分析、相似度检测和关键词提取
"""
import re
import logging
from typing import Dict, List, Tuple, Optional
from collections import Counter
import hashlib

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """情感分析器"""
    
    # 正面词汇
    POSITIVE_WORDS = {
        "上涨", "增长", "突破", "利好", "强势", "超预期", "创新高",
        "回暖", "复苏", "加速", "优化", "提升", "改善", "扩大",
        "盈利", "分红", "增持", "上调", "推荐", "买入"
    }
    
    # 负面词汇
    NEGATIVE_WORDS = {
        "下跌", "下滑", "暴跌", "利空", "弱势", "不及预期", "创新低",
        "萎缩", "衰退", "放缓", "恶化", "下降", "收窄", "减少",
        "亏损", "减持", "下调", "卖出", "风险", "警告"
    }
    
    # 不确定词汇
    UNCERTAIN_WORDS = {
        "可能", "或将", "预计", "有望", "传闻", "据悉", "消息称",
        "不排除", "存在", "待定", "观望", "谨慎"
    }
    
    def analyze(self, text: str) -> Dict:
        """
        分析文本情感
        
        Returns:
            {
                "score": float (-1 to 1),
                "label": str (positive/negative/neutral),
                "confidence": float (0 to 1),
                "positive_count": int,
                "negative_count": int,
                "uncertain_count": int
            }
        """
        positive_count = sum(1 for w in self.POSITIVE_WORDS if w in text)
        negative_count = sum(1 for w in self.NEGATIVE_WORDS if w in text)
        uncertain_count = sum(1 for w in self.UNCERTAIN_WORDS if w in text)
        
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            confidence = 0.3
        else:
            score = (positive_count - negative_count) / total
            confidence = min(total / 10, 1.0)
        
        # 不确定性降低置信度
        confidence *= (1 - min(uncertain_count / 5, 0.5))
        
        if score > 0.2:
            label = "positive"
        elif score < -0.2:
            label = "negative"
        else:
            label = "neutral"
        
        return {
            "score": round(score, 3),
            "label": label,
            "confidence": round(confidence, 3),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "uncertain_count": uncertain_count
        }


class KeywordExtractor:
    """关键词提取器"""
    
    # 停用词
    STOPWORDS = {
        "的", "了", "是", "在", "和", "与", "或", "以", "及",
        "等", "有", "为", "被", "将", "从", "到", "对", "于",
        "中", "上", "下", "前", "后", "此", "该", "其", "这"
    }
    
    def extract(
        self,
        text: str,
        top_n: int = 10,
        min_length: int = 2
    ) -> List[Tuple[str, int]]:
        """
        提取关键词
        
        Returns:
            [(keyword, count), ...]
        """
        # 简单分词 (按标点和空格)
        words = re.split(r'[,，。！？；：\s]+', text)
        
        # 过滤
        words = [
            w for w in words
            if len(w) >= min_length
            and w not in self.STOPWORDS
            and not w.isdigit()
        ]
        
        # 统计
        counter = Counter(words)
        return counter.most_common(top_n)


class SimilarityDetector:
    """新闻相似度检测器"""
    
    def __init__(self):
        self.news_hashes: Dict[str, str] = {}  # news_id -> hash
        self.hash_index: Dict[str, List[str]] = {}  # simhash -> news_ids
    
    def compute_simhash(self, text: str, hash_bits: int = 64) -> str:
        """计算 SimHash"""
        # 分词
        words = re.split(r'[,，。！？；：\s]+', text)
        words = [w for w in words if len(w) >= 2]
        
        if not words:
            return "0" * 16
        
        # 计算每个词的哈希
        v = [0] * hash_bits
        for word in words:
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            for i in range(hash_bits):
                if h & (1 << i):
                    v[i] += 1
                else:
                    v[i] -= 1
        
        # 生成 SimHash
        simhash = 0
        for i in range(hash_bits):
            if v[i] > 0:
                simhash |= (1 << i)
        
        return format(simhash, 'x').zfill(16)
    
    def hamming_distance(self, hash1: str, hash2: str) -> int:
        """计算汉明距离"""
        h1 = int(hash1, 16)
        h2 = int(hash2, 16)
        xor = h1 ^ h2
        return bin(xor).count('1')
    
    def add_news(self, news_id: str, text: str):
        """添加新闻到索引"""
        simhash = self.compute_simhash(text)
        self.news_hashes[news_id] = simhash
        
        if simhash not in self.hash_index:
            self.hash_index[simhash] = []
        self.hash_index[simhash].append(news_id)
    
    def find_similar(
        self,
        text: str,
        threshold: int = 5
    ) -> List[Tuple[str, int]]:
        """
        查找相似新闻
        
        Args:
            text: 待查找文本
            threshold: 汉明距离阈值
            
        Returns:
            [(news_id, distance), ...]
        """
        query_hash = self.compute_simhash(text)
        results = []
        
        for news_id, news_hash in self.news_hashes.items():
            distance = self.hamming_distance(query_hash, news_hash)
            if distance <= threshold:
                results.append((news_id, distance))
        
        return sorted(results, key=lambda x: x[1])
    
    def is_duplicate(self, text: str, threshold: int = 3) -> Optional[str]:
        """检查是否重复"""
        similar = self.find_similar(text, threshold)
        if similar:
            return similar[0][0]
        return None


class EnhancedNewsAnalyzer:
    """增强型新闻分析器"""
    
    def __init__(self):
        self.sentiment = SentimentAnalyzer()
        self.keyword_extractor = KeywordExtractor()
        self.similarity = SimilarityDetector()
        
        logger.info("增强型新闻分析器初始化完成")
    
    def analyze(self, news: Dict) -> Dict:
        """
        全面分析新闻
        
        Args:
            news: 新闻字典 {news_id, title, content}
            
        Returns:
            分析结果
        """
        news_id = news.get("news_id", "")
        title = news.get("title", "")
        content = news.get("content", "")
        text = f"{title} {content}"
        
        # 情感分析
        sentiment_result = self.sentiment.analyze(text)
        
        # 关键词提取
        keywords = self.keyword_extractor.extract(text)
        
        # 相似度检测
        duplicate_of = self.similarity.is_duplicate(text)
        
        # 添加到索引
        if news_id:
            self.similarity.add_news(news_id, text)
        
        return {
            "news_id": news_id,
            "sentiment": sentiment_result,
            "keywords": [{"word": w, "count": c} for w, c in keywords],
            "is_duplicate": duplicate_of is not None,
            "duplicate_of": duplicate_of,
            "text_length": len(text)
        }
    
    def batch_analyze(self, news_list: List[Dict]) -> List[Dict]:
        """批量分析"""
        return [self.analyze(news) for news in news_list]
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            "indexed_news": len(self.similarity.news_hashes),
            "unique_hashes": len(self.similarity.hash_index)
        }
