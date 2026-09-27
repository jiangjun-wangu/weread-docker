import zipfile
from io import BytesIO

MIMETYPE = 'application/epub+zip'
STYLESHEET = 'p{text-indent:2em}'


def xml_escape(text):
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    return text


def build_nav(book, chapters):
    buf = []
    buf.append('<?xml version="1.0" encoding="UTF-8"?>')
    buf.append('<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">')
    buf.append('<head><title>' + xml_escape(book.get('title', '')) + '</title></head>')
    buf.append('<body><nav epub:type="toc"><ol>')
    for i, ch in enumerate(chapters, 1):
        buf.append('<li><a href="ch%06d.xhtml">' % i + xml_escape(ch.get('title', '')) + '</a></li>')
    buf.append('</ol></nav></body></html>')
    return ''.join(buf).encode('utf-8')


def build_opf(book, chapters):
    buf = []
    buf.append('<?xml version="1.0" encoding="UTF-8"?>')
    buf.append('<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">')
    buf.append('<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">')
    buf.append('<dc:identifier id="book-id">' + xml_escape(book.get('bookId', '')) + '</dc:identifier>')
    buf.append('<dc:title>' + xml_escape(book.get('title', '')) + '</dc:title>')
    buf.append('<dc:creator>' + xml_escape(book.get('author', '')) + '</dc:creator>')
    buf.append('<dc:language>zh-CN</dc:language>')
    buf.append('</metadata><manifest>')
    buf.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
    buf.append('<item id="style" href="styles.css" media-type="text/css"/>')
    for i in range(1, len(chapters) + 1):
        buf.append('<item id="ch%06d" href="ch%06d.xhtml" media-type="application/xhtml+xml"/>' % (i, i))
    buf.append('</manifest><spine>')
    for i in range(1, len(chapters) + 1):
        buf.append('<itemref idref="ch%06d"/>' % i)
    buf.append('</spine></package>')
    return ''.join(buf).encode('utf-8')
CONTAINER_XML = '<?xml version="1.0" encoding="UTF-8"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'


def pack_epub(book, chapters):
    buf = BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo('mimetype')
        info.compress_type = zipfile.ZIP_STORED
        z.writestr(info, MIMETYPE)
        z.writestr('META-INF/container.xml', CONTAINER_XML)
        z.writestr('OEBPS/content.opf', build_opf(book, chapters))
        z.writestr('OEBPS/nav.xhtml', build_nav(book, chapters))
        z.writestr('OEBPS/styles.css', STYLESHEET)
        for i, ch in enumerate(chapters, 1):
            z.writestr('OEBPS/ch%06d.xhtml' % i, ch.get('xhtml', b''))
    return buf.getvalue()
