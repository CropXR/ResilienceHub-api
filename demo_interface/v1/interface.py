import gradio as gr
import requests
import json
import logging
import re
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.token = None
        self.logger = logger

    def login(self, username: str, password: str) -> str:
        """Handle Django token authentication"""
        url = f"{self.base_url}/token/"
        payload = {"username": username, "password": password}
        
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                self.token = response.json().get("token")
                if self.token:
                    self.session.headers.update({
                        "Authorization": f"Token {self.token}",
                        "Content-Type": "application/json"
                    })
                    return "Login successful"
            return f"Login failed: {response.text}"
        except Exception as e:
            return f"Login error: {str(e)}"

    def logout(self) -> str:
        """Handle logout by clearing the token and session headers"""
        self.token = None
        self.session.headers.clear()
        return "Logged out successfully"

    def get_entity_details(self, accession_code: str) -> dict:
        """Get detailed information for a specific entity"""
        if not self.token:
            return {"error": "Not authenticated"}
        
        url = f"{self.base_url}/{accession_code}/"
        
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Failed to fetch entity. Status: {response.status_code}"}
        except Exception as e:
            return {"error": f"Error fetching entity: {str(e)}"}
    
    def get_all_investigations(self, page=1) -> dict:
        """Get a list of all available investigations with pagination"""
        if not self.token:
            return {"error": "Not authenticated"}
        
        url = f"{self.base_url}/investigations/?page={page}"
        
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Failed to fetch investigations. Status: {response.status_code}"}
        except Exception as e:
            return {"error": f"Error fetching investigations: {str(e)}"}

# Create global API client instance
api_client = APIClient()

# Tracking the current view state
current_view = {
    "type": "investigations",  # "investigations", "investigation", "study", "assay"
    "page": 1,
    "accession": None,  # Current entity accession if applicable
    "total_pages": 1
}

def paginate_list(items, page=1, per_page=10):
    """Simple client-side pagination for lists (studies, assays)"""
    start = (page - 1) * per_page
    end = start + per_page
    
    # Calculate total pages
    total_pages = (len(items) + per_page - 1) // per_page
    
    # Get items for current page
    paged_items = items[start:end]
    
    # Determine if previous/next exists
    prev_exists = page > 1
    next_exists = page < total_pages
    
    return paged_items, total_pages, prev_exists, next_exists

