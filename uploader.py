import os
import time
import csv
import re
from pathlib import Path
# pyrefly: ignore [missing-import]
from playwright.sync_api import sync_playwright, expect
from question_model import Question
from typing import List

import time

def run_uploader(questions: List[Question], config: dict, credentials: dict):
    success_count = 0
    fail_count = 0
    start_time = time.time()
    # Prepare run log
    log_file = Path("run_log.csv")
    completed_q_nums = set()
    current_docx_name = Path(config["docx_path"]).name
    
    file_exists = log_file.exists()
    if not file_exists:
        # Create file with headers if it doesn't exist
        with open(log_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Document Name", "Question Number", "Status", "Timestamp", "Details"])
            
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                # New format: doc_name, question_number, status, timestamp, error
                if len(row) >= 3 and row[0] == current_docx_name and row[2] == "success":
                    completed_q_nums.add(int(row[1]))
                # Legacy format fallback (no doc_name). We will assume it belongs to the current doc ONLY IF it's the exact same script session,
                # but generally we can't trust it. To be safe and solve the module switching bug, we will ignore legacy success logs 
                # unless they manually clear them, but we will still read them to prevent crashing.
    
    with sync_playwright() as p:
        # Run visible (headless=False) so we can see why the login is failing or hanging
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Make the script highly network-resistant by giving it up to 60 seconds to wait for elements
        page.set_default_timeout(60000)
        
        # --- 1. Login with manual OTP ---
        print("Navigating to login URL...")
        page.goto(config["login_url"])
        
        page.fill('input[name="email"], input[type="email"]', credentials["username"])
        page.fill('input[name="password"], input[type="password"]', credentials["password"])
        page.click('button:has-text("Login"), button[type="submit"]')
        
        print("Waiting for OTP input screen to render (this may take a few seconds)...", flush=True)
        timeout = config.get("otp_wait_timeout_ms", 120000)
        page.wait_for_selector('input[inputmode="numeric"]', timeout=timeout)
        
        # Prompt for OTP in the terminal safely
        print("\n====================================", flush=True)
        print("OTP SCREEN DETECTED!", flush=True)
        print("Please check your email/phone.", flush=True)
        print("Enter the 6-digit OTP here:", flush=True)
        otp = input("> ").strip()
        
        # Type the OTP into the browser
        print("Submitting OTP...")
        # Usually clicking the first input and typing works for these split-input React components
        page.locator('input[inputmode="numeric"]').first.click()
        page.keyboard.type(otp)
        
        # Wait until we are successfully logged in (URL changes from login page)
        print("Waiting for dashboard to load...")
        page.wait_for_url(lambda url: "login" not in url, timeout=timeout)
        page.wait_for_timeout(3000)  # Give it a moment to establish the session
        
        # --- Filter out already completed questions ---
        questions_to_upload = [q for q in questions if q.absolute_index not in completed_q_nums]
        
        if not questions_to_upload:
            print("All questions selected have already been uploaded successfully according to the run log.")
            print("Stopping script before making any changes or clicking save...")
            browser.close()
            return
            
        # Add a visual line breaker to the log for this new run session
        if log_file.exists():
            with open(log_file, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["---", "---", "---", "---", "---"])
        

        chunk_size = 30
        for chunk_start in range(0, len(questions_to_upload), chunk_size):
            chunk = questions_to_upload[chunk_start:chunk_start + chunk_size]
            print(f"\n=====================================")
            print(f"Processing Batch: Questions {chunk_start + 1} to {min(chunk_start + chunk_size, len(questions_to_upload))} of {len(questions_to_upload)}")
            print(f"=====================================\n")
            
            print("Login successful! Navigating to Question Bank...")
            page.goto(config["question_bank_url"])
        
            # --- 2. Navigate UI exactly as requested ---
        
            # 3. Click + Add Questions tab
            print("Clicking '+ Add Questions' tab...")
            page.locator('text=Add Questions').first.click()
            page.wait_for_timeout(1000)
        
            # 4. Select subject type
            if config.get("subject_type") == "programming":
                print("Clicking 'Prog... Subjects' tab...")
                page.locator('text=Prog... Subjects').first.click()
            else:
                print("Clicking 'Academic' tab...")
                page.locator('text=Academic').first.click()
            page.wait_for_timeout(1000)
        
            # 5. Search and select course and module
            course = config["course_name"]
            module = config["module_name"]
        
            print(f"Searching and Selecting Course: {course}")
            search_input = page.locator('input[name="search_term"]')
            if search_input.count() > 0:
                search_input.fill(course)
                page.wait_for_timeout(1000)
            
            course_loc = page.get_by_text(course, exact=True).first
            try:
                course_loc.click(timeout=5000)
            except Exception:
                print(f"\n❌ ERROR: Could not find Course '{course}'.")
                print("Please check your spelling and capitalization, then run again.")
                browser.close()
                return
            
            page.wait_for_timeout(1000)
        
            print(f"Selecting Module: {module}")
            module_loc = page.get_by_text(module, exact=True).first
            try:
                module_loc.click(timeout=5000)
            except Exception:
                print(f"\n[ERROR] Could not find Module '{module}'.")
                print("Please check your spelling and capitalization, then run again.")
                browser.close()
                return
            
            page.wait_for_timeout(1000)
        
            # 5. Click the "Project Questions" card
            print("Clicking 'Project Questions' card...")
            page.locator('text=Project Questions').first.click()
            page.wait_for_timeout(2000)
            # Wait for the configuration form to appear
            expect(page.get_by_text("Project Questions Configuration")).to_be_visible(timeout=10000)
            page.wait_for_load_state("networkidle")
        

            form_index = 0
            pending_success = []
            for i, q in enumerate(chunk):
                print(f"Uploading [Absolute #{q.absolute_index} | Internal Q{q.question_number}]: {q.title[:30]}...")
                try:
                    # 1. Fill Title
                    page.locator('input[name="question_title"]').nth(form_index).fill(q.title[:150])
                
                    # 2. Select Difficulty
                    diff_input = page.locator('input.select__input').nth(form_index * 3 + 0)
                    diff_input.click(force=True)
                    page.wait_for_timeout(100)
                    diff_input.fill(q.difficulty)
                    # Wait for menu to populate, then press ArrowDown to ensure the first item is highlighted, then Enter
                    page.wait_for_timeout(300)
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(50)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(100)
                    if diff_input.input_value() != "":
                        raise ValueError(f"CRITICAL ERROR: Failed to select Difficulty '{q.difficulty}'. This option is not available in the website dropdown.")
                
                    # 3. Select Tags
                    tag_input = page.locator('input.select__input').nth(form_index * 3 + 1)
                    tag_input.click(force=True)
                    page.wait_for_timeout(100)
                    tag_input.fill(q.tags)
                    page.wait_for_timeout(300)
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(50)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(100)
                    if tag_input.input_value() != "":
                        raise ValueError(f"CRITICAL ERROR: Failed to select Tag '{q.tags}'. This tag is not available in the website dropdown.")
                
                    # 4. Select Language
                    lang_input = page.locator('input.select__input').nth(form_index * 3 + 2)
                    lang_input.click(force=True)
                    page.wait_for_timeout(100)
                    lang_input.fill(q.language)
                    page.wait_for_timeout(300)
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(50)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(100)
                    if lang_input.input_value() != "":
                        raise ValueError(f"CRITICAL ERROR: Failed to select Language '{q.language}'. This language is not available in the website dropdown.")
                
                    # 5. Actual time
                    page.locator('input[name="actualTime"]').nth(form_index).fill(str(q.actual_time_minutes))
                
                    # 6. Question Text (Rich Text Editor)
                    editor = page.locator('.ProseMirror, [contenteditable="true"]').nth(form_index)
                    editor.fill(q.question_text)
                
                    # 7. File Attachment
                    if q.attachment_filename and getattr(q, 'resolved_attachment_path', None):
                        att_path = q.resolved_attachment_path
                        if att_path.exists():
                            print(f"Attaching: {q.attachment_filename}")
                            abs_path = str(att_path.absolute())
                            try:
                                # Using set_input_files breaks React state mapping, so we must physically click the dropzone.
                                # Since button counts vary between Academic and Programming subjects, we use XPath 
                                # to find the specific 'Click to upload' button immediately following THIS question's 'Assignment Attachments' label.
                                xpath = f"(//*[contains(text(), 'Assignment Attachments')])[{form_index + 1}]/following::*[contains(text(), 'Click to upload')][1]"
                                with page.expect_file_chooser() as fc_info:
                                    page.locator(xpath).click(force=True)
                                fc_info.value.set_files(abs_path)
                                print(f"Successfully injected file: {q.attachment_filename}")
                                # Wait a bit longer to allow the website to process the upload to their server
                                page.wait_for_timeout(1000)
                            except Exception as e:
                                print(f"Failed to attach file: {e}")
                        else:
                            print(f"WARNING: Attachment missing: {att_path}")
                        
                    # 8. User Response Acceptance (PDF, Images, Word, ZIP, etc.)
                    try:
                        acceptance_str = str(q.user_response_acceptance).lower()
                    
                        # Map keywords from the CSV to the exact button text on the website
                        format_map = {
                            "Word": ["word", "doc", "docx"],
                            "PDF": ["pdf"],
                            "ZIP": ["zip", "archive", "rar"],
                            "Images": ["img", "image", "images", "png", "jpg", "jpeg"],
                            "ODS / ODT": ["ods", "odt"],
                            "Video": ["video", "mp4", "avi"]
                        }
                    
                        # Check which buttons to click based on the keywords
                        for button_text, keywords in format_map.items():
                            if any(keyword in acceptance_str for keyword in keywords):
                                # Click the button with the exact text on the latest question form
                                page.locator(f'button:has-text("{button_text}")').last.click(timeout=2000)
                                page.wait_for_timeout(50)
                            
                    except Exception as e:
                        print(f"Note: Could not select file formats automatically: {e}")
                
                    # Stage success for this specific question insertion
                    pending_success.append(q)
                
                    # 9. Save or Add Another
                    if i == len(chunk) - 1:
                        print("Last question! Clicking Save Questions...")
                        page.locator('button', has_text='Save Questions').first.click()
                        print("Waiting for server to process the save...")
                        page.wait_for_timeout(2000)
                    
                        # Verify if the save was actually successful by checking if the modal closes
                        try:
                            # Wait up to 60 seconds for the modal/save button to disappear (bulk saves can take longer on the server)
                            page.locator('button', has_text='Save Questions').first.wait_for(state='hidden', timeout=60000)
                            print("[SUCCESS] Upload process completed successfully and questions were saved!")
                        
                            # Now that the server actually saved them, commit them to the log!
                            success_count += len(pending_success)
                            with open(log_file, "a", encoding="utf-8", newline="") as f:
                                writer = csv.writer(f)
                                for completed_q in pending_success:
                                    writer.writerow([current_docx_name, completed_q.absolute_index, "success", time.strftime("%Y-%m-%d %H:%M:%S"), ""])
                                
                        except Exception as save_err:
                            print(f"\n[CRITICAL ERROR] SAVING: The website rejected the save (or is taking too long)!")
                            print("The 'Save Questions' button is still visible, which means the popup did not close.")
                            
                            fail_count += len(pending_success)
                            with open(log_file, "a", encoding="utf-8", newline="") as f:
                                writer = csv.writer(f)
                                for failed_q in pending_success:
                                    writer.writerow([current_docx_name, failed_q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), "Save operation timed out or was rejected"])
                            
                            # Use break instead of raise to smoothly trigger the outer loop abort logic without double-logging the final question
                            break
                    else:
                        print("Clicking Add Question...")
                        page.get_by_role("button", name="Add Question").last.click()
                        page.wait_for_timeout(300)
                    
                    form_index += 1
                    
                except KeyboardInterrupt:
                    print(f"\n[INTERRUPTED] Upload interrupted by user (Ctrl+C) on [Absolute #{q.absolute_index}]!")
                    fail_count += 1
                    with open(log_file, "a", encoding="utf-8", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([current_docx_name, q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), "User interrupted (Ctrl+C)"])
                    break
                except Exception as e:
                    print(f"Failed on [Absolute #{q.absolute_index} | Internal Q{q.question_number}]: {e}")
                    fail_count += 1
                    Path("screenshots").mkdir(exist_ok=True)
                    page.screenshot(path=f"screenshots/failed_abs{q.absolute_index}_q{q.question_number}.png")
                    with open(log_file, "a", encoding="utf-8", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([current_docx_name, q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), str(e)])
                    break
            
            if fail_count > 0:
                print("\n[ABORT] Stopping remaining batches due to a failure or interrupt.")
                break

        total_seconds = int(time.time() - start_time)
        mins, secs = divmod(total_seconds, 60)
        time_str = f"{mins} mins {secs} secs" if mins > 0 else f"{secs} secs"
        
        print(f"\n=================================")
        print(f"UPLOAD COMPLETE")
        print(f"=================================")
        print(f"Success: {success_count}")
        print(f"Failed: {fail_count}")
        print(f"Time Taken: {time_str}")
        print(f"=================================\n")
        browser.close()
