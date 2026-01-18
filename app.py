from flask import Flask, render_template, request, Response, send_file
import io
import subprocess
import tempfile
import shutil
import os

app = Flask(__name__)


def generate_scad(cols: int, rows: int, cell: float, height: float, wall: float, clearance: float = 0.2, grid: dict = None, posts: dict = None) -> str:
	"""Generate a simple OpenSCAD model for a Gridfinity-style tray: a grid of pockets with walls.

	This produces a top-down tray with internal pockets sized to `cell - wall - clearance`.
	The user can paste the .scad into OpenSCAD and export to STL.
	"""
	total_x = cols * cell
	total_y = rows * cell
	pocket_w = cell - wall - clearance
	pocket_h = cell - wall - clearance
	scad = []
	scad.append('// Generated Gridfinity SCAD')
	scad.append(f'cell = {cell};')
	scad.append(f'cols = {cols};')
	scad.append(f'rows = {rows};')
	scad.append(f'height = {height};')
	scad.append(f'wall = {wall};')
	scad.append(f'clearance = {clearance};')

	scad.append('module pocket() {')
	scad.append(f'  translate([wall/2 + clearance/2, wall/2 + clearance/2, 0])')
	scad.append(f'    cube([{pocket_w}, {pocket_h}, height], center=false);')
	scad.append('}')

	scad.append('// outer tray')
	scad.append('module tray() {')
	scad.append('  difference() {')
	scad.append(f'    cube([{total_x}, {total_y}, height + wall], center=false);')
	scad.append('    for (x = [0:' + str(cols-1) + ']) for (y = [0:' + str(rows-1) + '])')
	scad.append('      translate([x*cell, y*cell, 0]) pocket();')
	scad.append('  }')
	scad.append('}')

	# optional floor grid
	if grid and grid.get('enable'):
		pitch = grid.get('pitch', 6.0)
		rib = grid.get('thickness', 1.5)
		ribh = grid.get('height', 2.5)
		scad.append('module floor_grid() {')
		scad.append('  union() {')
		# vertical ribs
		# use for-loops in scad; use approximate ranges
		scad.append(f'    for (x = [{rib/2}:{pitch}:{total_x - rib/2}]) translate([x, 0, {wall}]) cube([{rib}, {total_y}, {ribh}], center=false);')
		# horizontal ribs
		scad.append(f'    for (y = [{rib/2}:{pitch}:{total_y - rib/2}]) translate([0, y, {wall}]) cube([{total_x}, {rib}, {ribh}], center=false);')
		scad.append('  }')
		scad.append('}')
		scad.append('floor_grid();')

	# optional posts
	if posts and posts.get('enable'):
		d = posts.get('diameter', 6.0)
		h = posts.get('height', 4.0)
		# place a cylinder at the center of each cell
		scad.append('module posts() {')
		scad.append('  union() {')
		for x in range(cols):
			for y in range(rows):
				cx = x*cell + cell/2
				cy = y*cell + cell/2
				scad.append(f'    translate([{cx}, {cy}, {wall}]) cylinder(h={h}, r={d/2}, $fn=32);')
		scad.append('  }')
		scad.append('}')
		scad.append('posts();')

	scad.append('tray();')
	return '\n'.join(scad)



def generate_svg(cols: int, rows: int, cell: float, wall: float) -> str:
	# Simple SVG top-down preview (mm units)
	width = cols * cell
	height = rows * cell
	viewbox = f'0 0 {width} {height}'
	svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="{width}px" height="{height}px">']
	svg.append('<style>rect{fill:#f5f5f5;stroke:#333;stroke-width:0.5}</style>')
	# outer border
	svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="none" stroke="#000" stroke-width="1"/>')
	# pockets
	inset = wall/2
	pocket_w = cell - wall
	pocket_h = cell - wall
	for x in range(cols):
		for y in range(rows):
			px = x * cell + inset
			py = y * cell + inset
			svg.append(f'<rect x="{px}" y="{py}" width="{pocket_w}" height="{pocket_h}" />')
	# optionally show simple post markers at cell centers if requested via global flag
	# The preview endpoint will append post circles by passing in extra html later.
	svg.append('</svg>')
	return '\n'.join(svg)