def lookup_entity(accession, page=1):
    """Handle the lookup of an entity and return formatted data for display"""
    global current_view
    
    if not api_client.token:
        return [], [], [], "Child Accessions (Please login to view)", "Page 0 of 0", gr.Button(value="Previous Page", interactive=False), gr.Button(value="Next Page", interactive=False), 1

    # Handle empty accession case - load all investigations
    if not accession or accession.strip() == "":
        data, label, page_info_val, prev_active, next_active, page = load_all_investigations(page)
        return [], data, [], label, page_info_val, gr.Button(value="Previous Page", interactive=prev_active), gr.Button(value="Next Page", interactive=next_active), page
    
    if re.match(r'^CXRP\d+$', accession):
        # Investigation lookup
        details = api_client.get_entity_details(accession)
        if 'error' in details:
            return [], [], [], "Error", "Page 0 of 0", gr.Button(value="Previous Page", interactive=False), gr.Button(value="Next Page", interactive=False), 1
        
        inv_data = [
            ["Investigation", details.get('accession_code', 'N/A')],
            ["Title", details.get('title', 'N/A')],
            ["Description", details.get('description', 'N/A')],
            ["Submission Date", details.get('submission_date', 'N/A')],
            ["Public Release Date", details.get('public_release_date', 'N/A')]
        ]
        
        # Get all studies
        all_studies = [
            [code, title]
            for code, title in details.get('studies', [])
        ]
        
        # Paginate studies
        paged_studies, total_pages, prev_exists, next_exists = paginate_list(all_studies, page)
        
        # Update current view state
        current_view = {
            "type": "investigation",
            "page": page,
            "accession": accession,
            "total_pages": total_pages
        }
        
        accession_data = []
        
        page_info = f"Page {page} of {total_pages}"
        label = f"Studies for {details.get('accession_code')} ({len(all_studies)} total)"
        
        prev_btn = gr.Button(value="Previous Page", interactive=prev_exists)
        next_btn = gr.Button(value="Next Page", interactive=next_exists)
        
        return inv_data, paged_studies, accession_data, label, page_info, prev_btn, next_btn, page
    
    elif re.match(r'^CXRS\d+$', accession):
        # Study lookup
        details = api_client.get_entity_details(accession)
        if 'error' in details:
            return [], [], [], "Error", "Page 0 of 0", gr.Button(value="Previous Page", interactive=False), gr.Button(value="Next Page", interactive=False), 1
            
        inv_data = [
            ["Accession", details.get('accession_code', 'N/A')],
            ["Study Label", details.get('study_label', 'N/A')],
            ["Title", details.get('title', 'N/A')],
            ["Description", details.get('description', 'N/A')],
            ["Submission Date", details.get('submission_date', 'N/A')],
            ["Study Design", details.get('study_design', 'N/A')]
        ]
        
        # Get all assays
        all_assays = [
            [code, measurement_type]
            for code, measurement_type in details.get('assays', [])
        ]
        
        # Paginate assays
        paged_assays, total_pages, prev_exists, next_exists = paginate_list(all_assays, page)
        
        # Update current view state
        current_view = {
            "type": "study",
            "page": page,
            "accession": accession,
            "total_pages": total_pages
        }
        
        accession_data = [
            [details.get('investigation_accession', 'N/A'), "Investigation"]
        ]
        
        page_info = f"Page {page} of {total_pages}"
        label = f"Assays for {details.get('accession_code')} ({len(all_assays)} total)"
        
        prev_btn = gr.Button(value="Previous Page", interactive=prev_exists)
        next_btn = gr.Button(value="Next Page", interactive=next_exists)
        
        return inv_data, paged_assays, accession_data, label, page_info, prev_btn, next_btn, page

    elif re.match(r'^CXRA\d+$', accession):
        # Assay lookup
        details = api_client.get_entity_details(accession)
        if 'error' in details:
            return [], [], [], "Error", "Page 0 of 0", gr.Button(value="Previous Page", interactive=False), gr.Button(value="Next Page", interactive=False), 1
            
        inv_data = [
            ["Assay Accession", details.get('accession_code', 'N/A')],
            ["Measurement Type", details.get('measurement_type', 'N/A')],
            ["Technology Platform", details.get('technology_platform', 'N/A')],
            ["Technology Type", details.get('technology_type', 'N/A')],
            ["Description", details.get('description', 'N/A')]
        ]
        
        # Assays don't have child elements, so nested_data is empty
        nested_data = []
        
        # Update current view state
        current_view = {
            "type": "assay",
            "page": 1,
            "accession": accession,
            "total_pages": 1
        }
        
        # Parent accessions
        accession_data = [
            [details.get('investigation_accession', 'N/A'), "Investigation"],
            [details.get('study_accession', 'N/A'), "Study"]
        ]
        
        page_info = "No pagination"
        label = "Assay Details"
        
        prev_btn = gr.Button(value="Previous Page", interactive=False)
        next_btn = gr.Button(value="Next Page", interactive=False)
        
        return inv_data, nested_data, accession_data, label, page_info, prev_btn, next_btn, 1
    
    # If accession doesn't match any known pattern
    return [], [], [], "Unknown Accession", "Page 0 of 0", gr.Button(value="Previous Page", interactive=False), gr.Button(value="Next Page", interactive=False), 1

