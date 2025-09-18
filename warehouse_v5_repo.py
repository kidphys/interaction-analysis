from re import I
from typing import List
from redshift_api import execute
import pandas as pd
import json
import ast

def get_wrong_often_questions_v2(user_id: int):
    sql = f"""
    SELECT
    dp.title AS presentation_title,
    ds.slide_title AS slide_title,
    COUNT(CASE WHEN fa.correct = true THEN fa.id END) AS correct_count,
    COUNT(CASE WHEN fa.correct != true THEN fa.id END) AS incorrect_count,
    COUNT(fa.id) AS total_answers
    FROM aha_report_v5.fact_answers fa
    JOIN aha_report_v5.dim_questions ds
        ON fa.slide_id = ds.id
    JOIN aha_report_v5.dim_presentations dp
        ON fa.master_presentation_id = dp.id
    WHERE fa.user_id = {user_id}
    AND fa.slide_type = 'Pick Answer'
    GROUP BY ds.slide_title, dp.title
    ORDER BY total_answers DESC;
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['Presentation', 'Question', 'Correct Count', 'Incorrect Count', 'Total Answers'])


def get_total_participants_joined(presentation_id: str):
    sql = f"""
    SELECT COUNT(DISTINCT participant_id)
    FROM aha_report_v5.dim_participants dp
    WHERE master_presentation_id = {presentation_id}
    """
    rows = execute(sql)
    return rows[0][0]


def get_total_participants_submitted(presentation_id: str):
    sql = f"""
    SELECT COUNT(DISTINCT participant_id)
    FROM aha_report_v5.fact_answers fa
    WHERE master_presentation_id = {presentation_id}
    """
    rows = execute(sql)
    return rows[0][0]


def get_recent_presentations(user_id: int):
    """
    Return a list of presentation sorted by last answered createdat
    """
    sql = f"""
    SELECT fa.master_presentation_id, dp.title, MAX(fa.createdat) as last_answered_at
    FROM aha_report_v5.fact_answers fa
    JOIN aha_report_v5.dim_presentations dp
        ON fa.master_presentation_id = dp.id
    LEFT JOIN aha_report_v5.dim_deleted_answers dda
        ON fa.id = dda.id
    WHERE fa.user_id = {user_id} AND dda.id IS NULL
    GROUP BY fa.master_presentation_id, dp.title
    ORDER BY MAX(fa.createdat) DESC
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['Id', 'Title', 'Last Answered At'])


def get_average_response_time(presentation_id: str):
    """
    Return the average answer_time_seconds for all answers submitted to a presentation_id
    """
    sql = f"""
    SELECT AVG(answer_time_seconds)
    FROM aha_report_v5.fact_answers fa
    LEFT JOIN aha_report_v5.dim_deleted_answers dda
        ON fa.id = dda.id
    WHERE fa.master_presentation_id = {presentation_id} AND dda.id IS NULL
    """
    rows = execute(sql)
    return rows[0][0]


def get_most_engaging_slides(presentation_id: str):
    """
    Return the slide that have the most number of participants submitted answers
    If there are a tie, pick the most recent answered slide
    """
    sql = f"""
    SELECT fa.slide_id, ds.slide_title, COUNT(DISTINCT participant_id) AS total_participants
    FROM aha_report_v5.fact_answers fa
    JOIN aha_report_v5.dim_questions ds
        ON fa.slide_id = ds.id
    LEFT JOIN aha_report_v5.dim_deleted_answers dda
        ON fa.id = dda.id
    WHERE fa.master_presentation_id = {presentation_id} AND dda.id IS NULL
    GROUP BY fa.slide_id, ds.slide_title
    ORDER BY total_participants DESC, MAX(fa.createdat) DESC
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['Slide Id', 'Title', 'Total Participants'])


def get_total_submissions(presentation_id: str):
    """
    Return the total of submissions for this presentation, along with the total number of participants
    """
    sql = f"""
    SELECT COUNT(fa.id), COUNT(DISTINCT participant_id) AS total_participants
    FROM aha_report_v5.fact_answers fa
    LEFT JOIN aha_report_v5.dim_deleted_answers dda
        ON fa.id = dda.id
    WHERE fa.master_presentation_id = {presentation_id} AND dda.id IS NULL
    """
    rows = execute(sql)
    df = pd.DataFrame(rows, columns=['Total Submissions', 'Total Participants'])
    df['Submission Ratio'] = df['Total Submissions'] / df['Total Participants']
    return df


def get_all_answers_full(presentation_id):
    """
    Return all the answers from a presentation, with dim presentation / slide
    """
    sql = f"""
    SELECT fa.id, fa.slide_id, fa.participant_id, fa.createdat, fa.correct, fa.answer_time_seconds, fa.submitted_answer_text,
    dp.title as presentation_title,
    dq.slide_title,
    dq.slide_order,
    fa.slide_type,
    dpa.name,
    dpa.email
    FROM aha_report_v5.fact_answers fa
    JOIN aha_report_v5.dim_presentations dp
        ON fa.master_presentation_id = dp.id
    JOIN aha_report_v5.dim_questions dq
        ON fa.slide_id = dq.id
    JOIN aha_report_v5.dim_participants dpa
        ON fa.participant_id = dpa.participant_id
    LEFT JOIN aha_report_v5.dim_deleted_answers dda
        ON fa.id = dda.id
    WHERE fa.master_presentation_id = {presentation_id}
    AND dda.id IS NULL
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['Id', 'Slide Id', 'Participant Id', 'Created At', 'Correct', 'Answer Time Seconds', 'Answer Text', 'Presentation Title', 'Slide Title', 'Slide Order', 'Slide Type', 'Participant Name', 'Participant Email'])

