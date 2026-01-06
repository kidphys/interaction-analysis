from typing import NamedTuple

class AnalysisTask(NamedTuple):
    id: str
    category: str
    sql_template: str
    analysis_prompt: str

TASKS = [
    AnalysisTask(
        id="Q1.1",
        category="PARTICIPATION & FLOW",
        sql_template="""
            SELECT
              slide_index,
              slide_title,
              slide_type,
              COUNT(DISTINCT participant_id) AS participants
            FROM mart
            GROUP BY slide_index, slide_title, slide_type
            ORDER BY slide_index;
        """,
        analysis_prompt="""
            Analyze participation per slide.

            Identify:
            - Slides with unusually low or high participation
            - Whether participation patterns correlate with slide type or slide order
            - Sudden participation drops or recoveries

            Interpret participation as a signal of engagement, clarity, or friction.

            Return:
            - Slides likely causing disengagement
            - Slides that successfully invite interaction
            - Recommendations for slide ordering or facilitation
        """
    ),
    AnalysisTask(
        id="Q1.2",
        category="PARTICIPATION & FLOW",
        sql_template="""
            SELECT
              slide_type,
              COUNT(DISTINCT participant_id) AS participants,
              COUNT(*) AS total_answers
            FROM mart
            GROUP BY slide_type;
        """,
        analysis_prompt="""
            Compare participation across slide types.

            Identify:
            - Slide types that consistently attract or discourage responses
            - Whether response effort appears to differ by slide type

            Return:
            - Engagement ranking by slide type
            - Design implications for mixing slide formats
        """
    ),
    AnalysisTask(
        id="Q2.2",
        category="QUIZ PERFORMANCE",
        sql_template="""
            SELECT
              slide_type,
              AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy,
              COUNT(*) AS answers
            FROM mart
            GROUP BY slide_type;
        """,
        analysis_prompt="""
            Compare accuracy across slide types where correctness applies.

            Do not compare quiz slides with expressive slide types.

            Identify:
            - Quiz formats that perform better or worse
            - Potential causes for performance differences

            Return:
            - Effectiveness ranking of quiz formats
            - Design recommendations
        """
    ),
    AnalysisTask(
        id="Q3.1",
        category="FREE-TEXT EXPRESSION QUALITY",
        sql_template="""
            SELECT
              slide_index,
              slide_title,
              slide_type,
              COUNT(*) AS total_responses,
              COUNT(DISTINCT answer_text) AS distinct_responses
            FROM mart
            GROUP BY slide_index, slide_title, slide_type;
        """,
        analysis_prompt="""
            Analyze free-text response volume and diversity.

            Important:
            - High diversity may be desirable for open-ended slides
            - Repetition may indicate consensus or low-effort answers

            Identify:
            - Slides with rich, varied contributions
            - Slides dominated by repetitive or minimal responses
            - Slides with very low response effort

            Return:
            - Which expressive slides are successful
            - Which slides may need better prompts or facilitation
        """
    ),
    AnalysisTask(
        id="Q3.2",
        category="FREE-TEXT EXPRESSION QUALITY",
        sql_template="""
            SELECT
              slide_index,
              slide_title,
              slide_type,
              answer_text,
              COUNT(*) AS cnt
            FROM mart
            WHERE slide_type in ('Word Cloud', 'Open Ended', 'Brainstorm', 'Short Answer')
            GROUP BY slide_index, slide_title, slide_type, answer_text
            ORDER BY slide_index, cnt DESC;
        """,
        analysis_prompt="""
            Analyze common free-text responses per slide.

            Do not assume there is a correct answer.

            Identify:
            - Dominant themes or shared sentiments
            - Signs of anchoring, priming, or herd behavior
            - Off-topic or low-effort responses

            Return:
            - Insights into participant thinking
            - Suggestions to improve prompt wording or facilitation
        """
    ),
    AnalysisTask(
        id="Q4.1",
        category="SLIDE HEALTH & QUALITY",
        sql_template="""
            SELECT
              slide_index,
              slide_title,
              slide_type,
              COUNT(DISTINCT participant_id) AS participants,
              COUNT(*) AS responses,
              AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy,
              COUNT(DISTINCT answer_text) AS answer_variability
            FROM mart
            GROUP BY slide_index, slide_title, slide_type;
        """,
        analysis_prompt="""
            Evaluate slide health using metrics appropriate to each slide type.

            Rules:
            - Quiz slides: participation + accuracy
            - Open-ended slides: participation + semantic richness
            - Word-cloud slides: response count + balance

            Classify slides as:
            - Highly effective
            - Adequate
            - Needs improvement
            - Risky or broken

            Return:
            - Slide health classification
            - Highest-priority fixes
        """
    ),
    AnalysisTask(
        id="Q5.1",
        category="SESSION FLOW & FATIGUE",
        sql_template="""
            SELECT
              slide_index,
              COUNT(DISTINCT participant_id) AS participants,
              AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy
            FROM mart
            GROUP BY slide_index
            ORDER BY slide_index;
        """,
        analysis_prompt="""
            Analyze engagement and performance trends across slide order.

            Account for:
            - Different slide types at different positions
            - Survivor and selection bias

            Identify:
            - Engagement decay or recovery
            - Sections that disrupt session flow

            Return:
            - Flow issues
            - Recommendations for pacing or reordering slides
        """
    ),
    AnalysisTask(
        id="Q6.1",
        category="PARTICIPANT BEHAVIOR",
        sql_template="""
            SELECT
              participant_id,
              participant_name,
              COUNT(*) AS responses,
              AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy
            FROM mart
            GROUP BY participant_id, participant_name;
        """,
        analysis_prompt="""
            Analyze participant engagement and performance.

            Account for:
            - Skipped slides
            - Different participation levels

            Identify:
            - Engagement archetypes (active, selective, minimal)
            - Participants whose metrics are unreliable due to low data

            Return:
            - Audience segmentation
            - Implications for interpreting aggregate results
        """
    ),
    AnalysisTask(
        id="Q6.2",
        category="PARTICIPANT BEHAVIOR",
        sql_template="""
            SELECT
              participant_id,
              participant_name,
              slide_type,
              COUNT(*) AS responses,
              AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy
            FROM mart
            GROUP BY participant_id, participant_name, slide_type;
        """,
        analysis_prompt="""
            Analyze how participants interact with different slide types.

            Identify:
            - Slide types that attract or repel certain participants
            - Opportunities for adaptive or optional content

            Return:
            - Key interaction patterns
            - Design recommendations for inclusive engagement
        """
    )
]

