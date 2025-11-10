"""
Knowledge Graph Agent: Knowledge graph construction and reasoning
Constructs and maintains knowledge graphs for enhanced reasoning and insights
"""
import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union, Set
from pathlib import Path
import asyncio
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
import uuid
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score
import xgboost as xgb
import lightgbm as lgb
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, Float, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import re
from collections import Counter
import networkx as nx
from rdflib import Graph, URIRef, Literal, BFO
from rdflib.namespace import RDF, RDFS, OWL, XSD
import spacy
from transformers import pipeline, AutoTokenizer, AutoModel
import torch
from sentence_transformers import SentenceTransformer
import faiss
import pickle

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import KnowledgeNode, KnowledgeRelation, KnowledgeGraph

logger = logging.getLogger(__name__)

Base = declarative_base()


class KnowledgeGraphAgent(BaseAgent):
    """
    Knowledge Graph Agent for constructing and maintaining knowledge graphs
    Uses RDF/SPARQL, graph algorithms, and ML for knowledge representation and reasoning
    """
    
    def __init__(
        self,
        agent_id: str = "knowledge_graph_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Knowledge graph configuration
        self.kg_config = {
            "graph_types": self.config.get("graph_types", [
                "entity_relationship", "concept_hierarchy", "temporal_knowledge",
                "causal_graph", "semantic_network", "property_graph"
            ]),
            "entity_types": self.config.get("entity_types", [
                "person", "organization", "location", "event", "concept", "document",
                "product", "service", "process", "system", "resource"
            ]),
            "relation_types": self.config.get("relation_types", [
                "is_a", "part_of", "related_to", "causes", "affects", "owns",
                "works_for", "located_in", "happened_at", "mentions", "references"
            ]),
            "reasoning_engines": self.config.get("reasoning_engines", [
                "rdf_inference", "graph_algorithms", "ml_reasoning", "rule_based"
            ]),
            "embedding_models": self.config.get("embedding_models", [
                "sentence-transformers", "bert", "roberta", "domain_specific"
            ]),
            "similarity_thresholds": self.config.get("similarity_thresholds", {
                "entity_linking": 0.85,
                "relation_extraction": 0.75,
                "concept_matching": 0.90
            }),
            "graph_limits": self.config.get("graph_limits", {
                "max_nodes": 100000,
                "max_edges": 500000,
                "max_depth": 10,
                "batch_size": 1000
            })
        }
        
        # Knowledge graphs
        self.knowledge_graphs = {}
        self.rdf_graphs = {}
        
        # ML models for knowledge processing
        self.entity_extraction_models = {}
        self.relation_extraction_models = {}
        self.embedding_models = {}
        self.reasoning_models = {}
        
        # Graph processing components
        self.nlp_pipeline = None
        self.vector_index = None
        self.graph_algorithms = {}
        
        # Knowledge state
        self.knowledge_state = {
            "entities": {},
            "relations": {},
            "concepts": {},
            "ontologies": {},
            "inference_rules": {},
            "graph_metrics": {},
            "processing_queue": deque(),
            "update_log": deque(maxlen=10000)
        }
        
        # Background tasks
        self.construction_task = None
        self.reasoning_task = None
        self.maintenance_task = None
        
        logger.info(f"Knowledge Graph Agent initialized: {agent_id}")
    
    async def start(self):
        """
        Start the knowledge graph agent
        """
        await super().start()
        
        # Initialize NLP and ML components
        await self._initialize_nlp_components()
        
        # Initialize knowledge graphs
        await self._initialize_knowledge_graphs()
        
        # Initialize ML models
        await self._initialize_kg_models()
        
        # Start background tasks
        self.construction_task = asyncio.create_task(self._continuous_construction())
        self.reasoning_task = asyncio.create_task(self._continuous_reasoning())
        self.maintenance_task = asyncio.create_task(self._graph_maintenance())
        
        logger.info("Knowledge graph processing started")
    
    async def stop(self):
        """
        Stop the knowledge graph agent
        """
        if self.construction_task:
            self.construction_task.cancel()
            try:
                await self.construction_task
            except asyncio.CancelledError:
                pass
        
        if self.reasoning_task:
            self.reasoning_task.cancel()
            try:
                await self.reasoning_task
            except asyncio.CancelledError:
                pass
        
        if self.maintenance_task:
            self.maintenance_task.cancel()
            try:
                await self.maintenance_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
        logger.info("Knowledge graph agent stopped")
    
    async def _initialize_nlp_components(self):
        """
        Initialize NLP components for text processing
        """
        try:
            # Load spaCy model for entity extraction
            self.nlp_pipeline = spacy.load("en_core_web_lg")
            
            # Add custom entity types
            entity_ruler = self.nlp_pipeline.add_pipe("entity_ruler")
            patterns = [
                {"label": "ORG", "pattern": [{"LOWER": "company"}]},
                {"label": "ORG", "pattern": [{"LOWER": "corporation"}]},
                {"label": "ORG", "pattern": [{"LOWER": "organization"}]},
                {"label": "PRODUCT", "pattern": [{"LOWER": "product"}]},
                {"label": "SERVICE", "pattern": [{"LOWER": "service"}]},
                {"label": "EVENT", "pattern": [{"LOWER": "event"}]},
                {"label": "CONCEPT", "pattern": [{"LOWER": "concept"}]}
            ]
            entity_ruler.add_patterns(patterns)
            
            logger.info("NLP components initialized")
            
        except Exception as e:
            logger.error(f"NLP initialization failed: {e}")
    
    async def _initialize_knowledge_graphs(self):
        """
        Initialize knowledge graphs for different domains
        """
        try:
            # Create RDF graphs for different domains
            domains = ["general", "business", "technical", "compliance", "security"]
            
            for domain in domains:
                # NetworkX graph for algorithms
                self.knowledge_graphs[domain] = nx.DiGraph()
                
                # RDF graph for semantic web
                self.rdf_graphs[domain] = Graph()
                
                # Bind common namespaces
                self.rdf_graphs[domain].bind("owl", OWL)
                self.rdf_graphs[domain].bind("rdf", RDF)
                self.rdf_graphs[domain].bind("rdfs", RDFS)
                
                # Initialize with basic ontology
                await self._initialize_domain_ontology(domain)
            
            # Initialize vector index for similarity search
            self.vector_index = faiss.IndexFlatIP(768)  # Inner product for cosine similarity
            
            logger.info("Knowledge graphs initialized")
            
        except Exception as e:
            logger.error(f"Knowledge graph initialization failed: {e}")
    
    async def _initialize_domain_ontology(self, domain: str):
        """
        Initialize basic ontology for a domain
        """
        try:
            rdf_graph = self.rdf_graphs[domain]
            
            # Define basic classes
            entity_class = URIRef(f"http://predator-analytics.com/kg/{domain}#Entity")
            relation_class = URIRef(f"http://predator-analytics.com/kg/{domain}#Relation")
            
            rdf_graph.add((entity_class, RDF.type, OWL.Class))
            rdf_graph.add((relation_class, RDF.type, OWL.Class))
            
            # Add domain-specific classes
            if domain == "business":
                company_class = URIRef(f"http://predator-analytics.com/kg/{domain}#Company")
                person_class = URIRef(f"http://predator-analytics.com/kg/{domain}#Person")
                product_class = URIRef(f"http://predator-analytics.com/kg/{domain}#Product")
                
                rdf_graph.add((company_class, RDF.type, OWL.Class))
                rdf_graph.add((person_class, RDF.type, OWL.Class))
                rdf_graph.add((product_class, RDF.type, OWL.Class))
                
                rdf_graph.add((company_class, RDFS.subClassOf, entity_class))
                rdf_graph.add((person_class, RDFS.subClassOf, entity_class))
                rdf_graph.add((product_class, RDFS.subClassOf, entity_class))
            
            logger.info(f"Domain ontology initialized for {domain}")
            
        except Exception as e:
            logger.error(f"Domain ontology initialization failed for {domain}: {e}")
    
    async def _initialize_kg_models(self):
        """
        Initialize ML models for knowledge graph processing
        """
        try:
            # Entity extraction models
            self.entity_extraction_models = {
                "spacy_ner": self.nlp_pipeline,
                "bert_ner": pipeline("ner", model="dbmdz/bert-large-cased-finetuned-conll03-english")
            }
            
            # Relation extraction models
            self.relation_extraction_models = {
                "rule_based": {},  # Rule-based patterns
                "ml_classifier": RandomForestClassifier(n_estimators=100, random_state=42)
            }
            
            # Embedding models
            self.embedding_models = {
                "sentence_transformer": SentenceTransformer('all-MiniLM-L6-v2'),
                "bert_embedding": AutoModel.from_pretrained('bert-base-uncased'),
                "bert_tokenizer": AutoTokenizer.from_pretrained('bert-base-uncased')
            }
            
            # Reasoning models
            self.reasoning_models = {
                "path_reasoning": {},  # Graph path algorithms
                "rule_reasoning": {},  # Rule-based inference
                "ml_reasoning": GradientBoostingClassifier(n_estimators=100, random_state=42)
            }
            
            logger.info("Knowledge graph models initialized")
            
        except Exception as e:
            logger.error(f"Knowledge graph model initialization failed: {e}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process knowledge graph requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "construct_graph":
                async for response in self._handle_graph_construction(message):
                    yield response
                    
            elif message_type == "query_graph":
                async for response in self._handle_graph_query(message):
                    yield response
                    
            elif message_type == "reason_over_graph":
                async for response in self._handle_graph_reasoning(message):
                    yield response
                    
            elif message_type == "extract_entities":
                async for response in self._handle_entity_extraction(message):
                    yield response
                    
            elif message_type == "extract_relations":
                async for response in self._handle_relation_extraction(message):
                    yield response
                    
            elif message_type == "find_similar":
                async for response in self._handle_similarity_search(message):
                    yield response
                    
            elif message_type == "update_graph":
                async for response in self._handle_graph_update(message):
                    yield response
                    
            elif message_type == "analyze_graph":
                async for response in self._handle_graph_analysis(message):
                    yield response
                    
            else:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": f"Unknown message type: {message_type}"
                    },
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Knowledge graph processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _continuous_construction(self):
        """
        Continuous knowledge graph construction from new data
        """
        try:
            while True:
                try:
                    # Process queued items
                    while self.knowledge_state["processing_queue"]:
                        item = self.knowledge_state["processing_queue"].popleft()
                        await self._process_knowledge_item(item)
                    
                    # Extract knowledge from recent data
                    await self._extract_knowledge_from_data()
                    
                    # Update graph metrics
                    await self._update_graph_metrics()
                    
                except Exception as e:
                    logger.error(f"Continuous construction error: {e}")
                
                # Wait for next construction cycle
                await asyncio.sleep(300)  # Process every 5 minutes
                
        except asyncio.CancelledError:
            logger.info("Continuous construction cancelled")
            raise
    
    async def _continuous_reasoning(self):
        """
        Continuous reasoning over knowledge graphs
        """
        try:
            while True:
                try:
                    # Perform inference
                    await self._perform_graph_inference()
                    
                    # Discover new relations
                    await self._discover_relations()
                    
                    # Update reasoning results
                    await self._update_reasoning_results()
                    
                except Exception as e:
                    logger.error(f"Continuous reasoning error: {e}")
                
                # Wait for next reasoning cycle
                await asyncio.sleep(600)  # Reason every 10 minutes
                
        except asyncio.CancelledError:
            logger.info("Continuous reasoning cancelled")
            raise
    
    async def _graph_maintenance(self):
        """
        Knowledge graph maintenance and optimization
        """
        try:
            while True:
                try:
                    # Clean up outdated knowledge
                    await self._cleanup_graph()
                    
                    # Optimize graph structure
                    await self._optimize_graph()
                    
                    # Backup graph state
                    await self._backup_graph()
                    
                except Exception as e:
                    logger.error(f"Graph maintenance error: {e}")
                
                # Wait for next maintenance cycle
                await asyncio.sleep(3600)  # Maintain every hour
                
        except asyncio.CancelledError:
            logger.info("Graph maintenance cancelled")
            raise
    
    async def _handle_graph_construction(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle knowledge graph construction request
        """
        try:
            domain = message.content.get("domain", "general")
            data_source = message.content.get("data_source", {})
            construction_type = message.content.get("construction_type", "incremental")
            
            # Construct knowledge graph
            construction_result = await self._construct_knowledge_graph(domain, data_source, construction_type)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "graph_construction_response",
                    "domain": domain,
                    "construction_type": construction_type,
                    "result": construction_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Graph construction handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _construct_knowledge_graph(
        self,
        domain: str,
        data_source: Dict[str, Any],
        construction_type: str
    ) -> Dict[str, Any]:
        """
        Construct knowledge graph from data source
        """
        try:
            construction_result = {
                "domain": domain,
                "construction_type": construction_type,
                "timestamp": datetime.now(),
                "entities_extracted": 0,
                "relations_extracted": 0,
                "nodes_added": 0,
                "edges_added": 0,
                "processing_time": 0
            }
            
            start_time = datetime.now()
            
            # Extract entities and relations from data
            if "text" in data_source:
                entities, relations = await self._extract_from_text(data_source["text"])
                construction_result["entities_extracted"] = len(entities)
                construction_result["relations_extracted"] = len(relations)
            
            elif "structured_data" in data_source:
                entities, relations = await self._extract_from_structured_data(data_source["structured_data"])
                construction_result["entities_extracted"] = len(entities)
                construction_result["relations_extracted"] = len(relations)
            
            # Add to knowledge graph
            if construction_type == "full":
                # Clear existing graph
                self.knowledge_graphs[domain].clear()
                self.rdf_graphs[domain] = Graph()
            
            # Add entities and relations
            nodes_added, edges_added = await self._add_to_graph(domain, entities, relations)
            construction_result["nodes_added"] = nodes_added
            construction_result["edges_added"] = edges_added
            
            construction_result["processing_time"] = (datetime.now() - start_time).total_seconds()
            
            # Log construction
            await self._log_graph_update("construction", construction_result)
            
            return construction_result
            
        except Exception as e:
            logger.error(f"Knowledge graph construction failed: {e}")
            return {"error": str(e), "status": "construction_failed"}
    
    async def _extract_from_text(self, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract entities and relations from text
        """
        try:
            entities = []
            relations = []
            
            # Process text with spaCy
            doc = self.nlp_pipeline(text)
            
            # Extract entities
            for ent in doc.ents:
                entity = {
                    "id": str(uuid.uuid4()),
                    "type": ent.label_,
                    "text": ent.text,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": 0.8  # spaCy confidence
                }
                entities.append(entity)
            
            # Extract relations using rule-based patterns
            relations.extend(await self._extract_relations_rule_based(doc))
            
            # Extract relations using ML model
            relations.extend(await self._extract_relations_ml(doc))
            
            return entities, relations
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return [], []
    
    async def _extract_from_structured_data(self, data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract entities and relations from structured data
        """
        try:
            entities = []
            relations = []
            
            # Process based on data structure
            if isinstance(data, dict):
                entities, relations = await self._process_dict_data(data)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        item_entities, item_relations = await self._process_dict_data(item)
                        entities.extend(item_entities)
                        relations.extend(item_relations)
            
            return entities, relations
            
        except Exception as e:
            logger.error(f"Structured data extraction failed: {e}")
            return [], []
    
    async def _process_dict_data(self, data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Process dictionary data for entities and relations
        """
        try:
            entities = []
            relations = []
            
            # Extract entities from dict keys/values
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 2:
                    # Try to identify entity type
                    entity_type = await self._classify_entity_type(value)
                    if entity_type != "unknown":
                        entity = {
                            "id": str(uuid.uuid4()),
                            "type": entity_type,
                            "text": value,
                            "source_field": key
                        }
                        entities.append(entity)
                
                # Extract relations based on key patterns
                if "company" in key.lower() and "person" in str(value).lower():
                    relations.append({
                        "id": str(uuid.uuid4()),
                        "type": "works_for",
                        "source": value if isinstance(value, str) else str(value),
                        "target": data.get("company", ""),
                        "confidence": 0.7
                    })
            
            return entities, relations
            
        except Exception as e:
            logger.error(f"Dict data processing failed: {e}")
            return [], []
    
    async def _classify_entity_type(self, text: str) -> str:
        """
        Classify entity type from text
        """
        try:
            # Simple rule-based classification
            text_lower = text.lower()
            
            if any(word in text_lower for word in ["ltd", "inc", "corp", "company", "organization"]):
                return "organization"
            elif any(word in text_lower for word in ["mr", "mrs", "dr", "person", "employee"]):
                return "person"
            elif any(word in text_lower for word in ["street", "city", "country", "location"]):
                return "location"
            elif any(word in text_lower for word in ["product", "service", "item"]):
                return "product"
            else:
                return "unknown"
                
        except Exception as e:
            logger.error(f"Entity type classification failed: {e}")
            return "unknown"
    
    async def _extract_relations_rule_based(self, doc) -> List[Dict[str, Any]]:
        """
        Extract relations using rule-based patterns
        """
        try:
            relations = []
            
            # Define relation patterns
            patterns = {
                "works_for": [
                    [{"POS": "PROPN"}, {"LOWER": "works"}, {"LOWER": "for"}, {"POS": "PROPN"}],
                    [{"POS": "PROPN"}, {"LOWER": "at"}, {"POS": "PROPN"}]
                ],
                "located_in": [
                    [{"POS": "PROPN"}, {"LOWER": "in"}, {"POS": "PROPN"}],
                    [{"POS": "PROPN"}, {"LOWER": "located"}, {"LOWER": "in"}, {"POS": "PROPN"}]
                ],
                "part_of": [
                    [{"POS": "PROPN"}, {"LOWER": "part"}, {"LOWER": "of"}, {"POS": "PROPN"}]
                ]
            }
            
            # Match patterns
            from spacy.matcher import Matcher
            matcher = Matcher(self.nlp_pipeline.vocab)
            
            for relation_type, pattern_list in patterns.items():
                for i, pattern in enumerate(pattern_list):
                    matcher.add(f"{relation_type}_{i}", [pattern])
            
            matches = matcher(doc)
            
            for match_id, start, end in matches:
                relation_type = self.nlp_pipeline.vocab.strings[match_id].split("_")[0]
                span = doc[start:end]
                
                # Extract entities from match
                entities_in_match = [ent for ent in span.ents]
                if len(entities_in_match) >= 2:
                    relation = {
                        "id": str(uuid.uuid4()),
                        "type": relation_type,
                        "source": entities_in_match[0].text,
                        "target": entities_in_match[1].text,
                        "confidence": 0.6,
                        "extraction_method": "rule_based"
                    }
                    relations.append(relation)
            
            return relations
            
        except Exception as e:
            logger.error(f"Rule-based relation extraction failed: {e}")
            return []
    
    async def _extract_relations_ml(self, doc) -> List[Dict[str, Any]]:
        """
        Extract relations using ML model
        """
        try:
            relations = []
            
            # Get entity pairs
            entities = list(doc.ents)
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    entity1 = entities[i]
                    entity2 = entities[j]
                    
                    # Create feature vector for relation classification
                    features = await self._create_relation_features(doc, entity1, entity2)
                    
                    # Predict relation type
                    if features:
                        prediction = self.relation_extraction_models["ml_classifier"].predict([features])[0]
                        confidence = max(self.relation_extraction_models["ml_classifier"].predict_proba([features])[0])
                        
                        if confidence > self.kg_config["similarity_thresholds"]["relation_extraction"]:
                            relation = {
                                "id": str(uuid.uuid4()),
                                "type": prediction,
                                "source": entity1.text,
                                "target": entity2.text,
                                "confidence": float(confidence),
                                "extraction_method": "ml"
                            }
                            relations.append(relation)
            
            return relations
            
        except Exception as e:
            logger.error(f"ML relation extraction failed: {e}")
            return []
    
    async def _create_relation_features(self, doc, entity1, entity2) -> Optional[List[float]]:
        """
        Create feature vector for relation classification
        """
        try:
            features = []
            
            # Distance between entities
            features.append(entity2.start - entity1.end)
            
            # Entity types
            features.append(hash(entity1.label_) % 100)
            features.append(hash(entity2.label_) % 100)
            
            # Words between entities
            between_text = doc[entity1.end:entity2.start].text
            features.append(len(between_text.split()))
            
            # Dependency path features
            # (simplified - would need more sophisticated dependency parsing)
            features.extend([0] * 10)  # Placeholder for dependency features
            
            return features
            
        except Exception as e:
            logger.error(f"Relation feature creation failed: {e}")
            return None
    
    async def _add_to_graph(
        self,
        domain: str,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """
        Add entities and relations to knowledge graph
        """
        try:
            nodes_added = 0
            edges_added = 0
            
            nx_graph = self.knowledge_graphs[domain]
            rdf_graph = self.rdf_graphs[domain]
            
            # Add entities as nodes
            for entity in entities:
                node_id = entity["id"]
                if node_id not in nx_graph:
                    nx_graph.add_node(
                        node_id,
                        type=entity["type"],
                        text=entity["text"],
                        **entity
                    )
                    nodes_added += 1
                    
                    # Add to RDF graph
                    entity_uri = URIRef(f"http://predator-analytics.com/kg/{domain}/entity/{node_id}")
                    rdf_graph.add((entity_uri, RDF.type, URIRef(f"http://predator-analytics.com/kg/{domain}#{entity['type']}")))
                    rdf_graph.add((entity_uri, RDFS.label, Literal(entity["text"])))
            
            # Add relations as edges
            for relation in relations:
                source_id = None
                target_id = None
                
                # Find entity IDs for source and target
                for node_id, node_data in nx_graph.nodes(data=True):
                    if node_data.get("text") == relation["source"]:
                        source_id = node_id
                    elif node_data.get("text") == relation["target"]:
                        target_id = node_id
                
                if source_id and target_id and not nx_graph.has_edge(source_id, target_id):
                    nx_graph.add_edge(
                        source_id,
                        target_id,
                        type=relation["type"],
                        confidence=relation["confidence"],
                        **relation
                    )
                    edges_added += 1
                    
                    # Add to RDF graph
                    source_uri = URIRef(f"http://predator-analytics.com/kg/{domain}/entity/{source_id}")
                    target_uri = URIRef(f"http://predator-analytics.com/kg/{domain}/entity/{target_id}")
                    relation_uri = URIRef(f"http://predator-analytics.com/kg/{domain}/relation/{relation['id']}")
                    
                    rdf_graph.add((relation_uri, RDF.type, URIRef(f"http://predator-analytics.com/kg/{domain}#{relation['type']}")))
                    rdf_graph.add((source_uri, relation_uri, target_uri))
            
            return nodes_added, edges_added
            
        except Exception as e:
            logger.error(f"Adding to graph failed: {e}")
            return 0, 0
    
    async def _handle_graph_query(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle knowledge graph query request
        """
        try:
            domain = message.content.get("domain", "general")
            query_type = message.content.get("query_type", "sparql")
            query = message.content.get("query", "")
            
            # Execute graph query
            query_result = await self._execute_graph_query(domain, query_type, query)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "graph_query_response",
                    "domain": domain,
                    "query_type": query_type,
                    "result": query_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Graph query handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _execute_graph_query(
        self,
        domain: str,
        query_type: str,
        query: str
    ) -> Dict[str, Any]:
        """
        Execute query on knowledge graph
        """
        try:
            if query_type == "sparql":
                return await self._execute_sparql_query(domain, query)
            elif query_type == "graph_algorithm":
                return await self._execute_graph_algorithm(domain, query)
            elif query_type == "similarity":
                return await self._execute_similarity_query(domain, query)
            else:
                return {"error": f"Unsupported query type: {query_type}"}
                
        except Exception as e:
            logger.error(f"Graph query execution failed: {e}")
            return {"error": str(e)}
    
    async def _execute_sparql_query(self, domain: str, query: str) -> Dict[str, Any]:
        """
        Execute SPARQL query on RDF graph
        """
        try:
            rdf_graph = self.rdf_graphs[domain]
            
            results = rdf_graph.query(query)
            
            # Convert results to list of dicts
            result_list = []
            for row in results:
                result_dict = {}
                for i, var in enumerate(results.vars):
                    result_dict[str(var)] = str(row[i])
                result_list.append(result_dict)
            
            return {
                "query_type": "sparql",
                "results": result_list,
                "count": len(result_list)
            }
            
        except Exception as e:
            logger.error(f"SPARQL query failed: {e}")
            return {"error": str(e)}
    
    async def _execute_graph_algorithm(self, domain: str, algorithm_spec: str) -> Dict[str, Any]:
        """
        Execute graph algorithm query
        """
        try:
            nx_graph = self.knowledge_graphs[domain]
            
            # Parse algorithm specification
            algorithm_config = json.loads(algorithm_spec) if isinstance(algorithm_spec, str) else algorithm_spec
            
            algorithm_type = algorithm_config.get("algorithm", "shortest_path")
            params = algorithm_config.get("params", {})
            
            if algorithm_type == "shortest_path":
                source = params.get("source")
                target = params.get("target")
                path = nx.shortest_path(nx_graph, source=source, target=target)
                return {"algorithm": "shortest_path", "path": path}
                
            elif algorithm_type == "centrality":
                centrality_type = params.get("type", "degree")
                if centrality_type == "degree":
                    centrality = nx.degree_centrality(nx_graph)
                elif centrality_type == "betweenness":
                    centrality = nx.betweenness_centrality(nx_graph)
                return {"algorithm": "centrality", "type": centrality_type, "scores": centrality}
                
            elif algorithm_type == "community_detection":
                # Simple community detection using label propagation
                communities = nx.community.label_propagation_communities(nx_graph)
                return {"algorithm": "community_detection", "communities": [list(c) for c in communities]}
            
            else:
                return {"error": f"Unsupported algorithm: {algorithm_type}"}
                
        except Exception as e:
            logger.error(f"Graph algorithm execution failed: {e}")
            return {"error": str(e)}
    
    async def _execute_similarity_query(self, domain: str, query_text: str) -> Dict[str, Any]:
        """
        Execute similarity search query
        """
        try:
            # Generate embedding for query
            query_embedding = self.embedding_models["sentence_transformer"].encode([query_text])[0]
            
            # Search for similar entities
            similarities = []
            
            nx_graph = self.knowledge_graphs[domain]
            for node_id, node_data in nx_graph.nodes(data=True):
                if "embedding" in node_data:
                    node_embedding = np.array(node_data["embedding"])
                    similarity = np.dot(query_embedding, node_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(node_embedding)
                    )
                    similarities.append({
                        "node_id": node_id,
                        "text": node_data.get("text", ""),
                        "similarity": float(similarity)
                    })
            
            # Sort by similarity
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            
            return {
                "query_type": "similarity",
                "query_text": query_text,
                "results": similarities[:10]  # Top 10 results
            }
            
        except Exception as e:
            logger.error(f"Similarity query failed: {e}")
            return {"error": str(e)}
    
    async def _handle_graph_reasoning(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle graph reasoning request
        """
        try:
            domain = message.content.get("domain", "general")
            reasoning_type = message.content.get("reasoning_type", "inference")
            query = message.content.get("query", {})
            
            # Perform graph reasoning
            reasoning_result = await self._perform_graph_reasoning(domain, reasoning_type, query)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "graph_reasoning_response",
                    "domain": domain,
                    "reasoning_type": reasoning_type,
                    "result": reasoning_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Graph reasoning handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _perform_graph_reasoning(
        self,
        domain: str,
        reasoning_type: str,
        query: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform reasoning over knowledge graph
        """
        try:
            if reasoning_type == "inference":
                return await self._perform_inference_reasoning(domain, query)
            elif reasoning_type == "path_reasoning":
                return await self._perform_path_reasoning(domain, query)
            elif reasoning_type == "rule_reasoning":
                return await self._perform_rule_reasoning(domain, query)
            else:
                return {"error": f"Unsupported reasoning type: {reasoning_type}"}
                
        except Exception as e:
            logger.error(f"Graph reasoning failed: {e}")
            return {"error": str(e)}
    
    async def _perform_inference_reasoning(self, domain: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform inference reasoning
        """
        try:
            rdf_graph = self.rdf_graphs[domain]
            
            # Perform RDFS inference
            from rdflib.plugins.sparql import prepareQuery
            
            inference_query = query.get("query", """
            SELECT ?subject ?predicate ?object
            WHERE {
                ?subject ?predicate ?object .
            }
            """)
            
            results = rdf_graph.query(inference_query)
            
            inferences = []
            for row in results:
                inferences.append({
                    "subject": str(row[0]),
                    "predicate": str(row[1]),
                    "object": str(row[2])
                })
            
            return {
                "reasoning_type": "inference",
                "inferences": inferences,
                "count": len(inferences)
            }
            
        except Exception as e:
            logger.error(f"Inference reasoning failed: {e}")
            return {"error": str(e)}
    
    async def _perform_path_reasoning(self, domain: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform path-based reasoning
        """
        try:
            nx_graph = self.knowledge_graphs[domain]
            
            start_node = query.get("start_node")
            end_node = query.get("end_node")
            max_length = query.get("max_length", 3)
            
            # Find all paths between nodes
            paths = list(nx.all_simple_paths(nx_graph, start_node, end_node, cutoff=max_length))
            
            # Analyze paths for reasoning
            reasoning_results = []
            for path in paths:
                path_analysis = await self._analyze_path(path, nx_graph)
                reasoning_results.append({
                    "path": path,
                    "analysis": path_analysis
                })
            
            return {
                "reasoning_type": "path_reasoning",
                "start_node": start_node,
                "end_node": end_node,
                "paths_found": len(paths),
                "results": reasoning_results
            }
            
        except Exception as e:
            logger.error(f"Path reasoning failed: {e}")
            return {"error": str(e)}
    
    async def _analyze_path(self, path: List[str], graph: nx.Graph) -> Dict[str, Any]:
        """
        Analyze a path for reasoning insights
        """
        try:
            analysis = {
                "length": len(path) - 1,
                "relations": [],
                "confidence": 1.0,
                "insights": []
            }
            
            # Analyze each edge in path
            for i in range(len(path) - 1):
                source = path[i]
                target = path[i + 1]
                
                edge_data = graph.get_edge_data(source, target)
                if edge_data:
                    relation_type = edge_data.get("type", "unknown")
                    confidence = edge_data.get("confidence", 1.0)
                    
                    analysis["relations"].append({
                        "source": source,
                        "target": target,
                        "type": relation_type,
                        "confidence": confidence
                    })
                    
                    analysis["confidence"] *= confidence
            
            # Generate insights based on path
            if len(path) >= 3:
                analysis["insights"].append(f"Found {len(path)-2} intermediate connections")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Path analysis failed: {e}")
            return {"error": str(e)}
    
    async def _perform_rule_reasoning(self, domain: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform rule-based reasoning
        """
        try:
            # Apply predefined reasoning rules
            rules = self.knowledge_state["inference_rules"].get(domain, [])
            
            reasoning_results = []
            for rule in rules:
                rule_result = await self._apply_reasoning_rule(domain, rule, query)
                if rule_result:
                    reasoning_results.append(rule_result)
            
            return {
                "reasoning_type": "rule_reasoning",
                "rules_applied": len(rules),
                "results": reasoning_results
            }
            
        except Exception as e:
            logger.error(f"Rule reasoning failed: {e}")
            return {"error": str(e)}
    
    async def _apply_reasoning_rule(self, domain: str, rule: Dict[str, Any], query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Apply a specific reasoning rule
        """
        try:
            rule_type = rule.get("type")
            
            if rule_type == "transitive":
                # If A related_to B and B related_to C, then A related_to C
                return await self._apply_transitive_rule(domain, rule)
            elif rule_type == "inheritance":
                # Subclass inheritance rules
                return await self._apply_inheritance_rule(domain, rule)
            
            return None
            
        except Exception as e:
            logger.error(f"Rule application failed: {e}")
            return None
    
    async def _apply_transitive_rule(self, domain: str, rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply transitive reasoning rule
        """
        try:
            nx_graph = self.knowledge_graphs[domain]
            relation_type = rule.get("relation_type", "related_to")
            
            # Find transitive relations
            transitive_edges = []
            
            for node in nx_graph.nodes():
                successors_1 = set(nx_graph.successors(node))
                for succ1 in successors_1:
                    successors_2 = set(nx_graph.successors(succ1))
                    for succ2 in successors_2:
                        if succ2 != node and not nx_graph.has_edge(node, succ2):
                            transitive_edges.append((node, succ2, succ1))
            
            return {
                "rule_type": "transitive",
                "relation_type": relation_type,
                "new_relations": len(transitive_edges),
                "examples": transitive_edges[:5]  # First 5 examples
            }
            
        except Exception as e:
            logger.error(f"Transitive rule application failed: {e}")
            return {"error": str(e)}
    
    async def _apply_inheritance_rule(self, domain: str, rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply inheritance reasoning rule
        """
        try:
            rdf_graph = self.rdf_graphs[domain]
            
            # Query for subclass relationships
            query = """
            SELECT ?subclass ?superclass
            WHERE {
                ?subclass rdfs:subClassOf ?superclass .
            }
            """
            
            results = rdf_graph.query(query)
            
            inheritance_relations = []
            for row in results:
                inheritance_relations.append({
                    "subclass": str(row[0]),
                    "superclass": str(row[1])
                })
            
            return {
                "rule_type": "inheritance",
                "inheritance_relations": inheritance_relations,
                "count": len(inheritance_relations)
            }
            
        except Exception as e:
            logger.error(f"Inheritance rule application failed: {e}")
            return {"error": str(e)}
    
    async def _handle_entity_extraction(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle entity extraction request
        """
        try:
            text = message.content.get("text", "")
            extraction_method = message.content.get("method", "combined")
            
            # Extract entities
            entities = await self._extract_entities(text, extraction_method)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "entity_extraction_response",
                    "text_length": len(text),
                    "method": extraction_method,
                    "entities": entities
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Entity extraction handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _extract_entities(self, text: str, method: str) -> List[Dict[str, Any]]:
        """
        Extract entities from text
        """
        try:
            entities = []
            
            if method == "spacy" or method == "combined":
                # spaCy NER
                doc = self.nlp_pipeline(text)
                for ent in doc.ents:
                    entities.append({
                        "text": ent.text,
                        "type": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "method": "spacy",
                        "confidence": 0.8
                    })
            
            if method == "bert" or method == "combined":
                # BERT NER
                bert_entities = self.entity_extraction_models["bert_ner"](text)
                
                for entity in bert_entities:
                    if entity["score"] > 0.5:  # Confidence threshold
                        entities.append({
                            "text": entity["word"],
                            "type": entity["entity_group"],
                            "start": entity["start"],
                            "end": entity["end"],
                            "method": "bert",
                            "confidence": float(entity["score"])
                        })
            
            # Remove duplicates and merge overlapping entities
            entities = await self._merge_entities(entities)
            
            return entities
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
    
    async def _merge_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge overlapping and duplicate entities
        """
        try:
            merged = []
            
            # Sort by start position
            entities.sort(key=lambda x: x["start"])
            
            for entity in entities:
                # Check for overlap with last merged entity
                if merged and self._entities_overlap(merged[-1], entity):
                    # Merge entities
                    merged[-1] = await self._merge_entity_pair(merged[-1], entity)
                else:
                    merged.append(entity)
            
            return merged
            
        except Exception as e:
            logger.error(f"Entity merging failed: {e}")
            return entities
    
    def _entities_overlap(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> bool:
        """Check if two entities overlap"""
        return not (entity1["end"] <= entity2["start"] or entity2["end"] <= entity1["start"])
    
    async def _merge_entity_pair(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two overlapping entities
        """
        try:
            # Choose the entity with higher confidence
            if entity1["confidence"] >= entity2["confidence"]:
                primary, secondary = entity1, entity2
            else:
                primary, secondary = entity2, entity1
            
            # Update boundaries
            merged = primary.copy()
            merged["start"] = min(primary["start"], secondary["start"])
            merged["end"] = max(primary["end"], secondary["end"])
            merged["text"] = primary["text"]  # Keep primary text
            
            return merged
            
        except Exception as e:
            logger.error(f"Entity pair merging failed: {e}")
            return entity1
    
    async def _handle_relation_extraction(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle relation extraction request
        """
        try:
            text = message.content.get("text", "")
            entities = message.content.get("entities", [])
            extraction_method = message.content.get("method", "combined")
            
            # Extract relations
            relations = await self._extract_relations(text, entities, extraction_method)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "relation_extraction_response",
                    "text_length": len(text),
                    "entities_count": len(entities),
                    "method": extraction_method,
                    "relations": relations
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Relation extraction handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _extract_relations(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        method: str
    ) -> List[Dict[str, Any]]:
        """
        Extract relations between entities
        """
        try:
            relations = []
            
            # Process text with spaCy
            doc = self.nlp_pipeline(text)
            
            if method == "rule_based" or method == "combined":
                relations.extend(await self._extract_relations_rule_based(doc))
            
            if method == "ml" or method == "combined":
                relations.extend(await self._extract_relations_ml(doc))
            
            # Filter relations to only include provided entities
            entity_texts = {ent["text"] for ent in entities}
            filtered_relations = [
                rel for rel in relations
                if rel["source"] in entity_texts and rel["target"] in entity_texts
            ]
            
            return filtered_relations
            
        except Exception as e:
            logger.error(f"Relation extraction failed: {e}")
            return []
    
    async def _handle_similarity_search(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle similarity search request
        """
        try:
            query_text = message.content.get("query_text", "")
            domain = message.content.get("domain", "general")
            top_k = message.content.get("top_k", 10)
            
            # Perform similarity search
            similar_items = await self._find_similar_entities(query_text, domain, top_k)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "similarity_search_response",
                    "query_text": query_text,
                    "domain": domain,
                    "top_k": top_k,
                    "results": similar_items
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Similarity search handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _find_similar_entities(
        self,
        query_text: str,
        domain: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Find entities similar to query text
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_models["sentence_transformer"].encode([query_text])[0]
            
            # Search in vector index
            similarities = []
            
            nx_graph = self.knowledge_graphs[domain]
            for node_id, node_data in nx_graph.nodes(data=True):
                if "embedding" in node_data:
                    node_embedding = np.array(node_data["embedding"])
                    
                    # Cosine similarity
                    similarity = np.dot(query_embedding, node_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(node_embedding)
                    )
                    
                    similarities.append({
                        "node_id": node_id,
                        "text": node_data.get("text", ""),
                        "type": node_data.get("type", ""),
                        "similarity": float(similarity)
                    })
            
            # Sort by similarity and return top-k
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
    
    async def _handle_graph_update(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle graph update request
        """
        try:
            domain = message.content.get("domain", "general")
            update_type = message.content.get("update_type", "add")
            update_data = message.content.get("update_data", {})
            
            # Update knowledge graph
            update_result = await self._update_knowledge_graph(domain, update_type, update_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "graph_update_response",
                    "domain": domain,
                    "update_type": update_type,
                    "result": update_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Graph update handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _update_knowledge_graph(
        self,
        domain: str,
        update_type: str,
        update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update knowledge graph
        """
        try:
            nx_graph = self.knowledge_graphs[domain]
            rdf_graph = self.rdf_graphs[domain]
            
            update_result = {
                "domain": domain,
                "update_type": update_type,
                "timestamp": datetime.now(),
                "changes": 0
            }
            
            if update_type == "add_entity":
                entity = update_data
                node_id = entity.get("id", str(uuid.uuid4()))
                
                if node_id not in nx_graph:
                    nx_graph.add_node(node_id, **entity)
                    
                    # Add embedding
                    if "text" in entity:
                        embedding = self.embedding_models["sentence_transformer"].encode([entity["text"]])[0]
                        nx_graph.nodes[node_id]["embedding"] = embedding.tolist()
                    
                    update_result["changes"] = 1
            
            elif update_type == "add_relation":
                relation = update_data
                source_id = relation.get("source_id")
                target_id = relation.get("target_id")
                
                if source_id in nx_graph and target_id in nx_graph:
                    if not nx_graph.has_edge(source_id, target_id):
                        nx_graph.add_edge(source_id, target_id, **relation)
                        update_result["changes"] = 1
            
            elif update_type == "remove_entity":
                entity_id = update_data.get("entity_id")
                if entity_id in nx_graph:
                    nx_graph.remove_node(entity_id)
                    update_result["changes"] = 1
            
            elif update_type == "remove_relation":
                source_id = update_data.get("source_id")
                target_id = update_data.get("target_id")
                
                if nx_graph.has_edge(source_id, target_id):
                    nx_graph.remove_edge(source_id, target_id)
                    update_result["changes"] = 1
            
            # Log update
            await self._log_graph_update("update", update_result)
            
            return update_result
            
        except Exception as e:
            logger.error(f"Knowledge graph update failed: {e}")
            return {"error": str(e)}
    
    async def _handle_graph_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle graph analysis request
        """
        try:
            domain = message.content.get("domain", "general")
            analysis_type = message.content.get("analysis_type", "metrics")
            
            # Analyze knowledge graph
            analysis_result = await self._analyze_knowledge_graph(domain, analysis_type)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "graph_analysis_response",
                    "domain": domain,
                    "analysis_type": analysis_type,
                    "result": analysis_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Graph analysis handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _analyze_knowledge_graph(
        self,
        domain: str,
        analysis_type: str
    ) -> Dict[str, Any]:
        """
        Analyze knowledge graph
        """
        try:
            nx_graph = self.knowledge_graphs[domain]
            
            if analysis_type == "metrics":
                return await self._compute_graph_metrics(nx_graph)
            elif analysis_type == "communities":
                return await self._detect_communities(nx_graph)
            elif analysis_type == "centrality":
                return await self._compute_centrality(nx_graph)
            elif analysis_type == "paths":
                return await self._analyze_paths(nx_graph)
            else:
                return {"error": f"Unsupported analysis type: {analysis_type}"}
                
        except Exception as e:
            logger.error(f"Knowledge graph analysis failed: {e}")
            return {"error": str(e)}
    
    async def _compute_graph_metrics(self, graph: nx.Graph) -> Dict[str, Any]:
        """
        Compute graph metrics
        """
        try:
            metrics = {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "density": nx.density(graph),
                "average_clustering": nx.average_clustering(graph),
                "connected_components": nx.number_connected_components(graph),
                "diameter": nx.diameter(graph) if nx.is_connected(graph) else None,
                "average_shortest_path": nx.average_shortest_path_length(graph) if nx.is_connected(graph) else None
            }
            
            # Entity type distribution
            entity_types = {}
            for node_id, node_data in graph.nodes(data=True):
                entity_type = node_data.get("type", "unknown")
                entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
            
            metrics["entity_type_distribution"] = entity_types
            
            # Relation type distribution
            relation_types = {}
            for source, target, edge_data in graph.edges(data=True):
                relation_type = edge_data.get("type", "unknown")
                relation_types[relation_type] = relation_types.get(relation_type, 0) + 1
            
            metrics["relation_type_distribution"] = relation_types
            
            return metrics
            
        except Exception as e:
            logger.error(f"Graph metrics computation failed: {e}")
            return {"error": str(e)}
    
    async def _detect_communities(self, graph: nx.Graph) -> Dict[str, Any]:
        """
        Detect communities in graph
        """
        try:
            # Use label propagation for community detection
            communities = list(nx.community.label_propagation_communities(graph))
            
            community_analysis = {
                "num_communities": len(communities),
                "communities": [],
                "modularity": nx.community.modularity(graph, communities)
            }
            
            for i, community in enumerate(communities):
                community_info = {
                    "id": i,
                    "size": len(community),
                    "members": list(community),
                    "entity_types": {}
                }
                
                # Analyze entity types in community
                for node_id in community:
                    node_data = graph.nodes[node_id]
                    entity_type = node_data.get("type", "unknown")
                    community_info["entity_types"][entity_type] = community_info["entity_types"].get(entity_type, 0) + 1
                
                community_analysis["communities"].append(community_info)
            
            return community_analysis
            
        except Exception as e:
            logger.error(f"Community detection failed: {e}")
            return {"error": str(e)}
    
    async def _compute_centrality(self, graph: nx.Graph) -> Dict[str, Any]:
        """
        Compute centrality measures
        """
        try:
            centrality_measures = {
                "degree_centrality": dict(nx.degree_centrality(graph)),
                "betweenness_centrality": dict(nx.betweenness_centrality(graph)),
                "closeness_centrality": dict(nx.closeness_centrality(graph)),
                "eigenvector_centrality": dict(nx.eigenvector_centrality(graph))
            }
            
            # Find top nodes for each centrality measure
            top_nodes = {}
            for measure_name, centrality_dict in centrality_measures.items():
                sorted_nodes = sorted(centrality_dict.items(), key=lambda x: x[1], reverse=True)
                top_nodes[measure_name] = sorted_nodes[:10]  # Top 10
            
            return {
                "centrality_measures": centrality_measures,
                "top_nodes": top_nodes
            }
            
        except Exception as e:
            logger.error(f"Centrality computation failed: {e}")
            return {"error": str(e)}
    
    async def _analyze_paths(self, graph: nx.Graph) -> Dict[str, Any]:
        """
        Analyze paths in graph
        """
        try:
            path_analysis = {
                "average_path_length": nx.average_shortest_path_length(graph) if nx.is_connected(graph) else None,
                "path_length_distribution": {},
                "most_connected_nodes": []
            }
            
            if nx.is_connected(graph):
                # Compute all pairs shortest paths
                lengths = dict(nx.all_pairs_shortest_path_length(graph))
                
                # Path length distribution
                path_lengths = {}
                for source_lengths in lengths.values():
                    for target, length in source_lengths.items():
                        path_lengths[length] = path_lengths.get(length, 0) + 1
                
                path_analysis["path_length_distribution"] = path_lengths
            
            # Most connected nodes (by degree)
            degrees = dict(graph.degree())
            sorted_degrees = sorted(degrees.items(), key=lambda x: x[1], reverse=True)
            path_analysis["most_connected_nodes"] = sorted_degrees[:10]
            
            return path_analysis
            
        except Exception as e:
            logger.error(f"Path analysis failed: {e}")
            return {"error": str(e)}
    
    async def _process_knowledge_item(self, item: Dict[str, Any]):
        """
        Process a knowledge item for graph construction
        """
        try:
            item_type = item.get("type", "text")
            
            if item_type == "text":
                await self._process_text_item(item)
            elif item_type == "structured":
                await self._process_structured_item(item)
            elif item_type == "relation":
                await self._process_relation_item(item)
                
        except Exception as e:
            logger.error(f"Knowledge item processing failed: {e}")
    
    async def _process_text_item(self, item: Dict[str, Any]):
        """
        Process text knowledge item
        """
        try:
            text = item.get("content", "")
            domain = item.get("domain", "general")
            
            # Extract entities and relations
            entities, relations = await self._extract_from_text(text)
            
            # Add to graph
            await self._add_to_graph(domain, entities, relations)
            
        except Exception as e:
            logger.error(f"Text item processing failed: {e}")
    
    async def _process_structured_item(self, item: Dict[str, Any]):
        """
        Process structured knowledge item
        """
        try:
            data = item.get("content", {})
            domain = item.get("domain", "general")
            
            # Extract entities and relations
            entities, relations = await self._extract_from_structured_data(data)
            
            # Add to graph
            await self._add_to_graph(domain, entities, relations)
            
        except Exception as e:
            logger.error(f"Structured item processing failed: {e}")
    
    async def _process_relation_item(self, item: Dict[str, Any]):
        """
        Process relation knowledge item
        """
        try:
            relation = item.get("content", {})
            domain = item.get("domain", "general")
            
            # Add relation to graph
            nx_graph = self.knowledge_graphs[domain]
            
            source_id = relation.get("source_id")
            target_id = relation.get("target_id")
            
            if source_id and target_id and source_id in nx_graph and target_id in nx_graph:
                if not nx_graph.has_edge(source_id, target_id):
                    nx_graph.add_edge(source_id, target_id, **relation)
            
        except Exception as e:
            logger.error(f"Relation item processing failed: {e}")
    
    async def _extract_knowledge_from_data(self):
        """
        Extract knowledge from recent data sources
        """
        try:
            # Query recent data from database
            async with get_db_session() as session:
                # Example: Extract from recent documents or messages
                # This would integrate with actual data sources
                pass
                
        except Exception as e:
            logger.error(f"Knowledge extraction from data failed: {e}")
    
    async def _perform_graph_inference(self):
        """
        Perform inference on knowledge graphs
        """
        try:
            for domain in self.knowledge_graphs.keys():
                # Apply inference rules
                await self._apply_inference_rules(domain)
                
                # Discover implicit relations
                await self._discover_implicit_relations(domain)
                
        except Exception as e:
            logger.error(f"Graph inference failed: {e}")
    
    async def _apply_inference_rules(self, domain: str):
        """
        Apply inference rules to domain graph
        """
        try:
            rules = self.knowledge_state["inference_rules"].get(domain, [])
            
            for rule in rules:
                await self._apply_reasoning_rule(domain, rule, {})
                
        except Exception as e:
            logger.error(f"Inference rule application failed for {domain}: {e}")
    
    async def _discover_implicit_relations(self, domain: str):
        """
        Discover implicit relations through graph analysis
        """
        try:
            nx_graph = self.knowledge_graphs[domain]
            
            # Find co-occurrence patterns
            # This is a simplified implementation
            entity_pairs = {}
            
            # Count co-occurrences in paths
            for node in nx_graph.nodes():
                neighbors = list(nx_graph.neighbors(node))
                for i in range(len(neighbors)):
                    for j in range(i + 1, len(neighbors)):
                        pair = tuple(sorted([neighbors[i], neighbors[j]]))
                        entity_pairs[pair] = entity_pairs.get(pair, 0) + 1
            
            # Add implicit relations for highly co-occurring entities
            threshold = 3  # Minimum co-occurrence count
            for (entity1, entity2), count in entity_pairs.items():
                if count >= threshold and not nx_graph.has_edge(entity1, entity2):
                    nx_graph.add_edge(entity1, entity2, 
                                    type="implicit_related", 
                                    confidence=0.5,
                                    discovery_method="co_occurrence")
                    
        except Exception as e:
            logger.error(f"Implicit relation discovery failed for {domain}: {e}")
    
    async def _discover_relations(self):
        """
        Discover new relations through various methods
        """
        try:
            for domain in self.knowledge_graphs.keys():
                await self._discover_implicit_relations(domain)
                
        except Exception as e:
            logger.error(f"Relation discovery failed: {e}")
    
    async def _update_reasoning_results(self):
        """
        Update reasoning results and insights
        """
        try:
            # Store reasoning results for queries
            pass
            
        except Exception as e:
            logger.error(f"Reasoning results update failed: {e}")
    
    async def _update_graph_metrics(self):
        """
        Update graph metrics
        """
        try:
            for domain, graph in self.knowledge_graphs.items():
                metrics = await self._compute_graph_metrics(graph)
                self.knowledge_state["graph_metrics"][domain] = metrics
                
        except Exception as e:
            logger.error(f"Graph metrics update failed: {e}")
    
    async def _cleanup_graph(self):
        """
        Clean up outdated knowledge from graphs
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=365)  # 1 year retention
            
            for domain, graph in self.knowledge_graphs.items():
                nodes_to_remove = []
                
                for node_id, node_data in graph.nodes(data=True):
                    created_date = node_data.get("created_at")
                    if created_date and isinstance(created_date, datetime) and created_date < cutoff_date:
                        nodes_to_remove.append(node_id)
                
                for node_id in nodes_to_remove:
                    graph.remove_node(node_id)
                    
                if nodes_to_remove:
                    logger.info(f"Cleaned up {len(nodes_to_remove)} outdated nodes from {domain} graph")
                    
        except Exception as e:
            logger.error(f"Graph cleanup failed: {e}")
    
    async def _optimize_graph(self):
        """
        Optimize graph structure and performance
        """
        try:
            for domain, graph in self.knowledge_graphs.items():
                # Remove isolated nodes
                isolated_nodes = list(nx.isolates(graph))
                if isolated_nodes:
                    graph.remove_nodes_from(isolated_nodes)
                    logger.info(f"Removed {len(isolated_nodes)} isolated nodes from {domain} graph")
                
                # Optimize embeddings (rebuild FAISS index if needed)
                if len(graph.nodes()) > 1000:  # Rebuild for large graphs
                    await self._rebuild_vector_index(domain)
                    
        except Exception as e:
            logger.error(f"Graph optimization failed: {e}")
    
    async def _rebuild_vector_index(self, domain: str):
        """
        Rebuild vector index for domain
        """
        try:
            graph = self.knowledge_graphs[domain]
            
            # Collect all embeddings
            embeddings = []
            ids = []
            
            for node_id, node_data in graph.nodes(data=True):
                if "embedding" in node_data:
                    embeddings.append(node_data["embedding"])
                    ids.append(node_id)
            
            if embeddings:
                # Rebuild FAISS index
                embeddings_array = np.array(embeddings, dtype=np.float32)
                dimension = embeddings_array.shape[1]
                
                new_index = faiss.IndexFlatIP(dimension)
                new_index.add(embeddings_array)
                
                # Update index (this would need to be stored persistently)
                logger.info(f"Rebuilt vector index for {domain} with {len(embeddings)} vectors")
                
        except Exception as e:
            logger.error(f"Vector index rebuild failed for {domain}: {e}")
    
    async def _backup_graph(self):
        """
        Backup graph state
        """
        try:
            for domain in self.knowledge_graphs.keys():
                # Serialize and backup graphs
                # This would save to persistent storage
                logger.info(f"Backed up {domain} knowledge graph")
                
        except Exception as e:
            logger.error(f"Graph backup failed: {e}")
    
    async def _log_graph_update(self, update_type: str, update_data: Dict[str, Any]):
        """
        Log graph update
        """
        try:
            log_entry = {
                "update_type": update_type,
                "update_data": update_data,
                "timestamp": datetime.now()
            }
            
            self.knowledge_state["update_log"].append(log_entry)
            
        except Exception as e:
            logger.error(f"Graph update logging failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":
    async def test_knowledge_graph_agent():
        # Initialize knowledge graph agent
        agent = KnowledgeGraphAgent()
        await agent.start()
        
        # Test graph construction
        construct_message = AgentMessage(
            id="test_construct",
            from_agent="test",
            to_agent="knowledge_graph_agent",
            content={
                "type": "construct_graph",
                "domain": "business",
                "data_source": {
                    "text": "John Smith works at Acme Corporation in New York. Acme Corporation produces software products."
                },
                "construction_type": "incremental"
            },
            timestamp=datetime.now()
        )
        
        print("Testing knowledge graph agent...")
        async for response in agent.process_message(construct_message):
            print(f"Graph construction response: {response.content.get('type')}")
        
        # Test graph query
        query_message = AgentMessage(
            id="test_query",
            from_agent="test",
            to_agent="knowledge_graph_agent",
            content={
                "type": "query_graph",
                "domain": "business",
                "query_type": "graph_algorithm",
                "query": {
                    "algorithm": "centrality",
                    "params": {"type": "degree"}
                }
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(query_message):
            print(f"Graph query response: {response.content.get('type')}")
        
        # Test entity extraction
        entity_message = AgentMessage(
            id="test_entities",
            from_agent="test",
            to_agent="knowledge_graph_agent",
            content={
                "type": "extract_entities",
                "text": "Apple Inc. is a technology company founded by Steve Jobs in Cupertino, California.",
                "method": "combined"
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(entity_message):
            print(f"Entity extraction response: {response.content.get('type')}")
            entities = response.content.get("entities", [])
            print(f"Extracted {len(entities)} entities")
        
        # Test similarity search
        similarity_message = AgentMessage(
            id="test_similarity",
            from_agent="test",
            to_agent="knowledge_graph_agent",
            content={
                "type": "find_similar",
                "query_text": "technology company",
                "domain": "business",
                "top_k": 5
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(similarity_message):
            print(f"Similarity search response: {response.content.get('type')}")
        
        # Stop agent
        await agent.stop()
        print("Knowledge graph agent test completed")
    
    # Run test
    asyncio.run(test_knowledge_graph_agent())
