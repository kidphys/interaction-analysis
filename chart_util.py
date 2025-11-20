import altair as alt


def map_data_with_audience_category(selected_slide, df):
    slide_type = df[df['Slideid'] == selected_slide['Slideid']]['Slidetypenormalized'].iloc[0]
    if slide_type == 'Poll':
        audience_df = df[df['Slideid'] == selected_slide['Slideid']][['Audience Name', 'Chosen Poll']]
        audience_df['Chosen Poll'] = audience_df['Chosen Poll'].fillna('No Category')
        data = df.merge(audience_df, on='Audience Name', how='left')
        data.rename(columns={'Chosen Poll_y': 'Category'}, inplace=True)
        return data
    if slide_type == 'Pick Answer':
        audience_df = df[df['Slideid'] == selected_slide['Slideid']][['Audience Name', 'Correct']]
        slide_title = df[df['Slideid'] == selected_slide['Slideid']]['Slidetitle'].iloc[0]
        audience_df['Correct'] = audience_df['Correct'].fillna('No Category')
        audience_df['Correct'] = audience_df['Correct'].apply(lambda x: f'Answered Correctly to `{slide_title}`' if x == 'correct' else f'Answered Incorrectly to `{slide_title}`')
        data = df.merge(audience_df, on='Audience Name', how='left')
        data.rename(columns={'Correct_y': 'Category'}, inplace=True)
        return data



def create_segment_line_chart(data, y_field='Interaction Count', title='Empty', type='number'):
    if type == 'percent':
        y_field_tool_tip = alt.Tooltip(f'{y_field}:Q', format='.2~%')
    elif type == 'number':
        y_field_tool_tip = alt.Tooltip(f'{y_field}:Q', format='.2~f')
    else:
        raise ValueError(f'Invalid type: {type}')

    chart = alt.Chart(data).mark_line(
            size=2,
            point=alt.OverlayMarkDef(filled=True, size=80)
            ).encode(
        x=alt.X('# Slidetitle:N', title='Slide Title',
                sort=alt.EncodingSortField(field='Slideorder', op='min', order='ascending'),
                axis=alt.Axis(ticks=True, tickBand='center', labelAngle=-45),   # Rotate x-axis labels to make them easier to read
        ),
        y=f'{y_field}:Q',  # count of interactions as the y-axis
        color='Segment:N',
        tooltip=['Segment:N', y_field_tool_tip, 'Slidetitle:N', alt.Tooltip('Slidetypenormalized:N', title='Slide Type')]
    ).properties(
        title=title
    )
        # Display technical options on chart
    chart = chart.copy()
    chart["usermeta"] = {
        "embedOptions": {
            "actions": {"export": True, "source": False, "compiled": False, "editor": False}
        }
    }
    return chart