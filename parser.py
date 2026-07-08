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
            # The new format uses a 5-row single-column table
            # Old format used a 3-row multi-column table
            if len(element.rows) >= 5:
                row1_text = element.rows[0].cells[0].text.strip()
                if re.match(r'^Q\d+', row1_text, re.IGNORECASE):
                    q_num_str = re.search(r'\d+', row1_text).group()
                    q_num = int(q_num_str)
                    
                    # Strip the "Q1 — " prefix from the title using regex
                    title = re.sub(r'^Q\d+\s*[-—–]\s*', '', row1_text, flags=re.IGNORECASE)
                    q_text = element.rows[1].cells[0].text.strip()
                    
                    attachment_text = element.rows[2].cells[0].text.strip()
                    attachment = None
                    if "no attachment" not in attachment_text.lower() and attachment_text != "":
                        attachment = attachment_text.replace("📎 Attachment:", "").strip()
                        attachment = attachment.replace("📎", "").strip()
                        attachment = attachment.replace("Attachment:", "").strip()
                        
                    user_response_text = element.rows[3].cells[0].text.strip()
                    user_response_acceptance = user_response_text.replace("User Response Acceptance:", "").strip()
                    
                    submission_instructions = element.rows[4].cells[0].text.strip()
                    submission_instructions = submission_instructions.replace("Submit:", "").strip()
                    
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
                        "user_response_acceptance": "PDF, Images",
                        "tags": current_section_tag
                    })
    
    return questions
