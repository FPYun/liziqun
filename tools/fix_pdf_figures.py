"""
Fix paper figure PDFs that use JPXDecode (JPEG 2000) compression.

Uses PyMuPDF (fitz) to render the original PDF to a bitmap,
then writes a clean PDF with FlateDecode (PNG-like, universally compatible).
"""

import os
import fitz  # PyMuPDF

BASE_DIR = r'c:\Users\云发鹏🐧\Desktop\毕设\liziqun\paper\figures'

FIGS = [
    'fig1_pareto_front',
    'fig2_objective_relation',
    'fig3_weighted_analysis',
    'fig4_challenging_scene',
]


def fix_pdf(pdf_path):
    """Render PDF to image and save as clean PDF."""
    print(f'\nProcessing: {os.path.basename(pdf_path)}')

    # Open and render the original PDF
    doc = fitz.open(pdf_path)
    page = doc[0]

    # Check the page dimensions
    rect = page.rect
    print(f'  Page size: {rect.width:.0f} x {rect.height:.0f} pts')

    # Render at high resolution
    zoom = 3.0  # 3x = high quality
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    print(f'  Rendered: {pix.width} x {pix.height}, alpha={pix.alpha}')

    doc.close()

    # Create a new clean PDF from the pixmap
    if pix.alpha:
        # Remove alpha by compositing on white
        pix2 = fitz.Pixmap(fitz.csRGB, pix)
        pix = pix2

    # Convert pixmap to PNG bytes, then create PDF
    png_bytes = pix.tobytes('png')

    # Create new PDF with the image
    new_doc = fitz.open()
    page_w = pix.width / zoom
    page_h = pix.height / zoom
    page = new_doc.new_page(width=page_w, height=page_h)

    # Insert the image (PNG data -> clean compression)
    img_rect = fitz.Rect(0, 0, page_w, page_h)
    page.insert_image(img_rect, stream=png_bytes)

    # Save
    new_doc.save(pdf_path, garbage=4, deflate=True)
    new_doc.close()

    new_size = os.path.getsize(pdf_path)
    print(f'  Saved clean PDF: {new_size:,} bytes')


def main():
    print('Fixing paper figure PDFs (JPEG2000 -> clean FlateDecode)...')
    print('=' * 60)

    for fig_name in FIGS:
        pdf_path = os.path.join(BASE_DIR, f'{fig_name}.pdf')

        # Check if already fixed
        with open(pdf_path, 'rb') as f:
            header = f.read(2000)
        if b'JPXDecode' not in header and b'ftypjp2' not in header:
            print(f'\n{fig_name}.pdf: Already clean (no JPX), skipping')
            continue

        fix_pdf(pdf_path)

    print('\n' + '=' * 60)
    print('Done! All paper figures have been fixed.')


if __name__ == '__main__':
    main()