def scad_to_stl(scad_text: str, timeout: int = 30) -> bytes:
	"""Convert SCAD text to an STL using the local OpenSCAD CLI.

	Returns STL bytes. Raises RuntimeError if openscad is not found or conversion fails.
	"""
	openscad_path = shutil.which('openscad')
	if not openscad_path:
		raise RuntimeError('OpenSCAD CLI not found. Install OpenSCAD and ensure `openscad` is on PATH')

	with tempfile.TemporaryDirectory() as td:
		scad_path = os.path.join(td, 'model.scad')
		stl_path = os.path.join(td, 'model.stl')
		with open(scad_path, 'w', encoding='utf-8') as f:
			f.write(scad_text)

		# Run openscad
		try:
			subprocess.run([openscad_path, '-o', stl_path, scad_path], check=True, timeout=timeout)
		except subprocess.CalledProcessError as e:
			raise RuntimeError(f'OpenSCAD failed: {e}')
		except subprocess.TimeoutExpired:
			raise RuntimeError('OpenSCAD timeout')

		if not os.path.exists(stl_path):
			raise RuntimeError('OpenSCAD did not produce an STL')

		with open(stl_path, 'rb') as f:
			data = f.read()
		return data


@app.route('/')
def index():
	# Default parameters
	params = {
		'cols': int(request.args.get('cols', 3)),
		'rows': int(request.args.get('rows', 2)),
		'cell': float(request.args.get('cell', 51.0)),
		'height': float(request.args.get('height', 12.0)),
		'wall': float(request.args.get('wall', 3.0)),
	}
	return render_template('index.html', params=params)


@app.route('/preview.svg')
def preview_svg():
	try:
		cols = max(1, min(80, int(request.args.get('cols', 3))))
		rows = max(1, min(80, int(request.args.get('rows', 2))))
		cell = float(request.args.get('cell', 51.0))
		wall = float(request.args.get('wall', 3.0))
		# optional post/grid flags for preview
		post_enable = request.args.get('posts', '0') in ('1','true','yes')
		grid_enable = request.args.get('grid', '1') in ('1','true','yes')
		post_d = float(request.args.get('post_d', 6.0))
		post_h = float(request.args.get('post_h', 4.0))
		grid_pitch = float(request.args.get('grid_pitch', 6.0))
		grid_thick = float(request.args.get('grid_thick', 1.5))
		grid_h = float(request.args.get('grid_h', 2.5))
	except Exception:
		return Response('Invalid parameters', status=400)
	svg = generate_svg(cols, rows, cell, wall)
	# append post markers if requested
	if post_enable:
		# inject circles at centers
		insert = []
		for x in range(cols):
			for y in range(rows):
				cx = x*cell + cell/2
				cy = y*cell + cell/2
				insert.append(f'<circle cx="{cx}" cy="{cy}" r="{post_d/2}" fill="#666" opacity="0.6" />')
		# place markers before closing svg tag
		svg = svg.replace('</svg>', '\n' + '\n'.join(insert) + '\n</svg>')
	return Response(svg, mimetype='image/svg+xml')


