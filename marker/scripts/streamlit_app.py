import os
import sys
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["IN_STREAMLIT"] = "true"

from marker.settings import settings
from marker.config.printer import CustomClickPrinter
from streamlit.runtime.uploaded_file_manager import UploadedFile

import base64
import io
import json
import re
import string
import tempfile
from typing import Any, Dict
import click

import pypdfium2
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered
from marker.schema import BlockTypes
# Import directly from the local file
from streamlit_utils import CustomUploadedFile, reset_file_selection, store_file_in_session, get_file_from_session

COLORS = [
    "#4e79a7",
    "#f28e2c",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc949",
    "#af7aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ab"
]

with open(
    os.path.join(os.path.dirname(__file__), "streamlit_app_blocks_viz.html"), encoding="utf-8"
) as f:
    BLOCKS_VIZ_TMPL = string.Template(f.read())


@st.cache_data()
def parse_args():
    # Use to grab common cli options
    @ConfigParser.common_options
    def options_func():
        pass

    def extract_click_params(decorated_function):
        if hasattr(decorated_function, '__click_params__'):
            return decorated_function.__click_params__
        return []

    cmd = CustomClickPrinter("Marker app.")
    extracted_params = extract_click_params(options_func)
    cmd.params.extend(extracted_params)
    ctx = click.Context(cmd)
    try:
        cmd_args = sys.argv[1:]
        cmd.parse_args(ctx, cmd_args)
        return ctx.params
    except click.exceptions.ClickException as e:
        return {"error": str(e)}

@st.cache_resource()
def load_models():
    return create_model_dict()


