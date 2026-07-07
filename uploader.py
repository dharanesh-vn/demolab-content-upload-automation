import os
import time
import csv
import re
from pathlib import Path
# pyrefly: ignore [missing-import]
from playwright.sync_api import sync_playwright, expect
from question_model import Question
from typing import List

def run_uploader(questions: List[Question], config: dict, credentials: dict):
    # Prepare run log
    log_file = Path("run_log.csv")
    completed_q_nums = set()
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2 and row[1] == "success":
                    completed_q_nums.add(int(row[0]))
    
    with sync_playwright() as p:
        # Run headed for manual OTP
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # --- 1. Login with manual OTP ---
        print("Navigating to login URL...")
        page.goto(config["login_url"])
        
        page.fill('input[name="email"], input[type="email"]', credentials["username"])
        page.fill('input[name="password"], input[type="password"]', credentials["password"])
        page.click('button:has-text("Login"), button[type="submit"]')
        
        print("Waiting for OTP input screen to render...")
        timeout = config.get("otp_wait_timeout_ms", 120000)
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
        page.wait_for_url(lambda url: "login" not in url, timeout=timeout)
        page.wait_for_timeout(3000)  # Give it a moment to establish the session
        
        print("Login successful! Navigating to Question Bank...")
        page.goto(config["question_bank_url"])
        
        # --- 2. Navigate UI exactly as requested ---
        
        # 3. Click + Add Questions tab
        print("Clicking '+ Add Questions' tab...")
        page.locator('text=Add Questions').first.click()
        page.wait_for_timeout(1000)
        
        # 4. Select course and module from sidebar
        course = config["course_name"]
        module = config["module_name"]
        
        print(f"Selecting Course: {course}")
        course_loc = page.get_by_text(course, exact=True).first
        course_loc.click()
        page.wait_for_timeout(1000)
        
        print(f"Selecting Module: {module}")
        module_loc = page.get_by_text(module, exact=True).first
        module_loc.click()
        page.wait_for_timeout(1000)
        
        # 5. Click the "Project Questions" card
        print("Clicking 'Project Questions' card...")
        page.locator('text=Project Questions').first.click()
        page.wait_for_timeout(2000)
        # Wait for the configuration form to appear
        expect(page.get_by_text("Project Questions Configuration")).to_be_visible(timeout=10000)
        
        # --- 3. Upload questions ---
        for i, q in enumerate(questions):
            if q.question_number in completed_q_nums:
                print(f"Skipping Q{q.question_number} (already logged as success).")
                continue
                
            print(f"Uploading Q{q.question_number}: {q.title[:30]}...")
            try:
                # 1. Fill Title
                page.locator('input[placeholder*="Title"], input[name*="title"]').first.fill(q.title[:150])
                
                # 2. Select Difficulty
                page.locator('div').filter(has_text="Difficulty Level").locator('svg').last.click()
                page.get_by_text(q.difficulty, exact=True).first.click()
                
                # 3. Select Tags
                tag_to_use = q.tags if q.tags else "General"
                page.locator('div').filter(has_text="Tags *").locator('svg').last.click()
                try:
                    page.keyboard.type(tag_to_use)
                    page.keyboard.press("Enter")
                except:
                    pass
                
                # 4. Select Language -> "Assignment"
                language_to_use = config.get("language", "Assignment")
                # Using get_by_label or checking the div
                try:
                    page.get_by_label(re.compile(r"Language")).click()
                except:
                    page.locator('div').filter(has_text="Language *").locator('svg').last.click()
                page.get_by_text(language_to_use, exact=True).first.click()
                page.wait_for_timeout(500) 
                
                # 5. Actual time
                try:
                    page.get_by_label(re.compile(r"Actual time")).fill(str(q.actual_time_minutes))
                except:
                    page.locator('input[placeholder="0"], input[name*="time"]').last.fill(str(q.actual_time_minutes))
                
                # 6. Question Text (Rich Text Editor)
                editor = page.locator('.ProseMirror, [contenteditable="true"]').first
                full_text = q.question_text
                if q.submission_instructions:
                    full_text += f"\n\n{q.submission_instructions}"
                editor.fill(full_text)
                
                # 7. File Attachment
                if q.attachment_filename:
                    att_path = Path(config["attachments_root"]) / q.attachment_filename
                    if att_path.exists():
                        print(f"Attaching: {q.attachment_filename}")
                        file_input = page.locator('input[type="file"]')
                        if file_input.count() > 0:
                            file_input.first.set_input_files(str(att_path))
                        else:
                            with page.expect_file_chooser() as fc_info:
                                page.locator('text=Click to upload').first.click()
                            fc_info.value.set_files(str(att_path))
                        page.wait_for_timeout(1000) 
                    else:
                        print(f"WARNING: Attachment missing: {att_path}")
                
                # 8. User Response Acceptance (PDF and Images)
                page.get_by_role("button", name="PDF").click()
                page.get_by_role("button", name="Images").click()
                
                # 9. Save or Add Another
                if i == len(questions) - 1:
                    print("Last question! Clicking Save Questions...")
                    page.get_by_role("button", name="Save Questions").click()
                else:
                    print("Clicking Add Question...")
                    page.get_by_role("button", name="Add Question").first.click()
                    page.wait_for_timeout(2000)
                
                # Log success
                with open(log_file, "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([q.question_number, "success", time.time(), ""])
                    
            except Exception as e:
                print(f"Failed on Q{q.question_number}: {e}")
                Path("screenshots").mkdir(exist_ok=True)
                page.screenshot(path=f"screenshots/failed_q{q.question_number}.png")
                with open(log_file, "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([q.question_number, "failed", time.time(), str(e)])
                break
                
        print("Upload process completed!")
        browser.close()
