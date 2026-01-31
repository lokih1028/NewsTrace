"""
语义去重模块 (Semantic Deduplicator)
用于过滤同一事件的重复新闻报道
"""
import logging
import re
from typing import List, Dict, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class SemanticDeduplicator:
    """语义去重器"""
    
    def __init__(self, similarity_threshold: float = 0.6):
        """
        初始化去重器
        
        Args:
            similarity_threshold: 相似度阈值，超过此值视为重复 (0.0-1.0)
        """
        self.threshold = similarity_threshold
        
        # 停用词（金融新闻常见无意义词）
        self.stopwords = {
            '的', '了', '是', '在', '和', '与', '或', '等', '将', '被',
            '为', '对', '从', '到', '年', '月', '日', '亿', '万', '元',
            '公司', '股份', '有限', '预计', '预期', '表示', '称', '据',
            '消息', '报道', '显示', '数据', '市场', '行业', '板块'
        }
        
        logger.info(f"语义去重器初始化: 阈值={self.threshold}")
    
    def filter(self, news_list: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        过滤重复新闻
        
        Args:
            news_list: 原始新闻列表
            
        Returns:
            (unique_news, duplicates) - 去重后的新闻和被过滤的重复新闻
        """
        if not news_list:
            return [], []
        
        unique_news = []
        duplicates = []
        seen_keywords: List[Set[str]] = []
        
        for news in news_list:
            title = news.get('title', '')
            keywords = self._extract_keywords(title)
            
            # 检查与已有新闻的相似度
            is_duplicate = False
            duplicate_of = None
            
            for i, existing_keywords in enumerate(seen_keywords):
                similarity = self._jaccard_similarity(keywords, existing_keywords)
                
                if similarity >= self.threshold:
                    is_duplicate = True
                    duplicate_of = unique_news[i].get('title', '')[:30]
                    break
            
            if is_duplicate:
                news['_duplicate_of'] = duplicate_of
                news['_similarity'] = similarity
                duplicates.append(news)
                logger.debug(f"过滤重复新闻: {title[:30]}... (相似于: {duplicate_of}...)")
            else:
                unique_news.append(news)
                seen_keywords.append(keywords)
        
        logger.info(f"语义去重完成: 原始={len(news_list)}, 保留={len(unique_news)}, "
                   f"过滤={len(duplicates)}")
        
        return unique_news, duplicates
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """
        提取文本关键词
        
        Args:
            text: 输入文本
            
        Returns:
            关键词集合
        """
        # 移除标点和数字
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z]', ' ', text)
        
        # 简单分词（按字符n-gram + 按词）
        keywords = set()
        
        # 提取2-4字的中文词组
        for i in range(len(text)):
            for n in [2, 3, 4]:
                if i + n <= len(text):
                    word = text[i:i+n]
                    if word and word not in self.stopwords and len(word.strip()) >= 2:
                        keywords.add(word)
        
        # 提取英文词
        english_words = re.findall(r'[a-zA-Z]+', text)
        for word in english_words:
            if len(word) >= 2:
                keywords.add(word.lower())
        
        return keywords
    
    def _jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """
        计算 Jaccard 相似度
        
        Args:
            set1, set2: 两个关键词集合
            
        Returns:
            相似度 (0.0-1.0)
        """
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def group_by_event(self, news_list: List[Dict]) -> Dict[str, List[Dict]]:
        """
        按事件聚合新闻（用于报告生成）
        
        Args:
            news_list: 新闻列表
            
        Returns:
            {event_key: [news1, news2, ...]}
        """
        if not news_list:
            return {}
        
        groups = defaultdict(list)
        group_keywords: Dict[str, Set[str]] = {}
        group_counter = 0
        
        for news in news_list:
            title = news.get('title', '')
            keywords = self._extract_keywords(title)
            
            # 找到最相似的已有分组
            best_group = None
            best_similarity = 0.0
            
            for group_key, existing_keywords in group_keywords.items():
                similarity = self._jaccard_similarity(keywords, existing_keywords)
                if similarity > best_similarity and similarity >= self.threshold:
                    best_similarity = similarity
                    best_group = group_key
            
            if best_group:
                groups[best_group].append(news)
                # 更新分组关键词（取并集）
                group_keywords[best_group] |= keywords
            else:
                # 创建新分组
                group_counter += 1
                group_key = f"event_{group_counter}"
                groups[group_key].append(news)
                group_keywords[group_key] = keywords
        
        logger.info(f"事件聚合完成: 新闻={len(news_list)}, 事件组={len(groups)}")
        
        return dict(groups)
    
    def get_representative(self, news_group: List[Dict]) -> Dict:
        """
        从新闻组中选取代表性新闻（标题最长的通常信息最完整）
        
        Args:
            news_group: 同一事件的新闻列表
            
        Returns:
            代表性新闻
        """
        if not news_group:
            return {}
        
        # 选择标题最长的作为代表
        return max(news_group, key=lambda n: len(n.get('title', '')))
