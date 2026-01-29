"""
新闻知识图谱模块
实现实体提取、关系识别和知识存储
"""
import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """实体结构"""
    name: str
    type: str  # PERSON, ORG, STOCK, SECTOR, POLICY, EVENT
    aliases: Set[str] = field(default_factory=set)
    properties: Dict = field(default_factory=dict)
    
    def __hash__(self):
        return hash((self.name, self.type))


@dataclass
class Relation:
    """关系结构"""
    source: Entity
    target: Entity
    relation_type: str  # MENTIONS, AFFECTS, RELATED_TO, PART_OF, PREDICTS
    weight: float = 1.0
    properties: Dict = field(default_factory=dict)


class EntityExtractor:
    """实体提取器"""
    
    # 预定义实体模式
    STOCK_PATTERN = re.compile(r'([0-9]{6}\.[SZ]{2}|[A-Z]{1,5})')
    PERCENT_PATTERN = re.compile(r'([+-]?\d+\.?\d*%)')
    MONEY_PATTERN = re.compile(r'(\d+\.?\d*[万亿]+[元美]?[元币]?)')
    
    # 常见机构/部门
    KNOWN_ORGS = {
        "央行", "中国人民银行", "证监会", "银保监会", "发改委",
        "财政部", "国资委", "商务部", "工信部", "国务院",
        "美联储", "欧洲央行", "日本央行"
    }
    
    # 行业关键词
    SECTORS = {
        "新能源": ["锂电", "光伏", "风电", "储能", "氢能"],
        "半导体": ["芯片", "晶圆", "封测", "设计", "设备"],
        "消费": ["白酒", "食品", "家电", "零售", "餐饮"],
        "医药": ["创新药", "仿制药", "医疗器械", "CXO", "疫苗"],
        "金融": ["银行", "保险", "券商", "基金", "信托"],
        "地产": ["房地产", "物业", "建材", "家居", "装修"]
    }
    
    def __init__(self, llm_provider=None):
        """
        初始化实体提取器
        
        Args:
            llm_provider: LLM 提供商实例 (可选,用于增强提取)
        """
        self.llm = llm_provider
        self.entity_cache = {}
        
        logger.info("实体提取器初始化完成")
    
    def extract(self, news: Dict) -> List[Entity]:
        """
        从新闻中提取实体
        
        Args:
            news: 新闻字典 {title, content, source}
            
        Returns:
            实体列表
        """
        entities = []
        title = news.get("title", "")
        content = news.get("content", "")
        text = f"{title} {content}"
        
        # 1. 规则提取
        entities.extend(self._extract_by_rules(text))
        
        # 2. 机构提取
        entities.extend(self._extract_orgs(text))
        
        # 3. 行业提取
        entities.extend(self._extract_sectors(text))
        
        # 4. LLM 增强提取 (可选)
        if self.llm:
            entities.extend(self._extract_by_llm(text))
        
        # 去重
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e.name, e.type)
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)
        
        return unique_entities
    
    def _extract_by_rules(self, text: str) -> List[Entity]:
        """规则提取"""
        entities = []
        
        # 股票代码
        for match in self.STOCK_PATTERN.finditer(text):
            entities.append(Entity(
                name=match.group(1),
                type="STOCK"
            ))
        
        return entities
    
    def _extract_orgs(self, text: str) -> List[Entity]:
        """机构提取"""
        entities = []
        for org in self.KNOWN_ORGS:
            if org in text:
                entities.append(Entity(
                    name=org,
                    type="ORG"
                ))
        return entities
    
    def _extract_sectors(self, text: str) -> List[Entity]:
        """行业提取"""
        entities = []
        for sector, keywords in self.SECTORS.items():
            for kw in keywords:
                if kw in text:
                    entities.append(Entity(
                        name=sector,
                        type="SECTOR",
                        aliases={kw}
                    ))
                    break
        return entities
    
    def _extract_by_llm(self, text: str) -> List[Entity]:
        """LLM 增强提取"""
        prompt = f"""从以下文本中提取关键实体,以 JSON 格式返回:
        
文本: {text[:500]}

返回格式:
{{
  "entities": [
    {{"name": "实体名", "type": "PERSON|ORG|STOCK|SECTOR|POLICY|EVENT"}}
  ]
}}

只返回 JSON,不要其他内容。"""
        
        try:
            response = self.llm.generate(prompt)
            data = json.loads(response.content)
            return [
                Entity(name=e["name"], type=e["type"])
                for e in data.get("entities", [])
            ]
        except Exception as e:
            logger.warning(f"LLM 实体提取失败: {e}")
            return []


