from abc import ABC, abstractmethod


class BaseEmbeddingModel(ABC):
    @abstractmethod
    def encode(self, texts, batch_size=32):
        """Encode a list of text strings into embedding vectors.

        Args:
            texts: List of strings to encode
            batch_size: Batch size for processing

        Returns:
            numpy array of shape (len(texts), embedding_dim), L2-normalized
        """
        ...

    @abstractmethod
    def get_dimension(self):
        """Return the embedding vector dimension."""
        ...

    @property
    @abstractmethod
    def model_name(self):
        """Human-readable model name for display."""
        ...
