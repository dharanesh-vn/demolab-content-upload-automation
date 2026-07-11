import os
import json
import csv
import re
import tkinter as tk
from tkinter import filedialog
from dotenv import load_dotenv
from docx_parser import parse_docx
from question_model import Question
from uploader import run_uploader
from pathlib import Path

def get_letter_input(prompt_text):
    while True:
        val = input(prompt_text).strip()
        if re.match(r'^[a-zA-Z\s,]+$', val):
            return val
        print("Invalid input. Please enter letters, spaces, and commas only.")

def get_number_input(prompt_text):
    while True:
        val = input(prompt_text).strip()
        if val.isdigit() and int(val) > 0:
            return val
        print("Invalid input. Please enter a number greater than 0.")

def main():
    load_dotenv()
    
    # Check credentials
    username = os.getenv("AMYPO_USERNAME")
    password = os.getenv("AMYPO_PASSWORD")
    if not username or not password or username == "your_email_here@example.com":
        print("Please set your real AMYPO_USERNAME and AMYPO_PASSWORD in the .env file.")
        return

    # Load config
    with open("config.json", "r") as f:
        config = json.load(f)
        
    print("\n=======================================================")
    print("Please select the Assignment Word Document (.docx) from the popup window...")
    print("=======================================================\n")
    
    # Use Tkinter to ask the user to select the file
    root = tk.Tk()
    root.withdraw() # Hide the main window
    root.attributes('-topmost', True) # Bring popup to front
    
    docx_file = filedialog.askopenfilename(
        title="Select the Assignment Word Document (.docx)",
        filetypes=[("Word Documents", "*.docx")]
    )
    
    if not docx_file:
        print("No file selected. Exiting...")
        return
        
    docx_path = Path(docx_file).absolute()
    project_folder = docx_path.parent
    attachments_root = project_folder / "Attachments"
    
    if not attachments_root.exists():
        print(f"❌ WARNING: Could not find the 'Attachments' folder at: {attachments_root}")
        print("The script will try to search the entire project folder for attachments instead.")
        
    # Inject dynamically discovered paths into config
    config["docx_path"] = str(docx_path)
    config["attachments_root"] = str(project_folder) # Use main project folder for rglob search
        
    print(f"Loading DOCX: {docx_path.name}")
    print(f"Attachments Folder: {attachments_root}")
    raw_questions = parse_docx(config["docx_path"])
    
    print("\nValidating and generating models...")
    validated_questions = []
    
    for q_dict in raw_questions:
        q = Question(
            absolute_index=q_dict["absolute_index"],
            question_number=q_dict["question_number"],
            title=q_dict["title"],
            question_text=q_dict["question_text"],
            attachment_filename=q_dict["attachment_filename"],
            submission_instructions=q_dict["submission_instructions"],
            tags=q_dict["tags"],
            difficulty=config["default_difficulty"],
            language=config["language"],
            actual_time_minutes=config["default_actual_time_minutes"],
            user_response_acceptance=q_dict.get("user_response_acceptance", "PDF, Images")
        )
        validated_questions.append(q)
        
        # Pre-check attachment existence using rglob
        if q.attachment_filename:
            # We search the entire project folder recursively for the filename
            matched_files = list(project_folder.rglob(q.attachment_filename))
            if not matched_files:
                print(f"\n[WARNING] Could not find attachment '{q.attachment_filename}' for Q{q.question_number}!")
                print(f"I searched the entire directory: {project_folder}")
                while True:
                    ans = input("Do you want to proceed and upload this question WITHOUT the attachment? (Y/N): ").strip().upper()
                    if ans == 'Y':
                        q.attachment_filename = None
                        break
                    elif ans == 'N':
                        print("Exiting so you can fix the missing attachment.")
                        return
            else:
                # Add the resolved absolute path to the question object temporarily for the uploader
                q.resolved_attachment_path = matched_files[0]
                
    if not validated_questions:
        print("No valid questions found in docx.")
        return
        
    print(f"\n=====================================")
    print(f"Total Questions Extracted: {len(validated_questions)}")
    print(f"=====================================")
    for q in validated_questions:
        att_status = f"[Attachment] {q.attachment_filename}" if q.attachment_filename else "No Attachment"
        print(f"Q{q.question_number}: {q.title[:40]:<42} | {att_status}")
    print(f"=====================================\n")
    
    print("\n--- Navigation Setup ---")
    subj_choice = input("Select Subject Type (0 for Academic, 1 for Programming Subjects): ").strip()
    config["subject_type"] = "academic" if subj_choice == "0" else "programming"
    
    course_name = input("Enter Course Name (Case Sensitive, e.g. 'Assign testing dot'): ").strip()
    if course_name:
        config["course_name"] = course_name
        
    module_name = input("Enter Module Name (Case Sensitive, e.g. 'Sample 02'): ").strip()
    if module_name:
        config["module_name"] = module_name
        
    print("\n--- Form Field Setup ---")
    bulk_mode = input("Is this a Bulk Multi-Module Upload with dynamic tags? (Y/N): ").strip().upper()
    if bulk_mode == 'Y':
        q_per_mod = int(get_number_input("Questions per module (e.g. 60): "))
        base_tag = input("Enter Base Tag prefix (e.g. 'module '): ")
        tags = ""
    else:
        tags_raw = input("Enter Tags (e.g. 'Python'): ").strip()
        tags = ", ".join([t.strip() for t in tags_raw.split(",") if t.strip()]) if tags_raw else ""
    
    # Constant values
    difficulty = "Medium"
    language = "Assignment"
    actual_time = 30
    
    for q in validated_questions:
        q.difficulty = difficulty
        if bulk_mode == 'Y':
            mod_num = ((q.absolute_index - 1) // q_per_mod) + 1
            q.tags = f"{base_tag}{mod_num}".strip()
        else:
            q.tags = tags
        q.language = language
        q.actual_time_minutes = actual_time
        
    csv_file = "questions_review.csv"
    print(f"\nWriting {len(validated_questions)} questions to {csv_file} for review...")
    
    headers = ["Question No.", "Question Title", "Difficulty Level", "Tags", "Language", "Actual time", "Question", "Attachment name", "User Response Acceptance"]
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(headers)
        for q in validated_questions:
            writer.writerow([
                f"Q{q.question_number}",
                q.title,
                q.difficulty,
                q.tags,
                q.language,
                q.actual_time_minutes,
                q.question_text,
                q.attachment_filename or "",
                q.user_response_acceptance
            ])
            
    print("\n=======================================================")
    print("CSV FILE GENERATED!")
    print(f"Please open '{csv_file}' in Excel, review, and edit any rows if needed.")
    print("Save the file when you are done.")
    print("=======================================================")
    
    while True:
        proceed = input("Enter 1 to proceed with upload, or 0 to exit: ").strip()
        if proceed == "0":
            print("Exiting...")
            return
        elif proceed == "1":
            break
            
    while True:
        try:
            print(f"\nReading updated data from {csv_file}...")
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i < len(validated_questions):
                        q = validated_questions[i]
                        q.title = row["Question Title"]
                        q.difficulty = row["Difficulty Level"]
                        q.tags = row["Tags"]
                        q.language = row["Language"]
                        try:
                            q.actual_time_minutes = int(row["Actual time"])
                        except ValueError:
                            q.actual_time_minutes = 0
                        q.question_text = row["Question"]
                        att = row["Attachment name"].strip()
                        q.attachment_filename = att if att else None
                        q.user_response_acceptance = row["User Response Acceptance"].strip() if row["User Response Acceptance"].strip() else "PDF, Images"
            break # Exit the loop if file was read successfully
        except PermissionError:
            print(f"\n[ERROR] '{csv_file}' is currently locked by another program (like Excel).")
            input("Please close the file in Excel and press Enter to try reading it again...")
                
    print(f"\n=====================================")
    
    while True:
        try:
            start_q = int(input("Enter the starting Absolute Index number to upload (e.g. 1): ").strip())
            if start_q <= 0:
                print("Starting number must be 1 or greater.")
                continue
                
            end_q = int(input(f"Enter the ending Absolute Index number to upload (e.g. {len(validated_questions)}): ").strip())
            if end_q < start_q:
                print(f"Ending number ({end_q}) cannot be less than starting number ({start_q}).")
                continue
                
            break
        except ValueError:
            print("Invalid input! Please enter valid integer numbers.")

    questions_to_upload = [q for q in validated_questions if start_q <= q.absolute_index <= end_q]
    
    if not questions_to_upload:
        print("No questions found in that range!")
        return

    print(f"\nStarting uploader for {len(questions_to_upload)} questions (Q{start_q} to Q{end_q})...")
    
    run_uploader(
        questions=questions_to_upload,
        config=config,
        credentials={"username": username, "password": password}
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        import sys
        print("\n\n[INTERRUPTED] Script interrupted by user (Ctrl+C). Exiting gracefully...")
        sys.exit(0)