class KnowledgeGraph:
    """知识图谱"""
    
    def __init__(self):
        """初始化知识图谱"""
        self.entities: Dict[str, Entity] = {}
        self.relations: List[Relation] = []
        self.entity_index: Dict[str, Set[str]] = defaultdict(set)  # type -> entity_ids
        
        logger.info("知识图谱初始化完成")
    
    def add_entity(self, entity: Entity) -> str:
        """添加实体"""
        entity_id = f"{entity.type}:{entity.name}"
        
        if entity_id in self.entities:
            # 合并别名
            self.entities[entity_id].aliases.update(entity.aliases)
        else:
            self.entities[entity_id] = entity
            self.entity_index[entity.type].add(entity_id)
        
        return entity_id
    
    def add_relation(self, relation: Relation):
        """添加关系"""
        # 确保实体存在
        self.add_entity(relation.source)
        self.add_entity(relation.target)
        self.relations.append(relation)
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        return self.entities.get(entity_id)
    
    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        """按类型获取实体"""
        return [
            self.entities[eid]
            for eid in self.entity_index.get(entity_type, [])
        ]
    
    def get_related_entities(
        self,
        entity_id: str,
        relation_type: Optional[str] = None,
        direction: str = "both"
    ) -> List[Tuple[Entity, Relation]]:
        """获取关联实体"""
        results = []
        
        for rel in self.relations:
            source_id = f"{rel.source.type}:{rel.source.name}"
            target_id = f"{rel.target.type}:{rel.target.name}"
            
            if relation_type and rel.relation_type != relation_type:
                continue
            
            if direction in ("both", "outgoing") and source_id == entity_id:
                results.append((rel.target, rel))
            
            if direction in ("both", "incoming") and target_id == entity_id:
                results.append((rel.source, rel))
        
        return results
    
    def find_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3
    ) -> Optional[List[str]]:
        """查找两个实体间的路径"""
        if start_id == end_id:
            return [start_id]
        
        visited = {start_id}
        queue = [(start_id, [start_id])]
        
        while queue:
            current, path = queue.pop(0)
            
            if len(path) > max_depth:
                continue
            
            for entity, _ in self.get_related_entities(current):
                entity_id = f"{entity.type}:{entity.name}"
                
                if entity_id == end_id:
                    return path + [entity_id]
                
                if entity_id not in visited:
                    visited.add(entity_id)
                    queue.append((entity_id, path + [entity_id]))
        
        return None
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        type_counts = {t: len(ids) for t, ids in self.entity_index.items()}
        return {
            "total_entities": len(self.entities),
            "total_relations": len(self.relations),
            "entities_by_type": type_counts
        }
    
    def to_dict(self) -> Dict:
        """导出为字典"""
        return {
            "entities": [
                {
                    "id": f"{e.type}:{e.name}",
                    "name": e.name,
                    "type": e.type,
                    "aliases": list(e.aliases),
                    "properties": e.properties
                }
                for e in self.entities.values()
            ],
            "relations": [
                {
                    "source": f"{r.source.type}:{r.source.name}",
                    "target": f"{r.target.type}:{r.target.name}",
                    "type": r.relation_type,
                    "weight": r.weight,
                    "properties": r.properties
                }
                for r in self.relations
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeGraph":
        """从字典导入"""
        kg = cls()
        
        # 添加实体
        entity_map = {}
        for e_data in data.get("entities", []):
            entity = Entity(
                name=e_data["name"],
                type=e_data["type"],
                aliases=set(e_data.get("aliases", [])),
                properties=e_data.get("properties", {})
            )
            entity_map[e_data["id"]] = entity
            kg.add_entity(entity)
        
        # 添加关系
        for r_data in data.get("relations", []):
            source = entity_map.get(r_data["source"])
            target = entity_map.get(r_data["target"])
            if source and target:
                kg.add_relation(Relation(
                    source=source,
                    target=target,
                    relation_type=r_data["type"],
                    weight=r_data.get("weight", 1.0),
                    properties=r_data.get("properties", {})
                ))
        
        return kg


class NewsKnowledgeBuilder:
    """新闻知识构建器"""
    
    def __init__(self, extractor: EntityExtractor = None):
        """
        初始化知识构建器
        
        Args:
            extractor: 实体提取器
        """
        self.extractor = extractor or EntityExtractor()
        self.graph = KnowledgeGraph()
        
        logger.info("新闻知识构建器初始化完成")
    
    def process_news(self, news: Dict) -> Dict:
        """
        处理新闻并更新知识图谱
        
        Args:
            news: 新闻字典
            
        Returns:
            处理结果
        """
        # 提取实体
        entities = self.extractor.extract(news)
        
        # 添加实体到图谱
        entity_ids = []
        for entity in entities:
            eid = self.graph.add_entity(entity)
            entity_ids.append(eid)
        
        # 创建实体间关系 (共现关系)
        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                self.graph.add_relation(Relation(
                    source=e1,
                    target=e2,
                    relation_type="RELATED_TO",
                    weight=0.5,
                    properties={"news_id": news.get("news_id")}
                ))
        
        return {
            "news_id": news.get("news_id"),
            "entities_extracted": len(entities),
            "entity_ids": entity_ids
        }
    
    def get_graph(self) -> KnowledgeGraph:
        """获取知识图谱"""
        return self.graph
    
    def get_insights(self, entity_name: str) -> Dict:
        """
        获取实体相关洞察
        
        Args:
            entity_name: 实体名称
            
        Returns:
            洞察信息
        """
        # 查找实体
        entity_id = None
        for eid in self.graph.entities:
            if entity_name in eid:
                entity_id = eid
                break
        
        if not entity_id:
            return {"error": f"实体 {entity_name} 未找到"}
        
        # 获取关联实体
        related = self.graph.get_related_entities(entity_id)
        
        return {
            "entity_id": entity_id,
            "related_count": len(related),
            "related_entities": [
                {
                    "name": e.name,
                    "type": e.type,
                    "relation": r.relation_type
                }
                for e, r in related[:10]
            ]
        }
