#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Local FAISS storage backed by remotely generated text embeddings."""

import hashlib
import json
import logging
import os
from pathlib import Path
from threading import RLock

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_DIR = PROJECT_ROOT / "data" / "faiss"
load_dotenv(PROJECT_ROOT / ".env")


def article_key(article):
    """Return the same stable identifier across MariaDB loads and index builds."""
    doi = str(article.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    url = str(article.get("url") or "").strip()
    if url:
        return f"url:{url}"
    title = str(article.get("titleCn") or article.get("title") or "").strip().lower()
    return f"title:{title}" if title else ""


def article_embedding_text(article):
    """Build a compact multilingual document for semantic retrieval."""
    tags = article.get("tags") or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    fields = [
        ("中文标题", article.get("titleCn")),
        ("英文标题", article.get("title")),
        ("学科", article.get("Subject")),
        ("标签", "、".join(str(tag) for tag in tags)),
        ("中文解读", article.get("interpretationCn")),
        ("摘要", article.get("abstract")),
        ("期刊", article.get("journal")),
    ]
    return "\n".join(
        f"{label}: {str(value).strip()}"
        for label, value in fields
        if value and str(value).strip()
    )[:24000]


class LocalFaissStore:
    """Persist vectors in FAISS while MariaDB remains the source of paper data."""

    def __init__(self, index_dir=None):
        self.index_dir = Path(
            index_dir or os.environ.get("FAISS_INDEX_DIR") or DEFAULT_INDEX_DIR
        ).expanduser().resolve()
        self.index_path = self.index_dir / "papers.faiss"
        self.metadata_path = self.index_dir / "papers.json"
        self.model = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
        self.api_base = os.environ.get(
            "SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1"
        )
        self.batch_size = max(1, int(os.environ.get("EMBEDDING_BATCH_SIZE", "16")))
        self._index = None
        self._metadata = None
        self._lock = RLock()

    @property
    def available(self):
        return bool(os.environ.get("SILICONFLOW_API_KEY"))

    def _imports(self):
        try:
            import faiss
            import numpy as np
        except ImportError as error:
            raise RuntimeError(
                "FAISS 检索依赖缺失，请执行 pip install -r requirements.txt"
            ) from error
        return faiss, np

    def _client(self):
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError(
                "Embedding API 依赖缺失，请执行 pip install -r requirements.txt"
            ) from error
        api_key = os.environ.get("SILICONFLOW_API_KEY")
        if not api_key:
            raise RuntimeError("SILICONFLOW_API_KEY 未配置")
        return OpenAI(api_key=api_key, base_url=self.api_base, timeout=12.0, max_retries=0)

    def embed(self, texts):
        if not texts:
            return []
        client = self._client()
        vectors = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            response = client.embeddings.create(
                model=self.model,
                input=batch,
                encoding_format="float",
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(item.embedding for item in ordered)
        return vectors

    def build(self, articles):
        """Rebuild the complete local index from MariaDB-loaded paper records."""
        records = []
        texts = []
        for article in articles:
            key = article_key(article)
            text = article_embedding_text(article)
            if not key or not text:
                continue
            records.append({
                "key": key,
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            })
            texts.append(text)

        if not records:
            raise RuntimeError("没有可用于构建索引的论文")

        faiss, np = self._imports()
        vectors = np.asarray(self.embed(texts), dtype="float32")
        if vectors.ndim != 2 or len(vectors) != len(records):
            raise RuntimeError("Embedding 服务返回的向量数量或维度无效")
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        metadata = {
            "version": 1,
            "model": self.model,
            "dimension": int(vectors.shape[1]),
            "count": len(records),
            "records": records,
        }
        self.index_dir.mkdir(parents=True, exist_ok=True)
        temp_index = self.index_path.with_suffix(".faiss.tmp")
        temp_metadata = self.metadata_path.with_suffix(".json.tmp")
        serialized_index = faiss.serialize_index(index)
        temp_index.write_bytes(serialized_index.tobytes())
        temp_metadata.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_index, self.index_path)
        os.replace(temp_metadata, self.metadata_path)
        with self._lock:
            self._index = index
            self._metadata = metadata
        logger.info("FAISS 索引已保存到 %s，共 %s 篇论文", self.index_dir, len(records))
        return len(records)

    def build_incremental(self, articles, previous=None):
        """Reuse matching vectors; build a separate complete, validated index."""
        faiss, np = self._imports()
        old = {}
        if previous and previous.load():
            old = {record['key']: (record['content_hash'], i)
                   for i, record in enumerate(previous._metadata['records'])}
        records, texts, reused, missing = [], [], {}, []
        seen = set()
        for article in articles:
            key, text = article_key(article), article_embedding_text(article)
            if not key or not text:
                raise RuntimeError('论文缺少可用于索引的标识或内容')
            if key in seen:
                raise RuntimeError('论文标识重复，无法安全构建索引')
            seen.add(key)
            digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
            records.append({'key': key, 'content_hash': digest})
            texts.append(text)
            if key in old and old[key][0] == digest:
                reused[len(records)-1] = old[key][1]
            else:
                missing.append(len(records)-1)
        if not records:
            raise RuntimeError('没有可用于构建索引的论文')
        fresh = np.asarray(self.embed([texts[i] for i in missing]), dtype='float32') if missing else None
        if fresh is not None and (fresh.ndim != 2 or len(fresh) != len(missing) or not np.isfinite(fresh).all()):
            raise RuntimeError('Embedding 服务返回的向量无效')
        dim = int(previous._index.d) if reused else int(fresh.shape[1])
        if fresh is not None and fresh.shape[1] != dim:
            raise RuntimeError('新向量维度与原索引不一致')
        vectors = np.empty((len(records), dim), dtype='float32')
        for index, position in reused.items():
            vectors[index] = previous._index.reconstruct(position)
        for row, index in enumerate(missing):
            vectors[index] = fresh[row]
        if not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors, axis=1) == 0):
            raise RuntimeError('索引包含无效或全零向量')
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(dim)
        index.add(vectors)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.write_bytes(faiss.serialize_index(index).tobytes())
        self.metadata_path.write_text(json.dumps({'version': 1, 'model': self.model,
            'dimension': dim, 'count': len(records), 'records': records}, ensure_ascii=False), encoding='utf-8')
        if not self.load() or self._index.ntotal != len(records):
            raise RuntimeError('新索引校验失败')
        logger.info('索引已校验：共 %s 篇，复用 %s 篇，新向量 %s 篇', len(records), len(reused), len(missing))
        return len(records), len(missing)

    def load(self):
        with self._lock:
            if self._index is not None and self._metadata is not None:
                return True
            if not self.index_path.exists() or not self.metadata_path.exists():
                return False
            faiss, np = self._imports()
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            serialized_index = np.frombuffer(
                self.index_path.read_bytes(), dtype="uint8"
            )
            index = faiss.deserialize_index(serialized_index)
            if index.ntotal != len(metadata.get("records", [])):
                raise RuntimeError("FAISS 索引与元数据记录数不一致，请重建索引")
            if metadata.get("model") != self.model:
                raise RuntimeError(
                    f"索引模型为 {metadata.get('model')}，当前模型为 {self.model}，请重建索引"
                )
            self._index = index
            self._metadata = metadata
            return True

    def search(self, query, articles, limit=12):
        """Return articles with cosine similarity scores."""
        if not query.strip() or not self.load():
            return []
        faiss, np = self._imports()
        query_vector = np.asarray(self.embed([query]), dtype="float32")
        faiss.normalize_L2(query_vector)
        count = min(max(1, limit), self._index.ntotal)
        scores, positions = self._index.search(query_vector, count)
        articles_by_key = {
            article_key(article): article for article in articles if article_key(article)
        }
        results = []
        records = self._metadata["records"]
        for score, position in zip(scores[0], positions[0]):
            if position < 0:
                continue
            key = records[int(position)]["key"]
            article = articles_by_key.get(key)
            if article is not None:
                results.append({
                    "id": article.get("doi") or article.get("url") or key,
                    "semanticScore": float(score),
                    "article": article,
                })
        return results
