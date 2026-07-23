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
    failed_questions_list = []
    global_similar_report = []
    start_time = time.time()
    
    def print_final_summary_report(is_abort=False, current_chunk=None):
        total_seconds = int(time.time() - start_time)
        mins, secs = divmod(total_seconds, 60)
        time_str = f"{mins} mins {secs} secs" if mins > 0 else f"{secs} secs"
        print("\n=================================")
        if is_abort:
            print("UPLOAD ABORTED (Ctrl+C)")
        else:
            print("UPLOAD COMPLETE")
        print("=================================")
        print(f"Success: {success_count}")
        if is_abort:
            print(f"Failed (incl. aborted batch): {fail_count + len(current_chunk)}")
        else:
            print(f"Failed: {fail_count}")
            if fail_count > 0:
                print(f"Failed Question Numbers: {failed_questions_list}")
        print(f"Time Taken: {time_str}")
        print("=================================\n")
        
        print("--- Similar Questions Report ---")
        if not global_similar_report:
            print("No similar questions were detected during this run.")
        else:
            for idx, report in enumerate(global_similar_report):
                print(f"Batch {idx + 1} (Q{report['start']} to Q{report['end']}):")
                if not report['similar_indexes']:
                    print("  None")
                else:
                    for q_idx in report['similar_indexes']:
                        print(f"  -> Q{q_idx} matched DB Title: '{report['similar_details'].get(q_idx, 'Unknown')}'")
        print("--------------------------------\n")

    # Clear old screenshots
    import shutil
    screenshots_dir = Path("screenshots")
    if screenshots_dir.exists():
        shutil.rmtree(screenshots_dir)
    screenshots_dir.mkdir(exist_ok=True)
    
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
        # Run headless (invisible) for maximum speed and zero visual clutter
        browser = p.chromium.launch(headless=True)
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
        
        print("Waiting for OTP input screen to render...")
        timeout = config.get("otp_wait_timeout_ms", 120000)
        
        # Check for invalid password error quickly before waiting for OTP
        try:
            # We wait a max of 2 seconds for the OTP field. If not there, we check for toasts.
            page.wait_for_selector('input[inputmode="numeric"]', timeout=3000)
        except Exception:
            # Check for error toast
            body_text = page.locator('body').inner_text().lower()
            if "invalid password" in body_text or "invalid credentials" in body_text or "wrong" in body_text:
                print("\n[ERROR] Login Failed: Incorrect Password or Username entered!")
                Path("screenshots").mkdir(exist_ok=True)
                dt_str = time.strftime("%Y-%m-%d_%H-%M-%S")
                page.screenshot(path=f"screenshots/login_failed_credentials_{dt_str}.png")
                browser.close()
                return
            else:
                # Still wait for the full timeout if no clear error is found
                page.wait_for_selector('input[inputmode="numeric"]', timeout=timeout)
        
        # Prompt for OTP in the terminal
        otp = input("Enter the 6-digit OTP here: ").strip()
        
        # Type the OTP into the browser
        print("Submitting OTP...")
        # Usually clicking the first input and typing works for these split-input React components
        page.locator('input[inputmode="numeric"]').first.click()
        page.keyboard.type(otp)
        
        # Wait until we are successfully logged in (URL changes from login page)
        print("Waiting for dashboard to load...")
        try:
            page.wait_for_url(lambda url: "login" not in url, timeout=3000)
        except Exception:
            body_text = page.locator('body').inner_text().lower()
            if "invalid otp" in body_text or "wrong otp" in body_text or "expired" in body_text:
                print("\n[ERROR] Login Failed: Incorrect or Expired OTP entered!")
                Path("screenshots").mkdir(exist_ok=True)
                dt_str = time.strftime("%Y-%m-%d_%H-%M-%S")
                page.screenshot(path=f"screenshots/login_failed_otp_{dt_str}.png")
                browser.close()
                return
            else:
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
                
        # --- Final UI Verification Function ---
        def take_final_screenshot(page_obj, conf, s_count):
            print("\n[VERIFICATION] Verifying final count on 'Our Questions' page...")
            try:
                # Reload the dashboard immediately to guarantee a clean state
                page_obj.goto(conf["question_bank_url"])
                page_obj.wait_for_timeout(1500)
                    
                # 1. Click "Our Questions" button
                page_obj.locator('button:has-text("Our Questions")').first.click(timeout=5000)
                page_obj.wait_for_timeout(1500)
                
                # 2. Search for the course
                search_input = page_obj.locator('input[placeholder="Search for Course..."], input[placeholder*="Search for"]')
                if search_input.count() > 0:
                    search_input.first.fill(conf["course_name"])
                    page_obj.wait_for_timeout(1000)
                
                # 3. Click the matching course card
                page_obj.locator(f'p:has-text("{conf["course_name"]}")').first.click(timeout=5000)
                page_obj.wait_for_timeout(2000)
                
                # 4. Try to extract the specific question count for the module
                try:
                    module_name = conf["module_name"]
                    # Find a text node that matches digits followed by "Questions" near the module name
                    count_pill = page_obj.locator(f'div:has-text("{module_name}")').locator('text=/\\d+\\s+Questions/').first
                    if count_pill.is_visible():
                        count_text = count_pill.inner_text().strip()
                        print(f"✅ [SUCCESS] Verification found module '{module_name}': {count_text}")
                    else:
                        print(f"⚠️ [WARNING] Could not read the exact question count for '{module_name}'.")
                except Exception:
                    pass
                    
                # Take a screenshot for the user's peace of mind
                Path("screenshots").mkdir(exist_ok=True)
                dt_str = time.strftime("%Y-%m-%d_%H-%M-%S")
                screenshot_path = f"screenshots/final_verification_{dt_str}.png"
                page_obj.screenshot(path=screenshot_path, full_page=True)
                print(f"[VERIFICATION] Saved screenshot of the module page to: {screenshot_path}")
                
            except Exception as e:
                print(f"[WARNING] Could not complete UI verification (navigation failed). Reason: {e}")
                Path("screenshots").mkdir(exist_ok=True)
                dt_str = time.strftime("%Y-%m-%d_%H-%M-%S")
                page_obj.screenshot(path=f"screenshots/ui_verification_failed_{dt_str}.png")
        
        # Process questions in chunks
        chunk_size = 20
        user_aborted = False
        for chunk_start in range(0, len(questions_to_upload), chunk_size):
            if user_aborted:
                break
            chunk = questions_to_upload[chunk_start:chunk_start + chunk_size]
            print("\n=====================================")
            print(f"Processing Batch: Questions {chunk[0].absolute_index} to {chunk[-1].absolute_index} (Batch size: {len(chunk)})")
            print("=====================================\n")
            
            print("Navigating to Question Bank (Clearing DOM Memory)...")
            page.goto(config["question_bank_url"])
            page.wait_for_timeout(1500)
            
            # --- Check for silent session expiration ---
            if "login" in page.url.lower():
                print("\n[CRITICAL ERROR] Session expired silently mid-run!")
                print(f"Failed at Batch: Q{chunk[0].absolute_index}")
                break
        
            # --- 2. Navigate UI exactly as requested ---
        
            # 3. Click + Add Questions tab
            print("Clicking '+ Add Questions' tab...")
            page.locator('text=Add Questions').first.click()
            page.wait_for_timeout(500)
        
            # 4. Select subject type
            if config.get("subject_type") == "programming":
                print("Clicking 'Prog... Subjects' tab...")
                page.locator('text=Prog... Subjects').first.click()
            else:
                print("Clicking 'Academic' tab...")
                page.locator('text=Academic').first.click()
            page.wait_for_timeout(500)
        
            # 5. Search and select course and module
            course = config["course_name"]
            module = config["module_name"]
        
            print(f"Searching and Selecting Course: {course}")
            search_input = page.locator('input[name="search_term"]')
            if search_input.count() > 0:
                search_input.fill(course)
                page.wait_for_timeout(500)
            
            course_loc = page.get_by_text(course, exact=True).first
            try:
                course_loc.click(timeout=5000, force=True)
            except Exception:
                print(f"\n❌ ERROR: Could not find Course '{course}'.")
                print("The course may have been renamed, deleted, or its visibility restricted prior to this upload batch.")
                with open(log_file, "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    for q in questions_to_upload[chunk_start:]:
                        writer.writerow([current_docx_name, q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), f"Course '{course}' missing"])
                browser.close()
                return
            
            page.wait_for_timeout(500)
        
            print(f"Selecting Module: {module}")
            module_loc = page.get_by_text(module, exact=True).first
            try:
                module_loc.click(timeout=5000, force=True)
            except Exception:
                print(f"\n[ERROR] Could not find Module '{module}'.")
                print("The module may have been renamed, deleted, or its visibility restricted prior to this upload batch.")
                with open(log_file, "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    for q in questions_to_upload[chunk_start:]:
                        writer.writerow([current_docx_name, q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), f"Module '{module}' missing"])
                browser.close()
                return
            
            page.wait_for_timeout(500)
        
            # 5. Click the "Project Questions" card
            print("Clicking 'Project Questions' card...")
            page.locator('text=Project Questions').first.click(force=True)
            page.wait_for_timeout(1000)
            # Wait for the configuration form to appear
            expect(page.get_by_text("Project Questions Configuration")).to_be_visible(timeout=10000)
            page.wait_for_load_state("networkidle")
        

            form_index = 0
            pending_success = []
            batch_success = True
            batch_error_reason = ""
            
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
                    page.wait_for_timeout(300)
                    if page.locator('text="No options"').is_visible():
                        raise ValueError(f"Difficulty '{q.difficulty}' does not exist (No options found).")
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(50)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(100)
                    if diff_input.input_value() != "":
                        raise ValueError(f"Failed to select Difficulty '{q.difficulty}'.")
                
                    # 3. Select Tags
                    tag_input = page.locator('input.select__input').nth(form_index * 3 + 1)
                    tag_input.click(force=True)
                    page.wait_for_timeout(100)
                    tag_input.fill(q.tags)
                    page.wait_for_timeout(300)
                    if page.locator('text="No options"').is_visible():
                        raise ValueError(f"Tag '{q.tags}' does not exist in the system (No options found).")
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(50)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(100)
                    if tag_input.input_value() != "":
                        raise ValueError(f"Failed to select Tag '{q.tags}'.")
                
                    # 4. Select Language
                    lang_input = page.locator('input.select__input').nth(form_index * 3 + 2)
                    lang_input.click(force=True)
                    page.wait_for_timeout(100)
                    lang_input.fill(q.language)
                    page.wait_for_timeout(300)
                    if page.locator('text="No options"').is_visible():
                        raise ValueError(f"Language '{q.language}' does not exist in the system (No options found).")
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(50)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(100)
                    if lang_input.input_value() != "":
                        raise ValueError(f"Failed to select Language '{q.language}'.")
                
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
                                xpath = f"(//*[contains(text(), 'Assignment Attachments')])[{form_index + 1}]/following::*[contains(text(), 'Click to upload')][1]"
                                with page.expect_file_chooser() as fc_info:
                                    page.locator(xpath).click(force=True)
                                fc_info.value.set_files(abs_path)
                                print(f"Successfully injected file: {q.attachment_filename}")
                                page.wait_for_timeout(300)
                            except Exception as e:
                                print(f"Failed to attach file: {e}")
                        else:
                            print(f"WARNING: Attachment missing: {att_path}")
                        
                    # 8. User Response Acceptance
                    try:
                        acceptance_str = str(q.user_response_acceptance).lower()
                        format_map = {
                            "Word": ["word", "doc", "docx"],
                            "PDF": ["pdf"],
                            "ZIP": ["zip", "archive", "rar"],
                            "Images": ["img", "image", "images", "png", "jpg", "jpeg"],
                            "ODS / ODT": ["ods", "odt"],
                            "Video": ["video", "mp4", "avi"]
                        }
                        for button_text, keywords in format_map.items():
                            if any(keyword in acceptance_str for keyword in keywords):
                                page.locator(f'button:has-text("{button_text}")').last.click(timeout=2000)
                                page.wait_for_timeout(50)
                    except Exception as e:
                        pass
                
                    pending_success.append(q)
                
                    # 9. Save or Add Another
                    if i == len(chunk) - 1:
                        print("Last question! Clicking Save Questions...")
                        try:
                            page.locator('button', has_text='Save Questions').first.click(timeout=5000, force=True)
                        except Exception as e:
                            print(f"\n[CRITICAL ERROR] Failed to click 'Save Questions' button! ({e})")
                            batch_success = False
                            batch_error_reason = "Failed to click Save button"
                            break
                            
                        print("Waiting for server to process the save...")
                        
                        save_success = False
                        confirm_handled = False
                        similar_indexes = []
                        similar_details = {}
                        
                        # Wait up to 60 seconds for the save button to hide
                        for wait_idx in range(60):
                            if page.locator('button', has_text='Save Questions').first.is_hidden():
                                save_success = True
                                break
                                
                            # Check if the similar confirm popup appeared
                            try:
                                confirm_btn = page.locator('button:has-text("Save Anyway"), button:has-text("Confirm")').first
                                if confirm_btn.is_visible():
                                    if not confirm_handled:
                                        print("\n[WARNING] Server detected similar questions!")
                                        
                                        # Scrape similar titles from modal before confirming
                                        try:
                                            modal_text = page.locator('body').inner_text()
                                            
                                            blocks = modal_text.split("Question: ")
                                            for block in blocks[1:]:
                                                lines = [line.strip() for line in block.split('\n') if line.strip()]
                                                if not lines:
                                                    continue
                                                    
                                                our_title_extracted = lines[0].lower()
                                                
                                                db_title = "Unknown DB Entry"
                                                if "Similar Existing Titles:" in lines:
                                                    idx = lines.index("Similar Existing Titles:")
                                                    if idx + 1 < len(lines):
                                                        db_title = lines[idx + 1].lstrip("•*- ").strip()
                                                        
                                                for pq in pending_success:
                                                    clean_title = pq.title.strip().lower()
                                                    if clean_title[:20] in our_title_extracted or our_title_extracted[:20] in clean_title:
                                                        if pq.absolute_index not in similar_indexes:
                                                            similar_indexes.append(pq.absolute_index)
                                                            similar_details[pq.absolute_index] = db_title
                                                        break
                                                    
                                            if similar_indexes:
                                                print(f"Identified similar questions at Abs Indexes: {similar_indexes}")
                                                for idx in similar_indexes:
                                                    print(f"  -> Q{idx} matched DB Title: '{similar_details[idx]}'")
                                        except Exception as parse_e:
                                            print(f"Could not parse similar titles: {parse_e}")
                                            
                                        btn_text = confirm_btn.inner_text().strip()
                                        print(f"Clicking '{btn_text}' to automatically bypass and force upload...")
                                        confirm_btn.click(force=True)
                                        confirm_handled = True
                                        page.wait_for_timeout(2000) # Give it time to process the confirm
                                        continue
                            except Exception:
                                pass
                                
                            page.wait_for_timeout(1000)
                        
                        if save_success:
                            print("[SUCCESS] Upload process completed successfully and questions were saved!")
                            success_count += len(pending_success)
                            
                            global_similar_report.append({
                                'start': chunk[0].absolute_index,
                                'end': chunk[-1].absolute_index,
                                'similar_indexes': similar_indexes.copy(),
                                'similar_details': similar_details.copy()
                            })
                            
                            with open(log_file, "a", encoding="utf-8", newline="") as f:
                                writer = csv.writer(f)
                                for completed_q in pending_success:
                                    status = "success"
                                    reason = ""
                                    if completed_q.absolute_index in similar_indexes:
                                        status = "success (similar warning)"
                                        db_match = similar_details.get(completed_q.absolute_index, "Unknown DB Entry")
                                        reason = f"Server flagged as similar to DB entry: '{db_match}'"
                                    writer.writerow([current_docx_name, completed_q.absolute_index, status, time.strftime("%Y-%m-%d %H:%M:%S"), reason])
                        else:
                            print("\n[CRITICAL ERROR] SAVING: The website rejected the save or timed out!")
                            error_reason = "Save operation timed out (server took too long)"
                            
                            try:
                                toasts = page.locator('.Toastify__toast, .toast, .alert, .swal-modal, .modal-content').all_inner_texts()
                                if toasts:
                                    error_reason = "Server Message: " + " | ".join([t.replace('\n', ' ') for t in toasts])
                                else:
                                    body_text = page.locator('body').inner_text().lower()
                                    if "already exist" in body_text or "similar question" in body_text:
                                        error_reason = "Similar question detected by server"
                            except Exception:
                                pass
                                
                            print(f"Reason: {error_reason}")
                            batch_success = False
                            batch_error_reason = error_reason
                            break
                    else:
                        print("Clicking Add Question...")
                        page.get_by_role("button", name="Add Question").last.click(force=True)
                        page.wait_for_timeout(300)
                    
                    form_index += 1
                    
                except KeyboardInterrupt:
                    print(f"\n[INTERRUPTED] Upload interrupted by user (Ctrl+C) on [Absolute #{q.absolute_index}]!")
                    print("\n[ABORT] Stopping all remaining batches due to user interrupt.")
                    
                    # Log the failed batch to CSV before hard exiting
                    try:
                        with open(log_file, "a", encoding="utf-8", newline="") as f:
                            writer = csv.writer(f)
                            for failed_q in chunk:
                                writer.writerow([current_docx_name, failed_q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), "User interrupted (Ctrl+C)"])
                    except Exception as e:
                        print(f"Could not write to run_log.csv: {e}")
                        
                    # Print summary statistics manually before hard kill
                    print_final_summary_report(is_abort=True, current_chunk=chunk)
                    os._exit(1)
                except Exception as e:
                    error_msg = str(e)
                    if "Timeout" in error_msg:
                        error_msg = f"Timeout Error: DOM lag or element missing ({error_msg.splitlines()[0]})"
                    print(f"Failed on [Absolute #{q.absolute_index} | Internal Q{q.question_number}]: {error_msg}")
                    batch_success = False
                    batch_error_reason = error_msg
                    Path("screenshots").mkdir(exist_ok=True)
                    dt_str = time.strftime("%Y-%m-%d_%H-%M-%S")
                    page.screenshot(path=f"screenshots/failed_abs{q.absolute_index}_{dt_str}.png")
                    break

            # Handle the result of the chunk upload
            if not batch_success:
                print(f"\n[BATCH FAILED] The batch from Q{chunk[0].absolute_index} to Q{chunk[-1].absolute_index} failed!")
                print(f"Detailed Error Reason: {batch_error_reason}")
                print(f"--> PLEASE FIX THE ISSUE AND RE-RUN STARTING FROM Q{chunk[0].absolute_index}")
                
                fail_count += len(chunk)
                with open(log_file, "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    for failed_q in chunk:
                        writer.writerow([current_docx_name, failed_q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), batch_error_reason])
                        failed_questions_list.append(failed_q.absolute_index)
                
                break # Abort the rest of the chunks
                
        # Skip UI verification to save time as requested by user
        print_final_summary_report(is_abort=False)
        browser.close()
