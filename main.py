import os
import json
import csv
import re
import tkinter as tk
from gui import get_credentials_and_file
from parser import parse_docx
from question_model import Question
from uploader import run_uploader
from pathlib import Path

def get_letter_input(prompt_text):
    while True:
        val = input(prompt_text).strip()
        if re.match(r'^[a-zA-Z\s]+$', val):
            return val
        print("Invalid input. Please enter letters and spaces only.")

def get_number_input(prompt_text):
    while True:
        val = input(prompt_text).strip()
        if val.isdigit():
            return val
        print("Invalid input. Please enter numbers only.")

def main():
    # Load config
    with open("config.json", "r") as f:
        config = json.load(f)
        
    print("\n=======================================================")
    print("Please fill out your credentials and select the Assignment Word Document (.docx) in the popup window...")
    print("=======================================================\n")
    
    # 1. Unified GUI for Credentials and File Selection
    username, password, docx_file = get_credentials_and_file()
    
    if not username or not password or not docx_file:
        print("Setup cancelled or incomplete. Exiting...")
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
                print(f"CRITICAL ERROR: Missing attachment file for Q{q.question_number}: {q.attachment_filename}")
                print(f"I searched the entire directory: {project_folder}")
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
        att_status = f"📎 {q.attachment_filename}" if q.attachment_filename else "No Attachment"
        print(f"Q{q.question_number}: {q.title[:40]:<42} | {att_status}")
    print(f"=====================================\n")
    
    print("\n--- Navigation Setup ---")
    subj_choice = input("Select Subject Type (0 for Academic, 1 for Programming Subjects): ").strip()
    config["subject_type"] = "academic" if subj_choice == "0" else "programming"
    
    course_name = input("Enter Course Name (Case Sensitive, e.g. 'Assign testing demo'): ").strip()
    if course_name:
        config["course_name"] = course_name
        
    module_name = input("Enter Module Name (Case Sensitive, e.g. 'Sample 02'): ").strip()
    if module_name:
        config["module_name"] = module_name
        
    print("\n--- Form Field Setup ---")
    difficulty = get_letter_input("Enter Difficulty Level (Case Sensitive, e.g. 'easy'): ")
    tags = get_letter_input("Enter Tags (Case Sensitive, e.g. 'Python'): ")
    language = get_letter_input("Enter Language (Case Sensitive, e.g. 'Assignment'): ")
    actual_time = int(get_number_input("Enter Actual time in minutes (e.g. '0'): "))
    
    for q in validated_questions:
        q.difficulty = difficulty
        q.tags = tags
        q.language = language
        q.actual_time_minutes = actual_time
        
    csv_file = "questions_review.csv"
    print(f"\nWriting {len(validated_questions)} questions to {csv_file} for review...")
    
    headers = ["Question Title", "Difficulty Level", "Tags", "Language", "Actual time", "Question", "Attachment name", "User Response Acceptance"]
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for q in validated_questions:
            writer.writerow([
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
                q.user_response_acceptance = row["User Response Acceptance"]
                
    print(f"\n=====================================")
    
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

    print(f"\nStarting uploader for {len(subset_questions)} questions (Q{start_q} to Q{end_q})...")
    
    run_uploader(
        questions=subset_questions,
        config=config,
        credentials={"username": username, "password": password}
    )

if __name__ == "__main__":
    main()
