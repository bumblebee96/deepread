"""This "graph" simply exposes an endpoint for a user to upload docs to be indexed."""
import numpy as np

from typing import Optional, Sequence

from langchain_core.documents import Document
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from retrieval_graph import retrieval
from retrieval_graph.configuration import IndexConfiguration
from retrieval_graph.state import IndexState

from retrieval_graph.topic_model import get_topic_modeling_info
from retrieval_graph.embeddings import get_embeddings_model


def ensure_docs_have_user_id(
    docs: Sequence[Document], config: RunnableConfig
) -> list[Document]:
    """Ensure that all documents have a user_id in their metadata.

        docs (Sequence[Document]): A sequence of Document objects to process.
        config (RunnableConfig): A configuration object containing the user_id.

    Returns:
        list[Document]: A new list of Document objects with updated metadata.
    """
    user_id = config["configurable"]["user_id"]
    return [
        Document(
            page_content=doc.page_content, metadata={**doc.metadata, "user_id": user_id}
        )
        for doc in docs
    ]


def add_topic_modeling_metadata(
    docs: Sequence[Document]
) -> list[Document]:
    """Ensure that all documents have topic modeling metadata.

        docs (Sequence[Document]): A sequence of Document objects to process.

    Returns:
        list[Document]: A new list of Document objects with updated metadata.
    """
    embedding_model = get_embeddings_model()

    texts = [doc.page_content for doc in docs]
    embeddings = embedding_model.embed_documents(texts)
    array_vectors = np.array(embeddings)

    labeled_docs = get_topic_modeling_info(docs, array_vectors)

    return labeled_docs


async def index_docs(
    state: IndexState, *, config: Optional[RunnableConfig] = None
) -> dict[str, str]:
    """Asynchronously index documents in the given state using the configured retriever.

    This function takes the documents from the state, ensures they have a user ID,
    adds them to the retriever's index, and then signals for the documents to be
    deleted from the state.

    Args:
        state (IndexState): The current state containing documents and retriever.
        config (Optional[RunnableConfig]): Configuration for the indexing process.r
    """
    if not config:
        raise ValueError("Configuration required to run index_docs.")
    with retrieval.make_retriever(config) as retriever:
        stamped_docs = ensure_docs_have_user_id(state.docs, config)
        labelled_docs = add_topic_modeling_metadata(stamped_docs)

        await retriever.aadd_documents(labelled_docs)
    return {"docs": "delete"}


# Define a new graph


builder = StateGraph(IndexState, config_schema=IndexConfiguration)
builder.add_node(index_docs)
builder.add_edge("__start__", "index_docs")
# Finally, we compile it!
# This compiles it into a graph you can invoke and deploy.
graph = builder.compile()
graph.name = "IndexGraph"
