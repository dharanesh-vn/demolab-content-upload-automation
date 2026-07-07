import re
# pyrefly: ignore [missing-import]
from docx import Document
from typing import List, Dict

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
            # Check if it's a 3-row table that matches our question pattern
            if len(element.rows) >= 3:
                row1 = [c.text.strip() for c in element.rows[0].cells]
                row2 = [c.text.strip() for c in element.rows[1].cells]
                row3 = [c.text.strip() for c in element.rows[2].cells]
                
                # Basic validation that it's a question table
                if len(row1) > 0 and re.match(r'^Q\d+', row1[0], re.IGNORECASE):
                    q_num_str = re.search(r'\d+', row1[0]).group()
                    q_num = int(q_num_str)
                    
                    q_text = row1[1] if len(row1) > 1 else ""
                    
                    attachment = None
                    if len(row2) > 1 and "no attachment" not in row2[1].lower() and row2[1].strip() != "":
                        attachment = row2[1].strip()
                        attachment = attachment.replace("📎 Attachment:", "").strip()
                        attachment = attachment.replace("📎", "").strip()
                        
                    submission_instructions = row3[1] if len(row3) > 1 else ""
                    
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
                        "tags": current_section_tag
                    })
    
    return questions
