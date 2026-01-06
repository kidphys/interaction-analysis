"""
Combined graph that merges ReAct agent and data analysis graph into a single composable graph.
This uses a flattened approach where all nodes are in the same graph, allowing full visibility
of the data analysis steps.
"""
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict
import operator
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langgraph.graph.state import RunnableConfig
from langgraph.types import Send

# Import nodes from data analyst graph
from slide_agents.data_analyst_graph import (
    map_tasks_node,
    query_node,
    persist_analysis_node,
    fanout_to_worker,
)
from slide_agents.message import InsightResponseV2
from slide_agents.prompt_slide_agent import prompt_template as base_system_prompt_template
from structured_agent import pre_model_hook


# =========================
# STATE DEFINITION
# =========================

class CombinedState(TypedDict):
    """
    Unified state for the combined agent graph.
    Merges AgentState and AnalysisState.
    """
    # --- Agent State Fields ---
    messages: Annotated[List[BaseMessage], add_messages]
    structured_response: Optional[InsightResponseV2]

    # --- Shared Fields ---
    csv_paths: List[str]
    name: str # name of the run/analysis
    insight_duckdb_file: str

    # --- Data Analysis State Fields ---
    # duckdb file path created from csvs
    duckdb_file: Optional[str]

    # list of questions to answer (from tool call)
    questions: Optional[List[Dict[str, Any]]]

    # task used by worker node (passed via Send)
    task: Optional[Dict[str, Any]]

    # Parallel worker results (list merge)
    results: Annotated[List[Dict[str, Any]], operator.add]


# =========================
# HELPER NODES
# =========================

def finalize_research_node(state: CombinedState) -> CombinedState:
    """
    Node that runs after data analysis is complete.
    It takes the results, formats them, and adds a ToolMessage to the conversation.
    This mimics the returning of a tool call.
    """
    # Find the last tool call to get the ID
    last_message = state["messages"][-1]
    tool_call_id = None

    if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls"):
        for tc in last_message.tool_calls:
            if tc.get("name") == "research":
                tool_call_id = tc.get("id")
                break

    # If we can't find the ID in the last message, search backwards
    if not tool_call_id:
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
                for tc in msg.tool_calls:
                    if tc.get("name") == "research":
                        tool_call_id = tc.get("id")
                        break
                if tool_call_id:
                    break

    if not tool_call_id:
        # Should not happen if graph is correct
        print("Warning: Could not find tool_call_id for research completion")
        # Create a dummy one to avoid crash, but this is bad
        tool_call_id = "unknown_tool_call"

    # Format results
    results = state.get("results", [])
    research_summary = format_research_results(results)

    # Create ToolMessage
    tool_message = ToolMessage(
        content=research_summary,
        tool_call_id=tool_call_id
    )

    # We return the NEW message to be added
    # Since 'messages' is Annotated with add_messages, we just return the update
    return {"messages": [tool_message]}


def format_research_results(results: List[Dict[str, Any]]) -> str:
    """Format research results for the LLM"""
    if not results:
        return "No research results available."

    formatted = "Research Results:\n\n"
    for idx, result in enumerate(results, 1):
        question = result.get("question", "Unknown question")
        analysis = result.get("analysis", {})
        items = analysis.get("items", [])

        formatted += f"Question {idx}: {question}\n"
        formatted += f"Found {len(items)} insights.\n"

        def extract_item(item):
            try:
                return {
                    'id': item['id'],
                    'insight': item['message']['content']
                }
            except Exception as e:
                return 'No insight or error extracting insight'

        item_texts = [extract_item(item) for item in items]
        formatted += str(item_texts)
        formatted += "\n"

    return formatted


# =========================
# AGENT NODES
# =========================

def create_llm_node(model_name: str, model_provider: str, system_prompt: str):
    """Create a node that calls the LLM with the current messages"""
    model = init_chat_model(model_name, max_tokens=8096, model_provider=model_provider)

    # Bind the research tool signature (LLM sees it as a tool)
    # We define the tool schema manually or use the function to get schema

    @tool
    def research(questions: List[str]):
        """
        Research the data to answer the questions.
        Returns insights with full visualization data.
        """
        pass # Actual implementation is handled by graph routing

    model_with_tools = model.bind_tools([research])
    model_with_structured_output = model.with_structured_output(InsightResponseV2)

    def node(state: CombinedState) -> CombinedState:
        # Apply pre_model_hook if available
        hook_result = pre_model_hook(state) if pre_model_hook else {}
        messages_to_use = hook_result.get("llm_input_messages", state["messages"])

        # Prepare messages with system prompt
        messages = [SystemMessage(content=system_prompt)]
        messages.extend(messages_to_use)

        # Check if we should output structured response directly
        # This happens when the last message is a ToolMessage (research complete)
        # and we haven't formatted yet
        last_message = messages_to_use[-1] if messages_to_use else None
        should_format_response = (
            isinstance(last_message, ToolMessage) and
            state.get("structured_response") is None
        )

        if should_format_response:
            # Output structured response directly from the conversation
            structured_response = model_with_structured_output.invoke(messages)
            # Also add a final AI message for completeness
            final_ai_message = AIMessage(content="Analysis complete. Here are the insights.")
            return {
                "messages": [final_ai_message],
                "structured_response": structured_response
            }
        else:
            # Normal agent call with tool support
            response = model_with_tools.invoke(messages)
            # Check if the response has no tool calls - if so, format it
            if (isinstance(response, AIMessage) and
                (not hasattr(response, "tool_calls") or not response.tool_calls) and
                state.get("structured_response") is None):
                # No tool calls means we're done - format the response
                structured_response = model_with_structured_output.invoke(messages + [response])
                return {
                    "messages": [response],
                    "structured_response": structured_response
                }
            return {"messages": [response]}

    return node


