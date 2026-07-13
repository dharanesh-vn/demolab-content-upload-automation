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

**Note on Credentials:** Your Amypo credentials are securely stored in the `.env` file. When you first clone the repository, copy the `.env.example` file and rename it to `.env`. Then, enter your `AMYPO_USERNAME` and `AMYPO_PASSWORD`. You only need to set them once, and the script will automatically log you in every time!

5. **Terminal Setup:** The script will ask you if this is a **Bulk Multi-Module Upload** (Y/N).
   - If **Y**: You define the questions per module (e.g. 60) and the prefix (e.g. 'module '). The script will magically tag the first 60 questions as `module 1`, the next 60 as `module 2`, etc.
   - If **N**: It will ask for a standard global tag.
6. **CSV Review Phase:** The script will generate a `questions_review.csv` file. You can open this in Excel to verify all questions, fix any typos, or modify "User Response Acceptance" formats before they are uploaded.
7. **Upload Execution:** Head back to the terminal, type `1` to confirm (the script will safely catch if you forget to close Excel), enter your starting and ending **Absolute Index** range, and then enter your OTP from WhatsApp!

## Sit Back and Relax!
Once the OTP is entered, the **Invisible Headless Browser** will take over! 
You will not see a browser window open. It runs completely silently in the background at maximum speed, bypassing visual rendering to drastically increase processing times. When it finishes, it will print a beautiful summary with exact minutes and seconds taken!

## Advanced Safety Features
- **Turbo Batch Chunking:** To handle massive 300+ question uploads without crashing your browser, the script breaks the workload into 30-question batches. It automatically navigates, saves, and refreshes the DOM to keep memory usage low and execution speed blazing fast!
- **Atomic Saving & Network Resistance:** The script tracks progress intelligently. If you hit `Ctrl+C` to abort mid-batch, or if the server crashes under heavy load, it safely logs the exact batch failure and aborts. It gives the server up to 60 seconds to process saves to survive network lag.

## Troubleshooting
- **Missing Attachments Warning?** If the script can't find an attachment mentioned in your Word Document (e.g., due to a typo), it will pause and print a Yellow Warning. You can press `Y` to upload the question anyway *without* the attachment, or `N` to abort and fix the file.
- **Website Rejects Save?** The script will print a Critical Error in red if the website rejects the save. Check the browser window for red UI errors on the form fields.
