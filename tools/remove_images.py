"""
Remove all images from the compiled main.pdf.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import fitz
import os

PDF_PATH = r'c:\Users\云发鹏🐧\Desktop\毕设\liziqun\paper\main.pdf'
OUT_PATH = r'c:\Users\云发鹏🐧\Desktop\毕设\liziqun\paper\main_noimg.pdf'


def remove_images_from_page(doc, page, page_num):
    """Remove all images from a page by replacing image Do ops with no-ops."""
    imgs = page.get_images()
    if not imgs:
        return 0

    # Get image info with bboxes
    img_infos = page.get_image_info()
    if not img_infos:
        return 0

    print(f'Page {page_num+1}: removing {len(img_infos)} image(s)')

    # Use redaction to remove images (fill with white)
    for info in img_infos:
        bbox = info['bbox']
        # Make a slightly larger rect to ensure full coverage
        rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
        page.add_redact_annot(rect, fill=(1, 1, 1))  # white fill

    # Apply redactions (removes the image drawing commands)
    page.apply_redactions()

    return len(img_infos)


def main():
    print(f'Opening: {PDF_PATH}')
    doc = fitz.open(PDF_PATH)
    total_removed = 0

    for i in range(doc.page_count):
        page = doc[i]
        removed = remove_images_from_page(doc, page, i)
        total_removed += removed

    print(f'\nTotal images removed: {total_removed}')
    print(f'Saving to: {OUT_PATH}')
    doc.save(OUT_PATH, garbage=4, deflate=True)
    doc.close()

    in_size = os.path.getsize(PDF_PATH)
    out_size = os.path.getsize(OUT_PATH)
    print(f'Original: {in_size:,} bytes')
    print(f'Without images: {out_size:,} bytes')
    print('Done!')


if __name__ == '__main__':
    main()
