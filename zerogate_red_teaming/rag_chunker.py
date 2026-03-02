import hashlib
import json
import os
from typing import Any

from dotenv import load_dotenv
from loguru import logger

try:
    import faiss  # type: ignore
    import numpy as np  # type: ignore
    import tree_sitter_python  # type: ignore
    from tree_sitter import Language, Parser  # type: ignore

    # Optional fallback logic for langchain_huggingface vs langchain_community
    try:
        from langchain_huggingface import HuggingFaceEmbeddings  # type: ignore
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore
except ImportError:
    pass  # Allow script to be viewed without dependencies

load_dotenv()


class ASTChunker:
    def __init__(self):
        try:
            self.language = Language(tree_sitter_python.language())
            self.parser = Parser(self.language)
        except NameError:
            pass  # Handle imports failing

    def _compute_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def parse_and_chunk(self, filepath: str) -> list[dict[str, Any]]:
        chunks = []
        if not os.path.exists(filepath):
            return chunks

        with open(filepath, encoding="utf-8") as f:
            source_code = f.read()

        try:
            tree = self.parser.parse(bytes(source_code, "utf8"))
            root_node = tree.root_node

            # Helper to recursively find classes and functions
            def traverse(node):
                if node.type in ["function_definition", "class_definition"]:
                    node_text = source_code[node.start_byte : node.end_byte]
                    chunk_hash = self._compute_hash(node_text)
                    chunks.append(
                        {
                            "text": node_text,
                            "metadata": {
                                "file_path": filepath,
                                "node_type": node.type,
                                "start_line": node.start_point[0]
                                + 1,  # Tree-sitter is 0-indexed for lines
                                "end_line": node.end_point[0] + 1,
                                "hash": chunk_hash,
                            },
                        }
                    )
                # Continue traversal to find nested functions/classes
                for child in node.children:
                    traverse(child)

            traverse(root_node)
        except Exception as e:
            logger.error(f"Error parsing {filepath}: {e}")

        return chunks


class VectorStore:
    def __init__(self, model_name: str | None = None):
        if model_name is None:
            model_name = os.getenv(
                "CODE_EMBEDDING_MODEL_NAME", "jinaai/jina-embeddings-v2-base-code"
            )

        self.model_name = model_name
        self.embeddings = None
        self.dimension = 768

        try:
            hf_token = os.getenv("HF_TOKEN")
            model_kwargs = {"trust_remote_code": True}
            if hf_token:
                # Some versions accept token via model_kwargs or encode_kwargs
                pass

            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name, model_kwargs=model_kwargs
            )
            # determine dimension
            dummy_vec = self.embeddings.embed_query("test")
            self.dimension = len(dummy_vec)
            self.index = faiss.IndexFlatIP(self.dimension)
        except Exception as e:
            logger.error(f"Error initializing HuggingFaceEmbeddings or FAISS: {e}")
            try:
                self.index = faiss.IndexFlatIP(self.dimension)
            except NameError:
                pass

        self.chunks_mapping = {}  # Map vector ID to metadata
        self.existing_hashes = set()
        self.current_id = 0

    def _generate_embedding(self, text: str) -> "np.ndarray | None":
        """Generates embedding using the actual HuggingFace model."""
        try:
            if not self.embeddings:
                return None
            vec = self.embeddings.embed_query(text)
            vec_np = np.array(vec).astype("float32")
            faiss.normalize_L2(np.expand_dims(vec_np, axis=0))
            return vec_np
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    def add_chunks(self, chunks: list[dict[str, Any]]):
        try:
            vectors_to_add = []
            mapping_updates = {}

            for chunk in chunks:
                chunk_hash = chunk["metadata"]["hash"]
                if chunk_hash in self.existing_hashes:
                    continue  # Deduplicate identical chunks

                embedding = self._generate_embedding(chunk["text"])
                if embedding is not None:
                    vectors_to_add.append(embedding)
                    mapping_updates[self.current_id] = {
                        "text": chunk["text"],
                        "metadata": chunk["metadata"],
                    }
                    self.existing_hashes.add(chunk_hash)
                    self.current_id += 1

            if vectors_to_add:
                embeddings_array = np.vstack(vectors_to_add)
                self.index.add(embeddings_array)
                self.chunks_mapping.update(mapping_updates)
                logger.info(
                    f"Added {len(vectors_to_add)} new chunks to the vector store."
                )
        except Exception as e:
            logger.error(f"Failed to add chunks: {e}")

    def save(self, index_path: str | None = None, mapping_path: str | None = None):
        if index_path is None:
            index_path = os.getenv("VECTOR_DB_PATH", "faiss_index.bin")
        if mapping_path is None:
            mapping_path = os.getenv("FAISS_INDEX_FILE", "faiss_mapping.json")
        try:
            faiss.write_index(self.index, index_path)
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(self.chunks_mapping, f, indent=2)
            logger.info(
                f"Successfully saved index to {index_path} and mapping to {mapping_path}."
            )
        except Exception as e:
            logger.error(f"Failed to save index/mapping: {e}")


if __name__ == "__main__":
    logger.info("Initializing AST Chunker...")
    chunker = ASTChunker()

    current_file = __file__
    logger.info(f"Parsing and chunking: {current_file}")
    chunks = chunker.parse_and_chunk(current_file)

    logger.info(f"Extracted {len(chunks)} chunks.")
    for i, chunk in enumerate(chunks):
        meta = chunk["metadata"]
        logger.debug(
            f"Chunk {i + 1}: {meta['node_type']} at lines {meta['start_line']}-{meta['end_line']} (Hash: {meta['hash'][:8]}...)"
        )

    logger.info("Initializing Vector Store...")
    vector_store = VectorStore()

    logger.info("Adding chunks to Vector Store...")
    vector_store.add_chunks(chunks)

    logger.info("Saving Vector Store...")
    vector_store.save()

    logger.info("Done!")