def router(state: CombinedState) -> Literal["research", "respond", "end"]:
    """
    Router that decides what to do next based on the last message.
    """
    # If we already have a structured response, we're done
    if state.get("structured_response") is not None:
        return "end"

    last_message = state["messages"][-1]

    # If it's a tool message, continue to LLM (which will format response)
    if isinstance(last_message, ToolMessage):
        return "respond"

    # If it's an AI message
    if isinstance(last_message, AIMessage):
        # Check if the message contains tool calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            # Check if any tool call is for research
            for tool_call in last_message.tool_calls:
                if tool_call.get("name") == "research":
                    return "research"

        # No tool calls, we're done - agent will format response
        return "end"

    # If it's a human message, go to LLM first
    if isinstance(last_message, HumanMessage):
        return "respond"

    return "end"


def prepare_research_state(state: CombinedState) -> CombinedState:
    """
    Extract questions from the tool call and setup state for research
    """
    last_message = state["messages"][-1]
    questions = []

    if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls"):
        for tool_call in last_message.tool_calls:
            if tool_call.get("name") == "research":
                args = tool_call.get("args", {})
                qs = args.get("questions", [])
                questions.extend(qs)

    if not questions:
         # Fallback mechanism
        # Try to use the last human message
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                questions = [msg.content]
                break

    # Format for data analyst graph expectation
    # It expects 'questions' key as list of dicts
    formatted_questions = [{"question": q} for q in questions]

    # Reset results for new research
    # Note: 'results' is annotated with operator.add, so we might need to be careful
    # But usually for a new branch we want fresh results.
    # Since we are in the same state object, we might append to existing results if we are not careful.
    # However, standard LangGraph behavior with operator.add appends.
    # For now, let's just add to it. unique IDs help distinguish if needed.

    return {
        "questions": formatted_questions,
        # We don't reset duckdb_file etc as they persist
    }


def query_node_with_retry(state: CombinedState):
    try:
        return query_node(state)
    except Exception as e:
        return f"Error: {e}"


# =========================
# BUILD GRAPH
# =========================

def create_flat_combined_graph(
    # model_name: str = "claude-sonnet-4-20250514",
    # model_provider: str = "anthropic",
    model_name: str = "gpt-4o",
    model_provider: str = "openai",
    system_prompt: str = None,
    csv_paths: List[str] = None,
    name: str = "answer_stats",
    insight_duckdb_file: str = "insight_items.duckdb",
    checkpointer=None
) -> StateGraph:

    if system_prompt is None:
        system_prompt = base_system_prompt_template

    graph = StateGraph(CombinedState)

    # 1. Agent Node (LLM)
    graph.add_node("agent", create_llm_node(model_name, model_provider=model_provider, system_prompt=system_prompt))

    # 2. Research Prep (Extract questions)
    graph.add_node("prepare_research", prepare_research_state)

    # 3. Data Analysis Nodes (from data_analyst_graph)
    # Note: We reuse the functions directly!
    graph.add_node("map_tasks_node", map_tasks_node)

    # The worker node needs to return a dict that matches CombinedState structure
    # The original query_node returns {'results': [...]}. This matches CombinedState.
    graph.add_node("query_node", query_node)

    graph.add_node("persist_analysis_node", persist_analysis_node)

    # 4. Finalize Research (Convert results to ToolMessage)
    graph.add_node("finalize_research", finalize_research_node)

    # --- EDGES ---

    # Entry
    graph.set_entry_point("agent")

    # Agent -> Router
    graph.add_conditional_edges(
        "agent",
        router,
        {
            "research": "prepare_research",
            "respond": "agent",
            "end": END
        }
    )

    # Research Flow
    graph.add_edge("prepare_research", "map_tasks_node")

    # Map Tasks -> Fanout -> Query Node
    graph.add_conditional_edges(
        "map_tasks_node",
        fanout_to_worker,
        ["query_node"]
    )

    # Query Node -> Persist
    graph.add_edge("query_node", "persist_analysis_node")

    # Persist -> Finalize
    graph.add_edge("persist_analysis_node", "finalize_research")

    # Finalize -> Back to Agent (which will format response)
    graph.add_edge("finalize_research", "agent")

    return graph.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    # Test script
    csv_paths = ['answer_stats_user_ids.csv']
    state = {
        'name': 'test_flat_graph',
        'csv_paths': csv_paths,
        'insight_duckdb_file': 'test_insight.duckdb',
        'messages': [HumanMessage(content="What are the common topics in the presentations?")]
    }

    g = create_flat_combined_graph()

    print("Running graph...")
    # Iterate to show steps
    for step in g.stream(state):
        print("\n--- STEP ---")
        for key, val in step.items():
            print(f"Node: {key}")
            if key == "agent":
                if val.get("messages"):
                    print(f"Agent Msg: {val['messages'][-1].content[:100]}...")
            elif key == "query_node":
                print("Query executed.")

    print("Done.")
