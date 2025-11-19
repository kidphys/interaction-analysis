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
