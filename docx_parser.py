import re
# pyrefly: ignore [missing-import]
from docx import Document
from typing import List, Dict

def extract_rich_text(cell) -> str:
    html_parts = []
    for paragraph in cell.paragraphs:
        p_html = ""
        p_style = paragraph.style.name.lower() if paragraph.style else ""
        
        for run in paragraph.runs:
            text = run.text
            if not text: continue
            
            # Escape HTML characters to prevent breaking the editor
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
            # Only apply formatting tags if the run contains actual non-whitespace content
            if text.strip():
                leading_spaces = " " * (len(text) - len(text.lstrip()))
                trailing_spaces = " " * (len(text) - len(text.rstrip()))
                core_text = text.strip()
                
                if run.bold: core_text = f"<strong>{core_text}</strong>"
                if run.italic: core_text = f"<em>{core_text}</em>"
                if run.underline: core_text = f"<u>{core_text}</u>"
                if getattr(run.font, 'strike', None): core_text = f"<s>{core_text}</s>"
                
                text = leading_spaces + core_text + trailing_spaces
                
            p_html += text
            
        p_html = p_html.strip()
        if p_html:
            if "code" in p_style:
                html_parts.append(f"<pre><code>{p_html}</code></pre>")
            elif "quote" in p_style:
                html_parts.append(f"<blockquote><p>{p_html}</p></blockquote>")
            elif "bullet" in p_style:
                html_parts.append(f"<ul><li><p>{p_html}</p></li></ul>")
            elif "number" in p_style:
                html_parts.append(f"<ol><li><p>{p_html}</p></li></ol>")
            else:
                html_parts.append(f"<p>{p_html}</p>")
                
    full_html = "".join(html_parts)
    full_html = re.sub(r'<(strong|em|u|s)>\s*</\1>', '', full_html)
    return full_html.strip()

def parse_docx(file_path: str) -> List[Dict]:
    doc = Document(file_path)
    questions = []
    
    current_section_tag = "General"
    
    # We need to walk the elements in order. 
    # python-docx doesn't provide a direct way to iterate all elements (paragraphs and tables) in order natively easily,
    # but we can do it by accessing the underlying XML or by checking the body elements.
    # Here is a helper to iterate block-level elements:
    
    # pyrefly: ignore [missing-import]
    from docx.document import Document as _Document
    # pyrefly: ignore [missing-import]
    from docx.oxml.text.paragraph import CT_P
    # pyrefly: ignore [missing-import]
    from docx.oxml.table import CT_Tbl
    # pyrefly: ignore [missing-import]
    from docx.table import Table
    # pyrefly: ignore [missing-import]
    from docx.text.paragraph import Paragraph

    def iter_block_items(parent):
        if isinstance(parent, _Document):
            parent_elm = parent.element.body
        else:
            raise ValueError("Something's not right")
        
        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)

    for element in iter_block_items(doc):
        if isinstance(element, Paragraph):
            text = element.text.strip()
            if text and text.isupper():
                current_section_tag = text
        elif isinstance(element, Table):
            # The new format uses a 5-row single-column table
            # Old format used a 3-row multi-column table
            if len(element.rows) >= 5:
                row1_text = element.rows[0].cells[0].text.strip()
                if re.match(r'^Q(uestion)?\s*\.?\s*\d+', row1_text, re.IGNORECASE):
                    q_num_match = re.search(r'\d+', row1_text)
                    q_num = int(q_num_match.group()) if q_num_match else len(questions) + 1
                    
                    # Strip the "Q1 — " or "Question 1 - " prefix from the title using regex
                    title = re.sub(r'^Q(uestion)?\s*\.?\s*\d+\s*[-—–:]\s*', '', row1_text, flags=re.IGNORECASE).strip()
                    
                    # Extract rich text (bold, italic) instead of raw text
                    q_text = extract_rich_text(element.rows[1].cells[0])
                    # Fallback to plain text if HTML extraction fails for some reason
                    if not q_text:
                        q_text = element.rows[1].cells[0].text.strip()
                    
                    attachment_text = element.rows[2].cells[0].text.strip()
                    attachment = None
                    if "no attachment" not in attachment_text.lower() and attachment_text != "":
                        attachment = re.sub(r'^(📎|\s)*(Attachment|File)\s*:\s*', '', attachment_text, flags=re.IGNORECASE).strip()
                        attachment = re.sub(r'^(📎|\s)+', '', attachment).strip()
                        
                    user_response_text = element.rows[3].cells[0].text.strip()
                    # Hardcoded to "Word, PDF, Images" per user request
                    user_response_acceptance = "Word, PDF, Images"
                    
                    submission_instructions = element.rows[4].cells[0].text.strip()
                    submission_instructions = re.sub(r'^Submi(t|ssion)\s*:\s*', '', submission_instructions, flags=re.IGNORECASE).strip()
                    
                    if submission_instructions:
                        q_text = f"{q_text}\n\nSubmission Method (Word/ PDF/ Images) : {submission_instructions}"
                    
                    questions.append({
                        "question_number": q_num,
                        "title": title,
                        "question_text": q_text,
                        "attachment_filename": attachment,
                        "submission_instructions": submission_instructions,
                        "user_response_acceptance": user_response_acceptance,
                        "tags": current_section_tag
                    })
            elif len(element.rows) >= 3:
                # Old 3-row format
                row1 = [c.text.strip() for c in element.rows[0].cells]
                row2 = [c.text.strip() for c in element.rows[1].cells]
                row3 = [c.text.strip() for c in element.rows[2].cells]
                
                # Basic validation that it's a question table
                if len(row1) > 0 and re.match(r'^Q(uestion)?\s*\.?\s*\d+', row1[0], re.IGNORECASE):
                    q_num_match = re.search(r'\d+', row1[0])
                    q_num = int(q_num_match.group()) if q_num_match else len(questions) + 1
                    
                    q_text = row1[1] if len(row1) > 1 else ""
                    
                    attachment = None
                    if len(row2) > 1 and "no attachment" not in row2[1].lower() and row2[1].strip() != "":
                        attachment = re.sub(r'^(📎|\s)*(Attachment|File)\s*:\s*', '', row2[1].strip(), flags=re.IGNORECASE).strip()
                        attachment = re.sub(r'^(📎|\s)+', '', attachment).strip()
                        
                    submission_instructions = row3[1] if len(row3) > 1 else ""
                    submission_instructions = re.sub(r'^Submi(t|ssion)\s*:\s*', '', submission_instructions, flags=re.IGNORECASE).strip()
                    
                    if submission_instructions:
                        q_text = f"{q_text}\n\nSubmission Method (Word/ PDF/ Images) : {submission_instructions}"
                    
                    # Generate a title from the first few words of the question text
                    title_words = q_text.split()[:10]
                    title = " ".join(title_words).rstrip('.,?:;')
                    if not title:
                        title = f"Question {q_num}"
                        
                    questions.append({
                        "question_number": q_num,
                        "title": title,
                        "question_text": q_text,
                        "attachment_filename": attachment,
                        "submission_instructions": submission_instructions,
                        "user_response_acceptance": "Word, PDF, Images",
                        "tags": current_section_tag
                    })
    for i, q in enumerate(questions):
        q["absolute_index"] = i + 1
        
    return questions
