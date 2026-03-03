"""Consensus detection logic."""

from typing import Any

from ..utils.config import get_discussion_config
from ..utils.logger import get_logger

logger = get_logger("consensus")


class ConsensusDetector:
    """Detect consensus among agents."""

    def __init__(self, threshold: float = 0.8):
        """
        Initialize consensus detector.

        Args:
            threshold: Consensus threshold (0-1)
        """
        self.threshold = threshold

    def check_consensus(
        self,
        messages: list[dict[str, Any]],
        stage: str,
    ) -> tuple[bool, str]:
        """
        Check if consensus has been reached.

        Args:
            messages: Recent messages from agents
            stage: Current discussion stage

        Returns:
            Tuple of (has_consensus, reason)
        """
        if len(messages) < 2:
            return False, "insufficient_messages"

        # Simple heuristic: if all recent messages are similar, consensus reached
        recent_messages = messages[-5:] if len(messages) >= 5 else messages

        # Extract content for comparison
        contents = [msg.get("content", "") for msg in recent_messages]

        # Calculate similarity (simplified)
        similarity = self._calculate_similarity(contents)

        if similarity >= self.threshold:
            logger.info(
                "consensus_reached",
                similarity=similarity,
                threshold=self.threshold,
                message_count=len(messages),
            )
            return True, f"consensus_reached_similarity_{similarity:.2f}"

        return False, f"no_consensus_similarity_{similarity:.2f}"

    def _calculate_similarity(self, contents: list[str]) -> float:
        """
        Calculate similarity between content strings.

        Simplified implementation using keyword overlap.
        """
        if len(contents) < 2:
            return 0.0

        # Extract keywords from each content
        keyword_sets = []
        for content in contents:
            keywords = set(self._extract_keywords(content))
            keyword_sets.append(keywords)

        # Calculate Jaccard similarity between all pairs
        total_similarity = 0.0
        pair_count = 0

        for i in range(len(keyword_sets)):
            for j in range(i + 1, len(keyword_sets)):
                intersection = len(keyword_sets[i] & keyword_sets[j])
                union = len(keyword_sets[i] | keyword_sets[j])

                if union > 0:
                    similarity = intersection / union
                    total_similarity += similarity
                    pair_count += 1

        if pair_count == 0:
            return 0.0

        return total_similarity / pair_count

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """
        Extract keywords from text.

        Simplified implementation.
        """
        # Simple word extraction (remove punctuation, split by space)
        words = text.lower().split()

        # Filter short words and common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all",
            "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than",
            "too", "very", "just", "and", "but", "if", "or", "because",
            "until", "while", "this", "that", "these", "those", "it",
        }

        keywords = [w.strip(".,!?;:()[]{}") for w in words]
        keywords = [w for w in keywords if len(w) > 2 and w not in stop_words]

        return keywords


def create_consensus_detector() -> ConsensusDetector:
    """Create consensus detector with config."""
    config = get_discussion_config()
    threshold = config.get("consensus_threshold", 0.8)
    return ConsensusDetector(threshold=threshold)