def load_all_investigations(page=1):
    """Load all investigations with pagination"""
    global current_view
    
    if not api_client.token:
        # Return empty data and update label
        formatted_data = []
        label = "Child Accessions (Please login to view)"
        page_info = "Page 0 of 0"
        current_view = {
            "type": "investigations",
            "page": 1,
            "accession": None,
            "total_pages": 0
        }
        return formatted_data, label, page_info, False, False, page
    else:
        investigations = api_client.get_all_investigations(page=page)
        if 'error' in investigations:
            # Return error message
            formatted_data = []
            label = f"Child Accessions (Error: {investigations['error']})"
            page_info = f"Page {page} of 0"
            current_view = {
                "type": "investigations",
                "page": page,
                "accession": None,
                "total_pages": 0
            }
            return formatted_data, label, page_info, False, False, page
        else:
            # Extract items and format for display
            items = investigations.get('results', [])
            
            # Format according to the dataframe structure
            formatted_data = [
                [item.get('accession_code', 'N/A'), item.get('title', 'N/A')]
                for item in items
            ]
            
            # Update label to show pagination info
            count = investigations.get('count', 0)
            next_page_exists = investigations.get('next', None) is not None
            prev_page_exists = investigations.get('previous', None) is not None
            
            start_item = (page - 1) * 10 + 1 if count > 0 else 0
            end_item = min(page * 10, count)
            
            # Calculate total pages
            total_pages = (count + 9) // 10  # Ceiling division by 10
            
            pagination_info = f" (showing {start_item}-{end_item} of {count})" if count > 0 else ""
            label = f"All Investigations{pagination_info}"
            page_info = f"Page {page} of {total_pages}"
            
            # Update current view state
            current_view = {
                "type": "investigations",
                "page": page,
                "accession": None,
                "total_pages": total_pages
            }
            
    return formatted_data, label, page_info, prev_page_exists, next_page_exists, page

def handle_row_click(evt: gr.SelectData, row):
    """Handle row clicks for both tables"""
    if not row.empty:
        # Since we now only have accession codes, get it directly from first column
        accession = row.iloc[evt.index[0], 0]  # Get first column value from clicked row
        
        # Reset to page 1 when clicking a new entity
        return lookup_entity(accession, 1)
    
    return [], [], [], "No Selection", "Page 0 of 0", gr.Button(value="Previous Page", interactive=False), gr.Button(value="Next Page", interactive=False), 1

def after_login(status_msg):
    """After login, load all investigations if login was successful"""
    if "successful" in status_msg:
        # If login is successful, reset to page 1
        return status_msg, 1
    # If login failed, return empty data
    return status_msg, 1

def navigate_prev(current_page_val):
    """Navigate to previous page based on current view"""
    global current_view
    
    new_page = max(1, int(current_page_val) - 1)
    
    # Handle navigation based on current view type
    if current_view["type"] == "investigations":
        data, label, page_info, prev_active, next_active, page = load_all_investigations(new_page)
        return new_page, data, label, page_info, gr.Button(value="Previous Page", interactive=prev_active), gr.Button(value="Next Page", interactive=next_active), [], []
    elif current_view["type"] in ["investigation", "study"]:
        # For entity-specific views, reload with new page
        details, nested_data, accession_data, label, page_info, prev_btn, next_btn, page = lookup_entity(current_view["accession"], new_page)
        return new_page, nested_data, label, page_info, prev_btn, next_btn, details, accession_data
    
    # Fallback
    return current_page_val, [], "No Data", "Page 0 of 0", gr.Button(value="Previous Page", interactive=False), gr.Button(value="Next Page", interactive=False), [], []

def navigate_next(current_page_val):
    """Navigate to next page based on current view"""
    global current_view
    
    new_page = int(current_page_val) + 1
    
    # Handle navigation based on current view type
    if current_view["type"] == "investigations":
        data, label, page_info, prev_active, next_active, page = load_all_investigations(new_page)
        return new_page, data, label, page_info, gr.Button(value="Previous Page", interactive=prev_active), gr.Button(value="Next Page", interactive=next_active), [], []
    elif current_view["type"] in ["investigation", "study"]:
        # For entity-specific views, reload with new page
        details, nested_data, accession_data, label, page_info, prev_btn, next_btn, page = lookup_entity(current_view["accession"], new_page)
        return new_page, nested_data, label, page_info, prev_btn, next_btn, details, accession_data
    
    # Fallback
    return current_page_val, [], "No Data", "Page 0 of 0", gr.Button(value="Previous Page", interactive=False), gr.Button(value="Next Page", interactive=False), [], []

