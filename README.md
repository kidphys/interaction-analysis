# Event Analysis Dashboard

A comprehensive dashboard for analyzing presentation interactions and events with filtering capabilities and time-series visualizations.

## Features

### 📊 **Event Analysis**
- **Event Count Over Time**: Line chart showing the number of events occurring over time
- **Distinct Properties Count Over Time**: Line chart showing the count of unique properties (event types, slide types, audiences, slides) over time
- **Interactive Time Granularity**: Choose between hourly, daily, or custom time intervals

### 🔍 **Advanced Filtering**
- **Event Type**: Filter by interaction source (opinion, answer, reaction, qa_submission)
- **Slide Type**: Filter by slide type (Poll, Brainstorm, Open Ended, Pick Answer)
- **Presentation**: Filter by specific presentation names
- **Team**: Filter by team names
- **Audience**: Filter by audience names
- **Reaction Type**: Filter by specific reaction types (like, heart, wow)

### 📈 **Key Metrics**
- Total Events count with delta indicators
- Unique Audiences count
- Unique Slides count
- Event Types count
- Peak events and properties analysis
- Average events and properties per time period

### 📋 **Data Preview**
- Filtered data table showing relevant columns
- Real-time updates based on applied filters
- Export capabilities through Streamlit

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the dashboard:**
   ```bash
   streamlit run event_analysis_dashboard.py
   ```

3. **Open your browser** and navigate to the URL shown in the terminal (usually `http://localhost:8501`)

## Usage Guide

### 1. **Data Selection**
- Use the sidebar to select from available data files:
  - Sample Data (sample_presentation_data.csv)
  - Dave Presentation (dave_presentation_interactions.csv)
  - Duke Presentation (duke_presentation_interactions.csv)

### 2. **Applying Filters**
- **Event Type**: Choose specific interaction types (e.g., only show poll responses)
- **Slide Type**: Filter by slide categories (e.g., only show quiz slides)
- **Presentation**: Focus on specific presentations
- **Team**: Analyze team-specific interactions
- **Audience**: Focus on specific audience segments
- **Reaction Type**: Analyze specific reaction patterns

### 3. **Time Analysis**
- **Time Granularity**: Select how to group time intervals:
  - 1H: Hourly analysis
  - 2H: 2-hour intervals
  - 4H: 4-hour intervals
  - 6H: 6-hour intervals
  - 12H: 12-hour intervals
  - 1D: Daily analysis

### 4. **Interpreting Charts**
- **Top Chart**: Shows event frequency over time
- **Bottom Chart**: Shows diversity of properties over time
- **Peaks**: Indicate high-engagement periods
- **Patterns**: Help identify trends and user behavior

## Data Structure

The dashboard works with CSV files containing the following key columns:

- **`Createdat`**: Event timestamp (primary time column)
- **`Interaction Source`**: Type of interaction (opinion, answer, reaction, qa_submission)
- **`Slidetypenormalized`**: Normalized slide type
- **`Slidetitle`**: Title of the slide
- **`Audienceid`**: Unique audience identifier
- **`Audience Name`**: Name of the audience member
- **`Team Name`**: Team identifier
- **`Presentation Name`**: Name of the presentation
- **`Reactiontype`**: Type of reaction (if applicable)

## Customization

### Adding New Filters
To add new filterable properties, modify the `get_event_properties()` function in `event_analysis_dashboard.py`:

```python
def get_event_properties(df):
    properties = {}
    # Add your new property here
    if 'Your_Column' in df.columns:
        properties['Your Property'] = df['Your_Column'].unique().tolist()
    return properties
```

### Modifying Charts
To customize the visualizations, edit the `create_charts()` function:

```python
def create_charts(event_counts, distinct_properties, filters_applied):
    # Modify chart appearance, colors, or add new chart types
    pass
```

## Troubleshooting

### Common Issues

1. **Data Loading Errors**
   - Ensure CSV files are in the same directory as the script
   - Check file permissions and format
   - Verify date column formats match expected patterns

2. **Chart Not Displaying**
   - Check if timestamp columns contain valid dates
   - Ensure filtered data is not empty
   - Verify time granularity selection

3. **Performance Issues**
   - Use smaller time granularities for large datasets
   - Apply filters to reduce data size
   - Consider sampling data for very large files

### Data Format Requirements

- **Timestamps**: Must be in format `DD-MM-YYYY, HH:MM`
- **CSV Encoding**: UTF-8 recommended
- **Missing Values**: Handled automatically with 'unknown' or 'N/A' placeholders

## Advanced Features

### Export Functionality
- Use Streamlit's built-in data export features
- Right-click on charts to save as images
- Copy filtered data to clipboard

### Real-time Updates
- Dashboard automatically refreshes when filters change
- Cached data loading for better performance
- Responsive design for different screen sizes

## Contributing

To contribute to this dashboard:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with sample data
5. Submit a pull request

## License

This project is open source and available under the MIT License.