import os
import sys
import pandas as pd

from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_insight.graph import create_session_insight_graph
from session_insight.schemas import SlideAnalysisResult, SlideAnalysisResultBase

def mock_execute_with_columns(sql):
    print(f"Mocking Redshift execution for SQL: {sql[:50]}...")
    # Return dummy data
    columns = [
        "id", "slide_id", "participant_id", "participant_name", "createdat",
        "correct", "is_partially_correct", "answer_time_seconds", "answer_timeout",
        "answer_text", "slide_type", "slide_title", "slide_order", "slide_index"
    ]

    data = [
        (1, 101, "p1", "Alice", "2023-01-01", True, False, 10, False, "A", "Pick Answer", "Q1", 1, 1),
        (2, 101, "p2", "Bob", "2023-01-01", False, False, 15, False, "B", "Pick Answer", "Q1", 1, 1),
        (3, 102, "p1", "Alice", "2023-01-01", None, None, 20, False, "Great!", "Open Ended", "Q2", 2, 2),
    ]

    return data, columns

def test_graph_execution():
    with patch('session_insight.graph.execute_with_columns', side_effect=mock_execute_with_columns):
        # We also need to mock OpenAI to avoid API costs or failures
        with patch('session_insight.graph.ChatOpenAI') as MockChat:
            # Mock the LLM chain
            mock_llm = MockChat.return_value
            mock_structured_llm = mock_llm.with_structured_output.return_value

            # Setup dummy responses
            dummy_analysis = SlideAnalysisResultBase(
                metadata={
                    "analysis_scope": "test",
                    "assumptions_applied": [],
                    "confidence_level": "high"
                },
                key_observations=[],
                interpretation=[],
                actionable_recommendations=[],
                follow_up_analysis=[]
            )

            dummy_coaching = {"message": "Great job on the presentation!"}

            def side_effect(*args, **kwargs):
                # We need to distinguish between calls for analysis and calls for coaching
                # Arg inspection or just simple state
                # The easiest way here is checking the tool or arg type but invoke doesn't pass that easily
                # However, our dummy_analysis is Pydantic, dummy_coaching is dict (TypedDict).
                # But mock return value is static.
                # Let's check `args[0]` which are messages.
                # COACH_PROMPT messages have specific content.
                messages = args[0]
                if any("supportive and encouraging presentation coach" in m.content for m in messages if hasattr(m, 'content')):
                     # Refinement returns SlideAnalysisResultBase too now!
                     return dummy_analysis
                return dummy_analysis

            mock_structured_llm.invoke.side_effect = side_effect

            # Run the graph
            graph = create_session_insight_graph()
            input_state = {"presentation_id": "12345", "insights": []}

            final_state = None
            for output in graph.stream(input_state):
                 for key, value in output.items():
                    print(f"Node completed: {key}")
                    if key == "aggregate_insights":
                        # This might not be the full state if stream returns partials
                        # But typically the last one will have final output
                        pass

            # Since stream yields updates, we can't easily capture the FINAL state object unless we merge them manually
            # or use graph.invoke()

            print("Running invoke...")
            final_state = graph.invoke(input_state)

            assert final_state["final_output_path"] == "session_insight_12345_results.json"
            assert len(final_state["insights"]) > 0
            print("Test Passed!")

if __name__ == "__main__":
    test_graph_execution()
