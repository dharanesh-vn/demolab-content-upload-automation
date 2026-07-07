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
        
    print(f"Successfully validated {len(validated_questions)} questions. Starting uploader...")
    
    run_uploader(
        questions=validated_questions,
        config=config,
        credentials={"username": username, "password": password}
    )

if __name__ == "__main__":
    main()
