"""
This script fixes all 'return' statements that are outside of functions in streamlit_app.py.
"""

import re

# Read the file
with open('marker/scripts/streamlit_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define patterns to search for and their replacements
patterns = [
    (r'if not file_paths:\s+st\.error\("No valid files were selected\."\)\s+return', 
     'if not file_paths:\n                            st.error("No valid files were selected.")\n                        else:'),
    
    (r'if not file_paths:\s+st\.error\("No valid files were selected\."\)\s+return\s+', 
     'if not file_paths:\n                                st.error("No valid files were selected.")\n                            else:'),
]

# Apply all replacements
for pattern, replacement in patterns:
    content = re.sub(pattern, replacement, content)

# Write the file back
with open('marker/scripts/streamlit_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed all 'return' statements outside of functions in streamlit_app.py.") 