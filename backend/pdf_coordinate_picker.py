import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from PIL import Image, ImageTk
import pymupdf as fitz


APP_TITLE = "Professional PDF Coordinate Picker"


class PDFCoordinatePicker:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x850")
        self.root.minsize(1000, 700)

        self.pdf_path: Path | None = None
        self.doc: fitz.Document | None = None
        self.page_index = 0
        self.zoom = 2.0
        self.tk_image = None
        self.points = []

        self._build_ui()
        self._bind_shortcuts()

    def _build_ui(self):
        self.root.configure(bg="#f3f4f6")

        topbar = ttk.Frame(self.root, padding=(10, 8))
        topbar.pack(fill=tk.X)

        ttk.Button(topbar, text="Open PDF", command=self.open_pdf).pack(side=tk.LEFT, padx=4)
        ttk.Button(topbar, text="Previous", command=self.prev_page).pack(side=tk.LEFT, padx=4)
        ttk.Button(topbar, text="Next", command=self.next_page).pack(side=tk.LEFT, padx=4)
        ttk.Button(topbar, text="Zoom -", command=self.zoom_out).pack(side=tk.LEFT, padx=4)
        ttk.Button(topbar, text="Zoom +", command=self.zoom_in).pack(side=tk.LEFT, padx=4)
        ttk.Button(topbar, text="Fit Width", command=self.fit_width).pack(side=tk.LEFT, padx=4)
        ttk.Button(topbar, text="Save Points JSON", command=self.save_points).pack(side=tk.LEFT, padx=14)

        self.status_var = tk.StringVar(value="Open a PDF file to start.")
        ttk.Label(topbar, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).pack(
            side=tk.LEFT, padx=12
        )

        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        canvas_frame = ttk.Frame(main)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#e5e7eb", cursor="crosshair")
        self.h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)

        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        side = ttk.Frame(main, width=330, padding=12)
        side.pack(side=tk.RIGHT, fill=tk.Y)
        side.pack_propagate(False)

        ttk.Label(side, text="Selected Coordinates", font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        self.mouse_var = tk.StringVar(value="X: - | Y: -")
        ttk.Label(side, textvariable=self.mouse_var).pack(anchor="w", pady=(0, 8))

        self.code_var = tk.StringVar(value="Click on the PDF...")
        code_box = ttk.Entry(side, textvariable=self.code_var)
        code_box.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(side, text="Copy Current Code", command=self.copy_current_code).pack(
            fill=tk.X, pady=(0, 10)
        )

        self.points_list = tk.Listbox(side, height=22)
        self.points_list.pack(fill=tk.BOTH, expand=True)

        ttk.Button(side, text="Remove Selected", command=self.remove_selected_point).pack(
            fill=tk.X, pady=(10, 4)
        )
        ttk.Button(side, text="Clear Points", command=self.clear_points).pack(fill=tk.X)

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)

    def _bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self.open_pdf())
        self.root.bind("<Left>", lambda e: self.prev_page())
        self.root.bind("<Right>", lambda e: self.next_page())
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())

    def open_pdf(self):
        path = filedialog.askopenfilename(
            title="Select PDF template",
            filetypes=[("PDF files", "*.pdf")],
        )

        if not path:
            return

        try:
            self.pdf_path = Path(path)
            self.doc = fitz.open(path)
            self.page_index = 0
            self.points.clear()
            self.points_list.delete(0, tk.END)
            self.render_page()
        except Exception as exc:
            messagebox.showerror("Error", f"Cannot open PDF:\n{exc}")

    def render_page(self):
        if not self.doc:
            return

        page = self.doc[self.page_index]
        matrix = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        self.tk_image = ImageTk.PhotoImage(img)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))

        self.redraw_points()

        self.status_var.set(
            f"{self.pdf_path.name if self.pdf_path else ''} | "
            f"Page {self.page_index + 1}/{len(self.doc)} | Zoom {self.zoom:.2f}x"
        )

    def get_canvas_position(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        return x, y

    def canvas_to_pdf(self, canvas_x, canvas_y):
        return round(canvas_x / self.zoom, 2), round(canvas_y / self.zoom, 2)

    def on_click(self, event):
        if not self.doc:
            return

        canvas_x, canvas_y = self.get_canvas_position(event)
        pdf_x, pdf_y = self.canvas_to_pdf(canvas_x, canvas_y)

        point = {
            "page": self.page_index + 1,
            "x": pdf_x,
            "y": pdf_y,
            "code": f'page.insert_text(({pdf_x}, {pdf_y}), "TEXT", fontsize=10)',
        }

        self.points.append(point)
        self.points_list.insert(
            tk.END,
            f'Page {point["page"]} | x={pdf_x}, y={pdf_y}',
        )

        self.code_var.set(point["code"])
        self.copy_to_clipboard(point["code"])
        self.redraw_points()

        self.status_var.set(f"Copied: {point['code']}")

    def on_mouse_move(self, event):
        if not self.doc:
            return

        canvas_x, canvas_y = self.get_canvas_position(event)
        pdf_x, pdf_y = self.canvas_to_pdf(canvas_x, canvas_y)

        self.mouse_var.set(f"X: {pdf_x} | Y: {pdf_y}")
        self.root.title(f"{APP_TITLE} - X: {pdf_x}, Y: {pdf_y}")

    def on_mousewheel(self, event):
        if event.state & 0x0004:
            if event.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def redraw_points(self):
        self.canvas.delete("marker")

        for point in self.points:
            if point["page"] != self.page_index + 1:
                continue

            x = point["x"] * self.zoom
            y = point["y"] * self.zoom

            self.canvas.create_oval(
                x - 5,
                y - 5,
                x + 5,
                y + 5,
                outline="#dc2626",
                width=2,
                tags="marker",
            )
            self.canvas.create_text(
                x + 8,
                y - 8,
                text=f'{point["x"]}, {point["y"]}',
                fill="#dc2626",
                anchor=tk.W,
                font=("Segoe UI", 9, "bold"),
                tags="marker",
            )

    def copy_current_code(self):
        value = self.code_var.get()
        if value and value != "Click on the PDF...":
            self.copy_to_clipboard(value)
            self.status_var.set("Current code copied.")

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def save_points(self):
        if not self.points:
            messagebox.showinfo("No points", "No coordinates selected yet.")
            return

        path = filedialog.asksaveasfilename(
            title="Save coordinates",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
        )

        if not path:
            return

        with open(path, "w", encoding="utf-8") as file:
            json.dump(self.points, file, indent=2, ensure_ascii=False)

        messagebox.showinfo("Saved", "Coordinates saved successfully.")

    def remove_selected_point(self):
        index = self.points_list.curselection()

        if not index:
            return

        idx = index[0]
        self.points.pop(idx)
        self.points_list.delete(idx)
        self.redraw_points()

    def clear_points(self):
        self.points.clear()
        self.points_list.delete(0, tk.END)
        self.canvas.delete("marker")
        self.code_var.set("Click on the PDF...")

    def next_page(self):
        if self.doc and self.page_index < len(self.doc) - 1:
            self.page_index += 1
            self.render_page()

    def prev_page(self):
        if self.doc and self.page_index > 0:
            self.page_index -= 1
            self.render_page()

    def zoom_in(self):
        if self.doc:
            self.zoom = min(self.zoom + 0.25, 5.0)
            self.render_page()

    def zoom_out(self):
        if self.doc:
            self.zoom = max(self.zoom - 0.25, 0.5)
            self.render_page()

    def fit_width(self):
        if not self.doc:
            return

        page = self.doc[self.page_index]
        canvas_width = max(self.canvas.winfo_width() - 30, 400)

        self.zoom = max(0.5, min(canvas_width / page.rect.width, 5.0))
        self.render_page()


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFCoordinatePicker(root)
    root.mainloop()