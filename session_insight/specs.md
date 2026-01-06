# Overview

This doc describe the langgraph system that can analyze a presenting session responses from multiple angles to draw meaningful insights and actionable recommendations for the presentation.

# Datamart
The datamart will be created from this query against the Redshift database. The data will be loaded into a duckdb conn to support multiple aggregation queries to run upon, each will help derive an insight about the session.

```
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
    ROW_NUMBER() OVER (ORDER BY dq.slide_order) AS slide_index
FROM aha_report_v5.fact_answers2 fa
JOIN aha_report_v5.dim_questions dq
  ON fa.slide_id = dq.slide_id
JOIN aha_report_v5.dim_participants dp
  ON fa.participant_id = dp.participant_id
WHERE fa.presentation_id = {presentation_id}
  AND fa.deleted IS FALSE
  AND dq.presentation_id = {presentation_id};
```

# Langgraph graph description
The graph may have the following nodes:
1. `Master`: this will load the datamart in to the state
2. `MapTasks`: this will dispatch all SQL queries to `Analyst` node at once to run in parallel
3. `Analyst`: this will receive the SQL input, execute the SQL to get the data and then use the insight prompt for this SQL to analyze the data to return the insights.
4. `Insight Aggregation`: receive all insights from multiple `Analyst` nodes and save to a JSON file.


# System prompt
This prompt applies to all version of `Analyst`.
```
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

Slide types:
- Quiz slide types: `Correct Order`, `Match Pairs`, `Categorise`, `Pick Answer`, `Short Answer`
- Non-quiz slide types: `Word Cloud`, `Open Ended`, `Brainstorm`, `Scales`, `Poll`
```

# Analyst prompt
Each SQL queries have a specific prompt, added to the `System prompt` to personalize the context of the insights.

The following is the pair SQL/prompt that will be hard-coded to a list that can be extended later.

## 1️⃣ PARTICIPATION & FLOW (UNIVERSAL)
### Q1.1 — Participation per slide
```
SELECT
  slide_index,
  slide_title,
  slide_type,
  COUNT(DISTINCT participant_id) AS participants
FROM mart
GROUP BY slide_index, slide_title, slide_type
ORDER BY slide_index;
```
```
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
```

### Q1.2 — Participation by slide type
```
SELECT
  slide_type,
  COUNT(DISTINCT participant_id) AS participants,
  COUNT(*) AS total_answers
FROM mart
GROUP BY slide_type;
```
```
Compare participation across slide types.

Identify:
- Slide types that consistently attract or discourage responses
- Whether response effort appears to differ by slide type

Return:
- Engagement ranking by slide type
- Design implications for mixing slide formats
```

## 2️⃣ QUIZ PERFORMANCE (QUIZ SLIDES ONLY)
### Q1.2 — Participation by slide type
```
SELECT
  slide_type,
  COUNT(DISTINCT participant_id) AS participants,
  COUNT(*) AS total_answers
FROM mart
GROUP BY slide_type;
```
```
Compare participation across slide types.

Identify:
- Slide types that consistently attract or discourage responses
- Whether response effort appears to differ by slide type

Return:
- Engagement ranking by slide type
- Design implications for mixing slide formats
```

### Q2.2 — Accuracy by quiz slide type
```
SELECT
  slide_type,
  AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy,
  COUNT(*) AS answers
FROM mart
GROUP BY slide_type;
```
```
Compare accuracy across slide types where correctness applies.

Do not compare quiz slides with expressive slide types.

Identify:
- Quiz formats that perform better or worse
- Potential causes for performance differences

Return:
- Effectiveness ranking of quiz formats
- Design recommendations
```

## 3️⃣ FREE-TEXT EXPRESSION QUALITY
### Q3.1 — Response volume & diversity per slide
```
SELECT
  slide_index,
  slide_title,
  slide_type,
  COUNT(*) AS total_responses,
  COUNT(DISTINCT answer_text) AS distinct_responses
FROM mart
GROUP BY slide_index, slide_title, slide_type;
```
```
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
```

### Q3.2 — Common free-text responses per slide
```
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
```
```
Analyze common free-text responses per slide.

Do not assume there is a correct answer.

Identify:
- Dominant themes or shared sentiments
- Signs of anchoring, priming, or herd behavior
- Off-topic or low-effort responses

Return:
- Insights into participant thinking
- Suggestions to improve prompt wording or facilitation
```

## 4️⃣ SLIDE HEALTH & QUALITY
### Q4.1 — Slide health metrics (composite view)
```
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
```
```
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
```
## 5️⃣ SESSION FLOW & FATIGUE
### Q5.1 — Engagement trend across slide order
```
SELECT
  slide_index,
  COUNT(DISTINCT participant_id) AS participants,
  AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy
FROM mart
GROUP BY slide_index
ORDER BY slide_index;
```
```
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
```
## 6️⃣ PARTICIPANT BEHAVIOR
### Q6.1 — Participant engagement profile
```
SELECT
  participant_id,
  participant_name,
  COUNT(*) AS responses,
  AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy
FROM mart
GROUP BY participant_id, participant_name;
```
```
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
```

### Q6.2 — Participant × slide type interaction
```
SELECT
  participant_id,
  participant_name,
  slide_type,
  COUNT(*) AS responses,
  AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy
FROM mart
GROUP BY participant_id, participant_name, slide_type;
```
```
Analyze how participants interact with different slide types.

Identify:
- Slide types that attract or repel certain participants
- Opportunities for adaptive or optional content

Return:
- Key interaction patterns
- Design recommendations for inclusive engagement
```