# Create the Gradio interface
with gr.Blocks(title="ResilienceHub Browser") as demo:
    gr.Markdown("# ResilienceHub Browser")
    
    # State variables for pagination
    current_page = gr.State(value=1)
            
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Row():
                username = gr.Textbox(label="Username")
                password = gr.Textbox(label="Password", type="password")
            with gr.Row():
                login_btn = gr.Button("Login")
                logout_btn = gr.Button("Logout")
        
        with gr.Column(scale=2):
            status = gr.Textbox(label="Login Status")
        
        with gr.Column(scale=3):
            accession_input = gr.Textbox(label="Accession Code", value="CXRP1")
            lookup_btn = gr.Button("Look Up")
    
    # Investigations view
    with gr.Row() as investigations_view:
        with gr.Column():
            accession_fields = gr.DataFrame(
                headers=["Accession", "Title"],
                label="Parent Accessions",
                wrap=True,
                interactive=False,
            )
        with gr.Column():
            nested_list_label = gr.Markdown("Child Accessions")
            nested_list = gr.DataFrame(
                headers=["Accession", "Title"],
                label="",
                wrap=True,
                interactive=False,
            )
    

            with gr.Row():
                prev_page_btn = gr.Button("Previous Page", interactive=False)
                page_info = gr.Textbox(value="Page 0 of 0", label="", interactive=False)
                next_page_btn = gr.Button("Next Page", interactive=False)
    
    with gr.Row():
        inv_details = gr.DataFrame(
            headers=["Field", "Value"],
            label="Details",
            wrap=True,
            interactive=False,
        )

    # Initial load function that returns correct button states
    def init_load():
        data, label, page_info_val, prev_active, next_active, page = load_all_investigations(1)
        return data, label, page_info_val, gr.Button(value="Previous Page", interactive=prev_active), gr.Button(value="Next Page", interactive=next_active), page
    
    # Bind handlers
    lookup_btn.click(
        fn=lookup_entity,
        inputs=[accession_input, gr.State(value=1)],  # Start at page 1 when manually looking up
        outputs=[inv_details, nested_list, accession_fields, nested_list_label, page_info, prev_page_btn, next_page_btn, current_page]
    )
    
    nested_list.select(
        fn=handle_row_click,
        inputs=nested_list,
        outputs=[inv_details, nested_list, accession_fields, nested_list_label, page_info, prev_page_btn, next_page_btn, current_page]
    )
    
    accession_fields.select(
        fn=handle_row_click,
        inputs=accession_fields,
        outputs=[inv_details, nested_list, accession_fields, nested_list_label, page_info, prev_page_btn, next_page_btn, current_page]
    )
    
    # Login and load investigations
    login_btn.click(
        fn=api_client.login,
        inputs=[username, password],
        outputs=status
    ).then(
        fn=after_login,
        inputs=[status],
        outputs=[status, current_page]
    ).then(
        fn=init_load,
        outputs=[nested_list, nested_list_label, page_info, prev_page_btn, next_page_btn, current_page]
    )

    logout_btn.click(
        fn=api_client.logout,
        outputs=status
    ).then(
        fn=lambda: 1,  # Reset to page 1 on logout
        outputs=current_page
    ).then(
        fn=lambda: ([], "Child Accessions (Please login to view)", "Page 0 of 0", 
                   gr.Button(value="Previous Page", interactive=False), 
                   gr.Button(value="Next Page", interactive=False), 1),
        outputs=[nested_list, nested_list_label, page_info, prev_page_btn, next_page_btn, current_page]
    )
    
    # Pagination handlers - now context-aware
    prev_page_btn.click(
        fn=navigate_prev,
        inputs=[current_page],
        outputs=[current_page, nested_list, nested_list_label, page_info, prev_page_btn, next_page_btn, inv_details, accession_fields]
    )
    
    next_page_btn.click(
        fn=navigate_next,
        inputs=[current_page],
        outputs=[current_page, nested_list, nested_list_label, page_info, prev_page_btn, next_page_btn, inv_details, accession_fields]
    )
    
    # Load investigations on startup if already logged in
    demo.load(
        fn=init_load,
        outputs=[nested_list, nested_list_label, page_info, prev_page_btn, next_page_btn, current_page]
    )

if __name__ == "__main__":
    demo.launch(debug=False)