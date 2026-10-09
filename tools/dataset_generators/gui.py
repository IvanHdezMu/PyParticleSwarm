"""Desktop form for the shared MITECO dataset generator."""

from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog
from urllib.request import urlopen

import customtkinter as ctk

if __package__:
    from . import generate_miteco as generator
else:
    import generate_miteco as generator


class ThemedDropdown(ctk.CTkFrame):
    """Read-only selector with a themed, bounded floating option list."""

    def __init__(self, master, values=(), state='readonly', height=38, command=None, **kwargs):
        theme = ctk.ThemeManager.theme['CTkComboBox']
        super().__init__(master, height=height, corner_radius=theme['corner_radius'],
                         fg_color=theme['fg_color'], border_width=theme['border_width'],
                         border_color=theme['border_color'], **kwargs)
        self._command = command
        self._values = list(values)
        self._state = state
        self._value = ''
        self._popup = None
        self._opened = False
        self._option_buttons = []
        self._rendered_values = None
        self._owner = self.winfo_toplevel()
        self.grid_columnconfigure(0, weight=1)
        style = dict(fg_color='transparent', hover_color=theme['button_hover_color'],
                     text_color=theme['text_color'],
                     text_color_disabled=theme['text_color_disabled'],
                     height=height - 8, command=self._toggle)
        self._button = ctk.CTkButton(self, text='', anchor='w', width=1, **style)
        self._button.grid(row=0, column=0, padx=(4, 0), pady=4, sticky='ew')
        self._indicator = ctk.CTkButton(self, text='⌄', width=28, **style)
        self._indicator.grid(row=0, column=1, padx=(0, 4), pady=4)
        self._bindings = [
            (sequence, self._owner.bind(sequence, callback, add='+'))
            for sequence, callback in (
                ('<ButtonPress-1>', self._outside_click),
                ('<Escape>', self._escape),
                ('<Configure>', self._owner_changed),
                ('<Unmap>', self._owner_changed),
            )
        ]
        self.configure(state=state)

    def get(self):
        return self._value

    def set(self, value):
        self._value = str(value)
        self._button.configure(text=self._value)
        self._close()

    def configure(self, **kwargs):
        if 'values' in kwargs:
            self._values = list(kwargs.pop('values'))
            self._close()
        if 'state' in kwargs:
            self._state = kwargs.pop('state')
            state = 'disabled' if self._state == 'disabled' else 'normal'
            self._button.configure(state=state)
            self._indicator.configure(state=state)
            if state == 'disabled':
                self._close()
        super().configure(**kwargs)

    def _toggle(self):
        if self._opened:
            self._close()
        elif self._state != 'disabled' and self._values:
            self._open()

    def _open(self):
        # Reuse the scrollable frame so its wheel bindings are installed only once.
        if self._popup is None:
            self._popup = ctk.CTkToplevel(self)
            self._popup.withdraw()
            self._popup.overrideredirect(True)
            self._popup.transient(self._owner)
            self._popup.grid_columnconfigure(0, weight=1)
            self._popup.grid_rowconfigure(0, weight=1)
            self._options = ctk.CTkScrollableFrame(
                self._popup, corner_radius=8, border_width=1,
                border_color=self.cget('border_color'), fg_color=self.cget('fg_color'))
            self._options.grid(row=0, column=0, sticky='nsew')
            self._options.grid_columnconfigure(0, weight=1)
            self._popup.bind('<Escape>', self._escape)
            self._popup.bind('<FocusOut>', self._focus_out)
            # X11 sends wheel buttons instead of MouseWheel events.
            self._popup.bind('<Button-4>', lambda event: self._scroll(-1))
            self._popup.bind('<Button-5>', lambda event: self._scroll(1))
        theme = ctk.ThemeManager.theme['CTkButton']
        if self._rendered_values != self._values:
            for option in self._option_buttons:
                option.destroy()
            self._option_buttons = []
            for index, value in enumerate(self._values):
                option = ctk.CTkButton(
                    self._options, text=value, anchor='w', height=32, width=1,
                    corner_radius=6, hover_color=theme['hover_color'],
                    command=lambda choice=value: self._select(choice))
                option.grid(row=index, column=0, padx=4, pady=2, sticky='ew')
                self._option_buttons.append(option)
            self._rendered_values = self._values[:]
        selected_row = 0
        for index, (value, option) in enumerate(zip(self._values, self._option_buttons)):
            selected = value == self._value
            if selected:
                selected_row = index
            option.configure(
                fg_color=theme['fg_color'] if selected else 'transparent',
                text_color=theme['text_color'] if selected else self._button.cget('text_color'))

        self.update_idletasks()
        width = self.winfo_width()
        # Screen coordinates are physical pixels; wm_geometry avoids CTk scaling them twice.
        scale = self._get_widget_scaling()
        desired_height = round(min(300, 36 * len(self._values) + 24) * scale)
        screen_width, screen_height = self.winfo_screenwidth(), self.winfo_screenheight()
        gap = round(4 * scale)
        below = self.winfo_rooty() + self.winfo_height() + gap
        above = self.winfo_rooty() - gap
        open_below = screen_height - below >= desired_height or screen_height - below >= above
        height = max(1, min(desired_height, screen_height - below if open_below else above))
        x = max(0, min(self.winfo_rootx(), screen_width - width))
        y = below if open_below else above - height
        self._popup.wm_geometry(f'{width}x{height}+{x}+{max(0, y)}')
        self._opened = True
        self._indicator.configure(text='⌃')
        self._popup.deiconify()
        self._popup.lift()
        self._popup.update_idletasks()
        # CTkScrollableFrame owns its canvas; bring the selected row into view on reopen.
        self._options._parent_canvas.yview_moveto(selected_row / len(self._values))
        self._popup.focus_force()

    def _scroll(self, direction):
        self._options._parent_canvas.yview_scroll(direction * 3, 'units')
        return 'break'

    def _select(self, value):
        self.set(value)
        self._button.focus_set()
        if self._command is not None:
            self._command(value)

    def _close(self):
        if self._opened:
            self._opened = False
            self._popup.withdraw()
            self._indicator.configure(text='⌄')

    def _escape(self, event=None):
        if self._opened:
            self._close()
            self._button.focus_set()
            return 'break'

    def _outside_click(self, event):
        if self._opened:
            widget = event.widget
            while widget is not None:
                if widget is self or widget is self._popup:
                    return
                widget = getattr(widget, 'master', None)
            self._close()

    def _focus_out(self, event):
        # Focus may be moving between descendants of the same popup.
        self.after_idle(self._check_focus)

    def _check_focus(self):
        if self._opened:
            focused = self.focus_get()
            if focused is None or focused.winfo_toplevel() is not self._popup:
                self._close()

    def _owner_changed(self, event):
        if event.widget is self._owner:
            self._close()

    def destroy(self):
        self._close()
        for sequence, binding in self._bindings:
            self._owner.unbind(sequence, binding)
        super().destroy()


class DatasetGeneratorApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title('PyParticleSwarm Dataset Generator')
        self.geometry('800x880')
        self.minsize(640, 800)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        self.raw = None
        self._source_cache = {}
        self._loaded_source = None
        self._loading_source = None
        self._busy = False
        self.results = Queue()
        self.output = ctk.StringVar(value=str(generator.DEFAULT_OUTPUT))

        title_font = ctk.CTkFont(size=28, weight='bold')
        section_font = ctk.CTkFont(size=16, weight='bold')
        secondary_font = ctk.CTkFont(size=12)
        control_height = 38
        secondary_button_style = {
            'fg_color': 'transparent',
            'border_width': 1,
            'text_color': ctk.ThemeManager.theme['CTkLabel']['text_color'],
            'hover_color': ctk.ThemeManager.theme['CTkFrame']['top_fg_color'],
        }

        header = ctk.CTkFrame(self, fg_color='transparent')
        header.grid(row=0, column=0, padx=28, pady=(24, 18), sticky='ew')
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text='PyParticleSwarm', font=secondary_font).grid(
            row=0, column=0, sticky='w')
        ctk.CTkLabel(header, text='Dataset Generator', font=title_font).grid(
            row=1, column=0, sticky='w')
        ctk.CTkLabel(header, text='Create a dataset from Spanish fuel station data.',
                     font=secondary_font).grid(row=2, column=0, pady=(4, 0), sticky='w')

        source_card = ctk.CTkFrame(self, corner_radius=12)
        source_card.grid(row=1, column=0, padx=28, pady=(0, 14), sticky='ew')
        source_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(source_card, text='Source', font=section_font).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(12, 8), sticky='w')
        self.source = ThemedDropdown(
            source_card, values=['MITECO Spain'], state='readonly', height=control_height,
            command=lambda value: self.load_source(force=False))
        self.source.set('MITECO Spain')
        self.source.grid(row=1, column=0, padx=(20, 12), pady=(0, 18), sticky='ew')
        self.reload_button = ctk.CTkButton(
            source_card, text='Reload source', width=130, height=control_height,
            command=self.load_source, **secondary_button_style)
        self.reload_button.grid(row=1, column=1, padx=(0, 20), pady=(0, 18))

        dataset_card = ctk.CTkFrame(self, corner_radius=12)
        dataset_card.grid(row=2, column=0, padx=28, pady=(0, 14), sticky='ew')
        dataset_card.grid_columnconfigure((0, 1), weight=1, uniform='dataset')
        ctk.CTkLabel(dataset_card, text='Dataset', font=section_font).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(12, 8), sticky='w')
        self.region = ThemedDropdown(dataset_card, values=[], state='disabled',
                                     height=control_height,
                                     command=lambda value: self.update_generate_state())
        self.fuel = ThemedDropdown(dataset_card, values=[], state='disabled',
                                   height=control_height,
                                   command=lambda value: self.update_generate_state())
        self.region.set('')
        self.fuel.set('')
        self.size_value = ctk.StringVar(value='20')
        self.seed_value = ctk.StringVar(value='42')
        self.size = ctk.CTkEntry(dataset_card, height=control_height, textvariable=self.size_value)
        self.seed = ctk.CTkEntry(dataset_card, height=control_height, textvariable=self.seed_value)
        fields = (('Region (province)', self.region), ('Fuel', self.fuel),
                  ('Dataset size', self.size), ('Seed', self.seed))
        for index, (label, widget) in enumerate(fields):
            row = 1 + (index // 2) * 2
            column = index % 2
            padding = (20, 8) if column == 0 else (8, 20)
            ctk.CTkLabel(dataset_card, text=label, font=secondary_font).grid(
                row=row, column=column, padx=padding, pady=(0, 4), sticky='w')
            widget.grid(row=row + 1, column=column, padx=padding,
                        pady=(0, 16), sticky='ew')

        output_card = ctk.CTkFrame(self, corner_radius=12)
        output_card.grid(row=3, column=0, padx=28, pady=(0, 18), sticky='ew')
        output_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(output_card, text='Output', font=section_font).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(12, 4), sticky='w')
        ctk.CTkLabel(output_card, text='Output directory', font=secondary_font).grid(
            row=1, column=0, columnspan=2, padx=20, pady=(0, 4), sticky='w')
        ctk.CTkEntry(output_card, textvariable=self.output, state='readonly',
                     height=control_height).grid(
            row=2, column=0, padx=(20, 12), pady=(0, 18), sticky='ew')
        ctk.CTkButton(output_card, text='Browse…', width=100, height=control_height,
                      command=self.choose_directory, **secondary_button_style).grid(
            row=2, column=1, padx=(0, 20), pady=(0, 18))

        self.generate_button = ctk.CTkButton(
            self, text='Generate dataset', height=44,
            font=ctk.CTkFont(size=15, weight='bold'),
            state='disabled', command=self.generate)
        self.generate_button.grid(row=4, column=0, padx=28, pady=(0, 18), sticky='ew')

        status_card = ctk.CTkFrame(self, corner_radius=12)
        status_card.grid(row=5, column=0, padx=28, pady=(0, 24), sticky='nsew')
        status_card.grid_columnconfigure(0, weight=1)
        status_card.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(status_card, text='Status / result', font=section_font).grid(
            row=0, column=0, padx=20, pady=(12, 4), sticky='w')
        status_content = ctk.CTkScrollableFrame(
            status_card, fg_color='transparent', height=80)
        status_content.grid(row=1, column=0, padx=14, pady=(0, 14), sticky='nsew')
        status_content.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(
            status_content, text='', font=secondary_font, anchor='nw',
            justify='left', wraplength=500)
        self.status.grid(row=0, column=0, sticky='ew')
        status_content.bind(
            '<Configure>',
            lambda event: self.status.configure(wraplength=max(1, event.width - 16)))
        for variable in (self.size_value, self.seed_value, self.output):
            variable.trace_add('write', lambda *args: self.update_generate_state())
        self.after(100, self.poll_results)
        self.load_source(force=False)

    def show_status(self, text):
        self.status.configure(text=text)

    def choose_directory(self):
        directory = filedialog.askdirectory(parent=self, title='Choose output directory',
                                            initialdir=self.output.get())
        if directory:
            self.output.set(directory)

    def start_work(self, kind, work):
        self._busy = True
        # Serialize source changes with work so results always belong to the visible source.
        self.source.configure(state='disabled')
        self.generate_button.configure(state='disabled')
        self.reload_button.configure(state='disabled')

        def worker():
            # Workers never call Tk; the main thread consumes results using after().
            try:
                self.results.put((kind, work(), None))
            except Exception as error:
                self.results.put((kind, None, str(error)))

        Thread(target=worker, daemon=True).start()

    def update_generate_state(self):
        try:
            valid_numbers = int(self.size_value.get()) > 0
            int(self.seed_value.get())
        except ValueError:
            valid_numbers = False
        ready = (not self._busy and self.raw is not None and self.region.get()
                 and self.fuel.get() and self.output.get() and valid_numbers)
        self.generate_button.configure(state='normal' if ready else 'disabled')

    def apply_source(self, source, result):
        self.raw, (regions, fuels) = result
        self._loaded_source = source
        self.region.configure(values=regions, state='readonly' if regions else 'disabled')
        self.fuel.configure(values=fuels, state='readonly' if fuels else 'disabled')
        self.region.set(regions[0] if regions else '')
        self.fuel.set(fuels[0] if fuels else '')
        self.show_status('MITECO data loaded. Select a province and fuel, then generate.')
        self.update_generate_state()

    def load_source(self, force=True):
        if self._busy:
            return
        source = self.source.get()
        if not force and source == self._loaded_source and self.raw is not None:
            return
        if not force and source in self._source_cache:
            self.apply_source(source, self._source_cache[source])
            return
        self._loading_source = source
        self._loaded_source = None
        self.raw = None
        self.region.configure(values=[], state='disabled')
        self.fuel.configure(values=[], state='disabled')
        self.region.set('')
        self.fuel.set('')
        self.show_status('Loading MITECO data...')

        def download():
            with urlopen(generator.SOURCE_URL, timeout=60) as response:
                raw = response.read()
            return raw, generator.available_options(raw)

        self.start_work('load', download)

    def generate(self):
        region, fuel = self.region.get(), self.fuel.get()
        if self.raw is None or not region or not fuel:
            self.show_status('Error: load MITECO data and select a region and fuel first.')
            return
        try:
            size = int(self.size.get())
        except ValueError:
            self.show_status('Error: dataset size must be an integer.')
            return
        try:
            seed = int(self.seed.get())
        except ValueError:
            self.show_status('Error: seed must be an integer.')
            return
        if not self.output.get():
            self.show_status('Error: choose an output directory.')
            return
        raw = self.raw
        directory = Path(self.output.get())
        self.show_status('Generating dataset...')

        def write_dataset():
            output = directory / generator.dataset_filename(region, size, seed)
            return generator.generate(raw, region, fuel, size, seed, output)

        self.start_work('generate', write_dataset)

    def poll_results(self):
        try:
            kind, result, error = self.results.get_nowait()
        except Empty:
            pass
        else:
            self._busy = False
            self.source.configure(state='readonly')
            if error is not None:
                prefix = 'Could not load MITECO data' if kind == 'load' else 'Could not generate dataset'
                self.show_status(f'{prefix}: {error}')
            elif kind == 'load':
                self._source_cache[self._loading_source] = result
                self.apply_source(self._loading_source, result)
            else:
                path, metadata = result
                self.show_status(
                    f"Dataset generated successfully.\n\nFilename: {path.name}\n"
                    f"Region: {metadata['region']}\nFuel: {metadata['fuel']}\n"
                    f"Nodes: {metadata['size']}\nSeed: {metadata['seed']}\n"
                    f"Full path: {path.resolve()}")
            self.reload_button.configure(state='normal')
            self.update_generate_state()
        self.after(100, self.poll_results)


if __name__ == '__main__':
    DatasetGeneratorApp().mainloop()
