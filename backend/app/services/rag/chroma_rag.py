"""
RAG: ChromaDB vector store, Gemini or default embeddings. Uses app.config.
Includes text chunking for better retrieval granularity.
"""
import os
import re
import chromadb
import google.generativeai as genai
from chromadb.utils import embedding_functions

from app.config import GEMINI_API_KEY, CHROMA_DIR


class GeminiEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """Chroma requires a stable name() so it does not report NotImplemented vs persisted default."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)

    def name(self) -> str:
        return "gemini-embedding-001"

    def __call__(self, input: list) -> list:
        if not self.api_key:
            return [[0.0] * 768 for _ in input]
        out = []
        for text in input:
            try:
                r = genai.embed_content(model="models/embedding-001", content=text, task_type="retrieval_document", title="Pathfinder Content")
                out.append(r["embedding"])
            except Exception as e:
                print(f"Embedding error: {e}")
                out.append([0.0] * 768)
        return out


class RAGService:
    def __init__(self, persist_path=None, chunk_size: int = 500, chunk_overlap: int = 100):
        """
        Initialize RAG service with chunking support.
        
        Args:
            persist_path: Path for ChromaDB persistence
            chunk_size: Maximum characters per chunk (default: 500)
            chunk_overlap: Characters to overlap between chunks (default: 100)
        """
        path = persist_path or str(CHROMA_DIR)
        self.client = chromadb.PersistentClient(path=path)
        if GEMINI_API_KEY:
            self.embed_fn = GeminiEmbeddingFunction(GEMINI_API_KEY)
            self.collection_name = "pathfinder_context_gemini"
        else:
            self.embed_fn = embedding_functions.DefaultEmbeddingFunction()
            self.collection_name = "pathfinder_context"
        self.collection = self._open_collection(self.collection_name)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _open_collection(self, name: str):
        """Open collection; recreate on embedding config mismatch (re-seed after)."""
        try:
            return self.client.get_or_create_collection(
                name=name, embedding_function=self.embed_fn
            )
        except ValueError as e:
            if "Embedding function conflict" not in str(e):
                raise
            print(
                f"WARNING: Chroma collection {name!r} has a different embedding config; "
                "recreating empty collection. Re-run: python scripts/seed_rag.py"
            )
            try:
                self.client.delete_collection(name)
            except Exception:
                pass
            return self.client.create_collection(
                name=name, embedding_function=self.embed_fn
            )

    def chunk_text(self, text: str) -> list[str]:
        """
        Split text into chunks with overlap for better context preservation.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        # Try to split on sentences first, then on words, then hard cut
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        current_chunk = ""
        for sentence in sentences:
            # If adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) + 1 > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # Start new chunk with overlap
                    if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                        # Take last chunk_overlap chars for overlap
                        overlap_text = current_chunk[-self.chunk_overlap:]
                        # Try to start from a word boundary
                        words = overlap_text.split()
                        if len(words) > 1:
                            overlap_text = ' '.join(words[1:])  # Skip first partial word
                        current_chunk = overlap_text + " " + sentence
                    else:
                        current_chunk = sentence
                else:
                    # Sentence itself is too long, split by words
                    words = sentence.split()
                    word_chunk = ""
                    for word in words:
                        if len(word_chunk) + len(word) + 1 > self.chunk_size:
                            if word_chunk:
                                chunks.append(word_chunk.strip())
                                word_chunk = word
                            else:
                                # Single word is too long, hard cut
                                chunks.append(word[:self.chunk_size])
                                word_chunk = word[self.chunk_size:]
                        else:
                            word_chunk += " " + word if word_chunk else word
                    if word_chunk:
                        current_chunk = word_chunk
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]

    def index_content(self, doc_id: str, text: str, metadata: dict = None):
        """
        Index content with automatic chunking.
        
        Args:
            doc_id: Base document ID (will be appended with chunk index)
            text: Text content to index
            metadata: Metadata dictionary (will be copied to each chunk)
        """
        chunks = self.chunk_text(text)
        
        if len(chunks) == 1:
            # Single chunk, use original doc_id
            self.collection.add(
                documents=[chunks[0]],
                metadatas=[metadata or {}],
                ids=[doc_id]
            )
        else:
            # Multiple chunks, add chunk index to IDs and metadata
            documents = []
            metadatas = []
            ids = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                chunk_metadata = (metadata or {}).copy()
                chunk_metadata["chunk_index"] = i
                chunk_metadata["total_chunks"] = len(chunks)
                chunk_metadata["chunk_text"] = chunk[:100] + "..." if len(chunk) > 100 else chunk  # Preview
                
                documents.append(chunk)
                metadatas.append(chunk_metadata)
                ids.append(chunk_id)
            
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

    def retrieve_context(self, query: str, n_results: int = 3):
        """
        Retrieve context chunks for a query.
        
        Args:
            query: Query text
            n_results: Number of chunks to retrieve
            
        Returns:
            Query results with documents, metadatas, distances, etc.
        """
        return self.collection.query(query_texts=[query], n_results=n_results)

    def clear_collection(self):
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self._open_collection(self.collection_name)


rag_service = RAGService()