def convert_pdf(fname: str, config_parser: ConfigParser) -> (str, Dict[str, Any], dict):
    config_dict = config_parser.generate_config_dict()
    config_dict["pdftext_workers"] = 1
    converter_cls = PdfConverter
    converter = converter_cls(
        config=config_dict,
        artifact_dict=model_dict,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    return converter(fname)


def open_pdf(pdf_file):
    stream = io.BytesIO(pdf_file.getvalue())
    return pypdfium2.PdfDocument(stream)


def img_to_html(img, img_alt):
    img_bytes = io.BytesIO()
    # Convert RGBA to RGB if needed before saving as JPEG
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(img_bytes, format=settings.OUTPUT_IMAGE_FORMAT)
    img_bytes = img_bytes.getvalue()
    encoded = base64.b64encode(img_bytes).decode()
    img_html = f'<img src="data:image/{settings.OUTPUT_IMAGE_FORMAT.lower()};base64,{encoded}" alt="{img_alt}" style="max-width: 100%;">'
    return img_html


def markdown_insert_images(markdown, images):
    image_tags = re.findall(r'(!\[(?P<image_title>[^\]]*)\]\((?P<image_path>[^\)"\s]+)\s*([^\)]*)\))', markdown)

    for image in image_tags:
        image_markdown = image[0]
        image_alt = image[1]
        image_path = image[2]
        if image_path in images:
            markdown = markdown.replace(image_markdown, img_to_html(images[image_path], image_alt))
    return markdown


@st.cache_data()
def get_page_image(_pdf_file, page_num, dpi=96):
    if "pdf" in _pdf_file.type:
        doc = open_pdf(_pdf_file)
        page = doc[page_num]
        png_image = page.render(
            scale=dpi / 72,
        ).to_pil().convert("RGB")
    else:
        png_image = Image.open(_pdf_file).convert("RGB")
    return png_image


@st.cache_data()
def get_page_count(_pdf_file: UploadedFile):
    if "pdf" in _pdf_file.type:
        doc = open_pdf(_pdf_file)
        return len(doc) - 1
    else:
        return 1


def pillow_image_to_base64_string(img: Image) -> str:
    buffered = io.BytesIO()
    # Convert RGBA to RGB if needed before saving as JPEG
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def block_display(image: Image, blocks: dict | None = None, dpi=96):
    if blocks is None:
        blocks = {}

    image_data_url = (
        'data:image/jpeg;base64,' + pillow_image_to_base64_string(image)
    )

    template_values = {
        "image_data_url": image_data_url,
        "image_width": image.width, "image_height": image.height,
        "blocks_json": blocks, "colors_json": json.dumps(COLORS),
        "block_types_json": json.dumps({
            bt.name: i for i, bt in enumerate(BlockTypes)
        })
    }
    return components.html(
        BLOCKS_VIZ_TMPL.substitute(**template_values),
        height=image.height
    )


st.set_page_config(layout="wide")
col1, col2 = st.columns([.5, .5])

model_dict = load_models()
cli_options = parse_args()

# Make sure file_loaded is initialized
if 'file_loaded' not in st.session_state:
    st.session_state.file_loaded = False

# Make sure run_marker is initialized
if 'run_marker' not in st.session_state:
    st.session_state.run_marker = False

# Check if we need to reset everything based on URL parameter
query_params = st.query_params
if 'reset' in query_params and query_params['reset'] == 'true':
    # Clear all session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    # Initialize essential variables
    st.session_state.file_loaded = False
    st.session_state.run_marker = False
    # Set a flag to auto-open the file dialog
    st.session_state.auto_open_dialog = True
    # Remove the reset parameter from URL
    del query_params['reset']
    # No need to rerun here as the page will reload with the new URL

# Initialize session state variables if they don't exist
if 'in_file' not in st.session_state:
    st.session_state.in_file = None

# Add custom CSS for buttons
st.markdown("""
<style>
div.stButton > button {
    background-color: #2e3440;
    color: #d8dee9;
    border-radius: 5px;
    border: none;
    padding: 10px 15px;
    font-weight: bold;
    width: 100%;
}
div.stButton > button:hover {
    background-color: #3b4252;
    color: #e5e9f0;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
# Marker Demo

This app will let you try marker, a PDF or image -> Markdown, HTML, JSON converter. It works with any language, and extracts images, tables, equations, etc.

Find the project [here](https://github.com/VikParuchuri/marker).
""")

in_file = None
file_path = None

# Define a function to open the file dialog
def open_file_dialog():
    # If a file is already loaded, reset the session state first
    if st.session_state.file_loaded:
        reset_file_selection()
        
    try:
        # Try different approaches for file dialog
        selected_path = None
        
        # For Windows, use PowerShell approach directly
        if os.name == 'nt':
            try:
                import subprocess
                import tempfile
                
                # Create a temporary PowerShell script
                ps_script = tempfile.NamedTemporaryFile(suffix='.ps1', delete=False)
                ps_script.write(b'''
                Add-Type -AssemblyName System.Windows.Forms
                
                # Create and configure the OpenFileDialog
                $openFileDialog = New-Object System.Windows.Forms.OpenFileDialog
                $openFileDialog.Filter = "All Files (*.*)|*.*|PDF Files (*.pdf)|*.pdf|Image Files (*.png;*.jpg;*.jpeg;*.gif)|*.png;*.jpg;*.jpeg;*.gif"
                $openFileDialog.FilterIndex = 1
                $openFileDialog.Multiselect = $true
                $openFileDialog.Title = "Select file(s) to convert"
                $openFileDialog.RestoreDirectory = $true
                
                # Enable visual styles for better appearance
                [System.Windows.Forms.Application]::EnableVisualStyles()
                
                # Create a form that will be the owner of the dialog
                $form = New-Object System.Windows.Forms.Form
                $form.TopMost = $true
                $form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
                $form.WindowState = [System.Windows.Forms.FormWindowState]::Normal
                $form.ShowInTaskbar = $false
                $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
                $form.Size = New-Object System.Drawing.Size(0, 0)
                $form.Opacity = 0
                
                # Show the form first (invisible)
                $form.Show()
                
                # Force the form to be the foreground window but keep it invisible
                $form.TopMost = $true
                $form.Focus()
                $form.BringToFront()
                $form.Activate()
                
                # Add a small delay to ensure the form is active
                Start-Sleep -Milliseconds 100
                
                # Show the dialog with the form as owner
                $result = $openFileDialog.ShowDialog($form)
                
                # Close the form
                $form.Close()
                
                # Return the selected file if OK was clicked
                if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
                    $openFileDialog.FileNames
                }
                ''')
                ps_script.close()
                
                # Run the PowerShell script with hidden window
                result = subprocess.run(
                    ['powershell', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', ps_script.name],
                    capture_output=True, text=True
                )
                
                # Clean up the temporary file
                os.unlink(ps_script.name)
                
                # Get the selected file paths
                if result.stdout.strip():
                    # Clean the output - remove any newlines, carriage returns, or other whitespace
                    raw_output = result.stdout.strip()
                    
                    # Split the output by lines to get multiple file paths
                    file_paths = []
                    for line in raw_output.splitlines():
                        clean_path = line.strip().replace('\r', '').replace('\n', '')
                        
                        # Remove any "True" prefix that might be added by PowerShell
                        if clean_path.startswith('True'):
                            clean_path = clean_path[4:]  # Remove 'True' from the beginning
                        
                        if clean_path and os.path.exists(clean_path):
                            file_paths.append(clean_path)
                    
                    if not file_paths:
                        st.error("No valid files were selected.")
                    else:
                        # Process the first file for now (we'll add multi-file support later)
                        selected_path = file_paths[0]
                        
                        # Verify the path exists
                        if not os.path.exists(selected_path):
                            st.error(f"Invalid path returned: '{selected_path}'")
                        else:
                            # Read the file from the provided path
                            with open(selected_path, "rb") as f:
                                file_content = f.read()
                            
                            # Create a UploadedFile-like object
                            file_name = os.path.basename(selected_path)
                            file_type = "application/pdf" if selected_path.lower().endswith(".pdf") else "image/jpeg"
                            
                            in_file = CustomUploadedFile(file_name, file_type, file_content, selected_path)
                            
                            # Show information about selected files
                            if len(file_paths) > 1:
                                st.success(f"Selected {len(file_paths)} files. Processing: {file_name}")
                                st.info(f"Note: Currently only processing the first file. The other {len(file_paths)-1} files will be available in a future update.")
                            else:
                                st.success(f"File loaded: {file_name} from {selected_path}")
                            
                            # Store the path for reuse
                            st.session_state['last_selected_path'] = selected_path
                            # Store all selected paths for future use
                            st.session_state['all_selected_paths'] = file_paths
                            
                            # We don't need to reset_file_selection() here since we already did it at the start of the function if needed
                            store_file_in_session(in_file)
                            
                            # Immediately rerun the app to show the new file
                            st.rerun()
            except Exception as e:
                st.error(f"Error with file dialog: {str(e)}")
        # For non-Windows systems, try PyQt5 if available
        else:
            try:
                from PyQt5.QtWidgets import QApplication, QFileDialog
                import sys
                
                # Create a Qt application
                app = QApplication.instance()
                if not app:
                    app = QApplication(sys.argv)
                
                # Show file dialog
                file_dialog = QFileDialog()
                file_dialog.setFileMode(QFileDialog.ExistingFiles)
                file_dialog.setNameFilter("All Files (*);;PDF Files (*.pdf);;Image Files (*.png *.jpg *.jpeg *.gif)")
                
                if file_dialog.exec_():
                    selected_paths = file_dialog.selectedFiles()
            except ImportError:
                st.error("PyQt5 not installed and not on Windows. File dialog not available.")
                st.stop()
    except Exception as e:
        st.error(f"Error opening file dialog: {str(e)}")
    
    return False

# Add a "Select files" button to the sidebar if no file is loaded
if not st.session_state.file_loaded:
    st.sidebar.markdown("### Select File")
    if st.sidebar.button("Select files", key="sidebar_file_dialog", use_container_width=True):
        # Directly open the file dialog without reloading the page
        open_file_dialog()
else:
    # Add "Change File" section to the sidebar when a file is loaded
    st.sidebar.markdown("---")
    st.sidebar.write("### Change File")
    
    if st.sidebar.button("Select files", key="change_file", use_container_width=True):
        # Directly open the file dialog without resetting the session state first
        # This will allow selecting a new file with just one click
        open_file_dialog()

# Add a prominent message in the main area if no file is loaded
if not st.session_state.file_loaded:
    st.markdown("### Select a file to convert")
    st.markdown("Use the 'Select files' button in the sidebar to open the file selection dialog.")
    
    # Display the last selected file if available
    if 'last_selected_path' in st.session_state and st.session_state['last_selected_path']:
        st.info(f"Last selected file: {st.session_state['last_selected_path']}")
        
        # Provide a button to reload the last file
        if st.button("Reload last file"):
            try:
                selected_path = st.session_state['last_selected_path']
                with open(selected_path, "rb") as f:
                    file_content = f.read()
                
                file_name = os.path.basename(selected_path)
                file_type = "application/pdf" if selected_path.lower().endswith(".pdf") else "image/jpeg"
                
                in_file = CustomUploadedFile(file_name, file_type, file_content, selected_path)
                st.success(f"File reloaded: {file_name}")
                store_file_in_session(in_file)
                st.rerun()
            except Exception as e:
                st.error(f"Error reloading file: {str(e)}")

# Use the file from session state if available
if in_file is None and st.session_state.file_loaded:
    in_file = get_file_from_session()
    # Debug information about the file from session state
    if hasattr(in_file, 'original_path') and in_file.original_path:
        st.sidebar.info(f"Using file from session state with path: {in_file.original_path}")
    else:
        st.sidebar.info("Using file from session state (no original path available)")

if in_file is None:
    st.stop()

filetype = in_file.type

with col1:
    total_pages = get_page_count(in_file)
    page_number = st.number_input(f"Page number out of {total_pages}:", min_value=0, value=0, max_value=total_pages)
    pil_image = get_page_image(in_file, page_number)
    image_placeholder = st.empty()

    with image_placeholder:
        block_display(pil_image)


page_range = st.sidebar.text_input("Page range to parse, comma separated like 0,5-10,20", value=f"{page_number}-{page_number}")
output_format = st.sidebar.selectbox("Output format", ["markdown", "json", "html"], index=0)

# Add a divider before save options
st.sidebar.markdown("---")

# Add save options to the sidebar BEFORE running the conversion
st.sidebar.write("### Save Options")

# Simple save location option
save_options = ["Current Working Directory", "Output folder with PDF name", "Desktop", "Documents", "Custom location"]
# Add "Same folder as original file" option when we have the original path
if hasattr(in_file, 'original_path') and in_file.original_path:
    original_dir = os.path.dirname(in_file.original_path)
    if os.path.exists(original_dir):
        save_options.insert(0, "Same folder as original file")
        st.sidebar.info(f"Original file location: {original_dir}")

save_location = st.sidebar.radio(
    "Where to save output:",
    save_options,
    index=0
)

# Custom location input
if save_location == "Custom location":
    custom_path = st.sidebar.text_input("Enter folder path:", value="")
    if custom_path and not os.path.exists(custom_path):
        st.sidebar.warning(f"Path does not exist: {custom_path}")
        st.sidebar.info("The folder will be created when saving")

# Function to handle the Run Marker button click
def on_run_marker_click():
    st.session_state.run_marker = True

# Run Marker button
st.sidebar.button("Run Marker", on_click=on_run_marker_click)

use_llm = st.sidebar.checkbox("Use LLM", help="Use LLM for higher quality processing", value=False)
show_blocks = st.sidebar.checkbox("Show Blocks", help="Display detected blocks, only when output is JSON", value=False, disabled=output_format != "json")
force_ocr = st.sidebar.checkbox("Force OCR", help="Force OCR on all pages", value=False)
strip_existing_ocr = st.sidebar.checkbox("Strip existing OCR", help="Strip existing OCR text from the PDF and re-OCR.", value=False)
debug = st.sidebar.checkbox("Debug", help="Show debug information", value=False)

# Check if we should run the marker
if 'run_marker' not in st.session_state:
    st.session_state.run_marker = False
    
if not st.session_state.run_marker:
    st.stop()

# Reset the run_marker flag for the next run
st.session_state.run_marker = False

# Run Marker
with tempfile.TemporaryDirectory() as tmp_dir:
    temp_pdf = os.path.join(tmp_dir, 'temp.pdf')
    with open(temp_pdf, 'wb') as f:
        f.write(in_file.getvalue())
    
    cli_options.update({
        "output_format": output_format,
        "page_range": page_range,
        "force_ocr": force_ocr,
        "debug": debug,
        "output_dir": settings.DEBUG_DATA_FOLDER if debug else None,
        "use_llm": use_llm,
        "strip_existing_ocr": strip_existing_ocr
    })
    config_parser = ConfigParser(cli_options)
    rendered = convert_pdf(
        temp_pdf,
        config_parser
    )
    page_range = config_parser.generate_config_dict()["page_range"]
    first_page = page_range[0] if page_range else 0

    text, ext, images = text_from_rendered(rendered)

    # Determine save location - MOVED from above but kept the logic
    base_filename = os.path.splitext(in_file.name)[0]
    if save_location == "Current Working Directory":
        # Save directly to the current working directory
        save_dir = os.getcwd()
        st.info(f"Output will be saved to current directory: {save_dir}")
    elif save_location == "Output folder with PDF name":
        # Create a subfolder with the PDF name in the current directory
        pdf_folder = os.path.join(os.getcwd(), base_filename + "_output")
        try:
            os.makedirs(pdf_folder, exist_ok=True)
            save_dir = pdf_folder
            st.info(f"Output will be saved to: {pdf_folder}")
        except Exception as e:
            st.error(f"Could not create folder: {pdf_folder}. Error: {str(e)}")
            save_dir = os.getcwd()
            st.info(f"Using current directory instead: {save_dir}")
    elif save_location == "Same folder as original file":
        # Try to use the original file's directory if available
        if hasattr(in_file, 'original_path') and in_file.original_path:
            original_dir = os.path.dirname(in_file.original_path)
            if os.path.exists(original_dir):
                save_dir = original_dir
                st.info(f"Output will be saved to original file location: {save_dir}")
            else:
                st.warning(f"Original file directory not accessible: {original_dir}")
                save_dir = os.getcwd()
                st.info(f"Using current directory instead: {save_dir}")
        else:
            # Debug information to understand what's happening
            st.warning(f"Original file location not available. File type: {type(in_file)}")
            if hasattr(in_file, 'original_path'):
                st.warning(f"Original path attribute exists but is empty or None: '{getattr(in_file, 'original_path', None)}'")
            else:
                st.warning("Original path attribute does not exist on the file object")
            
            save_dir = os.getcwd()
            st.info(f"Using current directory instead: {save_dir}")
    elif save_location == "Desktop":
        # Try to get desktop path - improved detection for Windows
        try:
            if os.name == 'nt':  # Windows
                # Use the Windows API to get the actual Desktop folder path
                import ctypes
                from ctypes import windll, wintypes
                CSIDL_DESKTOP = 0
                SHGFP_TYPE_CURRENT = 0
                buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
                windll.shell32.SHGetFolderPathW(0, CSIDL_DESKTOP, 0, SHGFP_TYPE_CURRENT, buf)
                desktop_path = buf.value
                
                # If that fails, try the standard path
                if not desktop_path or not os.path.exists(desktop_path):
                    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
                
                save_dir = desktop_path
            elif os.name == 'posix':  # macOS/Linux
                save_dir = os.path.join(os.path.expanduser("~"), "Desktop")
                # If Desktop doesn't exist, try localized name on macOS
                if not os.path.exists(save_dir) and sys.platform == 'darwin':
                    save_dir = os.path.join(os.path.expanduser("~"), "Επιφάνεια εργασίας")  # Greek
                    if not os.path.exists(save_dir):
                        save_dir = os.path.join(os.path.expanduser("~"), "Επιφάνεια Εργασίας")  # Alternative Greek
            
            # Final check if Desktop exists
            if not os.path.exists(save_dir):
                st.warning(f"Desktop folder not found at: {save_dir}")
                # Create a Desktop folder in the current directory as fallback
                fallback_desktop = os.path.join(os.getcwd(), "Desktop")
                os.makedirs(fallback_desktop, exist_ok=True)
                save_dir = fallback_desktop
                st.info(f"Created and using fallback Desktop folder: {fallback_desktop}")
            else:
                st.info(f"Output will be saved to Desktop: {save_dir}")
        except Exception as e:
            st.error(f"Error accessing Desktop: {str(e)}")
            save_dir = os.getcwd()
            st.info(f"Using current directory instead: {save_dir}")
    elif save_location == "Documents":
        # Try to get Documents folder path
        try:
            if os.name == 'nt':  # Windows
                # Use the Windows API to get the actual Documents folder path
                import ctypes
                from ctypes import windll, wintypes
                CSIDL_PERSONAL = 5  # My Documents
                SHGFP_TYPE_CURRENT = 0
                buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
                windll.shell32.SHGetFolderPathW(0, CSIDL_PERSONAL, 0, SHGFP_TYPE_CURRENT, buf)
                docs_path = buf.value
                
                # If that fails, try the standard path
                if not docs_path or not os.path.exists(docs_path):
                    docs_path = os.path.join(os.path.expanduser("~"), "Documents")
                    # Try alternative names
                    if not os.path.exists(docs_path):
                        docs_path = os.path.join(os.path.expanduser("~"), "My Documents")
                
                save_dir = docs_path
            elif os.name == 'posix':  # macOS/Linux
                save_dir = os.path.join(os.path.expanduser("~"), "Documents")
                # Try alternative names for localized systems
                if not os.path.exists(save_dir):
                    save_dir = os.path.join(os.path.expanduser("~"), "Έγγραφα")  # Greek
            
            # Final check if Documents exists
            if not os.path.exists(save_dir):
                st.warning(f"Documents folder not found at: {save_dir}")
                # Create a Documents folder in the current directory as fallback
                fallback_docs = os.path.join(os.getcwd(), "Documents")
                os.makedirs(fallback_docs, exist_ok=True)
                save_dir = fallback_docs
                st.info(f"Created and using fallback Documents folder: {fallback_docs}")
            else:
                st.info(f"Output will be saved to Documents: {save_dir}")
        except Exception as e:
            st.error(f"Error accessing Documents folder: {str(e)}")
            save_dir = os.getcwd()
            st.info(f"Using current directory instead: {save_dir}")
    else:  # Custom location
        if custom_path:
            save_dir = custom_path
            try:
                os.makedirs(save_dir, exist_ok=True)
                st.info(f"Output will be saved to: {save_dir}")
            except Exception as e:
                st.error(f"Could not create directory: {save_dir}. Error: {str(e)}")
                save_dir = os.getcwd()
                st.info(f"Using current directory instead: {save_dir}")
        else:
            save_dir = os.getcwd()
            st.info(f"No custom path provided. Using current directory: {save_dir}")

    # Save files automatically
    output_path = os.path.join(save_dir, f"{base_filename}.{ext}")
    meta_path = os.path.join(save_dir, f"{base_filename}_meta.json")

    # Save main output file
    try:
        with open(output_path, "w+", encoding=settings.OUTPUT_ENCODING) as f:
            f.write(text)
        save_success = True
    except Exception as e:
        st.error(f"Error saving output file: {str(e)}")
        save_success = False

    # Save metadata
    try:
        with open(meta_path, "w+", encoding=settings.OUTPUT_ENCODING) as f:
            f.write(json.dumps(rendered.metadata, indent=2))
    except Exception as e:
        st.error(f"Error saving metadata: {str(e)}")

    # Save images
    images_saved = 0
    for img_name, img in images.items():
        try:
            img_path = os.path.join(save_dir, img_name)
            img.save(img_path, settings.OUTPUT_IMAGE_FORMAT)
            images_saved += 1
        except Exception as e:
            st.error(f"Error saving image {img_name}: {str(e)}")

    with col2:
        if output_format == "markdown":
            text = markdown_insert_images(text, images)
            st.markdown(text, unsafe_allow_html=True)
        elif output_format == "json":
            st.json(text)
        elif output_format == "html":
            st.html(text)
        
        # Show save information
        st.write("---")
        st.write("### Output Files")
        
        if save_success:
            # Convert to absolute path for clearer display
            abs_output_path = os.path.abspath(output_path)
            st.success(f"✅ Output saved to: {abs_output_path}")
            # Add a button to open the folder containing the file
            if os.path.exists(os.path.dirname(abs_output_path)):
                st.markdown(f"📂 [Click to open containing folder](file://{os.path.dirname(abs_output_path)})")
            
            if images_saved > 0:
                st.success(f"✅ {images_saved} images saved to the same folder")

    # Check if we should display blocks
    if output_format == "json" and show_blocks:
        with image_placeholder:
            block_display(pil_image, text)

    # Check if debug mode is enabled
    if debug:
        with col1:
            debug_data_path = rendered.metadata.get("debug_data_path")
            if debug_data_path:
                pdf_image_path = os.path.join(debug_data_path, f"pdf_page_{first_page}.png")
                img = Image.open(pdf_image_path)
                st.image(img, caption="PDF debug image", use_container_width=True)
                layout_image_path = os.path.join(debug_data_path, f"layout_page_{first_page}.png")
                img = Image.open(layout_image_path)
                st.image(img, caption="Layout debug image", use_container_width=True)
            st.write("Raw output:")
            st.code(text, language=output_format)

if not st.session_state.file_loaded:
    if upload_method == "Native file dialog":
        uploaded_file = st.sidebar.file_uploader("PDF, document, or image file:", type=["pdf", "png", "jpg", "jpeg", "gif", "pptx", "docx", "xlsx", "html", "epub"])
        if uploaded_file is not None:
            in_file = uploaded_file
            store_file_in_session(in_file)
            st.rerun()

    # Auto-open file dialog when Native file dialog is selected and no file is loaded
    if (not st.session_state.file_loaded and 
        'auto_open_dialog' in st.session_state):
        
        # Clear the flag to avoid repeated dialog opening
        del st.session_state.auto_open_dialog
        
        # Open the file dialog
        open_file_dialog()
