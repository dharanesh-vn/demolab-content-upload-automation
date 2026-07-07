import os
import json
from dotenv import load_dotenv
from parser import parse_docx
from question_model import Question
from uploader import run_uploader
from pathlib import Path

def main():
    load_dotenv()
    
    # Check credentials
    username = os.getenv("AMYPO_USERNAME")
    password = os.getenv("AMYPO_PASSWORD")
    if not username or not password:
        print("Please set AMYPO_USERNAME and AMYPO_PASSWORD in .env")
        return
        
    # Load config
    with open("config.json", "r") as f:
        config = json.load(f)
        
    print("Parsing docx file...")
    raw_questions = parse_docx(config["docx_path"])
    
    print("Validating and generating models...")
    validated_questions = []
    attachments_root = Path(config["attachments_root"])
    
    for q_dict in raw_questions:
        q = Question(
            question_number=q_dict["question_number"],
            title=q_dict["title"],
            question_text=q_dict["question_text"],
            attachment_filename=q_dict["attachment_filename"],
            submission_instructions=q_dict["submission_instructions"],
            tags=q_dict["tags"],
            difficulty=config["default_difficulty"],
            language=config["language"],
            actual_time_minutes=config["default_actual_time_minutes"]
        )
        validated_questions.append(q)
        
        # Pre-check attachment existence
        if q.attachment_filename:
            att_path = attachments_root / q.attachment_filename
            if not att_path.exists():
                print(f"CRITICAL ERROR: Missing attachment file for Q{q.question_number}: {att_path}")
                return
    
    if not validated_questions:
        print("No valid questions found in docx.")
        return
        
    print(f"\n=====================================")
    print(f"Total Questions Extracted: {len(validated_questions)}")
    print(f"=====================================")
    for q in validated_questions:
        att_status = f"📎 {q.attachment_filename}" if q.attachment_filename else "No Attachment"
        print(f"Q{q.question_number}: {q.title[:40]:<42} | {att_status}")
    print(f"=====================================\n")
    
    try:
        start_q = int(input("Enter the starting question number to upload (e.g. 1): ").strip())
        end_q = int(input(f"Enter the ending question number to upload (e.g. {len(validated_questions)}): ").strip())
    except ValueError:
        print("Invalid input! Please enter valid numbers.")
        return

    subset_questions = [q for q in validated_questions if start_q <= q.question_number <= end_q]
    
    if not subset_questions:
        print("No questions found in that range!")
        return
        
    print("\n--- Navigation Setup ---")
    subj_choice = input("Select Subject Type (0 for Academic, 1 for Programming Subjects): ").strip()
    config["subject_type"] = "academic" if subj_choice == "0" else "programming"
    
    course_name = input("Enter Course Name (Case Sensitive, e.g. 'Assign testing demo'): ").strip()
    if course_name:
        config["course_name"] = course_name
        
    module_name = input("Enter Module Name (Case Sensitive, e.g. 'Sample 02'): ").strip()
    if module_name:
        config["module_name"] = module_name
        
    print(f"\nStarting uploader for {len(subset_questions)} questions (Q{start_q} to Q{end_q})...")
    
    run_uploader(
        questions=subset_questions,
        config=config,
        credentials={"username": username, "password": password}
    )

if __name__ == "__main__":
    main()
