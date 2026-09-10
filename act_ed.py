#!/usr/bin/env python3
"""
Interactive Activity Description Editor
Allows browsing and editing activity descriptions in formatted time log files.
"""

import re
import os
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog


def _default_file_path():
    return os.path.join(os.path.expanduser("~"), "Downloads", "pythonics", "Prod Program copy", "diaw.txt")


class ActivityEditor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.activities = defaultdict(set)
        self.file_content = ""

        if not self.load_file():
            raise SystemExit(1)

        self.root = tk.Tk()
        self.root.title("Activity Description Editor")
        self.root.geometry("800x600")

        self.setup_gui()
        self.load_activities()

    def load_file(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.file_content = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Could not load file: {e}")
            return False
        return True

    def save_file(self):
        try:
            print(f"DEBUG: Attempting to save to: {self.file_path}")
            print(f"DEBUG: Content length: {len(self.file_content)} characters")
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.file_content)
            print("DEBUG: File saved successfully")
            return True
        except Exception as e:
            print(f"DEBUG: Save error: {e}")
            messagebox.showerror("Error", f"Could not save file: {e}")
            return False

    def parse_activities(self):
        self.activities.clear()
        # Pattern: 4-digit time + space + 1-3 letter code + optional space + description
        pattern = r"(\d{4})\s+([A-Z]{1,3})(?:\s+(.+?))?(?=\n|$)"
        for match in re.finditer(pattern, self.file_content):
            time, code, description = match.groups()
            if description:  # Only add entries that have descriptions
                description = description.strip()
                if description:
                    self.activities[code].add(description)

    def setup_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for proper resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=0)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=0)
        main_frame.rowconfigure(2, weight=1)

        self.code_var = tk.StringVar()
        ttk.Label(main_frame, text="Select Activity Code:").grid(row=0, column=0, sticky=tk.W)
        self.code_combo = ttk.Combobox(main_frame, textvariable=self.code_var, state="readonly", width=10)
        self.code_combo.grid(row=0, column=1, sticky=tk.W)
        self.code_combo.bind('<<ComboboxSelected>>', self.on_code_selected)

        ttk.Button(main_frame, text="Refresh", command=self.load_activities).grid(row=0, column=2, padx=(10, 0))

        ttk.Label(main_frame, text="Descriptions:").grid(row=1, column=0, sticky=(tk.W, tk.N), pady=(6, 0))

        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.description_listbox = tk.Listbox(list_frame, height=15, selectmode=tk.EXTENDED)
        self.description_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.description_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.description_listbox.configure(yscrollcommand=scrollbar.set)
        self.description_listbox.bind('<Double-1>', self.on_description_double_click)
        
        # Bind Cmd+click for non-adjacent multi-selection (macOS)
        self.description_listbox.bind('<Command-Button-1>', self.on_cmd_click)
        # Also bind Ctrl+click for cross-platform compatibility
        self.description_listbox.bind('<Control-Button-1>', self.on_cmd_click)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(8, 0))
        ttk.Button(button_frame, text="Edit Selected", command=self.edit_selected_description).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Batch Edit Selected", command=self.batch_edit_selected).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Show Usage Count", command=self.show_usage_count).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Save Changes", command=self.save_changes).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Exit", command=self.root.quit).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(8, 0))

    def load_activities(self):
        if not self.load_file():
            return
        self.parse_activities()
        codes = sorted(self.activities.keys())
        self.code_combo['values'] = codes
        if codes:
            self.code_var.set(codes[0])
            self.on_code_selected()
        self.status_var.set(f"Loaded {len(codes)} activity codes from file")

    def on_code_selected(self, event=None):
        self.refresh_description_list()
    
    def refresh_description_list(self):
        """Refresh the description list without reloading the file"""
        code = self.code_var.get()
        if not code:
            return
        self.description_listbox.delete(0, tk.END)
        for desc in sorted(self.activities.get(code, [])):
            self.description_listbox.insert(tk.END, desc)
        self.status_var.set(f"Showing {self.description_listbox.size()} descriptions for {code}")

    def on_description_double_click(self, event):
        self.edit_selected_description()

    def on_cmd_click(self, event):
        """Handle Cmd+click for non-adjacent multi-selection"""
        # Get the index of the clicked item
        index = self.description_listbox.nearest(event.y)
        
        # Check if the item is already selected
        if index in self.description_listbox.curselection():
            # If selected, deselect it
            self.description_listbox.selection_clear(index)
        else:
            # If not selected, add it to selection
            self.description_listbox.selection_set(index)
        
        # Prevent the default selection behavior
        return "break"

    def batch_edit_selected(self):
        selections = self.description_listbox.curselection()
        if not selections:
            messagebox.showwarning("No Selection", "Please select one or more descriptions to batch edit.")
            return
        code = self.code_var.get()
        selected = [self.description_listbox.get(i) for i in selections]
        fmt = simpledialog.askstring("Batch Edit Descriptions", "Enter replacement format (use {old}):", initialvalue="{old}")
        if fmt is None:
            return
        preview = "\n".join(f"{s} -> {fmt.replace('{old}', s)}" for s in selected)
        if not messagebox.askyesno("Confirm Batch Replace", f"This will replace:\n\n{preview}\n\nProceed?"):
            return
        total = 0
        for old in selected:
            new = fmt.replace('{old}', old)
            total += self._replace_description(code, old, new)
        messagebox.showinfo("Batch Edit Complete", f"Total replacements: {total}")
        # Don't call load_activities() - changes are already applied

    def edit_selected_description(self):
        sel = self.description_listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a description to edit.")
            return
        code = self.code_var.get()
        old = self.description_listbox.get(sel[0])
        count = self.count_description_usage(code, old)
        new = simpledialog.askstring("Edit Description", f"Current: {old}\nOccurrences: {count}\nEnter new:", initialvalue=old)
        if new is None or new == old:
            return
        if messagebox.askyesno("Confirm Replacement", f"Replace all {count} occurrences of '{old}' with '{new}'?"):
            replaced = self._replace_description(code, old, new)
            messagebox.showinfo("Replaced", f"Replaced {replaced} occurrences")
            # Don't call load_activities() - changes are already applied

    def count_description_usage(self, code, description):
        # Pattern: 4-digit time + space + specific code + space + exact description
        pattern = rf"(\d{{4}})\s+{re.escape(code)}\s+{re.escape(description)}(?=\n|$)"
        return len(re.findall(pattern, self.file_content))

    def _replace_description(self, code, old_description, new_description):
        print(f"DEBUG: Replacing '{old_description}' with '{new_description}' for code '{code}'")
        # Pattern: 4-digit time + space + specific code + space + exact old description
        pattern = rf"(\d{{4}}\s+{re.escape(code)}\s+){re.escape(old_description)}(?=\n|$)"
        replacement = rf"\1{new_description}"
        print(f"DEBUG: Using pattern: {pattern}")
        print(f"DEBUG: Content length before: {len(self.file_content)}")
        
        new_content, n = re.subn(pattern, replacement, self.file_content)
        print(f"DEBUG: Replacements made: {n}")
        
        if n > 0:
            self.file_content = new_content
            print(f"DEBUG: Content length after: {len(self.file_content)}")
            # update parsed activities
            self.activities[code].discard(old_description)
            self.activities[code].add(new_description)
            self.status_var.set(f"Replaced {n} occurrences (not yet saved)")
            # DON'T reload activities - just refresh the display manually
            self.refresh_description_list()
        else:
            self.status_var.set("No replacements made")
        return n

    def show_usage_count(self):
        sel = self.description_listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a description to check.")
            return
        code = self.code_var.get()
        desc = self.description_listbox.get(sel[0])
        c = self.count_description_usage(code, desc)
        messagebox.showinfo("Usage Count", f"Code: {code}\nDescription: {desc}\nOccurrences: {c}")

    def save_changes(self):
        print("DEBUG: Save Changes button clicked")
        if self.save_file():
            messagebox.showinfo("Success", "Changes saved successfully")
            self.status_var.set("Saved")
            print("DEBUG: Save completed successfully")
        else:
            print("DEBUG: Save failed")

    def run(self):
        self.root.mainloop()


def main():
    default_path = _default_file_path()
    if not os.path.exists(default_path):
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(title="Select formatted time log", filetypes=[("Text files","*.txt"), ("All files","*.*")])
        if not file_path:
            print("No file selected. Exiting.")
            return
    else:
        file_path = default_path
    editor = ActivityEditor(file_path)
    editor.run()


if __name__ == '__main__':
    main()
 
