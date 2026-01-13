from typing import NamedTuple

class AnalysisTask(NamedTuple):
    id: str
    category: str
    sql_template: str
    analysis_prompt: str

TASKS = [
    AnalysisTask(
        id="Q1.1",
        category="🧭 Slide Attention Map",
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
            - IMPORTANT: consider the slide_title and the flow of content.
        """
    ),
    AnalysisTask(
        id="Q1.2",
        category="🧭 Slide Format Effectiveness",
        sql_template="""
            WITH base AS (
              SELECT
                slide_type,
                COUNT(DISTINCT slide_id) as slide_count,
                COUNT(DISTINCT participant_id) AS participants,
                COUNT(*) AS total_answers
              FROM mart
              GROUP BY slide_type
            )
            SELECT
              slide_type,
              slide_count,
              participants,
              total_answers,
              total_answers / participants as answer_per_partipants
            FROM base
        """,
        analysis_prompt="""
            Compare participation across slide types.

            Identify:
            - Slide types that consistently attract or discourage responses
            - Whether response effort appears to differ by slide type

            Slide types context:
            - Short Answer: each participant can submit 1 answer

            Return:
            - Engagement ranking by slide type
            - Design implications for mixing slide formats
        """
    ),
    AnalysisTask(
        id="Q2.2",
        category="🧭 Learning & Quiz Impact",
        sql_template="""
            SELECT
              slide_type,
              AVG(CASE WHEN correct THEN 1 ELSE 0 END) * 100 AS accuracy_percentage,
              COUNT(*) AS answers
            FROM mart
            WHERE slide_category = 'Quiz'
            GROUP BY slide_type;
        """,
        analysis_prompt="""
            Compare accuracy across slide types where correctness applies.

            On average, accuracy percentage of the whole AhaSlides data is at about 60%. Refer to this as a benchmark.

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
        category="💬 Idea Generation Strength",
        sql_template="""
            SELECT
              slide_index,
              slide_title,
              slide_type,
              COUNT(*) AS total_responses,
              COUNT(DISTINCT answer_text) AS distinct_responses
            FROM mart
            WHERE slide_type in ('Word Cloud', 'Open Ended', 'Brainstorm', 'Short Answer')
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
            - IMPORTANT: consider the slide_title and the flow of content.
        """
    ),
    AnalysisTask(
        id="Q3.2",
        category="🗣️ Audience Voice & Sentiment",
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
            - IMPORTANT: consider the slide_title and the flow of content.
        """
    ),
    AnalysisTask(
        id="Q4.1",
        category="🩺 Slide Health Check",
        sql_template="""
WITH totals AS (
  SELECT COUNT(DISTINCT participant_id) AS total_participants
  FROM mart
),
per_slide AS (
  SELECT
    slide_index,
    slide_title,
    slide_type,
    slide_category,

    COUNT(DISTINCT participant_id) AS participants,
    COUNT(*) AS responses,

    AVG(CASE WHEN correct THEN 1 ELSE 0 END) * 100 AS accuracy_percentage,
    COUNT(DISTINCT answer_text) AS distinct_answers
  FROM mart
  GROUP BY slide_index, slide_title, slide_type, slide_category
)
SELECT
  p.slide_index,
  p.slide_title,
  p.slide_type,
  p.slide_category,

  p.participants,
  t.total_participants,
  (p.participants * 1.0 / NULLIF(t.total_participants, 0)) AS participant_rate,

  p.responses,

  -- accuracy only meaningful for quiz-like slides; hide it otherwise if you want
  CASE
    WHEN p.slide_category = 'Quiz' THEN p.accuracy_percentage
    ELSE NULL
  END AS accuracy_percentage,

  -- variability should NOT exist for Poll
  CASE
    WHEN lower(p.slide_type) = 'poll' OR lower(p.slide_category) = 'poll' THEN NULL
    ELSE (p.distinct_answers * 1.0 / NULLIF(p.participants, 0))
  END AS answer_variability_per_participant

FROM per_slide p
CROSS JOIN totals t
ORDER BY p.slide_index;

        """,
        analysis_prompt="""
            Evaluate slide health using metrics appropriate to each slide type.

            Rules:
            - Quiz slides: participation + accuracy
              - On average, accuracy percentage of the whole AhaSlides data is at about 60%. Refer to this as a benchmark.
            - Open-ended slides: participation + semantic richness
            - Word-cloud slides: response count + balance + variability
            - Short answer slides: response count + balance + variability
            - Poll slides: response count + balance
              - IMPORTANT: variability & accuracy is IRRELEVANT to Poll slides

            Classify slides as:
            - Highly effective
            - Adequate
            - Needs improvement
            - Risky or broken

            Return:
            - Slide health classification
            - Highest-priority fixes for slide_title: make it very explicit and clear what the change should be.
            - IMPORTANT: consider the slide_title when assessing the metrics.
              - Take a look at the whole flow of the presentation
              - Ask: does this slide_title have something to do with how the result is?
              - Refer to slide as both index and slide_title when giving insight
        """
    ),
    AnalysisTask(
        id="Q5.1",
        category="⏱️ Energy & Fatigue Curve",
        sql_template="""
            SELECT
              slide_index,
              slide_title,
              COUNT(DISTINCT participant_id) AS participants,
              AVG(CASE WHEN correct THEN 1 ELSE 0 END) * 100 AS accuracy_percentage
            FROM mart
            where slide_category = 'Quiz' AND id IS NOT null
            GROUP BY slide_index, slide_title
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
            - IMPORTANT: consider the slide_title and the flow of content.
        """
    ),
    AnalysisTask(
        id="Q6.1",
        category="👤 Participation Quiz Performance",
        sql_template="""
            SELECT
              participant_id,
              participant_name,
              COUNT(*) AS responses,
              AVG(CASE WHEN correct IS TRUE THEN 1.0 ELSE 0.0 END) * 100 AS accuracy_percentage
            FROM mart
            where slide_category = 'Quiz' AND id IS NOT null
            GROUP by participant_id, participant_name
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
        category="🧩 Personalized Engagement Opportunities",
        sql_template="""
WITH participation AS (
  SELECT
    participant_id,
    participant_name,
    slide_type,
    COUNT(*) AS responses,
    COUNT(DISTINCT slide_id) AS slides_joined,
    AVG(CASE WHEN correct IS TRUE THEN 1.0 ELSE 0.0 END) * 100 AS accuracy_percentage
  FROM mart
  WHERE slide_category = 'Quiz'
    AND id IS NOT NULL
  GROUP BY participant_id, participant_name, slide_type
)

SELECT
  participant_id,
  participant_name,
  slide_type,
  responses,
  slides_joined,
  responses * 100.0 / slides_joined AS response_rate,
  accuracy_percentage
FROM participation;
        """,
        analysis_prompt="""
            Analyze how participants interact with different slide types.

            Identify:
            - Slide types that attract or repel certain participants
            - Opportunities for adaptive or optional content

            NOTE:
            - `response_rate` is in percentage

            Return:
            - Key interaction patterns
            - Design recommendations for inclusive engagement
        """
    )
]

