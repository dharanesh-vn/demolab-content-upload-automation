import json
from parser import parse_docx

docx_path = r"D:\workspace\content_automation\26SWP05_M1_Assignments_2026-27\26SWP05_M1_Assignment_Questions.docx"
questions = parse_docx(docx_path)

with open("parsed_questions.json", "w", encoding="utf-8") as f:
    json.dump(questions, f, indent=2, ensure_ascii=False)
    
print("Dumped to parsed_questions.json")
