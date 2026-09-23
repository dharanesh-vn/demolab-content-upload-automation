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
    success_with_attachment_count = 0
    success_without_attachment_count = 0
    fail_count = 0
    failed_questions_list = []
    global_similar_report = []
    start_time = time.time()
    
    def print_final_summary_report(is_abort=False, current_chunk=None):
        total_seconds = int(time.time() - start_time)
        max_mins, max_secs = divmod(total_seconds, 60)
        time_str = f"{max_mins} mins {max_secs} secs" if max_mins > 0 else f"{max_secs} secs"
        print("\n=================================")
        if is_abort:
            print("=== UPLOAD ABORTED (Ctrl+C) ===")
        else:
            print("=== UPLOAD COMPLETE ===")
        print("=================================")
        print(f"Total Questions Uploaded : {success_count}")
        print(f"  |-- With Attachments   : {success_with_attachment_count}")
        print(f"  |-- Without Attachments: {success_without_attachment_count}")
        if is_abort:
            actual_failed = fail_count + (len(current_chunk) if current_chunk else 0)
            print(f"Failed Questions         : {actual_failed}")
        else:
            print(f"Failed Questions         : {fail_count}")
            if fail_count > 0:
                print(f"Failed Question Numbers  : {failed_questions_list}")
        print(f"Total Time Taken         : {time_str}")
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
    
    # Prepare enhanced run log
    log_file = Path("run_log.csv")
    completed_q_nums = set()
    current_docx_name = Path(config["docx_path"]).name
    target_course = config.get("course_name", "").strip().lower()
    target_module = config.get("module_name", "").strip().lower()
    
    def get_diagnostic_tag(status_str: str, reason_str: str, att_status: str) -> str:
        s_upper = str(status_str).strip().upper()
        r_lower = str(reason_str).strip().lower()
        
        if "similar" in r_lower or "bypassed" in s_upper or "similar warning" in r_lower:
            return "[SIMILAR_DUPLICATE_BYPASSED]"
        elif "user interrupted" in r_lower or "ctrl+c" in r_lower:
            return "[USER_INTERRUPTED_ABORT]"
        elif "tag" in r_lower and ("not exist" in r_lower or "no options" in r_lower):
            return "[TAG_NOT_FOUND]"
        elif "difficulty" in r_lower and ("not exist" in r_lower or "no options" in r_lower):
            return "[DIFFICULTY_NOT_FOUND]"
        elif "language" in r_lower and ("not exist" in r_lower or "no options" in r_lower):
            return "[LANGUAGE_NOT_FOUND]"
        elif "course" in r_lower and ("not find" in r_lower or "no options" in r_lower):
            return "[COURSE_NOT_FOUND]"
        elif "save" in r_lower and "button" in r_lower:
            return "[SAVE_BUTTON_CLICK_FAILED]"
        elif "timeout" in r_lower or "rejected" in r_lower:
            return "[SAVE_TIMEOUT_REJECTED]"
        elif att_status == "Missing Local File":
            return "[ATTACHMENT_MISSING_LOCAL]"
        elif s_upper.startswith("SUCCESS"):
            if att_status == "Attached Successfully":
                return "[SUCCESS_WITH_ATTACHMENT]"
            else:
                return "[SUCCESS_CLEAN]"
        else:
            return "[UNKNOWN_ERROR]"
            
    # 13-Column Categorized Diagnostic Log Schema:
    enhanced_headers = [
        "Timestamp", "Course Name", "Module Name", "Document Name", 
        "Absolute Index", "Internal Q#", "Question Title", "Tags", 
        "Attachment File", "Attachment Status", "Upload Status", "Diagnostic Tag", "Diagnostic Details"
    ]
    
    if not log_file.exists():
        with open(log_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(enhanced_headers)
    else:
        # Read existing logs to determine completed questions for THIS SPECIFIC course & module
        with open(log_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0].startswith("---") or row[0] == "Timestamp":
                    continue
                # Enhanced 13-column / 12-column schema
                if len(row) >= 11:
                    c_name = row[1].strip().lower()
                    m_name = row[2].strip().lower()
                    d_name = row[3].strip()
                    status = row[10].strip().upper()
                    
                    if c_name == target_course and m_name == target_module and d_name == current_docx_name and status.startswith("SUCCESS"):
                        try:
                            completed_q_nums.add(int(row[4]))
                        except ValueError:
                            pass
                # Legacy format (5 columns: doc_name, question_num, status, timestamp, details)
                elif len(row) >= 3 and row[0] == current_docx_name and row[2].lower() == "success":
                    try:
                        completed_q_nums.add(int(row[1]))
                    except ValueError:
                        pass
    
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
        page.wait_for_selector('input[name="email"]', timeout=15000)
        page.fill('input[name="email"]', credentials["username"])
        page.fill('input[name="password"]', credentials["password"])
        page.click('button:has-text("Login"), button[type="submit"]')
        
        # Quick check for immediate login credentials error (wait up to 3 seconds)
        page.wait_for_timeout(1500) # Wait a moment for DOM/toast to update
        body_text = page.locator('body').inner_text()
        body_text_lower = body_text.lower()
        
        # Check for common login error messages
        login_error_keywords = ["does not match", "invalid password", "invalid credentials", "wrong email", "incorrect password", "user not found", "wrong password", "does not exist", "not exist"]
        has_error = any(kw in body_text_lower for kw in login_error_keywords)
        
        if has_error:
            error_msg = "Incorrect username or password."
            try:
                toasts = page.locator('.Toastify__toast, .toast, .alert, [role="alert"]').all_inner_texts()
                if toasts:
                    error_msg = " | ".join([t.replace('\n', ' ').strip() for t in toasts if t.strip()])
                else:
                    # Look for input validation error elements (usually red text below inputs)
                    match_el = page.locator('text=/does not match|invalid|incorrect|exist/i').first
                    if match_el.is_visible():
                        error_msg = match_el.inner_text().strip()
            except Exception:
                pass
                
            current_url = config['login_url']
            suggested_url = "https://dotlab.amypo.ai/login" if "demolab" in current_url else "https://demolab.amypo.ai/login"
            
            print("\n=======================================================")
            print(f"❌ ERROR: Invalid username or password in .env ({error_msg})")
            print(f"   Current login URL: {current_url}")
            print("=======================================================\n")
            Path("screenshots").mkdir(exist_ok=True)
            dt_str = time.strftime("%Y-%m-%d_%H-%M-%S")
            page.screenshot(path=f"screenshots/login_failed_credentials_{dt_str}.png")
            browser.close()
            return

        # Wait to see if we go directly to dashboard or hit the OTP screen
        print("Waiting for login response...")
        timeout = config.get("otp_wait_timeout_ms", 120000)
        try:
            # Wait up to 5 seconds for either OTP input or direct URL redirection
            page.wait_for_selector('input[inputmode="numeric"]', timeout=5000)
        except Exception:
            pass
            
        otp_required = page.locator('input[inputmode="numeric"]').count() > 0 and page.locator('input[inputmode="numeric"]').first.is_visible()
        
        if otp_required:
            print("OTP screen detected. Waiting for manual entry...")
            # Prompt for OTP in the terminal
            otp = input("Enter the 6-digit OTP here: ").strip()
            
            # Type the OTP into the browser
            print("Submitting OTP...")
            page.locator('input[inputmode="numeric"]').first.click()
            page.keyboard.type(otp)
            
            # Wait until we are successfully logged in (Dashboard element is visible)
            print("Waiting for dashboard to load after OTP...")
            try:
                page.wait_for_selector('text=Dashboard', timeout=15000)
            except Exception:
                body_text = page.locator('body').inner_text().lower()
                if "invalid otp" in body_text or "wrong otp" in body_text or "incorrect otp" in body_text or "incorrect" in body_text or "expired" in body_text:
                    print("\n=======================================================")
                    print("❌ ERROR: Incorrect or expired OTP entered.")
                    print("=======================================================\n")
                    Path("screenshots").mkdir(exist_ok=True)
                    dt_str = time.strftime("%Y-%m-%d_%H-%M-%S")
                    page.screenshot(path=f"screenshots/login_failed_otp_{dt_str}.png")
                    browser.close()
                    return
                else:
                    page.wait_for_selector('text=Dashboard', timeout=timeout)
        else:
            print("No OTP required. Navigating directly to Question Bank...")
            page.goto(config["question_bank_url"])
            page.wait_for_timeout(2000)
        
        page.wait_for_timeout(3000)  # Give it a moment to establish the session
        
        # --- Filter out already completed questions ---
        questions_to_upload = [q for q in questions if q.absolute_index not in completed_q_nums]
        
        if not questions_to_upload:
            print("\n=======================================================")
            print(f"ℹ️  SKIP NOTICE: All {len(questions)} selected questions (Q{questions[0].absolute_index} to Q{questions[-1].absolute_index})")
            print(f"   for Course: '{config.get('course_name', '')}' | Module: '{config.get('module_name', '')}'")
            print("   have ALREADY been uploaded successfully according to 'run_log.csv'.")
            print("   No duplicate questions were sent to the portal.")
            print("=======================================================\n")
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
                print("\n=======================================================")
                print(f"❌ WARNING: Course name not found ('{course}').")
                print("=======================================================\n")
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
                print("\n=======================================================")
                print(f"❌ WARNING: Module name not found ('{module}').")
                print("=======================================================\n")
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
            # This is a single-page app, so background requests may prevent networkidle indefinitely.
            page.wait_for_timeout(500)
        

            form_index = 0
            pending_success = []
            batch_success = True
            batch_error_reason = ""
            
            for i, q in enumerate(chunk):
                print(f"Uploading [Absolute #{q.absolute_index} | Internal Q{q.question_number}]: {q.title[:30]}...")
                try:
                    # Locate the specific form block container for this question card
                    title_input = page.locator('input[name="question_title"]').nth(form_index)
                    # Find the parent card element wrapping both title and attachment input for this question
                    card_candidate = title_input.locator('xpath=ancestor::div[.//input[@name="question_title"] and .//input[@type="file"]][1]')
                    if card_candidate.count() > 0:
                        form_block = card_candidate
                    else:
                        form_block = title_input.locator('xpath=ancestor::div[contains(@class, "relative") or contains(@class, "w-full") or contains(@class, "border")][1]')

                    # 1. Fill Title
                    title_input.fill(q.title[:150])
                
                    def select_dropdown_option(inp_el, val_text, f_name):
                        if not val_text or not str(val_text).strip() or inp_el.count() == 0:
                            return
                        clean_v = str(val_text).strip()
                        inp_el.click(force=True)
                        page.wait_for_timeout(100)
                        
                        # Try different case variations: Title Case, original, capitalized, lower, upper
                        vars_to_try = [clean_v.title(), clean_v, clean_v.capitalize(), clean_v.lower(), clean_v.upper()]
                        unique_vars = []
                        for v in vars_to_try:
                            if v not in unique_vars:
                                unique_vars.append(v)
                                
                        is_sel = False
                        for v in unique_vars:
                            inp_el.fill("")
                            inp_el.fill(v)
                            page.wait_for_timeout(200)
                            
                            if page.locator('text="No options"').is_visible():
                                continue

                            # Try clicking matching option element from dropdown list
                            opt_items = page.locator('.select__option, [class*="-option"], div[id*="option"]').filter(
                                has_text=re.compile(f"^{re.escape(clean_v)}$", re.IGNORECASE)
                            )
                            if opt_items.count() > 0:
                                opt_items.first.click(force=True)
                                page.wait_for_timeout(100)
                                is_sel = True
                                break
                                
                            # Fallback: keyboard navigation
                            page.keyboard.press("ArrowDown")
                            page.wait_for_timeout(50)
                            page.keyboard.press("Enter")
                            page.wait_for_timeout(100)
                            if inp_el.input_value() == "":
                                is_sel = True
                                break

                        if not is_sel:
                            raise ValueError(f"❌ WARNING: {f_name} option not found ('{val_text}').")

                    # 2. Select Difficulty
                    diff_input = form_block.locator('xpath=.//div[count(.//input[contains(@class, "select")]) = 1 and contains(., "Difficulty")]//input[contains(@class, "select")]').first
                    if diff_input.count() == 0:
                        diff_input = form_block.locator('input.select__input').nth(0)
                    select_dropdown_option(diff_input, q.difficulty, "Difficulty")

                    # 3. Select Tags
                    tag_input = form_block.locator('xpath=.//div[count(.//input[contains(@class, "select")]) = 1 and (contains(., "Tags") or contains(., "Tag"))]//input[contains(@class, "select")]').first
                    if tag_input.count() == 0:
                        tag_input = form_block.locator('input.select__input').nth(1)
                    select_dropdown_option(tag_input, q.tags, "Tag")

                    # 4. Select Language
                    lang_input = form_block.locator('xpath=.//div[count(.//input[contains(@class, "select")]) = 1 and contains(., "Language")]//input[contains(@class, "select")]').first
                    if lang_input.count() == 0 and form_block.locator('input.select__input').count() > 2:
                        lang_input = form_block.locator('input.select__input').nth(2)
                    if lang_input.count() > 0:
                        select_dropdown_option(lang_input, q.language, "Language")
                
                    # 5. Actual time
                    actual_time_inp = form_block.locator('input[name="actualTime"]')
                    if actual_time_inp.count() > 0:
                        actual_time_inp.first.fill(str(q.actual_time_minutes))
                    else:
                        page.locator('input[name="actualTime"]').nth(form_index).fill(str(q.actual_time_minutes))
                
                    # 6. Question Text (Rich Text Editor - Tiptap / ProseMirror)
                    editor = form_block.locator('.ProseMirror, [contenteditable="true"]').first
                    if editor.count() == 0:
                        editor = page.locator('.ProseMirror, [contenteditable="true"]').nth(form_index)
                    try:
                        injected = page.evaluate("""({ idx, html }) => {
                            const editors = document.querySelectorAll('.ProseMirror, [contenteditable="true"]');
                            const el = editors[idx];
                            if (!el) return false;
                            if (el.editor && el.editor.commands && typeof el.editor.commands.setContent === 'function') {
                                el.editor.commands.setContent(html, true);
                                return true;
                            }
                            return false;
                        }""", {"idx": form_index, "html": q.question_text})
                        
                        if injected:
                            # Perform native Playwright keypress trigger to ensure React Hook Form marks field valid
                            editor.click(force=True)
                            page.keyboard.press("End")
                            page.keyboard.press("Space")
                            page.keyboard.press("Backspace")
                            page.wait_for_timeout(100)
                        else:
                            editor.fill(q.question_text)
                    except Exception:
                        editor.fill(q.question_text)
                
                    # 7. File Attachment
                    if q.attachment_filename and getattr(q, 'resolved_attachment_path', None):
                        att_path = Path(q.resolved_attachment_path) if isinstance(q.resolved_attachment_path, (str, Path)) else None
                        if att_path and att_path.exists():
                            print(f"Attaching: {q.attachment_filename}")
                            try:
                                att_input_loc = form_block.locator('input[type="file"]:not([accept*="image"])')
                                if att_input_loc.count() == 0:
                                    target_input = page.locator('input[type="file"]:not([accept*="image"])').nth(form_index)
                                else:
                                    target_input = att_input_loc.first
                                    
                                target_input.set_input_files(str(att_path.absolute()))
                                print(f"Successfully injected file: {att_path.name}")
                                page.wait_for_timeout(300)
                            except Exception as e:
                                print(f"Failed to attach file: {e}")
                        else:
                            print(f"⚠️ WARNING: Local attachment file not found ('{att_path.name if att_path else q.attachment_filename}').")
                        
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
                                btn_loc = form_block.locator(f'button:has-text("{button_text}")')
                                if btn_loc.count() > 0:
                                    btn_loc.first.click(timeout=2000)
                                else:
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
                            print("\n=======================================================")
                            print(f"❌ ERROR: Could not click 'Save Questions' button.")
                            print("=======================================================\n")
                            batch_success = False
                            batch_error_reason = "Failed to click Save button"
                            break
                            
                        print("Waiting for server to process the save...")
                        
                        save_success = False
                        confirm_handled = False
                        similar_indexes = []
                        similar_details = {}
                        
                        # The Save Questions button remains visible after a successful save.
                        # A cleared first form is the reliable completion signal for this SPA.
                        for wait_idx in range(60):
                            success_notice = page.locator(
                                '.Toastify__toast, .toast, .alert, [role="alert"], div:has-text("saved successfully"), div:has-text("Question saved")'
                            ).filter(has_text=re.compile(r'success|saved|added|created', re.IGNORECASE))
                            first_title = page.locator('input[name="question_title"]').first
                            first_title_cleared = (
                                first_title.count() > 0 and first_title.input_value().strip() == ""
                            )
                            if success_notice.count() > 0 or first_title_cleared:
                                save_success = True
                                break
                                
                            # Check if the similar confirm popup appeared
                            try:
                                confirm_btn = page.locator('button:has-text("Save Anyway"), button:has-text("Confirm")').first
                                if confirm_btn.is_visible():
                                    if not confirm_handled:
                                        print("\n⚠️ WARNING: Similar questions found. Auto-clicking 'Save Anyway'.")
                                        
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
                                        
                                        # Check right after Save Anyway click if success toast appears
                                        if page.locator('text=/saved successfully|question saved|created/i').count() > 0:
                                            save_success = True
                                            break
                                        continue
                            except Exception:
                                pass
                                
                            page.wait_for_timeout(1000)
                        
                        # Fallback: check if page body contains success message
                        if not save_success:
                            toasts_check = page.locator('.Toastify__toast, .toast, .alert, [role="alert"]').all_inner_texts()
                            if any("saved successfully" in t.lower() or "success" in t.lower() for t in toasts_check):
                                save_success = True

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
                                    status = "SUCCESS"
                                    reason = ""
                                    if completed_q.absolute_index in similar_indexes:
                                        status = "SUCCESS (Similar Warning Bypassed)"
                                        db_match = similar_details.get(completed_q.absolute_index, "Unknown DB Entry")
                                        reason = f"Server flagged as similar to DB entry: '{db_match}'"
                                        
                                    att_file_name = completed_q.attachment_filename or ""
                                    if not att_file_name:
                                        att_status = "No Attachment"
                                        success_without_attachment_count += 1
                                    elif completed_q.resolved_attachment_path and Path(completed_q.resolved_attachment_path).exists():
                                        att_status = "Attached Successfully"
                                        success_with_attachment_count += 1
                                    else:
                                        att_status = "Missing Local File"
                                        success_without_attachment_count += 1

                                    diag_tag = get_diagnostic_tag(status, reason, att_status)
                                    writer.writerow([
                                        time.strftime("%Y-%m-%d %H:%M:%S"),
                                        config.get("course_name", ""),
                                        config.get("module_name", ""),
                                        current_docx_name,
                                        completed_q.absolute_index,
                                        f"Q{completed_q.question_number}",
                                        completed_q.title[:60],
                                        completed_q.tags,
                                        att_file_name,
                                        att_status,
                                        status,
                                        diag_tag,
                                        reason
                                    ])
                        else:
                            print("\n=======================================================")
                            print("❌ ERROR: Save failed on server (timed out or invalid fields).")
                            print("=======================================================\n")
                            error_reason = "Save operation timed out (server took too long or fields are invalid)"
                            
                            # Capture a screenshot immediately to see validation errors / modals
                            Path("screenshots").mkdir(exist_ok=True)
                            dt_str = time.strftime("%Y-%m-%d_%H-%M-%S")
                            save_failed_screenshot = f"screenshots/save_failed_{dt_str}.png"
                            page.screenshot(path=save_failed_screenshot, full_page=True)
                            print(f"[DIAGNOSTIC] Saved screenshot of save failure to: {save_failed_screenshot}")
                            
                            try:
                                toasts = page.locator(
                                    '.Toastify__toast, .toast, .alert, .swal-modal, .modal-content, [role="alert"]'
                                ).all_inner_texts()
                                if toasts:
                                    messages = [t.replace('\n', ' ').strip() for t in toasts if t.strip()]
                                    if messages:
                                        error_reason = "Server Message: " + " | ".join(messages)
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
                    print("\n=======================================================")
                    print(f"🛑 CANCELLED: Upload stopped by user (Ctrl+C) on Q{q.absolute_index}.")
                    print("=======================================================\n")
                    
                    # Log the failed batch to CSV before hard exiting
                    try:
                        with open(log_file, "a", encoding="utf-8", newline="") as f:
                            writer = csv.writer(f)
                            for failed_q in chunk:
                                att_file_name = failed_q.attachment_filename or ""
                                if not att_file_name:
                                    att_status = "No Attachment"
                                elif failed_q.resolved_attachment_path and Path(failed_q.resolved_attachment_path).exists():
                                    att_status = "Attached Successfully"
                                else:
                                    att_status = "Missing Local File"

                                diag_tag = get_diagnostic_tag("FAILED", "User interrupted (Ctrl+C)", att_status)
                                writer.writerow([
                                    time.strftime("%Y-%m-%d %H:%M:%S"),
                                    config.get("course_name", ""),
                                    config.get("module_name", ""),
                                    current_docx_name,
                                    failed_q.absolute_index,
                                    f"Q{failed_q.question_number}",
                                    failed_q.title[:60],
                                    failed_q.tags,
                                    att_file_name,
                                    att_status,
                                    "FAILED",
                                    diag_tag,
                                    "User interrupted (Ctrl+C)"
                                ])
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
                        att_file_name = failed_q.attachment_filename or ""
                        if not att_file_name:
                            att_status = "No Attachment"
                        elif failed_q.resolved_attachment_path and Path(failed_q.resolved_attachment_path).exists():
                            att_status = "Attached Successfully"
                        else:
                            att_status = "Missing Local File"

                        diag_tag = get_diagnostic_tag("FAILED", batch_error_reason, att_status)
                        writer.writerow([
                            time.strftime("%Y-%m-%d %H:%M:%S"),
                            config.get("course_name", ""),
                            config.get("module_name", ""),
                            current_docx_name,
                            failed_q.absolute_index,
                            f"Q{failed_q.question_number}",
                            failed_q.title[:60],
                            failed_q.tags,
                            att_file_name,
                            att_status,
                            "FAILED",
                            diag_tag,
                            batch_error_reason
                        ])
                        failed_questions_list.append(failed_q.absolute_index)
                
                print("Continuing with the next batch. Failed questions will be available for retry from run_log.csv.")
                continue
                
        # Skip UI verification to save time as requested by user
        print_final_summary_report(is_abort=False)
        browser.close()