class PresentationData:

    def __init__(self, presentation_id: str):
        self.presentation_id = presentation_id
        self.df = get_all_answers_full(presentation_id)
        self.total_participants = get_total_participants_joined(presentation_id)

    def get_total_submissions(self):
        return self.df['Id'].nunique()

    def get_total_participants_submitted(self):
        return self.df['Participant Id'].nunique()

    def get_engagement_rate(self):
        return self.get_total_participants_submitted() / self.total_participants * 100

    def get_slides_engagement_stats(self):
        df = self.df.copy()
        df['CorrectCount'] = df['Correct'].apply(lambda r: 1 if r else 0)
        slide_df = df.groupby(['Slide Id', 'Slide Title', 'Slide Order', 'Slide Type']).agg({
            'Participant Id': 'nunique',
            'Answer Time Seconds': 'mean',
            'CorrectCount': 'sum',
            'Id': 'count'  # Total submissions per slide
        }).reset_index()
        slide_df['Engagement Rate'] = slide_df['Participant Id'] / self.total_participants * 100
        slide_df['Accuracy'] = slide_df['CorrectCount'] / slide_df['Id'] * 100  # Correct answers / total answers

        def get_status(engagement_rate):
            # Determine engagement status
            if engagement_rate >= 90:
                return "🟢 Excellent"
            elif engagement_rate >= 80:
                return "🟢 Good"
            elif engagement_rate >= 60:
                return "🟡 Attention"
            else:
                return "🔴 Needs Work"

        slide_df['Status'] = slide_df['Engagement Rate'].apply(get_status)
        # Sort by slide order to maintain proper sequence
        slide_df = slide_df.sort_values('Slide Order').reset_index(drop=True)
        return slide_df

    def get_most_engaging_slide(self):
        slide_df = self.get_slides_engagement_stats()
        slide = slide_df[slide_df['Engagement Rate'] == slide_df['Engagement Rate'].max()]
        return slide.iloc[0].to_dict()

    def get_slides_need_attention_count(self, threshold=60):
        slide_df = self.get_slides_engagement_stats()
        return len(slide_df[slide_df['Engagement Rate'] < threshold])

    def get_total_slides_count(self):
        slide_df = self.get_slides_engagement_stats()
        return len(slide_df)

    def get_average_response_time(self):
        return self.df['Answer Time Seconds'].mean()

    def get_slides_performance_table(self):
        """
        Return a formatted table ready for display with all calculated metrics
        """
        slide_stats_df = self.get_slides_engagement_stats()

        table_data = []
        for _, slide in slide_stats_df.iterrows():
            slide_index = slide['Slide Order']
            slide_title = slide['Slide Title']
            slide_type = slide['Slide Type']
            participants = int(slide['Participant Id'])
            avg_time = slide['Answer Time Seconds']
            engagement_rate = slide['Engagement Rate']
            accuracy = slide['Accuracy']
            status = slide['Status']

            # Calculate participation percentage
            participation_percentage = (participants / self.total_participants) * 100

            table_data.append({
                "Slide": f"Slide {int(slide_index)}: {slide_title}",
                "Type": slide_type,
                "Engagement Rate": f"{engagement_rate:.1f}%",
                "Participation": f"{participation_percentage:.0f}% ({participants}/{self.total_participants})",
                "Response Time": f"{avg_time:.1f}s",
                "Submissions": f"{participants}",
                "Accuracy": f"{accuracy:.1f}%",
                "Status": status
            })

        return table_data

    def get_participant_performance_stats(self):
        """
        Return participant-level performance statistics
        """
        participant_df = self.df.copy()
        participant_df['CorrectCount'] = participant_df['Correct'].apply(lambda r: 1 if r else 0)

        # Group by participant to calculate metrics
        participant_stats = participant_df.groupby(['Participant Id', 'Participant Name', 'Participant Email']).agg({
            'Id': 'count',  # Total submissions
            'CorrectCount': 'sum',  # Correct answers
            'Answer Time Seconds': 'mean',  # Average response time
            'Created At': ['min', 'max'],  # First and last activity
            'Slide Id': 'nunique'  # Number of unique slides answered
        }).reset_index()

        # Flatten column names
        participant_stats.columns = ['Participant Id', 'Participant Name', 'Participant Email', 'Total Submissions', 'Correct Answers',
                                   'Avg Response Time', 'First Activity', 'Last Activity', 'Slides Answered']

        # Calculate metrics
        total_slides = self.get_total_slides_count()
        participant_stats['Response Rate'] = (participant_stats['Slides Answered'] / total_slides) * 100
        participant_stats['Accuracy'] = (participant_stats['Correct Answers'] / participant_stats['Total Submissions']) * 100

        # Determine status based on response rate
        def get_participant_status(response_rate):
            if response_rate >= 90:
                return "Active"
            elif response_rate >= 50:
                return "Moderate"
            else:
                return "Inactive"

        participant_stats['Status'] = participant_stats['Response Rate'].apply(get_participant_status)

        # Sort by response rate descending
        participant_stats = participant_stats.sort_values('Response Rate', ascending=False).reset_index(drop=True)

        return participant_stats

    def get_participant_engagement_summary(self):
        """
        Return summary metrics for participant engagement
        """
        participant_stats = self.get_participant_performance_stats()

        active_participants = len(participant_stats[participant_stats['Status'] != 'Inactive'])
        avg_response_rate = participant_stats['Response Rate'].mean()
        avg_response_time = participant_stats['Avg Response Time'].mean()
        total_qa_questions = self.df[self.df['Slide Type'].isin(['Pick Answer', 'Type Answer'])]['Slide Id'].nunique()

        return {
            'active_participants': active_participants,
            'avg_response_rate': avg_response_rate,
            'avg_response_time': avg_response_time,
            'total_qa_questions': total_qa_questions
        }

    def get_participant_performance_table(self):
        """
        Return formatted participant performance table ready for display
        """
        participant_stats = self.get_participant_performance_stats()

        # Get slide engagement data to find most/least engaged slides
        slide_stats = self.get_slides_engagement_stats()
        most_engaged_slide = slide_stats.loc[slide_stats['Engagement Rate'].idxmax()]
        least_engaged_slide = slide_stats.loc[slide_stats['Engagement Rate'].idxmin()]

        table_data = []
        for _, participant in participant_stats.iterrows():
            participant_id = participant['Participant Id']
            status = participant['Status']
            response_rate = participant['Response Rate']
            total_submissions = participant['Total Submissions']
            slides_answered = participant['Slides Answered']
            accuracy = participant['Accuracy']
            avg_response_time = participant['Avg Response Time']
            first_activity = participant['First Activity']
            last_activity = participant['Last Activity']

            # Format times
            import pandas as pd
            if pd.notna(first_activity):
                joined_time = pd.to_datetime(first_activity).strftime('%H:%M')
            else:
                joined_time = "N/A"

            if pd.notna(last_activity):
                last_time = pd.to_datetime(last_activity).strftime('%H:%M AM')
            else:
                last_time = "N/A"

            # Determine most/least engaged slide for this participant
            participant_data = self.df[self.df['Participant Id'] == participant_id]
            if not participant_data.empty:
                # Get slides this participant answered
                participant_slides = participant_data['Slide Order'].unique()
                most_slide = f"Slide {int(most_engaged_slide['Slide Order'])}"
                least_slide = f"Slide {int(least_engaged_slide['Slide Order'])}"
            else:
                most_slide = "N/A"
                least_slide = "N/A"

            table_data.append({
                "Participant": f"{participant['Participant Name']}",
                "Email": f"{participant['Participant Email']}",
                "Status": status,
                "Response Rate": f"{response_rate:.0f}% ({slides_answered}/{self.get_total_slides_count()})",
                "Accuracy": f"{accuracy:.0f}%" if pd.notna(accuracy) else "N/A",
                "Avg Response Time": f"{avg_response_time:.1f}s",
                "Q&A Questions": int(total_submissions),
                "Most/Least Engaged": f"👍 {most_slide}\n💤 {least_slide}",
                "Session Time": f"Joined: {joined_time}\nLast: {last_time}"
            })

        return table_data


# def get_presentations_stats(user_id: int):
#     sql = f"""
#     SELECT
#     dp.title AS presentation_title,
#     COUNT(DISTINCT fa.slide_id) AS total_slides,
#     COUNT(DISTINCT fa.user_id) AS total_participants,
#     COUNT(DISTINCT fa.id) AS total_answers
#     FROM aha_report_v5.fact_answers fa
#     JOIN aha_report_v5.dim_presentations dp
#         ON fa.master_presentation_id = dp.id
#     WHERE fa.user_id = {user_id}
#     GROUP BY dp.title;
#     """