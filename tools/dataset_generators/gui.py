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


class DatasetGeneratorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('PyParticleSwarm Dataset Generator')
        self.geometry('680x580')
        self.minsize(580, 520)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(8, weight=1)
        self.raw = None
        self.results = Queue()
        self.output = ctk.StringVar(value=str(generator.DEFAULT_OUTPUT))

        for row, text in enumerate(('Source', 'Region (province)', 'Fuel', 'Dataset size', 'Seed', 'Output directory')):
            ctk.CTkLabel(self, text=text).grid(row=row, column=0, padx=16, pady=8, sticky='w')
        self.source = ctk.CTkComboBox(self, values=['MITECO Spain'], state='readonly')
        self.region = ctk.CTkComboBox(self, values=[], state='disabled')
        self.fuel = ctk.CTkComboBox(self, values=[], state='disabled')
        self.region.set('')
        self.fuel.set('')
        self.size = ctk.CTkEntry(self)
        self.size.insert(0, '20')
        self.seed = ctk.CTkEntry(self)
        self.seed.insert(0, '42')
        for row, widget in enumerate((self.source, self.region, self.fuel, self.size, self.seed)):
            widget.grid(row=row, column=1, columnspan=2, padx=16, pady=8, sticky='ew')
        ctk.CTkEntry(self, textvariable=self.output, state='readonly').grid(
            row=5, column=1, padx=16, pady=8, sticky='ew')
        ctk.CTkButton(self, text='Browse…', width=90, command=self.choose_directory).grid(
            row=5, column=2, padx=16, pady=8)
        self.reload_button = ctk.CTkButton(self, text='Reload source', command=self.load_source)
        self.reload_button.grid(row=6, column=0, padx=16, pady=8)
        self.generate_button = ctk.CTkButton(self, text='Generate', state='disabled', command=self.generate)
        self.generate_button.grid(row=6, column=1, columnspan=2, padx=16, pady=8, sticky='ew')
        ctk.CTkLabel(self, text='Status / result').grid(row=7, column=0, padx=16, sticky='w')
        self.status = ctk.CTkTextbox(self, wrap='word', state='disabled')
        self.status.grid(row=8, column=0, columnspan=3, padx=16, pady=16, sticky='nsew')
        self.after(100, self.poll_results)
        self.load_source()

    def show_status(self, text):
        self.status.configure(state='normal')
        self.status.delete('1.0', 'end')
        self.status.insert('1.0', text)
        self.status.configure(state='disabled')

    def choose_directory(self):
        directory = filedialog.askdirectory(parent=self, title='Choose output directory',
                                            initialdir=self.output.get())
        if directory:
            self.output.set(directory)

    def start_work(self, kind, work):
        self.generate_button.configure(state='disabled')
        self.reload_button.configure(state='disabled')

        def worker():
            # Workers never call Tk; the main thread consumes results using after().
            try:
                self.results.put((kind, work(), None))
            except Exception as error:
                self.results.put((kind, None, str(error)))

        Thread(target=worker, daemon=True).start()

    def load_source(self):
        self.raw = None
        self.region.configure(state='disabled')
        self.fuel.configure(state='disabled')
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
            if error is not None:
                prefix = 'Could not load MITECO data' if kind == 'load' else 'Could not generate dataset'
                self.show_status(f'{prefix}: {error}')
            elif kind == 'load':
                self.raw, (regions, fuels) = result
                self.region.configure(values=regions, state='readonly')
                self.fuel.configure(values=fuels, state='readonly')
                self.region.set(regions[0])
                self.fuel.set(fuels[0])
                self.show_status('MITECO data loaded. Select a province and fuel, then generate.')
            else:
                path, metadata = result
                self.show_status(
                    f"Dataset generated successfully.\n\nFilename: {path.name}\n"
                    f"Region: {metadata['region']}\nFuel: {metadata['fuel']}\n"
                    f"Nodes: {metadata['size']}\nSeed: {metadata['seed']}\n"
                    f"Full path: {path.resolve()}")
            self.reload_button.configure(state='normal')
            self.generate_button.configure(state='normal' if self.raw is not None else 'disabled')
        self.after(100, self.poll_results)


if __name__ == '__main__':
    DatasetGeneratorApp().mainloop()