@app.route('/download/scad')
def download_scad():
	try:
		cols = max(1, min(80, int(request.args.get('cols', 3))))
		rows = max(1, min(80, int(request.args.get('rows', 2))))
		cell = float(request.args.get('cell', 51.0))
		height = float(request.args.get('height', 12.0))
		wall = float(request.args.get('wall', 3.0))
	except Exception:
		return Response('Invalid parameters', status=400)
	grid = {
		'enable': request.args.get('grid', '1') in ('1','true','yes'),
		'pitch': float(request.args.get('grid_pitch', 6.0)),
		'thickness': float(request.args.get('grid_thick', 1.5)),
		'height': float(request.args.get('grid_h', 2.5)),
	}
	posts = {
		'enable': request.args.get('posts', '0') in ('1','true','yes'),
		'diameter': float(request.args.get('post_d', 6.0)),
		'height': float(request.args.get('post_h', 4.0)),
	}
	scad = generate_scad(cols, rows, cell, height, wall, clearance=0.2, grid=grid, posts=posts)
	buf = io.BytesIO(scad.encode('utf-8'))
	filename = f'gridfinity_{cols}x{rows}_{int(cell)}mm.scad'
	buf.seek(0)
	return send_file(buf, mimetype='text/plain', as_attachment=True, download_name=filename)


@app.route('/model.stl')
def model_stl():
	"""Return an STL for inline preview (not as attachment).

	Uses OpenSCAD CLI; returns 400 if parameters invalid, 500 if conversion fails.
	"""
	try:
		cols = max(1, min(80, int(request.args.get('cols', 3))))
		rows = max(1, min(80, int(request.args.get('rows', 2))))
		cell = float(request.args.get('cell', 51.0))
		height = float(request.args.get('height', 12.0))
		wall = float(request.args.get('wall', 3.0))
	except Exception:
		return Response('Invalid parameters', status=400)
	grid = {
		'enable': request.args.get('grid', '1') in ('1','true','yes'),
		'pitch': float(request.args.get('grid_pitch', 6.0)),
		'thickness': float(request.args.get('grid_thick', 1.5)),
		'height': float(request.args.get('grid_h', 2.5)),
	}
	posts = {
		'enable': request.args.get('posts', '0') in ('1','true','yes'),
		'diameter': float(request.args.get('post_d', 6.0)),
		'height': float(request.args.get('post_h', 4.0)),
	}
	scad = generate_scad(cols, rows, cell, height, wall, clearance=0.2, grid=grid, posts=posts)
	try:
		stl_bytes = scad_to_stl(scad)
	except RuntimeError as e:
		return Response(str(e), status=500)
	buf = io.BytesIO(stl_bytes)
	buf.seek(0)
	return send_file(buf, mimetype='application/vnd.ms-pki.stl')


@app.route('/download/stl')
def download_stl():
	"""Return an STL file as attachment for downloading (requires OpenSCAD CLI)."""
	try:
		cols = max(1, min(80, int(request.args.get('cols', 3))))
		rows = max(1, min(80, int(request.args.get('rows', 2))))
		cell = float(request.args.get('cell', 51.0))
		height = float(request.args.get('height', 12.0))
		wall = float(request.args.get('wall', 3.0))
	except Exception:
		return Response('Invalid parameters', status=400)
	grid = {
		'enable': request.args.get('grid', '1') in ('1','true','yes'),
		'pitch': float(request.args.get('grid_pitch', 6.0)),
		'thickness': float(request.args.get('grid_thick', 1.5)),
		'height': float(request.args.get('grid_h', 2.5)),
	}
	posts = {
		'enable': request.args.get('posts', '0') in ('1','true','yes'),
		'diameter': float(request.args.get('post_d', 6.0)),
		'height': float(request.args.get('post_h', 4.0)),
	}
	scad = generate_scad(cols, rows, cell, height, wall, clearance=0.2, grid=grid, posts=posts)
	try:
		stl_bytes = scad_to_stl(scad)
	except RuntimeError as e:
		return Response(str(e), status=500)
	buf = io.BytesIO(stl_bytes)
	filename = f'gridfinity_{cols}x{rows}_{int(cell)}mm.stl'
	buf.seek(0)
	return send_file(buf, mimetype='application/vnd.ms-pki.stl', as_attachment=True, download_name=filename)


if __name__ == '__main__':
	app.run(debug=True)

