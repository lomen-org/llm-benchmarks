from flask import Flask, jsonify
import plotly.graph_objs as go
import pandas as pd
import json

app = Flask(__name__)

# Load your evaluation results
with open('evaluation_results.json') as f:
    data = json.load(f)

# Convert to DataFrame
df = pd.DataFrame(data)

@app.route('/')
def index():
    # Prepare data (handle missing scores)
    df_clean = df.dropna(subset=['score'])

    # Score distribution
    score_hist = go.Figure(data=[go.Histogram(x=df_clean['score'], nbinsx=20)])
    score_hist.update_layout(title='Score Distribution', xaxis_title='Score', yaxis_title='Count')

    # Scatter plot: Score per response
    scatter = go.Figure(data=[
        go.Scatter(
            x=list(range(len(df_clean))),
            y=df_clean['score'],
            mode='markers',
            marker=dict(size=8),
            text=df_clean.apply(
                lambda row: (
                    f"Prompt: {row['prompt']}\n"
                    f"Expected: {row.get('expected', 'N/A')}\n"
                    f"Actual: {row.get('actual', 'N/A')}\n"
                    f"Score: {row['score']}\n"
                    f"Reason: {row.get('scoreReasoning', 'N/A')}"
                ),
                axis=1
            ),
            hoverinfo='text'
        )
    ])
    scatter.update_layout(title='Score per Response', xaxis_title='Response Index', yaxis_title='Score')

    # Convert plots to HTML
    score_hist_html = score_hist.to_html(full_html=False)
    scatter_html = scatter.to_html(full_html=False)

    # Simple HTML template
    html = f"""
    <html>
    <head><title>Evaluation Dashboard</title></head>
    <body>
        <h1>Evaluation Results Dashboard</h1>
        <h2>Score Distribution</h2>
        {score_hist_html}
        <h2>Score per Response (with details on hover)</h2>
        {scatter_html}
    </body>
    </html>
    """
    return html

@app.route('/api/data')
def api_data():
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
