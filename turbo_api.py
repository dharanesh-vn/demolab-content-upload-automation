import os
import time
import csv
import re
from pathlib import Path
import json
import requests
from playwright.sync_api import sync_playwright, expect
from question_model import Question
from typing import List

def run_uploader(questions: List[Question], config: dict, credentials: dict):
    print("\n=============================================")
    print("🚀 INIT: API TURBO INJECTOR")
    print("=============================================\n")
    
    # Track completion
    success_count = 0
    fail_count = 0
    start_time = time.time()
    
    log_file = Path("run_log.csv")
    completed_q_nums = set()
    current_docx_name = Path(config["docx_path"]).name
    
    if not log_file.exists():
        with open(log_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Document Name", "Question Number", "Status", "Timestamp", "Details"])
            
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row: continue
                if len(row) >= 3 and row[0] == current_docx_name and row[2] == "success":
                    completed_q_nums.add(int(row[1]))
                    
    questions_to_upload = [q for q in questions if q.absolute_index not in completed_q_nums]
    
    if not questions_to_upload:
        print("All questions selected have already been uploaded successfully according to the run log.")
        return

    # Add a visual line breaker to the log for this new run session
    with open(log_file, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["---", "---", "---", "---", "---"])

        captured_api_data = {}

    def handle_response(response):
        req = response.request
        if req.method in ["POST", "PUT"]:
            # Write EVERY POST/PUT to a log file so we can see the exact flow!
            with open("network_log.txt", "a", encoding="utf-8") as f:
                f.write(f"\n[{req.method}] {req.url}\n")
                f.write(f"Headers: {req.headers}\n")
                
                # Check for multipart or json to safely log snippet
                content_type = req.headers.get("content-type", "")
                if "multipart/form-data" in content_type or "application/json" in content_type:
                    snippet = str(req.post_data)[:500]
                    f.write(f"Payload Snippet: {snippet}\n")
                else:
                    f.write(f"Payload (Binary/Other length): {len(req.post_data or b'')}\n")
                    
                try:
                    body = response.json()
                    f.write(f"Response JSON: {body}\n")
                except:
                    snippet = str(response.text())[:300]
                    f.write(f"Response Text: {snippet}\n")
                f.write("-" * 50 + "\n")

    def intercept_save(route):
        req = route.request
        if req.method == "POST" and "multipart/form-data" in req.headers.get("content-type", ""):
            if "questions[0][basicData]" in req.post_data:
                print("\n[SNIFFER] 🎯 BOOM! Caught the Save Questions API Request!")
                captured_api_data["url"] = req.url
                captured_api_data["headers"] = req.headers
                captured_api_data["post_data"] = req.post_data
                route.abort()
                return
        route.continue_()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(60000)
        
        # Listen for all network responses to catch the file upload
        page.on("response", handle_response)
        
        print("[SNIFFER] Navigating to login URL...")
        page.goto(config["login_url"])
        
        page.fill('input[name="email"], input[type="email"]', credentials["username"])
        page.fill('input[name="password"], input[type="password"]', credentials["password"])
        page.click('button:has-text("Login"), button[type="submit"]')
        
        print("[SNIFFER] Waiting for OTP input screen to render (this may take a few seconds)...", flush=True)
        timeout = config.get("otp_wait_timeout_ms", 120000)
        page.wait_for_selector('input[inputmode="numeric"]', timeout=timeout)
        
        print("\n====================================", flush=True)
        print("OTP SCREEN DETECTED!", flush=True)
        print("Please check your email/phone.", flush=True)
        print("Enter the 6-digit OTP here:", flush=True)
        otp = input("> ").strip()
        
        print("[SNIFFER] Submitting OTP...")
        page.locator('input[inputmode="numeric"]').first.click()
        page.keyboard.type(otp)
        
        print("[SNIFFER] Waiting for dashboard to load...")
        page.wait_for_url(lambda url: "login" not in url, timeout=timeout)
        page.wait_for_timeout(3000)
        
        print("\n[SNIFFER] Login successful! Navigating to Question Bank to steal database IDs...")
        page.goto(config["question_bank_url"])
        page.wait_for_timeout(3000)
        
        print("[SNIFFER] Clicking '+ Add Questions' tab...")
        page.locator('text=Add Questions').first.click()
        page.wait_for_timeout(1000)
        
        subject_type_btn = 'Prog... Subjects' if str(config.get("subject_type")).lower() == 'programming' else 'Academic'
        print(f"[SNIFFER] Clicking '{subject_type_btn}' tab...")
        page.locator(f'text={subject_type_btn}').first.click()
        page.wait_for_timeout(1000)
        
        print(f"[SNIFFER] Searching and Selecting Course: {config['course_name']}")
        search_input = page.locator('input[name="search_term"]')
        if search_input.count() > 0:
            search_input.fill(config['course_name'])
            page.wait_for_timeout(1000)
        page.get_by_text(config['course_name'], exact=True).first.click(timeout=5000, force=True)
        page.wait_for_timeout(1000)
        
        print(f"[SNIFFER] Selecting Module: {config['module_name']}")
        page.get_by_text(config['module_name'], exact=True).first.click(timeout=5000, force=True)
        page.wait_for_timeout(1000)
        
        print("[SNIFFER] Clicking 'Project Questions' card...")
        page.locator('text=Project Questions').first.click()
        page.wait_for_timeout(2000)
        expect(page.get_by_text("Project Questions Configuration")).to_be_visible(timeout=10000)
        
        # Route interception ON (for Save Questions only)
        page.route("**/*", intercept_save)
        
        q0 = questions_to_upload[0]
        print(f"[SNIFFER] Filling dummy form to capture the exact database IDs...")
        
        page.locator('input[name="question_title"]').nth(0).fill("Turbo Injector Sniff Test")
        
        diff_input = page.locator('input.select__input').nth(0)
        diff_input.click(force=True)
        diff_input.fill(q0.difficulty)
        page.wait_for_timeout(300)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        
        tag_input = page.locator('input.select__input').nth(1)
        tag_input.click(force=True)
        tag_input.fill(q0.tags)
        page.wait_for_timeout(300)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        if tag_input.input_value() != "":
            raise ValueError(f"CRITICAL ERROR: Failed to select Tag '{q0.tags}'. This tag is not available in the website dropdown.")
            
        lang_input = page.locator('input.select__input').nth(2)
        lang_input.click(force=True)
        lang_input.fill(q0.language)
        page.wait_for_timeout(300)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        
        page.locator('input[name="actualTime"]').nth(0).fill("30")
        page.locator('.ProseMirror, [contenteditable="true"]').nth(0).fill("API bypass sniff")
        
        # Create a dummy attachment file as a PDF so the UI doesn't reject it
        dummy_path = Path("dummy_sniff.pdf")
        dummy_path.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Count 0/Kids[]>>\nendobj\nxref\n0 3\n0000000000 65535 f \n0000000015 00000 n \n0000000060 00000 n \ntrailer\n<</Size 3/Root 1 0 R>>\nstartxref\n106\n%%EOF\n")
        
        print("[SNIFFER] 📂 Uploading a dummy attachment to reverse-engineer the hidden upload API...")
        xpath = f"(//*[contains(text(), 'Assignment Attachments')])[1]/following::*[contains(text(), 'Click to upload')][1]"
        with page.expect_file_chooser() as fc_info:
            page.locator(xpath).click(force=True)
        fc_info.value.set_files(str(dummy_path.absolute()))
        
        # Wait 3 seconds to ensure the upload finishes and we catch the response!
        page.wait_for_timeout(3000)
        
        # Dummy Acceptance
        page.locator(f"(//*[contains(text(), 'PDF')])[1]").click(force=True)
        
        print("[SNIFFER] Clicking 'Save Questions' and intercepting payload...")
        page.locator('button', has_text='Save Questions').first.click()
        
        # Wait up to 10 seconds for the intercept
        for _ in range(10):
            if "url" in captured_api_data:
                break
            page.wait_for_timeout(1000)
            
        if "url" not in captured_api_data:
            print("CRITICAL ERROR: Failed to sniff the API payload. Ensure the dummy form was fully valid.")
            return
            
        print("[SNIFFER] Payload captured successfully! Closing browser.")
        browser.close()
        dummy_path.unlink()

    # --- Phase 2: Python Requests Blaster ---
    print("\n=============================================")
    print("🚀 PHASE 2: BLASTER ACTIVATED")
    print("=============================================\n")
    
    raw_post_data = captured_api_data["post_data"]
    
    # Extract the Database IDs from the raw payload using regex!
    # Because boundaries are random like: ------WebKitFormBoundary8JVq2WFY7hB9uYDB
    
    def extract_val(field_name):
        # Escape the field name because it contains brackets like [0] which break regex
        safe_name = re.escape(field_name)
        # Match both \r\n and \n line endings just in case Playwright normalizes them
        match = re.search(f'name="{safe_name}"\\r?\\n\\r?\\n(.*?)\\r?\\n', raw_post_data)
        if match:
            return match.group(1)
        raise ValueError(f"Could not find field {field_name} in captured payload!")
        
    course_id = extract_val("courseId")
    topic_id = extract_val("topicId")
    diff_id = extract_val("questions[0][basicData][difficultyLevel]")
    tag_id = extract_val("questions[0][basicData][tags][0]")
    lang_id = extract_val("questions[0][basicData][language]")
    
    print(f"✅ Extracted Course ID: {course_id}")
    print(f"✅ Extracted Module ID: {topic_id}")
    print(f"✅ Extracted Difficulty ID ({q0.difficulty}): {diff_id}")
    print(f"✅ Extracted Tag ID ({q0.tags}): {tag_id}")
    print(f"✅ Extracted Language ID ({q0.language}): {lang_id}")
    
    headers = captured_api_data["headers"]
    
    # Remove content-type because requests module sets its own multipart boundary!
    if "content-type" in headers:
        del headers["content-type"]
    if "content-length" in headers:
        del headers["content-length"]
        
    url = captured_api_data["url"]
    
    # Format acceptance mapping
    format_map = {
        "Word": ["word", "doc", "docx"],
        "PDF": ["pdf"],
        "ZIP": ["zip", "archive", "rar"],
        "Images": ["img", "image", "images", "png", "jpg", "jpeg"],
        "ODS / ODT": ["ods", "odt"],
        "Video": ["video", "mp4", "avi"]
    }
    
    chunk_size = 50
    for chunk_start in range(0, len(questions_to_upload), chunk_size):
        chunk = questions_to_upload[chunk_start:chunk_start + chunk_size]
        print(f"\n[BLASTER] Blasting Questions {chunk[0].absolute_index} to {chunk[-1].absolute_index}...")
        
        data = {
            "courseId": course_id,
            "topicId": topic_id,
            "statusFlag": "1",
            "force": "1" # Force=1 bypasses the 'similar question already exists' 409 error!
        }
        files = [] # Tuples of (field_name, (filename, file_object, content_type))
        open_files = [] # To keep them open during the request
        
        for i, q in enumerate(chunk):
            prefix = f"questions[{i}]"
            data[f"{prefix}[basicData][title]"] = q.title[:150]
            data[f"{prefix}[basicData][difficultyLevel]"] = diff_id
            data[f"{prefix}[basicData][tags][0]"] = tag_id
            data[f"{prefix}[basicData][language]"] = lang_id
            data[f"{prefix}[basicData][actualTime]"] = str(q.actual_time_minutes)
            data[f"{prefix}[questionContent]"] = q.question_text
            data[f"{prefix}[questionType]"] = "1" # Project questions
            
            # Acceptance type
            acc_str = str(q.user_response_acceptance).lower()
            acc_key = "pdf"
            for k, v in format_map.items():
                if any(x in acc_str for x in v):
                    acc_key = k.lower()
                    break
                    
            data[f"{prefix}[responseAcceptance][0][type]"] = acc_key
            data[f"{prefix}[responseAcceptance][0][maxFiles]"] = "1"
            data[f"{prefix}[responseAcceptance][0][maxSizeKb]"] = "1000"
            data[f"{prefix}[html]"] = ""
            data[f"{prefix}[css]"] = ""
            data[f"{prefix}[js]"] = ""
            
            # File attachment
            if q.attachment_filename and getattr(q, 'resolved_attachment_path', None):
                att_path = q.resolved_attachment_path
                if att_path.exists():
                    f_obj = open(att_path, "rb")
                    open_files.append(f_obj)
                    # For requests multipart files: (field_name, (filename, file_object, mimetype))
                    files.append((f"{prefix}[attachments][0]", (q.attachment_filename, f_obj, "application/octet-stream")))
                    
        # BLAST IT!
        try:
            print(f"[BLASTER] Firing payload ({len(chunk)} questions)...")
            res = requests.post(url, headers=headers, data=data, files=files, timeout=60)
            
            if res.status_code in [200, 201]:
                print(f"[BLASTER] ✅ SUCCESS! Server returned {res.status_code}.")
                with open(log_file, "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    for q in chunk:
                        writer.writerow([current_docx_name, q.absolute_index, "success", time.strftime("%Y-%m-%d %H:%M:%S"), "API Turbo Success"])
                success_count += len(chunk)
            elif res.status_code == 409:
                print(f"[BLASTER] ⚠️ 409 CONFLICT: The server rejected this batch of {len(chunk)} because it found a duplicate!")
                print(f"[BLASTER] 🔄 SMART FALLBACK: Re-uploading this batch one-by-one so the non-duplicates can succeed...")
                
                # Close the batch files first
                for f_obj in open_files:
                    f_obj.close()
                open_files = []
                
                # Upload one by one
                for q in chunk:
                    single_data = {
                        "courseId": course_id,
                        "topicId": topic_id,
                        "statusFlag": "1",
                        "force": "1"
                    }
                    single_files = []
                    single_open_files = []
                    
                    prefix = "questions[0]"
                    single_data[f"{prefix}[basicData][title]"] = q.title[:150]
                    single_data[f"{prefix}[basicData][difficultyLevel]"] = diff_id
                    single_data[f"{prefix}[basicData][tags][0]"] = tag_id
                    single_data[f"{prefix}[basicData][language]"] = lang_id
                    single_data[f"{prefix}[basicData][actualTime]"] = str(q.actual_time_minutes)
                    single_data[f"{prefix}[questionContent]"] = q.question_text
                    single_data[f"{prefix}[questionType]"] = "1"
                    
                    acc_str = str(q.user_response_acceptance).lower()
                    acc_key = "pdf"
                    for k, v in format_map.items():
                        if any(x in acc_str for x in v):
                            acc_key = k.lower()
                            break
                            
                    single_data[f"{prefix}[responseAcceptance][0][type]"] = acc_key
                    single_data[f"{prefix}[responseAcceptance][0][maxFiles]"] = "1"
                    single_data[f"{prefix}[responseAcceptance][0][maxSizeKb]"] = "1000"
                    single_data[f"{prefix}[html]"] = ""
                    single_data[f"{prefix}[css]"] = ""
                    single_data[f"{prefix}[js]"] = ""
                    
                    if q.attachment_filename and getattr(q, 'resolved_attachment_path', None):
                        att_path = q.resolved_attachment_path
                        if att_path.exists():
                            f_obj = open(att_path, "rb")
                            single_open_files.append(f_obj)
                            import mimetypes
                            mime_type, _ = mimetypes.guess_type(str(att_path))
                            if not mime_type:
                                mime_type = "application/octet-stream"
                            single_files.append((f"{prefix}[attachments][0]", (q.attachment_filename, f_obj, mime_type)))
                            
                    try:
                        single_res = requests.post(url, headers=headers, data=single_data, files=single_files, timeout=30)
                        if single_res.status_code in [200, 201]:
                            success_count += 1
                            with open(log_file, "a", encoding="utf-8", newline="") as f:
                                csv.writer(f).writerow([current_docx_name, q.absolute_index, "success", time.strftime("%Y-%m-%d %H:%M:%S"), "API Turbo Success (Fallback)"])
                        elif single_res.status_code == 409:
                            fail_count += 1
                            print(f"  ⚠️ Q{q.absolute_index} Skipped (Duplicate detected by server)")
                            with open(log_file, "a", encoding="utf-8", newline="") as f:
                                csv.writer(f).writerow([current_docx_name, q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), "Skipped: Duplicate"])
                        else:
                            fail_count += 1
                            print(f"  ❌ Q{q.absolute_index} Failed: {single_res.status_code}")
                            with open(log_file, "a", encoding="utf-8", newline="") as f:
                                csv.writer(f).writerow([current_docx_name, q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), f"API Error {single_res.status_code}"])
                    except Exception as e:
                        fail_count += 1
                        print(f"  ❌ Q{q.absolute_index} Failed: {e}")
                        with open(log_file, "a", encoding="utf-8", newline="") as f:
                            csv.writer(f).writerow([current_docx_name, q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), "Exception"])
                    finally:
                        for f_obj in single_open_files:
                            f_obj.close()
            else:
                print(f"[BLASTER] ❌ ERROR! Server returned {res.status_code}. See run_log.csv")
                fail_count += len(chunk)
                with open(log_file, "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    for q in chunk:
                        writer.writerow([current_docx_name, q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), f"Chunk API Error {res.status_code}"])
        except Exception as e:
            print(f"[BLASTER] ❌ FATAL ERROR: {e}")
            fail_count += len(chunk)
            with open(log_file, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                for q in chunk:
                    writer.writerow([current_docx_name, q.absolute_index, "failed", time.strftime("%Y-%m-%d %H:%M:%S"), "Chunk Exception"])
        finally:
            for f_obj in open_files:
                f_obj.close()
                
    time_taken = time.time() - start_time
    print("\n=================================")
    print("TURBO UPLOAD COMPLETE")
    print("=================================")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Time Taken: {int(time_taken // 60)} mins {int(time_taken % 60)} secs")
    print("=================================")
