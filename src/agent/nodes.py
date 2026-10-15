from src.rag.embedder import Embedder
from src.rag.vector_store import VectorStore
from src.rag.llm import LLM
from src.rag.prompts import RAG_TEST_PROMPT_V3
from src.rag.reranker import Reranker
from src.agent.state import AgentState
from src.logger import get_logger

logger = get_logger(__name__)
_store =  None
_embedder = None
_llm = None
_reranker = None

def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store

def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder

def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = LLM()
    return _llm

def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker(llm=get_llm())
    return _reranker


def router(state: AgentState) -> dict:
    try: 
            system_prompt = """
        You are a professional financial analyst with 15 years of experience.

        Your task is to classify a user’s question into one of the following categories:

        Categories:
        - sec: Questions about filings, financial statements, risk factors, revenue, earnings, or annual reports
        - news: Questions about recent events, headlines, market movements, or breaking news
        - general: All other questions, including broad topics or comparisons

        Rules:
        - Respond with ONLY one word: sec, news, or general
        - Do NOT provide any explanation or additional text
        - If unsure, respond with: general
        """

            user_prompt = f"Question: {state['question']}"

            # 1. Call LLM
            response = get_llm().generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )

            # 2. Normalize output
            result = response.strip().lower()

            # 3. Validate output (critical)
            if result not in {"sec", "news", "general"}:
                
                return{
                    "route" : "general"
                }
            
            return {
                "route": result
            }
    except Exception as e:
        logger.error(f"Router Error: {e}")
        return {
            "route": "general",
            "error": str(e)
        }
    
def retrieve(state: AgentState) -> dict:
    
    #logic for source filter
    try: 
        source_filter = None if state["route"] == "general" else state["route"]


        #call the embed and to embed the questions
        embed_question = get_embedder().embed(state['question'])

        #call the store.search to search the relavent chunks
        retrieved_chunks = get_store().search(query_embedding= embed_question,top_k=state['top_k'],source_filter=source_filter, date_from=state['date_from'])

        #create a ranked chunks function get all reranked chunks
        ranked_chunks = get_reranker().rerank(question=state['question'], chunks=retrieved_chunks,top_k=state['top_k'])

        #return all reranked chunks
        context ="\n".join(
            f"[{r['id']}] {r['text']}" for r in ranked_chunks
        )

        sources= [
                {
                    "chunk_id": r["id"],
                    "text": r["text"][:200],
                    "metadata": r["metadata"],
                    "relevance": 1 - r["distance"]
                }
                for r in ranked_chunks
            ]

        return {
            "embed_question": embed_question,
            "retrieved_chunks": ranked_chunks,
            "context": context,
            "sources": sources
        }
    except Exception as e:
        logger.error(f"Retrieve Error: {e}")
        return {
            "embed_question": None,
            "retrieved_chunks": [],
            "context": "",
            "sources": [],
            "error": str(e)
        }
        
    
def generate_node(state: AgentState):
    try:
        # 1. Build history_text first
        history_text = "\n\n".join(
            f"User: {chat['question']}\nAssistant: {chat['answer']}"
            for chat in state.get("chat_history", [])
        )

        formatted_prompt = RAG_TEST_PROMPT_V3.format(
            context=state["context"],
            question=state["question"],
            chat_history=history_text
        )

        # 3. Call LLM
        answer = get_llm().generate(
            system_prompt="""
    You are a precise financial analyst.
    Only use the provided context and relevant chat history.
    Maintain consistency with previous response.
    """,
            user_prompt=formatted_prompt
        )

        # 4. Update chat history (FIX: correct .get key)
        updated_chat_history = state.get("chat_history", []) + [
            {
                "question": state["question"],
                "answer": answer
            }
        ]

        # 5. Return
        return {
            "answer": answer,
            "chat_history": updated_chat_history
    } 
    except Exception as e:
        logger.error(f"error in generate node : {e}")
        return {
            
            "answer": "I'm having trouble generating a response right now. Please try again in a moment.",
            "error": str(e),
            "risk_flags": ["llm_failure"]
        }

def after_generate(state: AgentState) -> str:
    if "llm_failure" in state.get("risk_flags", []):
        return  "llm_failure"
    return "risk_flagger"

def  risk_flagger_node(state: AgentState):
        
    try:

        flags = [
        "litigation",
        "material weakness",
        "regulatory investigation",
        "material adverse effect",
        "data breach",
        "sanctions",
        "fraud",
        "going concern",
        "default",
        "bankruptcy",
        "restatement",
        "compliance failure"
    ]
        texts = state["answer"].lower()

        result = [word for word in flags if word in texts]
    
        return{
            "risk_flags":result}
    except Exception as e:
        logger.error(f"error in flags : {e}")
        return{
            "risk_flags" : []
        }
