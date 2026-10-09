"""查询流程主图

使用 LangGraph 构建知识库查询工作流。
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from knowledge.core.configuration import load_environment
from knowledge.processor.query_processor.state import QueryGraphState
from knowledge.processor.query_processor.nodes.item_name_confirmed_node import (
    ItemNameConfirmedNode,
)
from knowledge.processor.query_processor.nodes.hybrid_vector_search_node import (
    HybridVectorSearch,
)
from knowledge.processor.query_processor.nodes.hyde_vector_search_node import (
    HyDeVectorSearchNode,
)
from knowledge.processor.query_processor.nodes.web_mcp_search_node import (
    WebMcpSearchNode,
)
from knowledge.processor.query_processor.nodes.rrf_merge_node import RrfMergeNode
from knowledge.processor.query_processor.nodes.reranker_node import RerankerNode
from knowledge.processor.query_processor.nodes.answer_output_node import (
    AnswerOutPutNode,
)

# 加载环境变量
load_environment()


def route_after_item_confirm(state: QueryGraphState) -> bool:
    """商品名称确认后的路由逻辑。

    根据是否已有答案决定是否跳过搜索直接输出。

    Args:
        state: 查询图状态。

    Returns:
        True 表示已有答案需要跳过搜索，False 表示继续搜索流程。
    """
    if state.get("answer"):
        return True
    return False


def join_search_results(state: QueryGraphState) -> QueryGraphState:
    statuses = [
        state.get(key, "") for key in ("hybrid_status", "hyde_status", "web_status")
    ]
    if not any(status == "completed" for status in statuses) and any(
        status.startswith("failed:") for status in statuses
    ):
        raise RuntimeError(
            "All enabled retrieval branches failed; no answer can be published"
        )
    return {"join_count": state.get("join_count", 0) + 1}


def create_query_graph() -> CompiledStateGraph:
    """创建查询流程图。

    Returns:
        编译后的 StateGraph 实例。

    流程结构::

        item_name_confirm
              │
              ├── (有答案) ──────────────────────────> answer_output
              │                                            │
              └── (无答案)                                  │
                   │                                       │
                   v                                       │
              multi_search                                 │
                   │                                       │
             ┌─────┼──────────┐                            │
             │     │          │                            │
             v     v          v                            │
        embedding  hyde    web_mcp                         │
             │     │          │                            │
             └─────┼──────────┘                            │
                   │                                       │
                   v                                       │
                 join                                      │
                   │                                       │
                   v                                       │
                  rrf                                      │
                   │                                       │
                   v                                       │
                rerank                                     │
                   │                                       │
                   v                                       │
             answer_output <───────────────────────────────┘
                   │
                   v
                  END
    """

    # 1. 定义LangGraph工作流
    workflow = StateGraph(QueryGraphState)  # type:ignore

    # 2. 实例化节点
    nodes = {
        "item_name_confirmed_node": ItemNameConfirmedNode(),
        "multi_search": lambda x: {},  # 虚拟节点
        "hybrid_vector_search_node": HybridVectorSearch(),
        "hyde_vector_search_node": HyDeVectorSearchNode(),
        "web_mcp_search_node": WebMcpSearchNode(),
        "join": join_search_results,
        "rrf_merge_node": RrfMergeNode(),
        "reranker_node": RerankerNode(),
        "answer_output_node": AnswerOutPutNode(),
    }

    # 3. 添加节点
    for name, node in nodes.items():
        workflow.add_node(name, node)  # type:ignore

    # 4. 设置入口点
    workflow.set_entry_point("item_name_confirmed_node")

    # 5. 添加条件边：商品名称确认后根据是否有答案路由
    workflow.add_conditional_edges(
        "item_name_confirmed_node",
        route_after_item_confirm,
        {
            False: "multi_search",
            True: "answer_output_node",
        },
    )

    # 6. 多路搜索分发（并行执行）
    workflow.add_edge("multi_search", "hybrid_vector_search_node")
    workflow.add_edge("multi_search", "hyde_vector_search_node")
    workflow.add_edge("multi_search", "web_mcp_search_node")

    # 7. 多路搜索汇合
    workflow.add_edge(
        ["hybrid_vector_search_node", "hyde_vector_search_node", "web_mcp_search_node"],
        "join",
    )

    # 8. 顺序边
    workflow.add_edge("join", "rrf_merge_node")
    workflow.add_edge("rrf_merge_node", "reranker_node")
    workflow.add_edge("reranker_node", "answer_output_node")
    workflow.add_edge("answer_output_node", END)

    # 9. 返回可运行的状态
    return workflow.compile()


# 创建全局图实例
query_app = create_query_graph()

if __name__ == "__main__":
    raise SystemExit(
        "Use scripts/verify_vertical.py or the authenticated /query API to create a durable task."
    )
