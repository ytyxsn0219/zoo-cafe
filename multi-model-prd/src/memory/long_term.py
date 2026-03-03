"""Long-term memory using ChromaDB for RAG."""

from typing import Any, Optional

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:
    chromadb = None

from ..utils.config import get_memory_config
from ..utils.logger import get_logger

logger = get_logger("long_term_memory")


class LongTermMemory:
    """ChromaDB-based long-term memory for historical PRD storage."""

    def __init__(self):
        """Initialize long-term memory."""
        if chromadb is None:
            raise ImportError("chromadb is required for long-term memory")

        self._config = get_memory_config()["vector_db"]
        self._client = None
        self._collection = None

    def connect(self) -> None:
        """Connect to ChromaDB."""
        if self._client is not None:
            return

        try:
            provider = self._config.get("provider", "chroma")

            if provider == "chroma":
                self._client = chromadb.PersistentClient(
                    path="./chroma_data",
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                        allow_reset=True,
                    ),
                )
            else:
                # For other providers, use HTTP client
                self._client = chromadb.HttpClient(
                    host="localhost",
                    port=8001,
                )

            # Get or create collection
            collection_name = self._config.get("collection", "prd_history")
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "Historical PRD documents"},
            )

            logger.info("chroma_connected", provider=provider)

        except Exception as e:
            logger.error("chroma_connection_failed", error=str(e))
            raise

    def add_prd(
        self,
        prd_id: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Add a PRD to long-term memory.

        Args:
            prd_id: Unique PRD identifier
            content: PRD content
            metadata: Optional metadata

        Returns:
            True if successful
        """
        if self._collection is None:
            self.connect()

        try:
            meta = metadata or {}
            meta["prd_id"] = prd_id

            self._collection.add(
                documents=[content],
                ids=[prd_id],
                metadatas=[meta],
            )

            logger.info("prd_added", prd_id=prd_id)
            return True

        except Exception as e:
            logger.error("prd_add_failed", prd_id=prd_id, error=str(e))
            return False

    def search(
        self,
        query: str,
        n_results: int = 3,
        filter_metadata: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar PRDs.

        Args:
            query: Search query
            n_results: Number of results
            filter_metadata: Optional metadata filter

        Returns:
            List of matching PRD results
        """
        if self._collection is None:
            self.connect()

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_metadata,
            )

            # Format results
            formatted = []
            if results["ids"] and results["ids"][0]:
                for i, prd_id in enumerate(results["ids"][0]):
                    formatted.append({
                        "id": prd_id,
                        "content": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0.0,
                    })

            logger.debug("search_completed", query=query, results=len(formatted))
            return formatted

        except Exception as e:
            logger.error("search_failed", query=query, error=str(e))
            return []

    def delete_prd(self, prd_id: str) -> bool:
        """
        Delete a PRD from memory.

        Args:
            prd_id: PRD identifier

        Returns:
            True if successful
        """
        if self._collection is None:
            return False

        try:
            self._collection.delete(ids=[prd_id])
            logger.info("prd_deleted", prd_id=prd_id)
            return True

        except Exception as e:
            logger.error("prd_delete_failed", prd_id=prd_id, error=str(e))
            return False

    def get_prd(self, prd_id: str) -> Optional[dict[str, Any]]:
        """
        Get a specific PRD.

        Args:
            prd_id: PRD identifier

        Returns:
            PRD data or None
        """
        if self._collection is None:
            self.connect()

        try:
            result = self._collection.get(ids=[prd_id])

            if result["ids"] and result["ids"][0]:
                return {
                    "id": result["ids"][0],
                    "content": result["documents"][0] if result["documents"] else "",
                    "metadata": result["metadatas"][0] if result["metadatas"] else {},
                }

            return None

        except Exception as e:
            logger.error("get_prd_failed", prd_id=prd_id, error=str(e))
            return None


# Global instance
_long_term_memory: Optional[LongTermMemory] = None


def get_long_term_memory() -> LongTermMemory:
    """Get global long-term memory instance."""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory()
        _long_term_memory.connect()
    return _long_term_memory
