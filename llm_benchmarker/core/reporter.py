import html
import json
import os
from typing import List, Dict, Any, Optional
# Ensure Jinja2 is imported
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Helper function (optional, as Jinja2 handles escaping)
def escape(text: Optional[Any]) -> str:
    """Safely converts value to string and escapes HTML."""
    if text is None:
        return ""
    return html.escape(str(text))

def generate_html_report(
    summary_report: Dict[str, Any],
    structured_results: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generates an HTML report string from the benchmark summary and results
    using the report_template.html Jinja2 template.

    Args:
        summary_report: The summary report dictionary from the aggregator.
        structured_results: The list of structured results (grouped conversations
                            and single prompts) from the aggregator.
        config: Optional configuration dictionary (currently unused).

    Returns:
        A string containing the rendered HTML report.

    Raises:
        FileNotFoundError: If the template file cannot be found.
        Exception: If there's an error during template rendering.
    """
    try:
        # Set up Jinja2 environment
        template_dir = os.path.dirname(os.path.abspath(__file__))
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']) # Enable autoescaping for security
        )
        # Add the tojson filter which is needed in the template
        env.filters['tojson'] = json.dumps

        # Load the template
        template = env.get_template("report_template.html")

        # Prepare data for the template
        summary_data = summary_report.get("overall_summary", {})

        # Serialize the detailed results to JSON string.
        # Jinja2's |tojson filter in the template handles final embedding and escaping.
        try:
            # No need to dump here, pass the Python object directly
            # The |tojson filter in the template will handle serialization
            results_for_template = structured_results
        except Exception as e:
            print(f"Error preparing results data for template: {e}")
            results_for_template = [] # Pass empty list on error

        # Render the template with the data
        rendered_html = template.render(
            summary=summary_data,
            results_json=results_for_template # Pass the Python list/dict directly
        )
        return rendered_html

    except FileNotFoundError:
        print(f"Error: Template file 'report_template.html' not found in {template_dir}")
        # Return a basic error message or re-raise
        return "<html><body><h1>Error: Report template not found.</h1></body></html>"
    except Exception as e:
        print(f"Error rendering HTML report with Jinja2: {e}")
        # Return a basic error message
        return f"<html><body><h1>Error generating report</h1><p>{escape(str(e))}</p></body></html>"