MART_SQL = """
WITH slides AS (
  SELECT
    dq.slide_id,
    dq.slide_title,
    dq.slide_type,
    dq.slide_order,
    dq.slide_content_attributes,
    dq.slide_metadata,
    ROW_NUMBER() OVER (
      ORDER BY dq.slide_order NULLS LAST, dq.slide_id
    ) AS slide_index
  FROM aha_report_v5.dim_questions dq
  WHERE dq.presentation_id = {presentation_id}
    AND deleted IS FALSE
),
fa_filtered AS (
  SELECT *
  FROM aha_report_v5.fact_answers2
  WHERE presentation_id = {presentation_id}
    AND deleted IS FALSE
),
mart as (
SELECT
    fa.id,
    s.slide_id,
    fa.participant_id,
    dp.name AS participant_name,
    fa.createdat,
    fa.correct,
    fa.is_partially_correct,
    fa.answer_time_seconds,
    fa.answer_timeout,
    fa.submitted_answer_text AS answer_text,
    COALESCE(fa.slide_type, s.slide_type) AS slide_type,
    s.slide_title,
    s.slide_order,
    s.slide_index,
    s.slide_content_attributes,
    s.slide_metadata,
    CASE
      WHEN COALESCE(fa.slide_type, s.slide_type) IN (
        'Correct Order','Match Pairs','Categorise','Pick Answer','Short Answer'
      ) THEN 'Quiz'
      WHEN COALESCE(fa.slide_type, s.slide_type) IN (
        'Word Cloud','Open Ended','Brainstorm','Scales','Poll'
      ) THEN 'Non-Quiz'
      ELSE 'Unknown'
    END AS slide_category
  FROM slides s
  LEFT JOIN fa_filtered fa
    ON fa.slide_id = s.slide_id
  LEFT JOIN aha_report_v5.dim_participants dp
    ON fa.participant_id = dp.participant_id
    )
    SELECT * FROM mart WHERE slide_category != 'Unknown' -- filter out non-interactive slides
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
- It's critical that you should provide concrete, suggestive, and specific recommendations (e.g., "Rename slide title from X to Y", "Move slide Z to earlier position"). Avoid generic advice like "Improve engagement".
- Actionable Recommendations must contain precise instructions. E.g. "Move Slide 5 to Slide 2 to maintain flow", "Change the question text to 'What is your main takeaway?'".
- If suggesting a content change, YOU MUST PROVIDE THE NEW CONTENT EXACTLY.
- ALWAYS include a 'coaching_message' that is positive, encouraging, and summarizes the key insight for this task.

Slide types:
- Quiz slide types: `Correct Order`, `Match Pairs`, `Categorise`, `Pick Answer`, `Short Answer`
- Non-quiz slide types: `Word Cloud`, `Open Ended`, `Brainstorm`, `Scales`, `Poll`. Do not analyze accuracy for these slide types.

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
