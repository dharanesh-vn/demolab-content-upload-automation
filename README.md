# Amypo Automated Question Uploader

Welcome to the Amypo Question Automation script! This tool is designed to save you hours of manual data entry. You just provide a Word Document (`.docx`) containing your questions, and the script will automatically parse them, map the attachments, and upload them to the Amypo platform.

## Getting Started

### 1. Prerequisites
If you haven't already, you need Python installed on your computer.
- Download Python from [python.org](https://www.python.org/downloads/)
- Once installed, open your terminal (Command Prompt) and run:
  ```bash
  pip install -r requirements.txt
  playwright install
  ```

### 2. Prepare Your Assignment Folder
For the script to work magically, keep your files organized.
- Ensure your questions are formatted correctly inside a **Master Word Document (`.docx`)**.
- Keep all of your attachment files (PDFs, Images, Data Tables) in the same folder (or sub-folders) as your Master Word Document.
- **Note:** You do not need to name the attachments folder perfectly. The script is smart enough to scan the entire project folder and find the attachments based on the file names listed in your Word Document!

## How to Run the Script

1. Open your terminal (Command Prompt).
2. Navigate to this `content_automation` folder.
3. Run the following command:
   ```bash
   python main.py
   ```
4. **The Setup Window:** A native Windows popup will appear!
   - Simply navigate to and select your Master Assignment `.docx` file.

**Note on Credentials:** Your Amypo credentials are securely stored in the `.env` file. You only need to set them once inside the `.env` file (`AMYPO_USERNAME` and `AMYPO_PASSWORD`), and the script will automatically log you in every time!

5. **Terminal Setup:** The script will ask you for Course Name, Subject Type, Module Name, and Tags. (Note: Difficulty, Language, and Time are intelligently defaulted behind the scenes to save you time!).
6. **CSV Review Phase:** The script will generate a `questions_review.csv` file. You can open this in Excel to verify all questions, fix any typos, or modify "User Response Acceptance" formats before they are uploaded.
7. **Upload Execution:** Head back to the terminal, type `1` to confirm, enter your starting and ending question range, and then enter your OTP from WhatsApp!

## Sit Back and Relax!
Once the OTP is entered, a Chromium browser window will open automatically. 
**Do not click inside the browser!** Watch as the script logs in, navigates to the correct course, creates the questions, attaches the files, and saves everything for you. When it finishes, it will print a beautiful summary in your terminal!

## Troubleshooting
- **Missing Attachments Warning?** If the script can't find an attachment mentioned in your Word Document (e.g., due to a typo), it will pause and print a Yellow Warning. You can press `Y` to upload the question anyway *without* the attachment, or `N` to abort and fix the file.
- **Website Rejects Save?** The script will print a Critical Error in red if the website rejects the save (meaning the "Save Questions" modal doesn't close). Check the browser window for red UI errors on the form fields.
