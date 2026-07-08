import tkinter as tk
from tkinter import filedialog, messagebox
import os

def get_credentials_and_file():
    """
    Opens a Tkinter GUI to get the user's email, password, and the docx file path.
    Returns: (email, password, docx_path)
    """
    root = tk.Tk()
    root.title("Amypo Automation Setup")
    root.geometry("450x300")
    
    # Center the window
    root.eval('tk::PlaceWindow . center')
    
    # Variables to store results
    result = {"email": "", "password": "", "docx_path": ""}
    
    def browse_file():
        filename = filedialog.askopenfilename(
            title="Select Assignment Word Document",
            filetypes=[("Word Documents", "*.docx")]
        )
        if filename:
            file_entry.delete(0, tk.END)
            file_entry.insert(0, filename)
            
    def submit():
        email = email_entry.get().strip()
        password = pass_entry.get().strip()
        docx_path = file_entry.get().strip()
        
        if not email or not password or not docx_path:
            messagebox.showerror("Error", "Please fill in all fields and select a file.")
            return
            
        if not os.path.exists(docx_path):
            messagebox.showerror("Error", "The selected file does not exist.")
            return
            
        result["email"] = email
        result["password"] = password
        result["docx_path"] = docx_path
        root.destroy()
        
    def on_closing():
        root.destroy()
        exit(0) # Exit the whole program if they close the window

    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # UI Elements
    tk.Label(root, text="Email:", font=("Arial", 10, "bold")).pack(pady=(20, 0))
    email_entry = tk.Entry(root, width=40)
    email_entry.pack()
    
    tk.Label(root, text="Password:", font=("Arial", 10, "bold")).pack(pady=(10, 0))
    pass_entry = tk.Entry(root, width=40, show="*")
    pass_entry.pack()
    
    tk.Label(root, text="Select Main Assignment (.docx):", font=("Arial", 10, "bold")).pack(pady=(15, 0))
    file_frame = tk.Frame(root)
    file_frame.pack(pady=5)
    file_entry = tk.Entry(file_frame, width=35)
    file_entry.pack(side=tk.LEFT, padx=(0, 5))
    tk.Button(file_frame, text="Browse...", command=browse_file).pack(side=tk.LEFT)
    
    tk.Button(root, text="Start Automation", command=submit, bg="green", fg="white", font=("Arial", 11, "bold"), padx=10, pady=5).pack(pady=20)
    
    root.mainloop()
    
    return result["email"], result["password"], result["docx_path"]

if __name__ == "__main__":
    e, p, f = get_credentials_and_file()
    print(f"Email: {e}, File: {f}")
