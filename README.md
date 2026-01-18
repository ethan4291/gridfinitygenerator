# Gridfinity Generator

Simple Flask app that generates a parameterized Gridfinity-style tray as an OpenSCAD file and an SVG preview.

# Gridfinity Generator

Simple Flask app that generates a parameterized Gridfinity-style tray as an OpenSCAD file, an SVG preview, and server-side STL export (requires OpenSCAD CLI).

How to run

1. Create a virtualenv and install requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Install OpenSCAD (required for STL export and 3D preview):

- macOS (homebrew):

```bash
brew install --cask openscad
```

- Linux (apt):

```bash
sudo apt update
sudo apt install openscad
```

3. Run the app:

```bash
python app.py
```

4. Open http://127.0.0.1:5000 in your browser.

Usage

- Adjust columns, rows, cell size, wall thickness and height.
- Click "Update preview" to refresh the SVG.
- Click "Refresh 3D preview" to regenerate and display an interactive 3D preview (requires OpenSCAD).
- Click "Download STL" to download a generated STL (server uses OpenSCAD CLI).

Notes

- The server runs OpenSCAD on demand; for large models this can take several seconds. Consider adding a job queue for heavy use.
- If OpenSCAD is not installed the STL endpoints will return an error; SCAD download still works without OpenSCAD.
- The three.js viewer is loaded from a CDN in the browser.

GitHub Pages (static hosting)

This project includes a static, client-side port of the app under `docs/index.html` so it can be hosted on GitHub Pages. The static page reproduces the SVG preview and generates the OpenSCAD (.scad) text entirely in the browser.

To publish on GitHub Pages (user or project site):

1. Commit and push the `docs/` folder to your repository's default branch (usually `main` or `master`).
2. In your repository Settings → Pages choose the branch (e.g. `main`) and set the folder to `/docs`.
3. Save; GitHub Pages will build and serve `docs/index.html` at your site URL.

Limitations on GitHub Pages

- GitHub Pages is static hosting and cannot run server-side tools like OpenSCAD. The "Download STL" feature from the original Flask app requires the OpenSCAD CLI on the server and therefore is not available when hosted on Pages.
- Workaround: use the provided "Download SCAD" button, then run OpenSCAD locally to convert the `.scad` to `.stl`:

	openscad -o model.stl model.scad