MART_SQL = """
SELECT
    fa.id,
    fa.slide_id,
    fa.participant_id,
    dp.name as participant_name,
    fa.createdat,
    fa.correct,
    fa.is_partially_correct,
    fa.answer_time_seconds,
    fa.answer_timeout,
    fa.submitted_answer_text as answer_text,
    fa.slide_type,
    dq.slide_title,
    dq.slide_order,
    DENSE_RANK() OVER (ORDER BY dq.slide_order) AS slide_index
FROM aha_report_v5.fact_answers2 fa
JOIN aha_report_v5.dim_questions dq
  ON fa.slide_id = dq.slide_id
JOIN aha_report_v5.dim_participants dp
  ON fa.participant_id = dp.participant_id
WHERE fa.presentation_id = {presentation_id}
  AND fa.deleted IS FALSE
  AND dq.presentation_id = {presentation_id};
"""

SYSTEM_PROMPT = """
You are a senior data analyst specializing in interactive learning and audience engagement data.

Important context:
- answer_text is free text
- participants may skip slides
- not all slide types have a concept of correctness
- participation is often the primary signal of success

Rules:
- Only interpret "correct" for slide types where correctness is meaningful
- Treat absence of an answer as a behavioral signal, not an error
- Do not assume multiple-choice structure unless clearly supported
- Focus on patterns, anomalies, and actionable insights
- Provide concrete, suggestive, and specific recommendations (e.g., "Rename slide title from X to Y", "Move slide Z to earlier position"). Avoid generic advice like "Improve engagement".
- Actionable Recommendations must contain precise instructions. E.g. "Move Slide 5 to Slide 2 to maintain flow", "Change the question text to 'What is your main takeaway?'".
- If suggesting a content change, YOU MUST PROVIDE THE NEW CONTENT EXACTLY.
- ALWAYS include a 'coaching_message' that is positive, encouraging, and summarizes the key insight for this task.

Slide types:
- Quiz slide types: `Correct Order`, `Match Pairs`, `Categorise`, `Pick Answer`, `Short Answer`
- Non-quiz slide types: `Word Cloud`, `Open Ended`, `Brainstorm`, `Scales`, `Poll`

Tones:
- Playful yet scientific
- Above and beyond: make the presenter feel proud of the session results
- The insight should very exciting, encouraging and persuative, inspiring for next actions
"""

COACH_PROMPT = """
You are a supportive and encouraging presentation coach.
Your goal is to summarize the provided insights into a single, positive, and motivating message for the presenter.
Focus on:
- Highlighting strengths and good engagement.
- Framing improvements as exciting opportunities with concrete examples (e.g. "Try asking X instead of Y").
- Using a tone that makes the presenter feel proud and inspired.
- Keep it concise but impactful.
"""
