import streamlit as st

# Define the CustomUploadedFile class
class CustomUploadedFile:
    def __init__(self, name, type, content, path):
        self.name = name
        self.type = type
        self._content = content
        self.original_path = path
    
    def getvalue(self):
        return self._content
    
    def __str__(self):
        return f"CustomUploadedFile(name={self.name}, type={self.type}, path={self.original_path})"
    
    def __repr__(self):
        return self.__str__()
    
    # Make the class picklable for session state
    def __getstate__(self):
        return {
            'name': self.name,
            'type': self.type,
            '_content': self._content,
            'original_path': self.original_path
        }
    
    def __setstate__(self, state):
        self.name = state['name']
        self.type = state['type']
        self._content = state['_content']
        self.original_path = state['original_path']

# Function to reset file selection
def reset_file_selection():
    # Set file_loaded to False
    st.session_state.file_loaded = False
    
    # Clear file-related variables
    st.session_state.in_file = None
    
    # Remove any other file-related keys
    keys_to_remove = [
        'file_original_path', 
        'file_name', 
        'file_type', 
        'auto_open_dialog',
        'last_selected_path',
        'all_selected_paths'
    ]
    
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]
    
    # Make sure run_marker is initialized to False
    st.session_state.run_marker = False

# Function to store file in session state
def store_file_in_session(file_obj):
    st.session_state.in_file = file_obj
    st.session_state.file_loaded = True
    # Store additional information separately to ensure it's preserved
    if hasattr(file_obj, 'original_path'):
        st.session_state.file_original_path = file_obj.original_path
    if hasattr(file_obj, 'name'):
        st.session_state.file_name = file_obj.name
    if hasattr(file_obj, 'type'):
        st.session_state.file_type = file_obj.type

# Function to retrieve file from session state
def get_file_from_session():
    if not st.session_state.file_loaded:
        return None
    
    file_obj = st.session_state.in_file
    
    # Ensure original_path is preserved
    if hasattr(file_obj, 'original_path') and not file_obj.original_path and 'file_original_path' in st.session_state:
        file_obj.original_path = st.session_state.file_original_path
    
    return file_obj 