"""
ChromaDB 向量记忆模块
存储用户品牌偏好和历史生成记录，供下次生成时参考
"""
import os
import json
from datetime import datetime
import chromadb
from chromadb.utils import embedding_functions


_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        persist_dir = os.path.join(os.path.dirname(__file__), ".chromadb")
        _client = chromadb.PersistentClient(path=persist_dir)
        ef = embedding_functions.DefaultEmbeddingFunction()
        _collection = _client.get_or_create_collection(
            name="brand_preferences",
            embedding_function=ef,
            metadata={"description": "用户品牌偏好和历史生成记录"},
        )
    return _collection


def save_generation(
    platform: str,
    product_desc: str,
    style_notes: str,
    scripts: list[dict],
) -> str:
    """保存一次生成记录到向量数据库"""
    collection = _get_collection()
    doc_id = f"{platform}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    document = f"平台:{platform} 产品:{product_desc} 风格:{style_notes}"
    metadata = {
        "platform": platform,
        "product_desc": product_desc[:200],
        "style_notes": style_notes[:200],
        "scripts_json": json.dumps(scripts, ensure_ascii=False)[:500],
        "created_at": datetime.now().isoformat(),
    }
    collection.add(documents=[document], metadatas=[metadata], ids=[doc_id])
    return doc_id


def query_similar(product_desc: str, platform: str, n_results: int = 3) -> list[dict]:
    """查询相似的历史记录，用于丰富 Script Agent 的提示词"""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    query_text = f"平台:{platform} 产品:{product_desc}"
    results = collection.query(
        query_texts=[query_text],
        n_results=min(n_results, collection.count()),
        where={"platform": platform} if platform else None,
    )
    memories = []
    if results and results["metadatas"]:
        for meta in results["metadatas"][0]:
            memories.append({
                "platform": meta.get("platform"),
                "product_desc": meta.get("product_desc"),
                "style_notes": meta.get("style_notes"),
                "created_at": meta.get("created_at"),
            })
    return memories


def get_stats() -> dict:
    """返回记忆库统计信息"""
    collection = _get_collection()
    return {"total_records": collection.count()}
