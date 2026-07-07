from parser import parse_docx
import pprint

docx_path = r"D:\workspace\content_automation\26SWP03_M2_Assignments_2026-27\26SWP03_M2_Assignment_Questions.docx"
questions = parse_docx(docx_path)

print(f"Total questions found: {len(questions)}")
if questions:
    print("First question:")
    pprint.pprint(questions[0])
    
    # Let's find one with an attachment
    for q in questions:
        if q["attachment_filename"]:
            print("First question with attachment:")
            pprint.pprint(q)
            break
